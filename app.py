import os
from flask import Flask, request, jsonify, render_template, send_from_directory, make_response
from werkzeug.utils import secure_filename
from config import Config, allowed_file
from models import db, Project, Questionnaire, Question, InterviewSession, Answer, Attachment
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
        os.makedirs(app.config['UPLOAD_FOLDER'])
        
    # Auto-création des tables et chargement des données de démonstration (seeding)
    with app.app_context():
        try:
            db.create_all()
            if Project.query.count() == 0:
                from datetime import date
                project = Project(
                    name="Projet d'Accès à l'Eau Potable et Assainissement (AEPA)",
                    description=(
                        "Ce projet vise à améliorer durablement l'accès à l'eau potable et aux infrastructures d'assainissement "
                        "de base pour 15 000 personnes vivant dans les zones rurales de la commune de Gandon. Il s'appuie sur la "
                        "construction de 5 forages solaires, l'installation de bornes-fontaines et le renforcement des capacités des "
                        "comités locaux de gestion de l'eau (ASUFOR)."
                    )
                )
                db.session.add(project)
                db.session.flush()
                
                questionnaire = Questionnaire(
                    project_id=project.id,
                    title="Évaluation Intermédiaire - Projet AEPA",
                    description="Questionnaire destiné à évaluer l'accès, le fonctionnement, la gestion financière et la satisfaction après 12 mois de mise en œuvre."
                )
                db.session.add(questionnaire)
                db.session.flush()
                
                q1 = Question(questionnaire_id=questionnaire.id, text="Quelle est votre appréciation globale de la disponibilité et de la qualité de l'eau potable ?", question_type="select", choices="Excellent, Bon, Moyen, Mauvais", order_num=1)
                q2 = Question(questionnaire_id=questionnaire.id, text="Quels sont les principaux changements constatés dans votre vie quotidienne (santé, temps de trajet, économies) ?", question_type="text", order_num=2)
                q3 = Question(questionnaire_id=questionnaire.id, text="Avez-vous rencontré des difficultés techniques ou des pannes récurrentes avec les nouvelles installations ?", question_type="text", order_num=3)
                q4 = Question(questionnaire_id=questionnaire.id, text="Selon vous, le comité de gestion local gère-t-il les cotisations et les installations de manière transparente ?", question_type="select", choices="Oui tout à fait, Oui partiellement, Non pas du tout", order_num=4)
                q5 = Question(questionnaire_id=questionnaire.id, text="Quelles sont vos recommandations prioritaires pour garantir la durabilité du service d'eau ?", question_type="text", order_num=5)
                db.session.add_all([q1, q2, q3, q4, q5])
                db.session.flush()
                
                s1 = InterviewSession(
                    project_id=project.id, questionnaire_id=questionnaire.id,
                    title="Focus Group - Femmes du quartier Nord", interviewer="Sophie Diouf (Évaluatrice)",
                    interviewee_name_or_group="Groupe de discussion (12 femmes)", actor_category="Bénéficiaire",
                    session_type="collectif", interview_date=date(2026, 6, 10)
                )
                db.session.add(s1)
                db.session.flush()
                db.session.add_all([
                    Answer(session_id=s1.id, question_id=q1.id, answer_text="Moyen"),
                    Answer(session_id=s1.id, question_id=q2.id, answer_text="La qualité de l'eau est très bonne et les enfants ne tombent plus malades de la diarrhée. C'est un grand changement positif pour la santé de nos familles."),
                    Answer(session_id=s1.id, question_id=q3.id, answer_text="Oui, nous rencontrons des pannes récurrentes de la pompe solaire ces derniers temps. Quand elle tombe en panne, le réparateur prend plus d'une semaine pour venir car il manque de pièces de rechange."),
                    Answer(session_id=s1.id, question_id=q4.id, answer_text="Oui partiellement"),
                    Answer(session_id=s1.id, question_id=q5.id, answer_text="Il faut absolument former un technicien local résidant dans le village et lui donner une caisse d'outils.")
                ])
                
                s2 = InterviewSession(
                    project_id=project.id, questionnaire_id=questionnaire.id,
                    title="Entretien individuel - M. Amadou Diallo (Maraîcher)", interviewer="Sophie Diouf (Évaluatrice)",
                    interviewee_name_or_group="Amadou Diallo", actor_category="Bénéficiaire",
                    session_type="individuel", interview_date=date(2026, 6, 12)
                )
                db.session.add(s2)
                db.session.flush()
                db.session.add_all([
                    Answer(session_id=s2.id, question_id=q1.id, answer_text="Excellent"),
                    Answer(session_id=s2.id, question_id=q2.id, answer_text="Grâce à la borne-fontaine installée près de mes parcelles, j'ai pu augmenter ma production de salades et de tomates. Mes revenus ont augmenté de 30%."),
                    Answer(session_id=s2.id, question_id=q3.id, answer_text="Pas de panne majeure de mon côté, mais la pression de l'eau baisse beaucoup en fin d'après-midi."),
                    Answer(session_id=s2.id, question_id=q4.id, answer_text="Oui tout à fait"),
                    Answer(session_id=s2.id, question_id=q5.id, answer_text="Il faudrait ajouter un deuxième réservoir de stockage d'eau.")
                ])
                db.session.commit()
                app.logger.info("Base de données initialisée et ensemencée (seeding) automatiquement.")
        except Exception as e:
            db.session.rollback()
            app.logger.error(f"Erreur d'initialisation automatique de la base : {e}")

        
    # --- ROUTES FRONTEND ---
    @app.route('/')
    def index():
        """Affiche le tableau de bord principal (Single Page Application)."""
        return render_template('index.html')

    # --- API PROJETS & QUESTIONNAIRES ---
    @app.route('/api/projects', methods=['GET'])
    def get_projects():
        """Récupère la liste de tous les projets."""
        projects = Project.query.order_by(Project.created_at.desc()).all()
        return jsonify([p.to_dict() for p in projects])

    @app.route('/api/projects', methods=['POST'])
    def create_project():
        """Crée un nouveau projet."""
        data = request.get_json()
        if not data or not data.get('name'):
            return jsonify({'success': False, 'message': 'Le nom du projet est requis.'}), 400
        
        project = Project(
            name=data['name'],
            description=data.get('description', '')
        )
        db.session.add(project)
        db.session.commit()
        return jsonify({'success': True, 'project': project.to_dict()}), 201

    @app.route('/api/projects/<int:project_id>', methods=['DELETE'])
    def delete_project(project_id):
        """Supprime un projet en cascade (base de données et pièces jointes sur le disque)."""
        project = Project.query.get_or_404(project_id)
        
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
    def get_project_questionnaires(project_id):
        """Récupère les questionnaires associés à un projet."""
        questionnaires = Questionnaire.query.filter_by(project_id=project_id).all()
        return jsonify([q.to_dict() for q in questionnaires])

    @app.route('/api/projects/<int:project_id>/questionnaires', methods=['POST'])
    def create_questionnaire(project_id):
        """Crée un questionnaire pour un projet avec ses questions associées."""
        data = request.get_json()
        if not data or not data.get('title'):
            return jsonify({'success': False, 'message': 'Le titre du questionnaire est requis.'}), 400
            
        questionnaire = Questionnaire(
            project_id=project_id,
            title=data['title'],
            description=data.get('description', '')
        )
        db.session.add(questionnaire)
        db.session.flush() # Récupérer l'ID pour insérer les questions
        
        # Insérer les questions fournies
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
    def get_questionnaire_details(questionnaire_id):
        """Récupère les détails complets d'un questionnaire (y compris ses questions)."""
        questionnaire = Questionnaire.query.get_or_404(questionnaire_id)
        return jsonify(questionnaire.to_dict())

    @app.route('/api/questions/<int:question_id>', methods=['PUT'])
    def update_question(question_id):
        """Met à jour le texte et les choix d'une question existante."""
        question = Question.query.get_or_404(question_id)
        data = request.get_json()
        if not data or not data.get('text'):
            return jsonify({'success': False, 'message': 'Le texte de la question est requis.'}), 400
            
        question.text = data['text']
        question.question_type = data.get('question_type', question.question_type)
        question.choices = data.get('choices', question.choices)
        
        db.session.commit()
        return jsonify({'success': True, 'question': question.to_dict()})

    @app.route('/api/questions/<int:question_id>', methods=['DELETE'])
    def delete_question(question_id):
        """Supprime une question spécifique (cascade automatique sur les réponses)."""
        question = Question.query.get_or_404(question_id)
        db.session.delete(question)
        db.session.commit()
        return jsonify({'success': True, 'message': 'Question supprimée avec succès.'})


    # --- API SESSIONS D'ENTRETIEN ---
    @app.route('/api/projects/<int:project_id>/sessions', methods=['GET'])
    def get_project_sessions(project_id):
        """Récupère toutes les sessions d'entretien d'un projet."""
        sessions = InterviewSession.query.filter_by(project_id=project_id).order_by(InterviewSession.interview_date.desc()).all()
        return jsonify([s.to_dict() for s in sessions])

    @app.route('/api/projects/<int:project_id>/sessions', methods=['POST'])
    def create_interview_session(project_id):
        """
        Enregistre une nouvelle session d'entretien (saisie manuelle des réponses).
        """
        data = request.get_json()
        if not data or not data.get('title') or not data.get('questionnaire_id'):
            return jsonify({'success': False, 'message': 'Le titre et le questionnaire sont requis.'}), 400
            
        # Création de la session
        session = InterviewSession(
            project_id=project_id,
            questionnaire_id=data['questionnaire_id'],
            title=data['title'],
            interviewer=data.get('interviewer', 'Non spécifié'),
            interviewee_name_or_group=data.get('interviewee_name_or_group', 'Anonyme'),
            actor_category=data.get('actor_category', 'Bénéficiaire'),
            session_type=data.get('session_type', 'individuel'),
            interview_date=secure_date(data.get('interview_date'))
        )
        db.session.add(session)
        db.session.flush() # Récupérer l'ID pour associer les réponses
        
        # Enregistrement des réponses aux questions
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
    def get_session_details(session_id):
        """Récupère les détails d'une session et ses réponses."""
        session = InterviewSession.query.get_or_404(session_id)
        return jsonify(session.to_dict())

    @app.route('/api/sessions/<int:session_id>', methods=['PUT'])
    def update_interview_session(session_id):
        """Met à jour un entretien existant et ses réponses."""
        session = InterviewSession.query.get_or_404(session_id)
        data = request.get_json()
        if not data or not data.get('title'):
            return jsonify({'success': False, 'message': 'Le titre est requis.'}), 400
            
        session.title = data['title']
        session.interviewer = data.get('interviewer', session.interviewer)
        session.interviewee_name_or_group = data.get('interviewee_name_or_group', session.interviewee_name_or_group)
        session.actor_category = data.get('actor_category', session.actor_category)
        session.session_type = data.get('session_type', session.session_type)
        session.interview_date = secure_date(data.get('interview_date'))
        
        # Supprimer les anciennes réponses pour réinsérer les nouvelles
        Answer.query.filter_by(session_id=session.id).delete()
        
        # Insérer les nouvelles réponses
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
    def delete_interview_session(session_id):
        """Supprime un entretien en cascade (base et pièces jointes associées)."""
        session = InterviewSession.query.get_or_404(session_id)
        
        # Supprimer les pièces jointes associées sur le disque
        try:
            for attachment in session.attachments:
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], attachment.filepath)
                if os.path.exists(filepath):
                    os.remove(filepath)
                # Supprimer la liaison en DB
                db.session.delete(attachment)
        except Exception as e:
            app.logger.error(f"Erreur lors de la suppression des pièces jointes de la session : {e}")
            
        db.session.delete(session)
        db.session.commit()
        return jsonify({'success': True, 'message': 'Entretien et réponses associés supprimés.'})


    # --- API IMPORT DE PIÈCES JOINTES ---
    @app.route('/api/projects/<int:project_id>/attachments', methods=['POST'])
    def upload_attachment(project_id):
        """Permet d'importer un fichier (pièce jointe) lié à un projet ou à une session."""
        if 'file' not in request.files:
            return jsonify({'success': False, 'message': 'Aucun fichier fourni.'}), 400
            
        file = request.files['file']
        if file.filename == '':
            return jsonify({'success': False, 'message': 'Nom de fichier vide.'}), 400
            
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            # Ajout d'un timestamp pour éviter les écrasements
            unique_filename = f"{int(os.urandom(4).hex(), 16)}_{filename}"
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
            file.save(filepath)
            
            # Liaison optionnelle à une session
            session_id = request.form.get('session_id')
            if session_id == 'null' or session_id == '':
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
    def get_project_attachments(project_id):
        """Récupère toutes les pièces jointes importées pour un projet."""
        attachments = Attachment.query.filter_by(project_id=project_id).order_by(Attachment.uploaded_at.desc()).all()
        return jsonify([a.to_dict() for a in attachments])

    @app.route('/uploads/<filename>')
    def serve_uploaded_file(filename):
        """Sert un fichier uploadé de manière sécurisée."""
        return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

    # --- API ANALYSE IA & CHAT ASSISTANT ---
    @app.route('/api/projects/<int:project_id>/triangulation', methods=['GET'])
    def get_project_triangulation_data(project_id):
        """Exécute l'analyse IA de triangulation de données pour un projet."""
        analysis = run_project_triangulation(project_id)
        if not analysis.get('success'):
            return jsonify(analysis), 400
        return jsonify(analysis)

    @app.route('/api/projects/<int:project_id>/chat', methods=['POST'])
    def chat_assistant(project_id):
        """Endpoint pour interagir en langage naturel avec les données d'évaluation."""
        data = request.get_json()
        if not data or not data.get('query'):
            return jsonify({'success': False, 'message': 'Requête vide.'}), 400
            
        user_query = data['query']
        response = chat_assistant_respond(user_query, project_id)
        return jsonify({'success': True, 'response': response})

    # --- API GENERATION DE RAPPORTS PDF ---
    @app.route('/api/projects/<int:project_id>/report', methods=['GET'])
    def download_global_report(project_id):
        """Génère et télécharge le rapport d'évaluation global en PDF."""
        project = Project.query.get_or_404(project_id)
        
        # Nom de fichier temporaire
        pdf_filename = f"rapport_evaluation_projet_{project_id}.pdf"
        pdf_path = os.path.join(app.config['UPLOAD_FOLDER'], pdf_filename)
        
        try:
            generate_global_evaluation_pdf(project, pdf_path)
            
            # Envoi du fichier
            return send_from_directory(
                app.config['UPLOAD_FOLDER'], 
                pdf_filename, 
                as_attachment=True, 
                download_name=f"Rapport_Evaluation_{secure_filename(project.name)}.pdf"
            )
        except Exception as e:
            return jsonify({'success': False, 'message': f"Erreur de génération PDF : {str(e)}"}), 500

    @app.route('/api/sessions/<int:session_id>/report', methods=['GET'])
    def download_session_report(session_id):
        """Génère et télécharge le compte rendu d'entretien en PDF."""
        session = InterviewSession.query.get_or_404(session_id)
        
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
    # Récupération du port défini par l'environnement (Render, Heroku, etc.) ou 5000 par défaut
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)

