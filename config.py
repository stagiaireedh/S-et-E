import os
import ssl
from dotenv import load_dotenv

# Contournement des erreurs de certificats SSL locaux (SSL_ERROR_SSL) en développement
try:
    ssl._create_default_https_context = ssl._create_unverified_context
except AttributeError:
    pass

# Charger les variables d'environnement depuis le fichier .env local si présent
load_dotenv()


class Config:
    # Clé secrète pour sécuriser les sessions Flask
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-key-suivi-evaluation-projets-2026')
    
    # Chemin absolu du dossier racine du projet
    BASE_DIR = os.path.abspath(os.path.dirname(__file__))
    
    # Configuration de la base de données SQLite et dossier d'uploads (utilisation de /tmp sur Vercel)
    if os.environ.get('VERCEL_ENV') or os.environ.get('VERCEL'):
        SQLALCHEMY_DATABASE_URI = 'sqlite:///' + os.path.join('/tmp', 'suivi_evaluation.db')
        UPLOAD_FOLDER = os.path.join('/tmp', 'uploads')
    else:
        SQLALCHEMY_DATABASE_URI = 'sqlite:///' + os.path.join(BASE_DIR, 'suivi_evaluation.db')
        UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')
        
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    
    # Taille maximale autorisée pour les fichiers (16 Mo)
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024
    
    # Extensions autorisées pour les pièces jointes
    ALLOWED_EXTENSIONS = {'pdf', 'docx', 'xlsx', 'txt', 'csv', 'png', 'jpg', 'jpeg'}
    
    # Clés API pour la cascade d'IA
    GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')
    GROQ_API_KEY = os.environ.get('GROQ_API_KEY')
    GITHUB_TOKEN = os.environ.get('GITHUB_TOKEN')
    
    # Activer ou désactiver la vraie IA (Gemini, Groq, GitHub)
    if os.environ.get('VERCEL_ENV') or os.environ.get('RENDER'):
        USE_REAL_IA = False
    else:
        USE_REAL_IA = True


def allowed_file(filename):
    """Vérifie si le fichier a une extension autorisée."""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in Config.ALLOWED_EXTENSIONS
