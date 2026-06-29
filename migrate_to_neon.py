import os
import bcrypt
from datetime import datetime
from flask import Flask
from models import db, User, Project, Questionnaire, Question, InterviewSession, Answer, Attachment
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

def migrate():
    # 1. Configurer la connexion cible (PostgreSQL Neon)
    target_url = os.environ.get('DATABASE_URL')
    if not target_url:
        print("Erreur : La variable d'environnement DATABASE_URL n'est pas définie.")
        print("Veuillez la définir avant de lancer le script. Exemple :")
        print("export DATABASE_URL='postgresql://user:pass@ep-flat-water-123456.us-east-2.aws.neon.tech/neondb?sslmode=require'")
        return

    # Convertir postgres:// en postgresql:// si nécessaire
    if target_url.startswith("postgres://"):
        target_url = target_url.replace("postgres://", "postgresql://", 1)

    print(f"Connexion à la base de données PostgreSQL Neon : {target_url.split('@')[-1]}")

    # 2. Configurer la connexion source (SQLite local)
    base_dir = os.path.abspath(os.path.dirname(__file__))
    sqlite_path = os.path.join(base_dir, 'suivi_evaluation.db')
    if not os.path.exists(sqlite_path):
        print(f"Avertissement : Fichier SQLite source introuvable à {sqlite_path}.")
        print("Le script va uniquement initialiser la structure et créer l'utilisateur démo.")
        sqlite_exists = False
    else:
        print(f"Lecture des données depuis la base SQLite locale : {sqlite_path}")
        sqlite_exists = True

    # 3. Créer une application Flask temporaire pour initialiser SQLAlchemy
    app = Flask(__name__)
    app.config['SQLALCHEMY_DATABASE_URI'] = target_url
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    db.init_app(app)

    with app.app_context():
        print("Création de la structure des tables sur Neon PostgreSQL...")
        db.create_all()
        print("Structure des tables créée avec succès !")

        # 4. Créer l'utilisateur démo par défaut
        demo_email = "demo@example.com"
        demo_user = User.query.filter_by(email=demo_email).first()
        if not demo_user:
            print("Création de l'utilisateur démo par défaut...")
            password = "demo123"
            password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
            demo_user = User(
                username="demo",
                email=demo_email,
                password_hash=password_hash
            )
            db.session.add(demo_user)
            db.session.commit()
            print("Utilisateur démo créé avec succès ! (demo@example.com / demo123)")
        else:
            print("L'utilisateur démo existe déjà.")

        if not sqlite_exists:
            print("Migration terminée (base vierge initialisée avec utilisateur démo).")
            return

        # 5. Connecter SQLAlchemy à la base SQLite source
        source_engine = create_engine(f"sqlite:///{sqlite_path}")
        SourceSession = sessionmaker(bind=source_engine)
        source_session = SourceSession()

        try:
            print("Début du transfert des données...")

            # Dictionnaire pour mapper les anciens IDs aux nouveaux IDs
            project_id_map = {}
            quest_id_map = {}
            question_id_map = {}
            session_id_map = {}

            # A. Transférer les Projets
            # On récupère les lignes SQLite brutes
            sqlite_projects = source_session.execute("SELECT id, name, description, created_at FROM projects").fetchall()
            for row in sqlite_projects:
                # Vérifier si le projet existe déjà sur la cible pour éviter les doublons
                # Le projet AEPA sera marqué is_demo=True
                name = row[1]
                is_demo = "aepa" in name.lower() or "potable" in name.lower()
                
                existing_proj = Project.query.filter_by(name=name).first()
                if not existing_proj:
                    new_proj = Project(
                        name=name,
                        description=row[2],
                        created_at=datetime.strptime(row[3].split('.')[0], "%Y-%m-%d %H:%M:%S") if row[3] else datetime.utcnow(),
                        is_demo=is_demo,
                        user_id=demo_user.id if is_demo else None
                    )
                    db.session.add(new_proj)
                    db.session.flush() # Récupérer le nouvel ID
                    project_id_map[row[0]] = new_proj.id
                    print(f"Projet transféré : {name} (Nouveau ID: {new_proj.id}, Démo: {is_demo})")
                else:
                    project_id_map[row[0]] = existing_proj.id
                    print(f"Projet déjà existant : {name} (ID cible: {existing_proj.id})")

            # B. Transférer les Questionnaires
            sqlite_quest = source_session.execute("SELECT id, project_id, title, description, created_at FROM questionnaires").fetchall()
            for row in sqlite_quest:
                target_project_id = project_id_map.get(row[1])
                if not target_project_id:
                    continue
                
                existing_quest = Questionnaire.query.filter_by(project_id=target_project_id, title=row[2]).first()
                if not existing_quest:
                    new_quest = Questionnaire(
                        project_id=target_project_id,
                        title=row[2],
                        description=row[3],
                        created_at=datetime.strptime(row[4].split('.')[0], "%Y-%m-%d %H:%M:%S") if row[4] else datetime.utcnow()
                    )
                    db.session.add(new_quest)
                    db.session.flush()
                    quest_id_map[row[0]] = new_quest.id
                    print(f"Questionnaire transféré : {row[2]}")
                else:
                    quest_id_map[row[0]] = existing_quest.id

            # C. Transférer les Questions
            sqlite_questions = source_session.execute("SELECT id, questionnaire_id, text, question_type, choices, order_num FROM questions").fetchall()
            for row in sqlite_questions:
                target_quest_id = quest_id_map.get(row[1])
                if not target_quest_id:
                    continue
                
                # Vérifier les doublons
                existing_q = Question.query.filter_by(questionnaire_id=target_quest_id, text=row[2]).first()
                if not existing_q:
                    new_q = Question(
                        questionnaire_id=target_quest_id,
                        text=row[2],
                        question_type=row[3],
                        choices=row[4],
                        order_num=row[5]
                    )
                    db.session.add(new_q)
                    db.session.flush()
                    question_id_map[row[0]] = new_q.id
                else:
                    question_id_map[row[0]] = existing_q.id

            # D. Transférer les Sessions d'entretien
            sqlite_sessions = source_session.execute("SELECT id, project_id, questionnaire_id, title, interviewer, interviewee_name_or_group, actor_category, session_type, interview_date, created_at FROM interview_sessions").fetchall()
            for row in sqlite_sessions:
                target_project_id = project_id_map.get(row[1])
                target_quest_id = quest_id_map.get(row[2])
                if not target_project_id or not target_quest_id:
                    continue
                
                existing_s = InterviewSession.query.filter_by(project_id=target_project_id, title=row[3]).first()
                if not existing_s:
                    # Formater la date d'entretien
                    idate_str = row[8]
                    if isinstance(idate_str, str):
                        idate = datetime.strptime(idate_str.split('T')[0], "%Y-%m-%d").date()
                    else:
                        idate = datetime.utcnow().date()

                    new_s = InterviewSession(
                        project_id=target_project_id,
                        questionnaire_id=target_quest_id,
                        title=row[3],
                        interviewer=row[4],
                        interviewee_name_or_group=row[5],
                        actor_category=row[6],
                        session_type=row[7],
                        interview_date=idate,
                        created_at=datetime.strptime(row[9].split('.')[0], "%Y-%m-%d %H:%M:%S") if row[9] else datetime.utcnow(),
                        user_id=demo_user.id
                    )
                    db.session.add(new_s)
                    db.session.flush()
                    session_id_map[row[0]] = new_s.id
                    print(f"Entretien transféré : {row[3]}")
                else:
                    session_id_map[row[0]] = existing_s.id

            # E. Transférer les Réponses
            sqlite_answers = source_session.execute("SELECT id, session_id, question_id, answer_text FROM answers").fetchall()
            for row in sqlite_answers:
                target_session_id = session_id_map.get(row[1])
                target_question_id = question_id_map.get(row[2])
                if not target_session_id or not target_question_id:
                    continue
                
                existing_ans = Answer.query.filter_by(session_id=target_session_id, question_id=target_question_id).first()
                if not existing_ans:
                    new_ans = Answer(
                        session_id=target_session_id,
                        question_id=target_question_id,
                        answer_text=row[3]
                    )
                    db.session.add(new_ans)

            # F. Transférer les Pièces jointes
            sqlite_atts = source_session.execute("SELECT id, project_id, session_id, filename, filepath, file_type, uploaded_at FROM attachments").fetchall()
            for row in sqlite_atts:
                target_project_id = project_id_map.get(row[1])
                if not target_project_id:
                    continue
                
                target_session_id = session_id_map.get(row[2]) if row[2] else None
                
                existing_att = Attachment.query.filter_by(project_id=target_project_id, filename=row[3]).first()
                if not existing_att:
                    new_att = Attachment(
                        project_id=target_project_id,
                        session_id=target_session_id,
                        filename=row[3],
                        filepath=row[4],
                        file_type=row[5],
                        uploaded_at=datetime.strptime(row[6].split('.')[0], "%Y-%m-%d %H:%M:%S") if row[6] else datetime.utcnow()
                    )
                    db.session.add(new_att)

            db.session.commit()
            print("Félicitations ! Toutes les données existantes ont été migrées avec succès vers Neon PostgreSQL.")
        except Exception as e:
            db.session.rollback()
            print(f"Erreur lors de la migration des données : {e}")
        finally:
            source_session.close()

if __name__ == "__main__":
    migrate()
