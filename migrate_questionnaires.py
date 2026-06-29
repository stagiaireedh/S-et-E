import os
import json
from datetime import datetime
from models import db, Questionnaire, Question, QuestionnaireBlock, SystemConfig

def migrate_with_app(app):
    with app.app_context():
        # 1. S'assurer que les nouvelles tables sont créées
        print("Création des nouvelles tables si nécessaire...")
        db.create_all()
        
        # 2. Ajouter les nouvelles colonnes aux tables existantes via SQL ALTER (support SQLite & PostgreSQL)
        engine = db.engine
        
        # Colonnes pour questionnaires
        cols_questionnaire = [
            ("is_template", "BOOLEAN DEFAULT FALSE"),
            ("template_category", "VARCHAR(50)"),
            ("status", "VARCHAR(20) DEFAULT 'draft'"),
            ("updated_at", "TIMESTAMP")
        ]
        
        # Colonnes pour questions
        cols_question = [
            ("options", "JSON"),
            ("is_required", "BOOLEAN DEFAULT FALSE"),
            ("validation_rules", "JSON"),
            ("conditions", "JSON"),
            ("default_value", "VARCHAR(255)"),
            ("help_text", "TEXT"),
            ("ai_prompt", "TEXT"),
            ("created_at", "TIMESTAMP"),
            ("updated_at", "TIMESTAMP")
        ]
        
        print("Ajout des nouvelles colonnes à 'questionnaires'...")
        for col_name, col_type in cols_questionnaire:
            try:
                with engine.connect() as conn:
                    sql = f"ALTER TABLE questionnaires ADD COLUMN {col_name} {col_type}"
                    conn.execute(db.text(sql))
                    conn.commit()
                print(f"  + Colonne '{col_name}' ajoutée.")
            except Exception as e:
                if "already exists" in str(e) or "duplicate column" in str(e) or "duplicate" in str(e).lower():
                    pass
                else:
                    print(f"  (Ignoré) Impossible d'ajouter '{col_name}' : {e}")
                    
        print("Ajout des nouvelles colonnes à 'questions'...")
        for col_name, col_type in cols_question:
            try:
                with engine.connect() as conn:
                    sql = f"ALTER TABLE questions ADD COLUMN {col_name} {col_type}"
                    conn.execute(db.text(sql))
                    conn.commit()
                print(f"  + Colonne '{col_name}' ajoutée.")
            except Exception as e:
                if "already exists" in str(e) or "duplicate column" in str(e) or "duplicate" in str(e).lower():
                    pass
                else:
                    print(f"  (Ignoré) Impossible d'ajouter '{col_name}' : {e}")
        
        # 3. Migrer les questionnaires existants vers des structures par blocs
        print("Migration des questionnaires existants en structures par blocs...")
        try:
            all_questionnaires = Questionnaire.query.all()
            migrated_count = 0
            
            for q in all_questionnaires:
                # Si le questionnaire n'a aucun bloc associé, on le convertit
                if len(q.blocks) == 0:
                    print(f"Conversion du questionnaire '{q.title}' (ID: {q.id})...")
                    
                    # Bloc Titre
                    title_block = QuestionnaireBlock(
                        questionnaire_id=q.id,
                        block_type='title',
                        order_index=0,
                        content={
                            'title': q.title,
                            'description': q.description or ''
                        }
                    )
                    db.session.add(title_block)
                    
                    # Blocs Questions
                    sorted_questions = sorted(q.questions, key=lambda x: x.order_num)
                    for idx, quest in enumerate(sorted_questions):
                        choices_list = [c.strip() for c in quest.choices.split(',')] if quest.choices else []
                        
                        quest_block = QuestionnaireBlock(
                            questionnaire_id=q.id,
                            block_type='question',
                            order_index=idx + 1,
                            content={
                                'label': quest.text,
                                'question_type': 'select' if quest.question_type == 'select' else 'text',
                                'choices': choices_list,
                                'is_required': quest.is_required or False,
                                'help_text': quest.help_text or '',
                                'question_id': quest.id
                            }
                        )
                        db.session.add(quest_block)
                    
                    migrated_count += 1
                    
            if migrated_count > 0:
                db.session.commit()
                print(f"Succès : {migrated_count} questionnaire(s) migré(s) en structure par blocs.")
            else:
                print("Aucun questionnaire à migrer ou déjà converti.")
        except Exception as e:
            print(f"Erreur lors de la migration des blocs : {e}")

        print("Migration terminée avec succès !")

def run_migration():
    from app import create_app
    app = create_app()
    migrate_with_app(app)

if __name__ == "__main__":
    run_migration()
