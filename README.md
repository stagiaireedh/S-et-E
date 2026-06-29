# Application de Suivi-Évaluation et Triangulation de Données d'Entretiens

Ce projet est une application web conçue pour les équipes de suivi-évaluation (M&E) afin de réaliser la **triangulation des données qualitatives et quantitatives** après des entretiens individuels ou collectifs (focus groups). 

L'application intègre des modules d'analyse intelligente simulée (sentiments, thèmes, risques et recommandations), de visualisation de données interactives et un assistant IA interactif sous forme de chat.

---

## 🚀 Fonctionnalités Clés

1.  **Collecte des Données** :
    *   Interface de création de questionnaires dynamiques (type texte libre ou choix unique).
    *   Formulaire de saisie manuelle guidée des réponses pour chaque session d'entretien.
    *   Zone d'import (Drag-and-Drop) de fichiers complémentaires (comptes rendus, rapports) liés aux projets.
2.  **Analyse de Triangulation Inteligente** :
    *   Analyse de sentiment en français basée sur un dictionnaire lexical (positif, négatif, neutre).
    *   Extraction automatique des thèmes récurrents par analyse fréquentielle pondérée.
    *   Détection automatique des risques et génération de recommandations d'action prioritaires.
3.  **Visualisation de Données (Dashboard)** :
    *   Indicateurs de performance (KPIs) dynamiques.
    *   Graphique en anneau (Doughnut) de répartition des acteurs interrogés (Bénéficiaires, Partenaires, Équipe, Autorités).
    *   Courbe d'évolution temporelle du sentiment des interlocuteurs.
    *   Filtre interactif par projet.
4.  **Matrice Comparative de Triangulation** :
    *   Vue côte-à-côte permettant de comparer les réponses à une question précise entre les différentes catégories d'acteurs pour déceler les convergences ou divergences.
5.  **Rapports Automatisés en PDF** :
    *   Génération d'un **Rapport d'Évaluation Global** complet du projet intégrant la synthèse IA, les statistiques d'acteurs, les thèmes, les risques et les recommandations d'action.
    *   Génération d'une **Fiche de Compte Rendu** détaillée par session d'entretien individuel ou collectif.
6.  **Assistant IA (Chat)** :
    *   Interface de discussion interactive permettant de poser des questions en langage naturel (ex: *"Quels sont les risques ?"*, *"Synthèse du projet"*).

---

## 🛠️ Stack Technique

*   **Backend** : Python 3.10+ avec le framework **Flask** et **Flask-SQLAlchemy**.
*   **Base de Données** : **SQLite** (Base locale relationnelle légère).
*   **Génération PDF** : **FPDF2** (Génération PDF moderne en français).
*   **Frontend** : HTML5, Vanilla CSS3 (Design sombre premium inspiré de glassmorphism, responsive) et JavaScript (ES6+ asynchrone, intégration avec **Chart.js** pour les graphiques).

---

## 📦 Installation et Lancement

### 1. Prérequis
Assurez-vous d'avoir Python 3.10 ou supérieur installé sur votre machine.

### 2. Cloner ou naviguer dans le dossier du projet
```bash
cd d:/Antigravity/suivi_evaluation
```

### 3. Créer et activer un environnement virtuel (recommandé)
Sur Windows (PowerShell) :
```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

### 4. Installer les dépendances
```bash
pip install -r requirements.txt
```

### 5. Initialiser la base de données avec des données de démonstration
Exécutez le script d'initialisation pour générer la structure SQLite et y insérer les données d'un projet réaliste d'accès à l'eau potable (Projet AEPA) comprenant 6 sessions d'entretiens diversifiés :
```bash
python database_init.py
```

### 6. Lancer le serveur Flask
```bash
python app.py
```

L'application sera accessible localement à l'adresse suivante :
👉 **[http://localhost:5000](http://localhost:5000)**

---

## 🔑 Configuration des Clés API et Cascade d'IA

L'application intègre une architecture intelligente en cascade. Lors d'une requête analytique (sentiments, thèmes, triangulation, chat), elle interroge successivement :
1.  **Google Gemini** (`gemini-2.5-flash`) via son SDK officiel.
2.  **Groq Cloud** (`llama-3.3-70b-versatile`) en cas de dépassement de quota ou d'erreur sur Gemini.
3.  **GitHub Models** (`gpt-4o`) en dernier recours d'API.
4.  **Simulation locale déterministe** (basée sur des dictionnaires locaux en français) si toutes les APIs échouent ou si aucune clé n'est fournie.

### Comment obtenir les clés API gratuitement :

*   **Google Gemini Key** :
    1. Rendez-vous sur [Google AI Studio](https://aistudio.google.com/).
    2. Connectez-vous avec un compte Google et cliquez sur **Get API key**.
    3. Générez une clé gratuite pour vos tests de développement.
*   **Groq Cloud Key** :
    1. Créez un compte gratuit sur la [Console Groq Cloud](https://console.groq.com/).
    2. Naviguez vers la section **API Keys** et cliquez sur **Create API Key**.
*   **GitHub Token** :
    1. Accédez à vos paramètres GitHub : [GitHub Developer Settings](https://github.com/settings/tokens).
    2. Cliquez sur **Generate new token (classic)**.
    3. Donnez-lui un nom et sélectionnez les permissions minimales requises.
    4. Utilisez ce token comme clé d'accès.

Pour configurer les clés, dupliquez le fichier `.env.example` en un fichier nommé `.env` à la racine du projet et renseignez-y vos clés :
```bash
cp .env.example .env
```

---

## ☁️ Déploiement sur le Cloud

Cette application est préconfigurée pour être déployée gratuitement sur **Vercel** ou **Render**.

### 1. Déploiement sur Render (Recommandé pour la persistance SQLite)
Render permet d'héberger l'application Flask avec un serveur web de production (**Gunicorn**).

1. Poussez votre projet sur un dépôt **GitHub**.
2. Créez un compte gratuit sur [Render](https://render.com/).
3. Cliquez sur **New +** -> **Blueprint** et connectez votre dépôt GitHub (cela lira automatiquement le fichier [render.yaml](file:///d:/Antigravity/suivi_evaluation/render.yaml)).
4. *Alternativement*, créez un **Web Service** manuel :
   - **Build Command** : `pip install -r requirements.txt && python database_init.py`
   - **Start Command** : `gunicorn app:app`
5. Dans l'onglet **Environment**, ajoutez les variables d'environnement si vous souhaitez activer la vraie IA : `GEMINI_API_KEY`, `GROQ_API_KEY`, `GITHUB_TOKEN`.
6. Tutoriel officiel : [Render Python/Flask Deployment](https://docs.render.com/deploy-flask).

*Note : La base de données SQLite étant stockée localement, le disque est éphémère sur les serveurs gratuits de Render. Pour un projet de production persistant, utilisez un disque persistant (Persistent Disk) sur Render ou connectez une base de données PostgreSQL gratuite.*

### 2. Déploiement sur Vercel
Vercel héberge le backend Flask sous forme de fonctions serverless à l'aide de [vercel.json](file:///d:/Antigravity/suivi_evaluation/vercel.json).

1. Installez le CLI de Vercel : `npm install -g vercel`.
2. Lancez le déploiement depuis la racine du projet :
   ```bash
   vercel
   ```
3. Suivez les instructions pour lier le projet.
4. Pour déployer en production :
   ```bash
   vercel --prod
   ```
5. Ajoutez vos clés secrètes dans le tableau de bord Vercel sous **Settings -> Environment Variables**.
6. Tutoriel officiel : [Vercel Python Serverless Functions](https://vercel.com/docs/concepts/functions/serverless-functions/runtimes/python).

---



## 📁 Structure du Projet

```text
d:/Antigravity/suivi_evaluation/
├── app.py                  # Initialisation Flask et déclaration des routes REST API
├── config.py               # Fichier de configuration (Database, Uploads, Extensions)
├── models.py               # Schéma de base de données relationnelle SQLAlchemy
├── ai_service.py           # Algorithmes d'analyse lexicale, de triangulation et chat IA
├── pdf_service.py          # Moteur de génération de documents PDF (FPDF2)
├── database_init.py        # Script de création et de remplissage de la base de données
├── requirements.txt        # Fichier de dépendances Python
├── README.md               # Le présent fichier d'aide
├── uploads/                # Répertoire de stockage des fichiers importés (géré automatiquement)
├── static/
│   ├── css/
│   │   └── style.css       # Style design premium responsive (effets de verre / glassmorphism)
│   └── js/
│       └── app.js          # Contrôleur frontend, intégration AJAX, Chart.js et discussion
└── templates/
    └── index.html          # Template HTML principal (Application Shell)
```
