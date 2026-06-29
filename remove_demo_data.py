import os
import sqlite3
import psycopg2

def remove_demo():
    url = os.environ.get('DATABASE_URL')
    
    if url:
        # PostgreSQL Neon
        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql://", 1)
        print("Connexion à la base de données PostgreSQL Neon...")
        try:
            conn = psycopg2.connect(url)
            cursor = conn.cursor()
            is_postgres = True
            placeholder = "%s"
        except Exception as e:
            print(f"Erreur de connexion PostgreSQL : {e}")
            return
    else:
        # SQLite local
        base_dir = os.path.abspath(os.path.dirname(__file__))
        db_path = os.path.join(base_dir, 'suivi_evaluation.db')
        if not os.path.exists(db_path):
            print(f"Base SQLite locale introuvable à {db_path}.")
            return
        print(f"Connexion à la base SQLite locale : {db_path}")
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        is_postgres = False
        placeholder = "?"

    try:
        # 1. Récupérer l'ID du projet démo
        cursor.execute("SELECT id FROM projects WHERE name LIKE '%AEPA%'")
        rows = cursor.fetchall()
        
        if not rows:
            print("Aucun projet démo AEPA trouvé.")
        else:
            for r in rows:
                project_id = r[0]
                print(f"Suppression du projet AEPA (ID: {project_id}) et de ses dépendances...")
                
                # Suppression en cascade
                cursor.execute(f"""
                    DELETE FROM answers WHERE session_id IN (
                        SELECT id FROM interview_sessions WHERE project_id = {placeholder}
                    )
                """, (project_id,))
                
                cursor.execute(f"DELETE FROM attachments WHERE project_id = {placeholder}", (project_id,))
                
                cursor.execute(f"""
                    DELETE FROM shared_questionnaires WHERE questionnaire_id IN (
                        SELECT id FROM questionnaires WHERE project_id = {placeholder}
                    )
                """, (project_id,))
                
                cursor.execute(f"DELETE FROM interview_sessions WHERE project_id = {placeholder}", (project_id,))
                
                cursor.execute(f"""
                    DELETE FROM questions WHERE questionnaire_id IN (
                        SELECT id FROM questionnaires WHERE project_id = {placeholder}
                    )
                """, (project_id,))
                
                cursor.execute(f"DELETE FROM questionnaires WHERE project_id = {placeholder}", (project_id,))
                cursor.execute(f"DELETE FROM projects WHERE id = {placeholder}", (project_id,))
                
            print("Projet démo AEPA et ses dépendances supprimés avec succès.")
        
        # 2. Supprimer la colonne is_demo de la table projects
        print("Suppression de la colonne is_demo de la table projects...")
        if is_postgres:
            cursor.execute("ALTER TABLE projects DROP COLUMN IF EXISTS is_demo;")
            print("Colonne is_demo supprimée avec succès de PostgreSQL.")
        else:
            try:
                cursor.execute("ALTER TABLE projects DROP COLUMN is_demo;")
                print("Colonne is_demo supprimée avec succès de SQLite.")
            except Exception as e:
                print(f"Note : Impossible de supprimer la colonne is_demo de SQLite (version locale) : {e}")
                print("Ce n'est pas bloquant, SQLite sera recréée proprement au prochain démarrage.")
        
        conn.commit()
        print("Nettoyage de la base de données terminé avec succès !")
    except Exception as e:
        conn.rollback()
        print(f"Erreur lors de l'exécution de la migration : {e}")
    finally:
        cursor.close()
        conn.close()

if __name__ == "__main__":
    remove_demo()
