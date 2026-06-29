from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

# Initialisation de SQLAlchemy (sera lié à l'application Flask dans app.py)
db = SQLAlchemy()

class Project(db.Model):
    """Représente un projet suivi et évalué."""
    __tablename__ = 'projects'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relations
    questionnaires = db.relationship('Questionnaire', backref='project', lazy=True, cascade="all, delete-orphan")
    sessions = db.relationship('InterviewSession', backref='project', lazy=True, cascade="all, delete-orphan")
    attachments = db.relationship('Attachment', backref='project', lazy=True, cascade="all, delete-orphan")

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

class Questionnaire(db.Model):
    """Représente un questionnaire d'évaluation associé à un projet."""
    __tablename__ = 'questionnaires'
    
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id'), nullable=False)
    title = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relations
    questions = db.relationship('Question', backref='questionnaire', lazy=True, order_by="Question.order_num", cascade="all, delete-orphan")
    sessions = db.relationship('InterviewSession', backref='questionnaire', lazy=True)

    def to_dict(self):
        return {
            'id': self.id,
            'project_id': self.project_id,
            'title': self.title,
            'description': self.description,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'questions': [q.to_dict() for q in self.questions]
        }

class Question(db.Model):
    """Une question spécifique au sein d'un questionnaire."""
    __tablename__ = 'questions'
    
    id = db.Column(db.Integer, primary_key=True)
    questionnaire_id = db.Column(db.Integer, db.ForeignKey('questionnaires.id'), nullable=False)
    text = db.Column(db.Text, nullable=False)
    question_type = db.Column(db.String(20), default='text')  # 'text' ou 'select' (choix multiples)
    choices = db.Column(db.Text, nullable=True)  # Options séparées par des virgules pour le type 'select'
    order_num = db.Column(db.Integer, default=0)
    
    # Relations
    answers = db.relationship('Answer', backref='question', lazy=True, cascade="all, delete-orphan")

    def to_dict(self):
        return {
            'id': self.id,
            'questionnaire_id': self.questionnaire_id,
            'text': self.text,
            'question_type': self.question_type,
            'choices': [c.strip() for c in self.choices.split(',')] if self.choices else [],
            'order_num': self.order_num
        }

class InterviewSession(db.Model):
    """Représente une session d'entretien (individuel ou collectif/focus group)."""
    __tablename__ = 'interview_sessions'
    
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id'), nullable=False)
    questionnaire_id = db.Column(db.Integer, db.ForeignKey('questionnaires.id'), nullable=False)
    title = db.Column(db.String(150), nullable=False)
    interviewer = db.Column(db.String(100), nullable=False)
    interviewee_name_or_group = db.Column(db.String(150), nullable=False)
    
    # Catégorie d'acteurs : 'Bénéficiaire', 'Partenaire', 'Équipe Projet', 'Autorité Locale'
    actor_category = db.Column(db.String(50), nullable=False)
    
    # Type de session : 'individuel' ou 'collectif'
    session_type = db.Column(db.String(20), default='individuel')
    
    interview_date = db.Column(db.Date, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relations
    answers = db.relationship('Answer', backref='session', lazy=True, cascade="all, delete-orphan")
    attachments = db.relationship('Attachment', backref='session', lazy=True)

    def to_dict(self):
        return {
            'id': self.id,
            'project_id': self.project_id,
            'questionnaire_id': self.questionnaire_id,
            'title': self.title,
            'interviewer': self.interviewer,
            'interviewee_name_or_group': self.interviewee_name_or_group,
            'actor_category': self.actor_category,
            'session_type': self.session_type,
            'interview_date': self.interview_date.isoformat() if self.interview_date else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'answers': [a.to_dict() for a in self.answers]
        }

class Answer(db.Model):
    """Réponse d'un entretien à une question précise."""
    __tablename__ = 'answers'
    
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey('interview_sessions.id'), nullable=False)
    question_id = db.Column(db.Integer, db.ForeignKey('questions.id'), nullable=False)
    answer_text = db.Column(db.Text, nullable=False)

    def to_dict(self):
        return {
            'id': self.id,
            'session_id': self.session_id,
            'question_id': self.question_id,
            'answer_text': self.answer_text
        }

class Attachment(db.Model):
    """Pièce jointe importée (rapport, compte rendu, etc.) associée à un projet/entretien."""
    __tablename__ = 'attachments'
    
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id'), nullable=False)
    session_id = db.Column(db.Integer, db.ForeignKey('interview_sessions.id'), nullable=True)  # Optionnel
    filename = db.Column(db.String(255), nullable=False)
    filepath = db.Column(db.String(510), nullable=False)
    file_type = db.Column(db.String(50), nullable=True)  # ex: 'application/pdf', 'text/plain'
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'project_id': self.project_id,
            'session_id': self.session_id,
            'filename': self.filename,
            'filepath': self.filepath,
            'file_type': self.file_type,
            'uploaded_at': self.uploaded_at.isoformat() if self.uploaded_at else None
        }
