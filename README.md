# S&E-CSB — Suivi-Évaluation & Collecte de Base

Ce projet est une application web conçue pour les équipes de suivi-évaluation (M&E) afin de réaliser la **triangulation des données qualitatives et quantitatives** après des entretiens individuels ou collectifs (focus groups). 

L'application intègre des modules d'analyse intelligente (sentiments, thèmes, risques et recommandations), de visualisation de données interactives (tableau de bord) et un assistant IA interactif grounded dans les témoignages.

---

## 🚀 Fonctionnalités Avancées (Version 2.0)

1.  **Authentification Multi-Utilisateurs** :
    *   Gestion des sessions avec **Flask-Login** et hachage de sécurité **bcrypt**.
    *   Isolation stricte des projets : chaque évaluateur gère ses propres données d'études en toute confidentialité.
    *   Profil utilisateur (avatar/initiales) et menu de déconnexion dans l'en-tête.

2.  **Persistance Cloud avec Neon PostgreSQL** :
    *   Mode hybride intelligent : connexion automatique à **Neon PostgreSQL** en production (via `DATABASE_URL`) et repli sur **SQLite** local en développement.
    *   Persistance garantie (finies les bases SQLite éphémères réinitialisées à chaque déploiement Vercel).

3.  **Partage Collaboratif de Questionnaires** :
    *   Permet de partager des formulaires d'enquête avec d'autres utilisateurs inscrits sur la plateforme (recherche par adresse email).
    *   Attribution de droits fins : **Lecture seule** (pour saisie d'entretiens uniquement) ou **Édition** (pour modifier ou ajouter des questions).
    *   Révocation des partages en temps réel.

4.  **Exports Analytiques Excel & CSV** :
    *   Génération et téléchargement d'exports de données brutes structurées avec **Pandas** et **Openpyxl**.
    *   Colonnes exportées : Projet, Session d'entretien, Catégorie d'acteur, Question, Réponse verbatim, Sentiment calculé, Thématique associée.
    *   Boutons d'export directs sur le Tableau de bord et dans l'onglet Triangulation.

5.  **Bascule de Thème Sombre / Clair Premium** :
    *   Design Premium HSL moderne s'adaptant instantanément.
    *   Persistance automatique de la préférence dans le `localStorage` de l'utilisateur ou détection du thème système par défaut.

6.  **Conservation Sécurisée de la Démo (Projet AEPA)** :
    *   Le projet fictif AEPA reste partagé comme projet d'exploration en lecture seule pour tous les nouveaux comptes.
    *   Un badge **DÉMO** s'affiche et toutes les actions d'écriture (suppression de projet, modification d'entretiens) sont grisées et bloquées pour ce projet d'étude.

---

## 🛠️ Stack Technique

*   **Backend** : Python 3.12 avec **Flask**, **Flask-Login** et **Bcrypt**.
*   **Analyse de Données & Exports** : **Pandas** et **Openpyxl** (manipulation de feuilles de calcul).
*   **Base de Données** : **PostgreSQL (Neon Cloud)** en production et **SQLite** local.
*   **Génération PDF** : **FPDF2** (gestion des caractères spéciaux Unicode).
*   **Frontend** : HTML5, Vanilla CSS3 (variables CSS dynamiques, effets glassmorphism) et JavaScript (ES6+ asynchrone avec cache local et événements de synchronisation inter-onglets).

---

## 📦 Installation et Lancement Local

### 1. Cloner ou naviguer dans le dossier du projet
```bash
cd d:/Antigravity/suivi_evaluation
```

### 2. Créer et activer un environnement virtuel
Sur Windows (PowerShell) :
```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

### 3. Installer les dépendances
```bash
pip install -r requirements.txt
```

### 4. Lancement local (SQLite par défaut)
Supprimez l'ancienne base SQLite si vous souhaitez repartir à zéro. Le premier démarrage de Flask recréera les tables et ensemencera le projet démo AEPA de manière automatisée.
```bash
python app.py
```
Accédez à l'application locale sur :
👉 **[http://localhost:5000](http://localhost:5000)**

---

## 🐘 Configuration de Neon (PostgreSQL Cloud) & Migration

### 1. Créer un compte sur Neon
1. Allez sur [Neon Tech](https://neon.tech/) et créez un compte gratuit.
2. Créez un nouveau projet (ex: `suivi-evaluation`).
3. Dans votre tableau de bord, copiez la **Connection String** sous le format `postgres://...` ou `postgresql://...` (en cochant `Connection pooling` si nécessaire).

### 2. Exécuter le Script de Migration
Vous pouvez pousser vos données locales existantes (les questionnaires et sessions AEPA déjà saisis) vers votre base Neon en définissant la variable d'environnement `DATABASE_URL` et en lançant le script de migration :

Sur Windows (PowerShell) :
```powershell
$env:DATABASE_URL="votre_connection_string_neon"
python migrate_to_neon.py
```
Le script va :
1. Se connecter à votre instance Neon et y créer la structure des tables.
2. Créer un compte de démonstration par défaut : **`demo@example.com`** avec le mot de passe **`demo123`**.
3. Transférer l'ensemble de votre base SQLite vers PostgreSQL en conservant le statut de démo en lecture seule pour le projet AEPA.

---

## ☁️ Déploiement sur Vercel

1. Rendez-vous sur votre tableau de bord [Vercel](https://vercel.com).
2. Liez votre dépôt GitHub **stagiaireedh/S-et-E**.
3. Dans la configuration du projet, ajoutez les variables d'environnement suivantes :
   *   `DATABASE_URL` : (votre chaîne de connexion Neon PostgreSQL).
   *   `SECRET_KEY` : (une chaîne aléatoire pour sécuriser les cookies de session).
   *   `GEMINI_API_KEY`, `GROQ_API_KEY`, `GITHUB_TOKEN` (pour activer les vrais modèles d'IA en production).
4. Vercel lancera automatiquement la compilation via `vercel.json` et déploiera l'application.

---

## 📁 Structure du Projet

```text
d:/Antigravity/suivi_evaluation/
├── app.py                  # Initialisation Flask, LoginManager et déclaration des routes REST API
├── config.py               # Fichier de configuration (choix dynamique Postgres/SQLite, uploads)
├── models.py               # Définition des schémas SQLAlchemy (User, Project, SharedQuestionnaire...)
├── migrate_to_neon.py      # Script autonome de transfert de données SQLite -> Neon PostgreSQL
├── ai_service.py           # Algorithmes d'analyse lexicale, de triangulation et chat IA
├── pdf_service.py          # Moteur de génération de documents PDF (FPDF2)
├── requirements.txt        # Fichier des dépendances Python
├── README.md               # Le présent fichier d'aide
├── static/
│   ├── css/
│   │   └── style.css       # Styles graphiques des thèmes (sombre/clair), formulaires d'auth, badges
│   └── js/
│       └── app.js          # Logique d'authentification, bascule de thèmes, gestion des partages et exports
└── templates/
    └── index.html          # Template HTML principal (Application Shell avec formulaires d'authentification)
```
