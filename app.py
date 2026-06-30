import os
import io
import bcrypt
import pandas as pd
from datetime import datetime
from flask import Flask, request, jsonify, render_template, send_from_directory, make_response
from werkzeug.utils import secure_filename
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from config import Config, allowed_file
from models import db, User, Project, Questionnaire, Question, InterviewSession, Answer, Attachment, SharedQuestionnaire, QuestionnaireBlock, BlockLibrary
from ai_service import run_project_triangulation, chat_assistant_respond
from pdf_service import generate_global_evaluation_pdf, generate_session_summary_pdf

def create_app():
    """Initialise et configure l'application Flask."""
    app = Flask(__name__)
    app.config.from_object(Config)
    
    # Initialisation de la base de données avec l'application Flask
    db.init_app(app)
    
    # Protection pour Vercel / Render : Forcer la désactivation de l'IA réelle si dans le cloud
    if os.environ.get('VERCEL_ENV') or os.environ.get('RENDER'):
        import ai_service
        ai_service.ai_client = None
        app.logger.info("Environnement Cloud (Vercel/Render) détecté. Mode Simulation IA activé d'office.")

    # Création du dossier d'upload s'il n'existe pas
    if not os.path.exists(app.config['UPLOAD_FOLDER']):
        try:
            os.makedirs(app.config['UPLOAD_FOLDER'])
        except Exception as e:
            app.logger.warning(f"Impossible de créer le dossier d'uploads local : {e}")
        
    # --- CONFIGURATION FLASK-LOGIN ---
    login_manager = LoginManager()
    login_manager.init_app(app)
    login_manager.login_view = 'index'  # Redirection si non authentifié vers l'index SPA

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    @login_manager.unauthorized_handler
    def unauthorized():
        return jsonify({'success': False, 'message': 'Authentification requise.'}), 401

    # Auto-création des tables (le projet démo a été supprimé) & migration automatique des questionnaires
    with app.app_context():
        try:
            db.create_all()
            app.logger.info("Base de données initialisée avec succès.")
            try:
                from migrate_questionnaires import migrate_with_app
                migrate_with_app(app)
            except Exception as migration_error:
                app.logger.error(f"Erreur lors de la migration des blocs : {migration_error}")
            
            # Seeding automatique : créer l'utilisateur démo s'il n'existe pas
            try:
                demo_email = "demo@example.com"
                if not User.query.filter_by(email=demo_email).first():
                    demo_password_hash = bcrypt.hashpw("demo123".encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
                    demo_user = User(username="demo", email=demo_email, password_hash=demo_password_hash)
                    db.session.add(demo_user)
                    db.session.commit()
                    app.logger.info("Utilisateur démo créé automatiquement (demo@example.com / demo123).")
            except Exception as seed_error:
                app.logger.warning(f"Seeding utilisateur démo ignoré : {seed_error}")
        except Exception as e:
            app.logger.error(f"Erreur d'initialisation automatique de la base : {e}")

    # --- ROUTES FRONTEND ---
    @app.route('/')
    def index():
        """Affiche le tableau de bord principal (Single Page Application)."""
        return render_template('index.html')

    # --- API AUTHENTIFICATION ---
    @app.route('/api/register', methods=['POST'])
    def register():
        """Crée un nouvel utilisateur en hachant le mot de passe."""
        data = request.get_json()
        if not data or not data.get('username') or not data.get('email') or not data.get('password'):
            return jsonify({'success': False, 'message': 'Champs requis manquants.'}), 400
            
        username = data['username'].strip()
        email = data['email'].strip().lower()
        password = data['password']
        
        if User.query.filter((User.username == username) | (User.email == email)).first():
            return jsonify({'success': False, 'message': 'Nom d\'utilisateur ou email déjà utilisé.'}), 400
            
        password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        
        user = User(
            username=username,
            email=email,
            password_hash=password_hash
        )
        db.session.add(user)
        db.session.commit()
        
        login_user(user)
        return jsonify({'success': True, 'user': user.to_dict()}), 201

    @app.route('/api/login', methods=['POST'])
    def login():
        """Authentifie l'utilisateur et crée sa session Flask-Login."""
        data = request.get_json()
        if not data or not data.get('email') or not data.get('password'):
            return jsonify({'success': False, 'message': 'Email et mot de passe requis.'}), 400
            
        email = data['email'].strip().lower()
        password = data['password']
        
        user = User.query.filter_by(email=email).first()
        if not user or not bcrypt.checkpw(password.encode('utf-8'), user.password_hash.encode('utf-8')):
            return jsonify({'success': False, 'message': 'Identifiants incorrects.'}), 401
            
        login_user(user, remember=True)
        return jsonify({'success': True, 'user': user.to_dict()})

    @app.route('/api/logout', methods=['POST'])
    @login_required
    def logout():
        """Ferme la session Flask-Login."""
        logout_user()
        return jsonify({'success': True, 'message': 'Déconnexion réussie.'})

    @app.route('/api/me', methods=['GET'])
    def get_me():
        """Renvoie l'identité de l'utilisateur connecté."""
        if current_user.is_authenticated:
            return jsonify({'success': True, 'user': current_user.to_dict()})
        return jsonify({'success': False, 'message': 'Non connecté.'}), 401

    # --- API PROJETS & QUESTIONNAIRES ---
    @app.route('/api/projects', methods=['GET'])
    @login_required
    def get_projects():
        """Récupère la liste de tous les projets de l'utilisateur."""
        projects = Project.query.filter_by(user_id=current_user.id).order_by(Project.created_at.desc()).all()
        return jsonify([p.to_dict() for p in projects])

    @app.route('/api/projects', methods=['POST'])
    @login_required
    def create_project():
        """Crée un nouveau projet privé."""
        data = request.get_json()
        if not data or not data.get('name'):
            return jsonify({'success': False, 'message': 'Le nom du projet est requis.'}), 400
        
        project = Project(
            name=data['name'],
            description=data.get('description', ''),
            user_id=current_user.id
        )
        db.session.add(project)
        db.session.commit()
        return jsonify({'success': True, 'project': project.to_dict()}), 201

    @app.route('/api/projects/<int:project_id>', methods=['DELETE'])
    @login_required
    def delete_project(project_id):
        """Supprime un projet en cascade (base de données et pièces jointes sur le disque)."""
        project = Project.query.get_or_404(project_id)
        
        if project.user_id != current_user.id:
            return jsonify({'success': False, 'message': 'Accès interdit.'}), 403
            
        # Supprimer physiquement les fichiers joints associés de l'arborescence
        try:
            for attachment in project.attachments:
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], attachment.filepath)
                if os.path.exists(filepath):
                    os.remove(filepath)
        except Exception as e:
            app.logger.error(f"Erreur lors de la suppression des pièces jointes physiques : {e}")

        db.session.delete(project)
        db.session.commit()
        return jsonify({'success': True, 'message': 'Projet et toutes ses données associées supprimés.'})

    @app.route('/api/projects/<int:project_id>/questionnaires', methods=['GET'])
    @login_required
    def get_project_questionnaires(project_id):
        """Récupère les questionnaires du projet ou ceux partagés avec l'utilisateur."""
        project = Project.query.get_or_404(project_id)
        has_project_access = (project.user_id == current_user.id)
        
        if has_project_access:
            questionnaires = Questionnaire.query.filter_by(project_id=project_id).all()
        else:
            # Récupérer les questionnaires partagés avec l'utilisateur sur ce projet
            shares = SharedQuestionnaire.query.filter_by(shared_with_user_id=current_user.id).all()
            quest_ids = [s.questionnaire_id for s in shares]
            questionnaires = Questionnaire.query.filter(
                Questionnaire.id.in_(quest_ids),
                Questionnaire.project_id == project_id
            ).all()
            
        return jsonify([q.to_dict() for q in questionnaires])

    @app.route('/api/projects/<int:project_id>/questionnaires', methods=['POST'])
    @login_required
    def create_questionnaire(project_id):
        """Crée un questionnaire pour un projet."""
        project = Project.query.get_or_404(project_id)
        if project.user_id != current_user.id:
            return jsonify({'success': False, 'message': 'Accès interdit.'}), 403
            
        data = request.get_json()
        if not data or not data.get('title'):
            return jsonify({'success': False, 'message': 'Le titre du questionnaire est requis.'}), 400
            
        questionnaire = Questionnaire(
            project_id=project_id,
            title=data['title'],
            description=data.get('description', '')
        )
        db.session.add(questionnaire)
        db.session.flush()
        
        questions = data.get('questions', [])
        for i, q_data in enumerate(questions):
            question = Question(
                questionnaire_id=questionnaire.id,
                text=q_data['text'],
                question_type=q_data.get('question_type', 'text'),
                choices=q_data.get('choices', ''),
                order_num=i+1
            )
            db.session.add(question)
            
        db.session.commit()
        return jsonify({'success': True, 'questionnaire': questionnaire.to_dict()}), 201

    @app.route('/api/questionnaires/<int:questionnaire_id>', methods=['GET'])
    @login_required
    def get_questionnaire_details(questionnaire_id):
        """Récupère les détails complets d'un questionnaire."""
        questionnaire = Questionnaire.query.get_or_404(questionnaire_id)
        # Vérification d'accès
        is_owner = (questionnaire.project.user_id == current_user.id)
        is_shared = SharedQuestionnaire.query.filter_by(questionnaire_id=questionnaire_id, shared_with_user_id=current_user.id).first() is not None
        if not (is_owner or is_shared):
            return jsonify({'success': False, 'message': 'Accès interdit.'}), 403
            
        return jsonify(questionnaire.to_dict())

    @app.route('/api/questions/<int:question_id>', methods=['PUT'])
    @login_required
    def update_question(question_id):
        """Met à jour une question existante."""
        question = Question.query.get_or_404(question_id)
            
        # Droits : propriétaire du projet ou partagé avec permission "edit"
        is_owner = (question.questionnaire.project.user_id == current_user.id)
        share = SharedQuestionnaire.query.filter_by(questionnaire_id=question.questionnaire_id, shared_with_user_id=current_user.id).first()
        is_editor = (share and share.permission == 'edit')
        
        if not (is_owner or is_editor):
            return jsonify({'success': False, 'message': 'Accès interdit.'}), 403
            
        data = request.get_json()
        if not data or not data.get('text'):
            return jsonify({'success': False, 'message': 'Le texte de la question est requis.'}), 400
            
        question.text = data['text']
        question.question_type = data.get('question_type', question.question_type)
        question.choices = data.get('choices', question.choices)
        
        db.session.commit()
        return jsonify({'success': True, 'question': question.to_dict()})

    @app.route('/api/questions/<int:question_id>', methods=['DELETE'])
    @login_required
    def delete_question(question_id):
        """Supprime une question spécifique."""
        question = Question.query.get_or_404(question_id)
            
        is_owner = (question.questionnaire.project.user_id == current_user.id)
        share = SharedQuestionnaire.query.filter_by(questionnaire_id=question.questionnaire_id, shared_with_user_id=current_user.id).first()
        is_editor = (share and share.permission == 'edit')
        
        if not (is_owner or is_editor):
            return jsonify({'success': False, 'message': 'Accès interdit.'}), 403
            
        db.session.delete(question)
        db.session.commit()
        return jsonify({'success': True, 'message': 'Question supprimée avec succès.'})

    # --- API PARTAGE DE QUESTIONNAIRES ---
    @app.route('/api/questionnaires/<int:questionnaire_id>/share', methods=['POST'])
    @login_required
    def share_questionnaire(questionnaire_id):
        """Partage un questionnaire avec un utilisateur via son email."""
        questionnaire = Questionnaire.query.get_or_404(questionnaire_id)
        
        if questionnaire.project.user_id != current_user.id:
            return jsonify({'success': False, 'message': 'Seul le propriétaire du projet peut partager le questionnaire.'}), 403
            
        data = request.get_json()
        if not data or not data.get('email'):
            return jsonify({'success': False, 'message': 'L\'email du collaborateur est requis.'}), 400
            
        target_email = data['email'].strip().lower()
        permission = data.get('permission', 'read')
        
        if target_email == current_user.email:
            return jsonify({'success': False, 'message': 'Vous ne pouvez pas partager avec vous-même.'}), 400
            
        target_user = User.query.filter_by(email=target_email).first()
        if not target_user:
            return jsonify({'success': False, 'message': f"L'utilisateur associé à l'email {target_email} n'existe pas."}), 404
            
        # Vérifier si déjà partagé
        share = SharedQuestionnaire.query.filter_by(questionnaire_id=questionnaire_id, shared_with_user_id=target_user.id).first()
        if share:
            share.permission = permission
            db.session.commit()
            return jsonify({'success': True, 'message': 'Droits mis à jour.', 'share': share.to_dict()})
            
        share = SharedQuestionnaire(
            questionnaire_id=questionnaire_id,
            shared_with_user_id=target_user.id,
            permission=permission,
            shared_by_user_id=current_user.id
        )
        db.session.add(share)
        db.session.commit()
        return jsonify({'success': True, 'message': 'Questionnaire partagé avec succès.', 'share': share.to_dict()}), 201

    @app.route('/api/questionnaires/<int:questionnaire_id>/shares', methods=['GET'])
    @login_required
    def get_questionnaire_shares(questionnaire_id):
        """Récupère les collaborateurs d'un questionnaire."""
        questionnaire = Questionnaire.query.get_or_404(questionnaire_id)
        if questionnaire.project.user_id != current_user.id:
            return jsonify({'success': False, 'message': 'Accès interdit.'}), 403
            
        shares = SharedQuestionnaire.query.filter_by(questionnaire_id=questionnaire_id).all()
        return jsonify([s.to_dict() for s in shares])

    @app.route('/api/questionnaires/<int:questionnaire_id>/share/<int:user_id>', methods=['DELETE'])
    @login_required
    def revoke_questionnaire_share(questionnaire_id, user_id):
        """Révoque le partage d'un questionnaire."""
        questionnaire = Questionnaire.query.get_or_404(questionnaire_id)
        if questionnaire.project.user_id != current_user.id:
            return jsonify({'success': False, 'message': 'Accès interdit.'}), 403
            
        share = SharedQuestionnaire.query.filter_by(questionnaire_id=questionnaire_id, shared_with_user_id=user_id).first_or_404()
        db.session.delete(share)
        db.session.commit()
        return jsonify({'success': True, 'message': 'Partage révoqué avec succès.'})

    # --- API SESSIONS D'ENTRETIEN ---
    @app.route('/api/projects/<int:project_id>/sessions', methods=['GET'])
    @login_required
    def get_project_sessions(project_id):
        """Récupère toutes les sessions d'un projet."""
        project = Project.query.get_or_404(project_id)
        if project.user_id != current_user.id:
            return jsonify({'success': False, 'message': 'Accès interdit.'}), 403
            
        sessions = InterviewSession.query.filter_by(project_id=project_id).order_by(InterviewSession.interview_date.desc()).all()
        return jsonify([s.to_dict() for s in sessions])

    @app.route('/api/projects/<int:project_id>/sessions', methods=['POST'])
    @login_required
    def create_interview_session(project_id):
        """Enregistre un nouvel entretien."""
        project = Project.query.get_or_404(project_id)
            
        is_owner = (project.user_id == current_user.id)
        data = request.get_json()
        quest_id = data.get('questionnaire_id') if data else None
        
        # Vérification si partagé avec droit edit
        share = SharedQuestionnaire.query.filter_by(questionnaire_id=quest_id, shared_with_user_id=current_user.id, permission='edit').first()
        is_editor = (share is not None)
        
        if not (is_owner or is_editor):
            return jsonify({'success': False, 'message': 'Accès interdit.'}), 403
            
        if not data or not data.get('title') or not quest_id:
            return jsonify({'success': False, 'message': 'Le titre et le questionnaire sont requis.'}), 400
            
        session = InterviewSession(
            project_id=project_id,
            questionnaire_id=quest_id,
            title=data['title'],
            interviewer=data.get('interviewer', 'Non spécifié'),
            interviewee_name_or_group=data.get('interviewee_name_or_group', 'Anonyme'),
            actor_category=data.get('actor_category', 'Bénéficiaire'),
            session_type=data.get('session_type', 'individuel'),
            interview_date=secure_date(data.get('interview_date')),
            user_id=current_user.id
        )
        db.session.add(session)
        db.session.flush()
        
        answers = data.get('answers', {})
        for q_id, ans_text in answers.items():
            if ans_text and str(ans_text).strip():
                answer = Answer(
                    session_id=session.id,
                    question_id=int(q_id),
                    answer_text=str(ans_text)
                )
                db.session.add(answer)
                
        db.session.commit()
        return jsonify({'success': True, 'session': session.to_dict()}), 201

    @app.route('/api/sessions/<int:session_id>', methods=['GET'])
    @login_required
    def get_session_details(session_id):
        """Récupère les détails d'une session."""
        session = InterviewSession.query.get_or_404(session_id)
        # Vérifier droits d'accès
        is_owner = (session.project.user_id == current_user.id)
        is_shared = SharedQuestionnaire.query.filter_by(questionnaire_id=session.questionnaire_id, shared_with_user_id=current_user.id).first() is not None
        if not (is_owner or is_shared):
            return jsonify({'success': False, 'message': 'Accès interdit.'}), 403
            
        return jsonify(session.to_dict())

    @app.route('/api/sessions/<int:session_id>', methods=['PUT'])
    @login_required
    def update_interview_session(session_id):
        """Met à jour un entretien existant."""
        session = InterviewSession.query.get_or_404(session_id)
            
        is_owner = (session.project.user_id == current_user.id)
        is_author = (session.user_id == current_user.id)
        share = SharedQuestionnaire.query.filter_by(questionnaire_id=session.questionnaire_id, shared_with_user_id=current_user.id, permission='edit').first()
        is_editor = (share is not None)
        
        if not (is_owner or is_author or is_editor):
            return jsonify({'success': False, 'message': 'Accès interdit.'}), 403
            
        data = request.get_json()
        if not data or not data.get('title'):
            return jsonify({'success': False, 'message': 'Le titre est requis.'}), 400
            
        session.title = data['title']
        session.interviewer = data.get('interviewer', session.interviewer)
        session.interviewee_name_or_group = data.get('interviewee_name_or_group', session.interviewee_name_or_group)
        session.actor_category = data.get('actor_category', session.actor_category)
        session.session_type = data.get('session_type', session.session_type)
        session.interview_date = secure_date(data.get('interview_date'))
        
        Answer.query.filter_by(session_id=session.id).delete()
        
        answers = data.get('answers', {})
        for q_id, ans_text in answers.items():
            if ans_text and str(ans_text).strip():
                answer = Answer(
                    session_id=session.id,
                    question_id=int(q_id),
                    answer_text=str(ans_text)
                )
                db.session.add(answer)
                
        db.session.commit()
        return jsonify({'success': True, 'session': session.to_dict()})

    @app.route('/api/sessions/<int:session_id>', methods=['DELETE'])
    @login_required
    def delete_interview_session(session_id):
        """Supprime un entretien en cascade."""
        session = InterviewSession.query.get_or_404(session_id)
            
        if session.project.user_id != current_user.id and session.user_id != current_user.id:
            return jsonify({'success': False, 'message': 'Accès interdit.'}), 403
            
        try:
            for attachment in session.attachments:
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], attachment.filepath)
                if os.path.exists(filepath):
                    os.remove(filepath)
                db.session.delete(attachment)
        except Exception as e:
            app.logger.error(f"Erreur lors de la suppression des pièces jointes : {e}")
            
        db.session.delete(session)
        db.session.commit()
        return jsonify({'success': True, 'message': 'Entretien supprimé.'})

    # --- API IMPORT DE PIÈCES JOINTES ---
    @app.route('/api/projects/<int:project_id>/attachments', methods=['POST'])
    @login_required
    def upload_attachment(project_id):
        """Permet d'importer un fichier joint."""
        project = Project.query.get_or_404(project_id)
        if project.user_id != current_user.id:
            return jsonify({'success': False, 'message': 'Accès interdit.'}), 403
            
        if 'file' not in request.files:
            return jsonify({'success': False, 'message': 'Aucun fichier fourni.'}), 400
            
        file = request.files['file']
        if file.filename == '':
            return jsonify({'success': False, 'message': 'Nom de fichier vide.'}), 400
            
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            unique_filename = f"{int(os.urandom(4).hex(), 16)}_{filename}"
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
            file.save(filepath)
            
            session_id = request.form.get('session_id')
            if session_id == 'null' or session_id == '' or not session_id:
                session_id = None
            else:
                session_id = int(session_id)
                
            attachment = Attachment(
                project_id=project_id,
                session_id=session_id,
                filename=filename,
                filepath=unique_filename,
                file_type=file.content_type
            )
            db.session.add(attachment)
            db.session.commit()
            
            return jsonify({'success': True, 'attachment': attachment.to_dict()}), 201
            
        return jsonify({'success': False, 'message': 'Extension de fichier non autorisée.'}), 400

    @app.route('/api/projects/<int:project_id>/attachments', methods=['GET'])
    @login_required
    def get_project_attachments(project_id):
        """Récupère toutes les pièces jointes visibles."""
        project = Project.query.get_or_404(project_id)
        if project.user_id != current_user.id:
            return jsonify({'success': False, 'message': 'Accès interdit.'}), 403
            
        attachments = Attachment.query.filter_by(project_id=project_id).order_by(Attachment.uploaded_at.desc()).all()
        return jsonify([a.to_dict() for a in attachments])

    @app.route('/uploads/<filename>')
    def serve_uploaded_file(filename):
        """Sert un fichier uploadé de manière sécurisée."""
        return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

    # --- API ANALYSE IA & CHAT ASSISTANT ---
    @app.route('/api/projects/<int:project_id>/triangulation', methods=['GET'])
    @login_required
    def get_project_triangulation_data(project_id):
        """Exécute la triangulation de données pour un projet."""
        project = Project.query.get_or_404(project_id)
        if project.user_id != current_user.id:
            return jsonify({'success': False, 'message': 'Accès interdit.'}), 403
            
        analysis = run_project_triangulation(project_id)
        if not analysis.get('success'):
            return jsonify(analysis), 400
        return jsonify(analysis)

    @app.route('/api/projects/<int:project_id>/chat', methods=['POST'])
    @login_required
    def chat_assistant(project_id):
        """Endpoint du chat IA."""
        project = Project.query.get_or_404(project_id)
        if project.user_id != current_user.id:
            return jsonify({'success': False, 'message': 'Accès interdit.'}), 403
            
        data = request.get_json()
        if not data or not data.get('query'):
            return jsonify({'success': False, 'message': 'Requête vide.'}), 400
            
        user_query = data['query']
        response = chat_assistant_respond(user_query, project_id)
        return jsonify({'success': True, 'response': response})

    # --- API EXPORT CSV / EXCEL (PANDAS) ---
    @app.route('/api/projects/<int:project_id>/export/csv', methods=['GET'])
    @login_required
    def export_project_csv(project_id):
        """Exporte toutes les réponses du projet en fichier CSV."""
        project = Project.query.get_or_404(project_id)
        if project.user_id != current_user.id:
            return jsonify({'success': False, 'message': 'Accès interdit.'}), 403
            
        data_list = []
        for s in project.sessions:
            score_sum = 0
            for a in s.answers:
                text_lower = a.answer_text.lower()
                if any(w in text_lower for w in ['panne', 'difficile', 'problème', 'mauvais', 'échoué', 'défaut', 'plainte']):
                    score_sum -= 0.5
                elif any(w in text_lower for w in ['bon', 'excellent', 'très bien', 'réussite', 'facile', 'satisfait', 'progrès']):
                    score_sum += 0.5
            avg_score = score_sum / len(s.answers) if s.answers else 0
            sentiment_label = "Positif" if avg_score > 0.15 else ("Négatif" if avg_score < -0.15 else "Neutre")
            
            for a in s.answers:
                text_lower = a.answer_text.lower()
                theme = "Maintenance & Technique"
                if any(w in text_lower for w in ['eau', 'forage', 'pompe', 'installation', 'pression']):
                    theme = "Maintenance & Technique"
                elif any(w in text_lower for w in ['santé', 'diarrhée', 'malade', 'famille', 'vie', 'revenus', 'salades', 'maraîcher']):
                    theme = "Impact & Satisfaction"
                elif any(w in text_lower for w in ['comité', 'cotisation', 'transparence', 'gestion', 'argent', 'technicien']):
                    theme = "Aspect Financier & Gestion"
                else:
                    theme = "Général"
                    
                data_list.append({
                    'Projet': project.name,
                    'Session': s.title,
                    'Acteur': s.actor_category,
                    'Question': a.question.text,
                    'Réponse': a.answer_text,
                    'Sentiment': sentiment_label,
                    'Thèmes': theme
                })
                
        df = pd.DataFrame(data_list)
        if df.empty:
            df = pd.DataFrame(columns=['Projet', 'Session', 'Acteur', 'Question', 'Réponse', 'Sentiment', 'Thèmes'])
            
        output = io.StringIO()
        df.to_csv(output, index=False, encoding='utf-8-sig')
        response = make_response(output.getvalue())
        response.headers["Content-Disposition"] = f"attachment; filename=export_{secure_filename(project.name)}.csv"
        response.headers["Content-type"] = "text/csv; charset=utf-8"
        return response

    @app.route('/api/projects/<int:project_id>/export/excel', methods=['GET'])
    @login_required
    def export_project_excel(project_id):
        """Exporte toutes les réponses du projet en fichier Excel."""
        project = Project.query.get_or_404(project_id)
        if project.user_id != current_user.id:
            return jsonify({'success': False, 'message': 'Accès interdit.'}), 403
            
        data_list = []
        for s in project.sessions:
            score_sum = 0
            for a in s.answers:
                text_lower = a.answer_text.lower()
                if any(w in text_lower for w in ['panne', 'difficile', 'problème', 'mauvais', 'échoué', 'défaut', 'plainte']):
                    score_sum -= 0.5
                elif any(w in text_lower for w in ['bon', 'excellent', 'très bien', 'réussite', 'facile', 'satisfait', 'progrès']):
                    score_sum += 0.5
            avg_score = score_sum / len(s.answers) if s.answers else 0
            sentiment_label = "Positif" if avg_score > 0.15 else ("Négatif" if avg_score < -0.15 else "Neutre")
            
            for a in s.answers:
                text_lower = a.answer_text.lower()
                theme = "Maintenance & Technique"
                if any(w in text_lower for w in ['eau', 'forage', 'pompe', 'installation', 'pression']):
                    theme = "Maintenance & Technique"
                elif any(w in text_lower for w in ['santé', 'diarrhée', 'malade', 'famille', 'vie', 'revenus', 'salades', 'maraîcher']):
                    theme = "Impact & Satisfaction"
                elif any(w in text_lower for w in ['comité', 'cotisation', 'transparence', 'gestion', 'argent', 'technicien']):
                    theme = "Aspect Financier & Gestion"
                else:
                    theme = "Général"
                    
                data_list.append({
                    'Projet': project.name,
                    'Session': s.title,
                    'Acteur': s.actor_category,
                    'Question': a.question.text,
                    'Réponse': a.answer_text,
                    'Sentiment': sentiment_label,
                    'Thèmes': theme
                })
                
        df = pd.DataFrame(data_list)
        if df.empty:
            df = pd.DataFrame(columns=['Projet', 'Session', 'Acteur', 'Question', 'Réponse', 'Sentiment', 'Thèmes'])
            
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='Données Triangulées')
            
        response = make_response(output.getvalue())
        response.headers["Content-Disposition"] = f"attachment; filename=export_{secure_filename(project.name)}.xlsx"
        response.headers["Content-type"] = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        return response

    # --- API GENERATION DE RAPPORTS PDF ---
    @app.route('/api/projects/<int:project_id>/report', methods=['GET'])
    @login_required
    def download_global_report(project_id):
        """Génère et télécharge le rapport d'évaluation global en PDF."""
        project = Project.query.get_or_404(project_id)
        if project.user_id != current_user.id:
            return jsonify({'success': False, 'message': 'Accès interdit.'}), 403
            
        pdf_filename = f"rapport_evaluation_projet_{project_id}.pdf"
        pdf_path = os.path.join(app.config['UPLOAD_FOLDER'], pdf_filename)
        
        try:
            generate_global_evaluation_pdf(project, pdf_path)
            
            return send_from_directory(
                app.config['UPLOAD_FOLDER'], 
                pdf_filename, 
                as_attachment=True, 
                download_name=f"Rapport_Evaluation_{secure_filename(project.name)}.pdf"
            )
        except Exception as e:
            return jsonify({'success': False, 'message': f"Erreur de génération PDF : {str(e)}"}), 500

    @app.route('/api/sessions/<int:session_id>/report', methods=['GET'])
    @login_required
    def download_session_report(session_id):
        """Génère et télécharge le compte rendu d'entretien en PDF."""
        session = InterviewSession.query.get_or_404(session_id)
        if session.project.user_id != current_user.id:
            return jsonify({'success': False, 'message': 'Accès interdit.'}), 403
            
        pdf_filename = f"compte_rendu_entretien_{session_id}.pdf"
        pdf_path = os.path.join(app.config['UPLOAD_FOLDER'], pdf_filename)
        
        try:
            generate_session_summary_pdf(session, pdf_path)
            
            return send_from_directory(
                app.config['UPLOAD_FOLDER'], 
                pdf_filename, 
                as_attachment=True, 
                download_name=f"Compte_Rendu_{secure_filename(session.title)}.pdf"
            )
        except Exception as e:
            return jsonify({'success': False, 'message': f"Erreur de génération PDF : {str(e)}"}), 500

    # --- API CONSTRUCTEUR PAR BLOCS ---
    @app.route('/api/questionnaires/<int:questionnaire_id>/blocks', methods=['GET'])
    @login_required
    def get_questionnaire_blocks(questionnaire_id):
        """Récupère tous les blocs d'un questionnaire, ordonnés par index."""
        quest = Questionnaire.query.get_or_404(questionnaire_id)
        is_owner = (quest.project.user_id == current_user.id)
        is_shared = SharedQuestionnaire.query.filter_by(questionnaire_id=questionnaire_id, shared_with_user_id=current_user.id).first() is not None
        if not (is_owner or is_shared):
            return jsonify({'success': False, 'message': 'Accès interdit.'}), 403
            
        blocks = QuestionnaireBlock.query.filter_by(questionnaire_id=questionnaire_id).order_by(QuestionnaireBlock.order_index.asc()).all()
        return jsonify([b.to_dict() for b in blocks])

    @app.route('/api/questionnaires/<int:questionnaire_id>/blocks', methods=['POST'])
    @login_required
    def add_questionnaire_block(questionnaire_id):
        """Ajoute un nouveau bloc à un questionnaire et synchronise la table Question."""
        quest = Questionnaire.query.get_or_404(questionnaire_id)
        is_owner = (quest.project.user_id == current_user.id)
        share = SharedQuestionnaire.query.filter_by(questionnaire_id=questionnaire_id, shared_with_user_id=current_user.id).first()
        if not (is_owner or (share and share.permission == 'edit')):
            return jsonify({'success': False, 'message': 'Accès interdit.'}), 403
            
        data = request.get_json() or {}
        block_type = data.get('block_type', 'text')
        content = data.get('content', {})
        order_index = data.get('order_index')
        parent_block_id = data.get('parent_block_id')
        
        if order_index is None:
            max_idx = db.session.query(db.func.max(QuestionnaireBlock.order_index)).filter_by(questionnaire_id=questionnaire_id).scalar() or 0
            order_index = max_idx + 1
            
        # Synchronisation avec le modèle Question historique
        if block_type == 'question':
            q_entry = Question(
                questionnaire_id=questionnaire_id,
                text=content.get('label', 'Question sans titre'),
                question_type=content.get('question_type', 'text'),
                choices=",".join(content.get('choices', [])) if isinstance(content.get('choices'), list) else "",
                order_num=order_index,
                is_required=content.get('is_required', False),
                help_text=content.get('help_text', '')
            )
            db.session.add(q_entry)
            db.session.flush()
            content = dict(content)
            content['question_id'] = q_entry.id
            
        block = QuestionnaireBlock(
            questionnaire_id=questionnaire_id,
            block_type=block_type,
            content=content,
            order_index=order_index,
            parent_block_id=parent_block_id
        )
        db.session.add(block)
        db.session.commit()
        return jsonify({'success': True, 'block': block.to_dict()}), 201

    @app.route('/api/blocks/<int:block_id>', methods=['PUT'])
    @login_required
    def update_block(block_id):
        """Met à jour les propriétés d'un bloc et synchronise la table Question."""
        block = QuestionnaireBlock.query.get_or_404(block_id)
        quest = block.questionnaire
        is_owner = (quest.project.user_id == current_user.id)
        share = SharedQuestionnaire.query.filter_by(questionnaire_id=quest.id, shared_with_user_id=current_user.id).first()
        if not (is_owner or (share and share.permission == 'edit')):
            return jsonify({'success': False, 'message': 'Accès interdit.'}), 403
            
        data = request.get_json() or {}
        if 'content' in data:
            block.content = data['content']
            # Synchronisation de la table Question si c'est un bloc Question
            if block.block_type == 'question':
                q_id = block.content.get('question_id')
                if q_id:
                    q = Question.query.get(q_id)
                    if q:
                        q.text = block.content.get('label', 'Question')
                        q.question_type = block.content.get('question_type', 'text')
                        q.choices = ",".join(block.content.get('choices', [])) if isinstance(block.content.get('choices'), list) else ""
                        q.is_required = block.content.get('is_required', False)
                        q.help_text = block.content.get('help_text', '')
                        q.order_num = block.order_index
                else:
                    q_entry = Question(
                        questionnaire_id=quest.id,
                        text=block.content.get('label', 'Question'),
                        question_type=block.content.get('question_type', 'text'),
                        choices=",".join(block.content.get('choices', [])) if isinstance(block.content.get('choices'), list) else "",
                        order_num=block.order_index,
                        is_required=block.content.get('is_required', False),
                        help_text=block.content.get('help_text', '')
                    )
                    db.session.add(q_entry)
                    db.session.flush()
                    new_content = dict(block.content)
                    new_content['question_id'] = q_entry.id
                    block.content = new_content
                    
        if 'order_index' in data:
            block.order_index = data['order_index']
            if block.block_type == 'question':
                q_id = block.content.get('question_id') if block.content else None
                if q_id:
                    q = Question.query.get(q_id)
                    if q:
                        q.order_num = block.order_index
                        
        if 'parent_block_id' in data:
            block.parent_block_id = data['parent_block_id']
            
        db.session.commit()
        return jsonify({'success': True, 'block': block.to_dict()})

    @app.route('/api/blocks/<int:block_id>', methods=['DELETE'])
    @login_required
    def delete_block(block_id):
        """Supprime un bloc et sa question historique associée."""
        block = QuestionnaireBlock.query.get_or_404(block_id)
        quest = block.questionnaire
        is_owner = (quest.project.user_id == current_user.id)
        share = SharedQuestionnaire.query.filter_by(questionnaire_id=quest.id, shared_with_user_id=current_user.id).first()
        if not (is_owner or (share and share.permission == 'edit')):
            return jsonify({'success': False, 'message': 'Accès interdit.'}), 403
            
        if block.block_type == 'question':
            q_id = block.content.get('question_id') if block.content else None
            if q_id:
                q = Question.query.get(q_id)
                if q:
                    db.session.delete(q)
                    
        db.session.delete(block)
        db.session.commit()
        return jsonify({'success': True, 'message': 'Bloc supprimé.'})

    @app.route('/api/questionnaires/<int:questionnaire_id>/blocks/reorder', methods=['PUT'])
    @login_required
    def reorder_blocks(questionnaire_id):
        """Met à jour l'ordre de tous les blocs et des questions associées."""
        quest = Questionnaire.query.get_or_404(questionnaire_id)
        is_owner = (quest.project.user_id == current_user.id)
        share = SharedQuestionnaire.query.filter_by(questionnaire_id=questionnaire_id, shared_with_user_id=current_user.id).first()
        if not (is_owner or (share and share.permission == 'edit')):
            return jsonify({'success': False, 'message': 'Accès interdit.'}), 403
            
        data = request.get_json() or {}
        block_orders = data.get('blocks', [])
        
        for bo in block_orders:
            b = QuestionnaireBlock.query.filter_by(id=bo['id'], questionnaire_id=questionnaire_id).first()
            if b:
                b.order_index = bo['order_index']
                if b.block_type == 'question':
                    q_id = b.content.get('question_id') if b.content else None
                    if q_id:
                        q = Question.query.get(q_id)
                        if q:
                            q.order_num = bo['order_index']
                            
        db.session.commit()
        return jsonify({'success': True, 'message': 'Ordre des blocs sauvegardé.'})

    # --- API BIBLIOTHÈQUE DE BLOCS ---
    @app.route('/api/library', methods=['GET'])
    @login_required
    def get_library_blocks():
        """Récupère les blocs de la bibliothèque de l'utilisateur."""
        blocks = BlockLibrary.query.filter(
            (BlockLibrary.user_id == current_user.id) | (BlockLibrary.is_shared == True)
        ).order_by(BlockLibrary.created_at.desc()).all()
        return jsonify([b.to_dict() for b in blocks])

    @app.route('/api/library', methods=['POST'])
    @login_required
    def add_library_block():
        """Sauvegarde un bloc dans la bibliothèque."""
        data = request.get_json() or {}
        block_type = data.get('block_type')
        name = data.get('name')
        content = data.get('content', {})
        is_shared = data.get('is_shared', False)
        
        if not block_type or not name:
            return jsonify({'success': False, 'message': 'Type de bloc et nom requis.'}), 400
            
        lib_block = BlockLibrary(
            user_id=current_user.id,
            block_type=block_type,
            name=name,
            content=content,
            is_shared=is_shared
        )
        db.session.add(lib_block)
        db.session.commit()
        return jsonify({'success': True, 'block': lib_block.to_dict()}), 201

    @app.route('/api/library/<int:library_id>', methods=['DELETE'])
    @login_required
    def delete_library_block(library_id):
        """Supprime un bloc de la bibliothèque."""
        lib_block = BlockLibrary.query.get_or_404(library_id)
        if lib_block.user_id != current_user.id:
            return jsonify({'success': False, 'message': 'Accès interdit.'}), 403
            
        db.session.delete(lib_block)
        db.session.commit()
        return jsonify({'success': True, 'message': 'Bloc de bibliothèque supprimé.'})

    # --- API MODÈLES ET IMPORTS ---
    @app.route('/api/templates', methods=['GET'])
    @login_required
    def get_templates():
        """Liste tous les modèles de questionnaires disponibles."""
        templates = Questionnaire.query.filter_by(is_template=True).all()
        return jsonify([t.to_dict() for t in templates])

    @app.route('/api/questionnaires/from-template', methods=['POST'])
    @login_required
    def create_from_template():
        """Crée un nouveau questionnaire à partir d'un modèle (seeding dynamique)."""
        data = request.get_json() or {}
        template_id = data.get('template_id')  # ID ou clé de catégorie comme 'mission'
        project_id = data.get('project_id')
        title = data.get('title')
        
        if not template_id or not project_id or not title:
            return jsonify({'success': False, 'message': 'template_id, project_id et title requis.'}), 400
            
        new_quest = Questionnaire(
            project_id=project_id,
            title=title,
            description=f"Questionnaire créé à partir du modèle {template_id}",
            status='draft'
        )
        db.session.add(new_quest)
        db.session.flush()
        
        blocks_to_create = []
        
        if str(template_id).isdigit():
            template = Questionnaire.query.get(template_id)
            if template:
                new_quest.description = template.description
                for b in template.blocks:
                    blocks_to_create.append({
                        'block_type': b.block_type,
                        'content': b.content
                    })
        else:
            category = str(template_id).lower()
            if category == 'mission':
                blocks_to_create = [
                    {'block_type': 'title', 'content': {'title': title, 'description': 'Suivi des missions de terrain'}},
                    {'block_type': 'section', 'content': {'title': '1. Informations Générales'}},
                    {'block_type': 'question', 'content': {'label': 'Date de la mission', 'question_type': 'text', 'help_text': 'Format AAAA-MM-JJ'}},
                    {'block_type': 'question', 'content': {'label': 'Nom de l\'enquêteur / responsable', 'question_type': 'text'}},
                    {'block_type': 'section', 'content': {'title': '2. Observations'}},
                    {'block_type': 'question', 'content': {'label': 'Observations terrain clés', 'question_type': 'text'}},
                    {'block_type': 'question', 'content': {'label': 'Risques ou points bloquants relevés', 'question_type': 'text'}},
                    {'block_type': 'signature', 'content': {'label': 'Signature du responsable'}}
                ]
            elif category == 'evaluation':
                blocks_to_create = [
                    {'block_type': 'title', 'content': {'title': title, 'description': 'Évaluation des réalisations et impacts'}},
                    {'block_type': 'section', 'content': {'title': '1. Performances'}},
                    {'block_type': 'question', 'content': {'label': 'Niveau global de réussite des objectifs', 'question_type': 'select', 'choices': ['Excellent', 'Satisfaisant', 'Insatisfaisant']}},
                    {'block_type': 'question', 'content': {'label': 'Principaux facteurs de succès ou d\'échec', 'question_type': 'text'}},
                    {'block_type': 'gps', 'content': {'label': 'Coordonnées GPS du site visité'}},
                    {'block_type': 'photo', 'content': {'label': 'Preuve photographique de la réalisation'}}
                ]
            elif category == 'satisfaction':
                blocks_to_create = [
                    {'block_type': 'title', 'content': {'title': title, 'description': 'Enquête de satisfaction des usagers et bénéficiaires'}},
                    {'block_type': 'section', 'content': {'title': '1. Évaluation du Service'}},
                    {'block_type': 'question', 'content': {'label': 'Votre niveau global de satisfaction', 'question_type': 'select', 'choices': ['Très satisfait', 'Satisfait', 'Insatisfaisant', 'Très insatisfait']}},
                    {'block_type': 'question', 'content': {'label': 'Le service répond-il à vos besoins quotidiens ?', 'question_type': 'select', 'choices': ['Oui, entièrement', 'Partiellement', 'Non, pas du tout']}},
                    {'block_type': 'comment', 'content': {'label': 'Remarques et suggestions d\'amélioration'}}
                ]
            elif category == 'focus_group':
                blocks_to_create = [
                    {'block_type': 'title', 'content': {'title': title, 'description': 'Synthèse des discussions de Focus Group'}},
                    {'block_type': 'section', 'content': {'title': '1. Contexte du Groupe'}},
                    {'block_type': 'question', 'content': {'label': 'Nombre total de participants', 'question_type': 'text'}},
                    {'block_type': 'question', 'content': {'label': 'Principaux points de consensus', 'question_type': 'text'}},
                    {'block_type': 'question', 'content': {'label': 'Principaux points de divergence', 'question_type': 'text'}}
                ]
            else:
                blocks_to_create = [
                    {'block_type': 'title', 'content': {'title': title, 'description': 'Nouveau questionnaire personnalisé'}}
                ]
                
        for idx, b_data in enumerate(blocks_to_create):
            block_type = b_data['block_type']
            content = b_data['content']
            
            if block_type == 'question':
                q_entry = Question(
                    questionnaire_id=new_quest.id,
                    text=content.get('label', 'Question'),
                    question_type=content.get('question_type', 'text'),
                    choices=",".join(content.get('choices', [])) if isinstance(content.get('choices'), list) else "",
                    order_num=idx,
                    is_required=content.get('is_required', False),
                    help_text=content.get('help_text', '')
                )
                db.session.add(q_entry)
                db.session.flush()
                content = dict(content)
                content['question_id'] = q_entry.id
                
            block = QuestionnaireBlock(
                questionnaire_id=new_quest.id,
                block_type=block_type,
                order_index=idx,
                content=content
            )
            db.session.add(block)
            
        db.session.commit()
        return jsonify({'success': True, 'questionnaire': new_quest.to_dict()}), 201

    @app.route('/api/questionnaires/import', methods=['POST'])
    @login_required
    def import_questionnaire_file():
        """Analyse un fichier (Word/PDF/Excel) et extrait la structure avec l'IA."""
        if 'file' not in request.files:
            return jsonify({'success': False, 'message': 'Aucun fichier fourni.'}), 400
            
        file = request.files['file']
        if file.filename == '':
            return jsonify({'success': False, 'message': 'Fichier vide.'}), 400
            
        filename = secure_filename(file.filename)
        file_stream = io.BytesIO(file.read())
        
        file_text = extract_text_from_file(file_stream, filename)
        
        if not file_text:
            return jsonify({'success': False, 'message': 'Impossible d\'extraire du texte de ce fichier.'}), 400
            
        from ai_service import import_questionnaire_from_text
        structure = import_questionnaire_from_text(file_text, filename)
        
        return jsonify({'success': True, 'structure': structure})

    @app.route('/api/questionnaires/import/confirm', methods=['POST'])
    @login_required
    def confirm_import_questionnaire():
        """Valide la structure importée et crée le questionnaire définitif en blocs."""
        data = request.get_json() or {}
        project_id = data.get('project_id')
        structure = data.get('structure', {})
        
        if not project_id or not structure.get('title'):
            return jsonify({'success': False, 'message': 'project_id et structure de questionnaire requis.'}), 400
            
        quest = Questionnaire(
            project_id=project_id,
            title=structure['title'],
            description=structure.get('description', ''),
            status='draft'
        )
        db.session.add(quest)
        db.session.flush()
        
        blocks = structure.get('blocks', [])
        for idx, b in enumerate(blocks):
            block = QuestionnaireBlock(
                questionnaire_id=quest.id,
                block_type=b['block_type'],
                order_index=idx,
                content=b.get('content', {})
            )
            db.session.add(block)
            
        db.session.commit()
        return jsonify({'success': True, 'questionnaire': quest.to_dict()}), 201

    # --- API ASSISTANT IA CRÉATION ---
    @app.route('/api/assistant/create-questionnaire', methods=['POST'])
    @login_required
    def generate_questionnaire_ai():
        """Génère un questionnaire en blocs complet à partir d'une description descriptive."""
        data = request.get_json() or {}
        prompt = data.get('prompt')
        if not prompt:
            return jsonify({'success': False, 'message': 'Le prompt de description est requis.'}), 400
            
        from ai_service import generate_questionnaire_from_prompt
        structure = generate_questionnaire_from_prompt(prompt)
        
        return jsonify({'success': True, 'structure': structure})

    # --- API EXPORTS MULTI-FORMATS ---
    @app.route('/api/questionnaires/<int:questionnaire_id>/export/word', methods=['GET'])
    @login_required
    def export_word(questionnaire_id):
        """Exporte le questionnaire en format Word (.docx)."""
        quest = Questionnaire.query.get_or_404(questionnaire_id)
        if quest.project.user_id != current_user.id:
            return jsonify({'success': False, 'message': 'Accès interdit.'}), 403
            
        from export_service import export_to_word
        docx_data = export_to_word(quest)
        
        response = make_response(docx_data)
        response.headers['Content-Type'] = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
        response.headers['Content-Disposition'] = f'attachment; filename=Questionnaire_{secure_filename(quest.title)}.docx'
        return response

    @app.route('/api/questionnaires/<int:questionnaire_id>/export/excel', methods=['GET'])
    @login_required
    def export_excel(questionnaire_id):
        """Exporte le questionnaire en format Excel (.xlsx)."""
        quest = Questionnaire.query.get_or_404(questionnaire_id)
        if quest.project.user_id != current_user.id:
            return jsonify({'success': False, 'message': 'Accès interdit.'}), 403
            
        from export_service import export_to_excel
        xlsx_data = export_to_excel(quest)
        
        response = make_response(xlsx_data)
        response.headers['Content-Type'] = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        response.headers['Content-Disposition'] = f'attachment; filename=Questionnaire_{secure_filename(quest.title)}.xlsx'
        return response

    @app.route('/api/questionnaires/<int:questionnaire_id>/export/pdf', methods=['GET'])
    @login_required
    def export_pdf(questionnaire_id):
        """Exporte le questionnaire en PDF mis en page."""
        quest = Questionnaire.query.get_or_404(questionnaire_id)
        if quest.project.user_id != current_user.id:
            return jsonify({'success': False, 'message': 'Accès interdit.'}), 403
            
        from export_service import export_to_pdf
        pdf_data = export_to_pdf(quest)
        
        response = make_response(pdf_data)
        response.headers['Content-Type'] = 'application/pdf'
        response.headers['Content-Disposition'] = f'attachment; filename=Questionnaire_{secure_filename(quest.title)}.pdf'
        return response

    @app.route('/api/questionnaires/<int:questionnaire_id>/export/mobile', methods=['GET'])
    @login_required
    def export_mobile(questionnaire_id):
        """Renvoie le questionnaire structuré en JSON optimisé pour terminaux mobiles."""
        quest = Questionnaire.query.get_or_404(questionnaire_id)
        if quest.project.user_id != current_user.id:
            return jsonify({'success': False, 'message': 'Accès interdit.'}), 403
            
        return jsonify(quest.to_dict())

    @app.errorhandler(Exception)
    def handle_exception(e):
        if request.path.startswith('/api/'):
            from werkzeug.exceptions import HTTPException
            if isinstance(e, HTTPException):
                return jsonify({'success': False, 'message': e.description}), e.code
            app.logger.error(f"Erreur interne du serveur : {e}")
            return jsonify({'success': False, 'message': f"Erreur interne : {str(e)}"}), 500
        return e

    return app

def secure_date(date_str):
    """Convertit une chaîne ISO AAAA-MM-JJ en objet Date (ou date du jour en cas d'erreur)."""
    try:
        if date_str:
            return datetime.strptime(date_str, '%Y-%m-%d').date()
    except Exception:
        pass
    return datetime.now().date()

def extract_text_from_file(file_stream, filename):
    """Extrait le texte brut d'un fichier Word, Excel, PDF ou texte brut."""
    ext = filename.split('.')[-1].lower()
    if ext == 'docx':
        import docx
        doc = docx.Document(file_stream)
        return "\n".join([p.text for p in doc.paragraphs])
    elif ext in ['xlsx', 'xls']:
        import openpyxl
        wb = openpyxl.load_workbook(file_stream, data_only=True)
        lines = []
        for sheet in wb.worksheets:
            for row in sheet.iter_rows(values_only=True):
                lines.append(" ".join([str(v) for v in row if v is not None]))
        return "\n".join(lines)
    elif ext == 'pdf':
        try:
            import pypdf
            reader = pypdf.PdfReader(file_stream)
            text = ""
            for page in reader.pages:
                t = page.extract_text()
                if t:
                    text += t + "\n"
            return text
        except Exception as e:
            return f"Erreur d'extraction PDF : {e}"
    else:
        try:
            return file_stream.read().decode('utf-8', errors='ignore')
        except:
            return ""


# Instanciation globale au niveau du module pour gunicorn / Vercel WSGI
app = create_app()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
