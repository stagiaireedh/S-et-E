from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from flask_login import UserMixin

# Initialisation de SQLAlchemy (sera lié à l'application Flask dans app.py)
db = SQLAlchemy()

class User(db.Model, UserMixin):
    """Modèle représentant un évaluateur / utilisateur de la plateforme."""
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relations
    projects = db.relationship('Project', backref='owner', lazy=True, cascade="all, delete-orphan")
    sessions = db.relationship('InterviewSession', backref='author', lazy=True)
    
    def to_dict(self):
        return {
            'id': self.id,
            'username': self.username,
            'email': self.email,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


class Project(db.Model):
    """Représente un projet suivi et évalué."""
    __tablename__ = 'projects'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Propriétaire
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    
    # Relations
    questionnaires = db.relationship('Questionnaire', backref='project', lazy=True, cascade="all, delete-orphan")
    sessions = db.relationship('InterviewSession', backref='project', lazy=True, cascade="all, delete-orphan")
    attachments = db.relationship('Attachment', backref='project', lazy=True, cascade="all, delete-orphan")

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'user_id': self.user_id
        }


class Questionnaire(db.Model):
    """Représente un questionnaire d'évaluation associé à un projet."""
    __tablename__ = 'questionnaires'
    
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id'), nullable=False)
    title = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text, nullable=True)
    is_template = db.Column(db.Boolean, default=False)
    template_category = db.Column(db.String(50), nullable=True)  # ex: 'vide', 'mission', 'evaluation', etc.
    status = db.Column(db.String(20), default='draft')  # 'draft', 'published', 'archived'
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relations
    questions = db.relationship('Question', backref='questionnaire', lazy=True, order_by="Question.order_num", cascade="all, delete-orphan")
    blocks = db.relationship('QuestionnaireBlock', backref='questionnaire', lazy=True, order_by="QuestionnaireBlock.order_index", cascade="all, delete-orphan")
    sessions = db.relationship('InterviewSession', backref='questionnaire', lazy=True)
    shares = db.relationship('SharedQuestionnaire', lazy=True, cascade="all, delete-orphan")

    def to_dict(self):
        return {
            'id': self.id,
            'project_id': self.project_id,
            'title': self.title,
            'description': self.description,
            'is_template': self.is_template,
            'template_category': self.template_category,
            'status': self.status,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'questions': [q.to_dict() for q in self.questions],
            'blocks': [b.to_dict() for b in self.blocks],
            'shares': [s.to_dict() for s in self.shares]
        }

class SharedQuestionnaire(db.Model):
    """Table de jonction gérant le partage collaboratif des questionnaires."""
    __tablename__ = 'shared_questionnaires'
    
    id = db.Column(db.Integer, primary_key=True)
    questionnaire_id = db.Column(db.Integer, db.ForeignKey('questionnaires.id'), nullable=False)
    shared_with_user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    permission = db.Column(db.String(20), default='read')  # 'read' ou 'edit'
    shared_by_user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relations explicites
    shared_with = db.relationship('User', foreign_keys=[shared_with_user_id], backref='shared_questionnaires_received', lazy=True)
    shared_by = db.relationship('User', foreign_keys=[shared_by_user_id], backref='shared_questionnaires_given', lazy=True)

    def to_dict(self):
        return {
            'id': self.id,
            'questionnaire_id': self.questionnaire_id,
            'shared_with_user_id': self.shared_with_user_id,
            'shared_with_email': self.shared_with.email if self.shared_with else '',
            'shared_with_username': self.shared_with.username if self.shared_with else '',
            'permission': self.permission,
            'shared_by_user_id': self.shared_by_user_id,
            'created_at': self.created_at.isoformat() if self.created_at else None
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
    
    # Nouveaux attributs pour le constructeur par blocs et la compatibilité ascendante
    options = db.Column(db.JSON, nullable=True)  # structure optionnelle
    is_required = db.Column(db.Boolean, default=False)
    validation_rules = db.Column(db.JSON, nullable=True)
    conditions = db.Column(db.JSON, nullable=True)
    default_value = db.Column(db.String(255), nullable=True)
    help_text = db.Column(db.Text, nullable=True)
    ai_prompt = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relations
    answers = db.relationship('Answer', backref='question', lazy=True, cascade="all, delete-orphan")

    def to_dict(self):
        return {
            'id': self.id,
            'questionnaire_id': self.questionnaire_id,
            'text': self.text,
            'question_type': self.question_type,
            'choices': [c.strip() for c in self.choices.split(',')] if self.choices else [],
            'order_num': self.order_num,
            'options': self.options if self.options else {},
            'is_required': self.is_required,
            'validation_rules': self.validation_rules if self.validation_rules else {},
            'conditions': self.conditions if self.conditions else {},
            'default_value': self.default_value,
            'help_text': self.help_text,
            'ai_prompt': self.ai_prompt,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

class QuestionnaireBlock(db.Model):
    """Représente un bloc visuel interactif au sein d'un questionnaire (style Notion/Canva)."""
    __tablename__ = 'questionnaire_blocks'
    
    id = db.Column(db.Integer, primary_key=True)
    questionnaire_id = db.Column(db.Integer, db.ForeignKey('questionnaires.id', ondelete='CASCADE'), nullable=False)
    block_type = db.Column(db.String(50), nullable=False)  # 'title', 'text', 'section', 'question', 'table', 'photo', 'signature', 'gps', 'file', 'ai', 'matrix', 'checkbox', 'comment'
    order_index = db.Column(db.Integer, nullable=False, default=0)
    parent_block_id = db.Column(db.Integer, db.ForeignKey('questionnaire_blocks.id', ondelete='CASCADE'), nullable=True)
    content = db.Column(db.JSON, nullable=False, default=dict)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relation récursive pour sous-blocs
    sub_blocks = db.relationship('QuestionnaireBlock', backref=db.backref('parent', remote_side=[id]), lazy=True, cascade="all, delete-orphan")

    def to_dict(self):
        return {
            'id': self.id,
            'questionnaire_id': self.questionnaire_id,
            'block_type': self.block_type,
            'order_index': self.order_index,
            'parent_block_id': self.parent_block_id,
            'content': self.content if self.content else {},
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

class BlockLibrary(db.Model):
    """Bibliothèque de blocs réutilisables créés ou sauvegardés par les utilisateurs."""
    __tablename__ = 'block_library'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    block_type = db.Column(db.String(50), nullable=False)
    name = db.Column(db.String(150), nullable=False)
    content = db.Column(db.JSON, nullable=False, default=dict)
    is_shared = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relation vers l'utilisateur créateur
    user = db.relationship('User', backref='library_blocks', lazy=True)

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'block_type': self.block_type,
            'name': self.name,
            'content': self.content if self.content else {},
            'is_shared': self.is_shared,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
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
    
    # Évaluateur associé
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    
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
            'user_id': self.user_id,
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

class SystemConfig(db.Model):
    """Table de configuration système pour stocker l'état global (seeding, etc.)."""
    __tablename__ = 'system_configs'
    
    key = db.Column(db.String(50), primary_key=True)
    value = db.Column(db.String(255), nullable=False)

    def to_dict(self):
        return {
            'key': self.key,
            'value': self.value
        }
