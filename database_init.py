import os
from app import create_app
from models import db, SystemConfig

def init_db():
    app = create_app()
    
    with app.app_context():
        # 1. Si on est connecté à Neon (PostgreSQL), on vérifie si la base est déjà initialisée
        if app.config['SQLALCHEMY_DATABASE_URI'].startswith('postgresql'):
            try:
                db.create_all() # Créer les tables si elles n'existent pas
                seeded = SystemConfig.query.filter_by(key='is_seeded').first()
                if seeded and seeded.value == 'True':
                    print("La base de données PostgreSQL (Neon) est déjà initialisée. Saut de l'initialisation.")
                    return
            except Exception as e:
                print(f"Vérification du flag is_seeded sur PostgreSQL impossible, création des tables : {e}")

        # 2. Supprimer la base de données SQLite locale existante pour repartir de zéro
        if not app.config['SQLALCHEMY_DATABASE_URI'].startswith('postgresql'):
            db_path = os.path.join(app.config['BASE_DIR'], 'suivi_evaluation.db')
            if os.path.exists(db_path):
                try:
                    os.remove(db_path)
                    print("Ancienne base de données locale SQLite supprimée.")
                except Exception as e:
                    print(f"Avertissement lors de la suppression de la base locale : {e}")
            
        # 3. Créer les tables
        db.create_all()
        
        # 4. Enregistrer le flag is_seeded pour bloquer les futures réinitialisations
        try:
            # Vérifier si déjà présent pour éviter l'erreur de clé primaire
            seeded = SystemConfig.query.filter_by(key='is_seeded').first()
            if not seeded:
                seeded = SystemConfig(key='is_seeded', value='True')
                db.session.add(seeded)
                db.session.commit()
            print("Flag is_seeded enregistré en base de données.")
        except Exception as e:
            print(f"Impossible d'enregistrer le flag is_seeded : {e}")
            
        print("Base de données et tables initialisées avec succès.")

if __name__ == '__main__':
    init_db()
