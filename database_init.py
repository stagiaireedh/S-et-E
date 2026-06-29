import os
from app import create_app
from models import db

def init_db():
    app = create_app()
    
    with app.app_context():
        # Supprimer la base de données SQLite locale existante pour repartir de zéro
        db_path = os.path.join(app.config['BASE_DIR'], 'suivi_evaluation.db')
        if os.path.exists(db_path):
            try:
                os.remove(db_path)
                print("Ancienne base de données locale SQLite supprimée.")
            except Exception as e:
                print(f"Avertissement lors de la suppression de la base locale : {e}")
            
        # Créer les tables (le schéma n'a plus de colonne is_demo)
        db.create_all()
        print("Base de données et tables initialisées avec succès (sans données démo).")

if __name__ == '__main__':
    init_db()
