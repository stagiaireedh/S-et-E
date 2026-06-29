import os
import io
import bcrypt
import pandas as pd
from flask import Flask, request, jsonify, render_template, send_from_directory, make_response
from werkzeug.utils import secure_filename
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from config import Config, allowed_file
from models import db, User, Project, Questionnaire, Question, InterviewSession, Answer, Attachment, SharedQuestionnaire
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

    # Auto-création des tables (le projet démo a été supprimé)
    with app.app_context():
        try:
            db.create_all()
            app.logger.info("Base de données initialisée avec succès.")
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

    return app

def secure_date(date_str):
    """Convertit une chaîne ISO AAAA-MM-JJ en objet Date (ou date du jour en cas d'erreur)."""
    try:
        if date_str:
            return datetime.strptime(date_str, '%Y-%m-%d').date()
    except Exception:
        pass
    return datetime.now().date()

# Instanciation globale au niveau du module pour gunicorn / Vercel WSGI
app = create_app()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
