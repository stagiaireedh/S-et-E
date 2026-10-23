"""
seed_professional_dataset.py — Génération d'un jeu de données de test professionnel
pour Changement Social Bénin (CSB) avec plus de 60 formulaires remplis et des fichiers PDF d'exemple.
"""

import os
import sys
import random
from datetime import datetime, timedelta

# Ajouter le chemin du projet
sys.path.insert(0, os.path.dirname(__file__))

from app import create_app
from models import db, User, Project, Questionnaire, Question, InterviewSession, Answer

app = create_app()

with app.app_context():
    print("Démarrage du peuplement professionnel...")
    
    # 1. Utilisateur principal
    user = User.query.filter_by(email="demo@example.com").first()
    if not user:
        user = User.query.first()
    if not user:
        import bcrypt
        p_hash = bcrypt.hashpw("demo123".encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        user = User(username="csb_evaluator", email="demo@example.com", password_hash=p_hash)
        db.session.add(user)
        db.session.commit()
    
    print(f"Utilisateur sélectionné : {user.username} (ID: {user.id})")

    # 2. Projet Changement Social Bénin
    project = Project.query.filter_by(name="Programme Eau & Redevabilité Communale — Changement Social Bénin").first()
    if not project:
        project = Project(
            name="Programme Eau & Redevabilité Communale — Changement Social Bénin",
            description="Évaluation participative à mi-parcours de la gouvernance locale de l'eau potable et de l'hygiène dans 12 communes cibles du Bénin (Borgou, Alibori, Zou, Atlantique).",
            user_id=user.id
        )
        db.session.add(project)
        db.session.commit()
    print(f"Projet actif : {project.name} (ID: {project.id})")

    # 3. Questionnaire officiel
    quest = Questionnaire.query.filter_by(project_id=project.id, title="Enquête de Satisfaction & Triangulation des Acteurs").first()
    if not quest:
        quest = Questionnaire(
            project_id=project.id,
            title="Enquête de Satisfaction & Triangulation des Acteurs",
            description="Grille d'entretien standardisée pour mesurer la qualité des services d'eau potable, la transparence des comités de gestion et la réactivité des autorités.",
            status="published"
        )
        db.session.add(quest)
        db.session.commit()

        questions_def = [
            {
                "order": 1,
                "text": "Quel est votre niveau d'accès effectif à l'eau potable au quotidien ?",
                "type": "select",
                "choices": "Très bon accès, Bon accès, Accès limité, Accès critique / Rupture récurrente"
            },
            {
                "order": 2,
                "text": "Comment jugez-vous la réactivité du comité de gestion en cas de panne ?",
                "type": "select",
                "choices": "Très rapide (< 24h), Rapide (1 à 3 jours), Lente (1 à 2 semaines), Inacceptable (> 2 semaines)"
            },
            {
                "order": 3,
                "text": "Les tarifs et cotisations appliqués sont-ils transparents et équitables ?",
                "type": "select",
                "choices": "Oui tout à fait, Oui modérément, Non peu transparents, Non contestés"
            },
            {
                "order": 4,
                "text": "Note globale sur la gouvernance et le dialogue avec la commune (sur 5)",
                "type": "select",
                "choices": "5/5 - Excellent, 4/5 - Bon, 3/5 - Moyen, 2/5 - Faible, 1/5 - Très insuffisant"
            },
            {
                "order": 5,
                "text": "Principales difficultés rencontrées et suggestions d'amélioration pour CSB",
                "type": "text",
                "choices": ""
            }
        ]

        for q_data in questions_def:
            q = Question(
                questionnaire_id=quest.id,
                text=q_data["text"],
                question_type=q_data["type"],
                choices=q_data["choices"],
                order_num=q_data["order"]
            )
            db.session.add(q)
        db.session.commit()
    print(f"Questionnaire : {quest.title} (ID: {quest.id}, {len(quest.questions)} questions)")

    # 4. Génération de 60 Sessions d'Entretiens réparties entre les 4 catégories d'acteurs
    existing_sessions = InterviewSession.query.filter_by(project_id=project.id, questionnaire_id=quest.id).count()
    if existing_sessions < 60:
        print(f"Génération de {60 - existing_sessions} sessions réalistes...")
        
        actors_distribution = [
            ("Bénéficiaire", 30),        # 50%
            ("Autorité Locale", 12),     # 20%
            ("Équipe Projet", 10),       # 17%
            ("Partenaire", 8)            # 13%
        ]

        beneficiary_groups = [
            "Association des femmes usagères de Calavi", "Comité de quartier Aitchedji",
            "Coopérative maraîchère de Zè", "Groupement des jeunes artisans d'Allada",
            "Ménages du village de Tangbo", "Usagers de la borne-fontaine centrale",
            "Collectif des éleveurs de Parakou", "Comité villageois d'Assanté",
            "Association pour la santé communautaire", "Représentants des usagers de Kandi"
        ]

        authorities = [
            "M. le Maire adjoint chargé de l'Eau", "Chef d'arrondissement de Godomey",
            "Responsable des Services Techniques Communaux", "Chef du village d'Avakpa",
            "Point Focal Eau & Assainissement Mairie", "Secrétaire Général de la Commune",
            "Conseiller communal de Bohicon", "Directrice de l'urbanisme local"
        ]

        project_team = [
            "Superviseur Terrain CSB Atlantique", "Animatrice Communautaire Zou",
            "Expert M&E CSB Cotonou", "Responsable Logistique & Approvisionnement",
            "Coordinateur de Zone Nord", "Chargé de Redevabilité Sociale"
        ]

        partners = [
            "Représentant Agence Territoriale de Développement", "Délégation Bailleur Enabel / Union Européenne",
            "ONG Partenaire Eau Pour Tous", "Société d'exploitation des forages",
            "Fédération Nationale des Usagers de l'Eau"
        ]

        verbatims_beneficiaries = [
            "Le débit est satisfaisant mais les coupures sont fréquentes en saison sèche.",
            "Les cotisations ont augmenté sans explication claire lors de l'assemblée générale.",
            "L'eau est claire et potable, nos enfants ont beaucoup moins de maladies diarrhéiques.",
            "Nous demandons l'extension du réseau vers les hameaux éloignés qui marchent plus de 2 km.",
            "Le fontainier est très disponible, mais les pièces de rechange manquent en cas de grosse panne."
        ]

        verbatims_authorities = [
            "La commune soutient pleinement l'initiative mais réclame plus de remontées d'indicateurs financiers.",
            "Les comités de gestion manquent parfois de formation sur la comptabilité simplifiée.",
            "Un protocole communal a été adopté pour sécuriser le périmètre de protection des forages.",
            "Très bon partenariat avec Changement Social Bénin, les délais d'exécution sont respectés."
        ]

        verbatims_project = [
            "Le taux de recouvrement des forfaits est en progression constante sur les 6 derniers mois.",
            "Difficulté ponctuelle sur la maintenance des pompes solaires due aux retards d'importation.",
            "La dynamique participative des femmes dans les bureaux exécutifs atteint désormais 45%."
        ]

        verbatims_partners = [
            "Projet très bien structuré avec un alignement parfait sur la stratégie nationale du Bénin.",
            "Nous encourageons CSB à poursuivre l'institutionnalisation des revues citoyennes.",
            "Indicateurs d'impact très encourageants pour le renouvellement du financement."
        ]

        interviewers = ["Koffi Mensah (CSB)", "Mireille Dossou (M&E)", "Sabi Bio (Enquêteur)", "Awa Traoré (Superviseur)"]

        questions_list = list(quest.questions)
        q1, q2, q3, q4, q5 = questions_list[0], questions_list[1], questions_list[2], questions_list[3], questions_list[4]

        now = datetime.now()
        for actor_category, count in actors_distribution:
            for i in range(count):
                dt = now - timedelta(days=random.randint(1, 90))
                session_type = "collectif" if actor_category == "Bénéficiaire" and random.random() > 0.4 else "individuel"

                if actor_category == "Bénéficiaire":
                    name = random.choice(beneficiary_groups)
                    # Les bénéficiaires ont des avis plus contrastés
                    ans1 = random.choice(["Très bon accès", "Bon accès", "Bon accès", "Accès limité", "Accès critique / Rupture récurrente"])
                    ans2 = random.choice(["Rapide (1 à 3 jours)", "Lente (1 à 2 semaines)", "Lente (1 à 2 semaines)", "Inacceptable (> 2 semaines)"])
                    ans3 = random.choice(["Oui modérément", "Non peu transparents", "Non contestés", "Oui tout à fait"])
                    ans4 = random.choice(["3/5 - Moyen", "4/5 - Bon", "2/5 - Faible", "3/5 - Moyen"])
                    ans5 = random.choice(verbatims_beneficiaries)
                elif actor_category == "Autorité Locale":
                    name = random.choice(authorities)
                    # Les autorités sont plus positives sur les délais et la gouvernance
                    ans1 = random.choice(["Très bon accès", "Bon accès", "Bon accès"])
                    ans2 = random.choice(["Très rapide (< 24h)", "Rapide (1 à 3 jours)", "Rapide (1 à 3 jours)"])
                    ans3 = random.choice(["Oui tout à fait", "Oui tout à fait", "Oui modérément"])
                    ans4 = random.choice(["5/5 - Excellent", "4/5 - Bon", "4/5 - Bon"])
                    ans5 = random.choice(verbatims_authorities)
                elif actor_category == "Équipe Projet":
                    name = random.choice(project_team)
                    ans1 = random.choice(["Bon accès", "Bon accès", "Très bon accès"])
                    ans2 = random.choice(["Rapide (1 à 3 jours)", "Très rapide (< 24h)"])
                    ans3 = random.choice(["Oui tout à fait", "Oui modérément"])
                    ans4 = random.choice(["4/5 - Bon", "4/5 - Bon", "5/5 - Excellent"])
                    ans5 = random.choice(verbatims_project)
                else: # Partenaire
                    name = random.choice(partners)
                    ans1 = random.choice(["Bon accès", "Très bon accès"])
                    ans2 = random.choice(["Rapide (1 à 3 jours)", "Très rapide (< 24h)"])
                    ans3 = random.choice(["Oui tout à fait", "Oui modérément"])
                    ans4 = random.choice(["4/5 - Bon", "5/5 - Excellent"])
                    ans5 = random.choice(verbatims_partners)

                sess = InterviewSession(
                    project_id=project.id,
                    questionnaire_id=quest.id,
                    title=f"Entretien {actor_category} - {name[:30]}",
                    interviewer=random.choice(interviewers),
                    interviewee_name_or_group=name,
                    actor_category=actor_category,
                    session_type=session_type,
                    interview_date=dt.date(),
                    user_id=user.id
                )
                db.session.add(sess)
                db.session.flush()

                # Ajout des réponses
                db.session.add(Answer(session_id=sess.id, question_id=q1.id, answer_text=ans1))
                db.session.add(Answer(session_id=sess.id, question_id=q2.id, answer_text=ans2))
                db.session.add(Answer(session_id=sess.id, question_id=q3.id, answer_text=ans3))
                db.session.add(Answer(session_id=sess.id, question_id=q4.id, answer_text=ans4))
                db.session.add(Answer(session_id=sess.id, question_id=q5.id, answer_text=ans5))

        project.cached_triangulation_signature = None
        db.session.commit()
        print("60 sessions générées avec succès !")

    # 5. Création de formulaires PDF d'exemple pour tester l'ingestion massive
    sample_dir = os.path.join(app.config['UPLOAD_FOLDER'], 'sample_pdfs_batch')
    os.makedirs(sample_dir, exist_ok=True)
    
    from fpdf import FPDF
    
    pdf_samples = [
        {
            "filename": "formulaire_terrain_01_femmes_calavi.pdf",
            "enqueteur": "Mireille Dossou (CSB)",
            "repondant": "Association des Femmes de Calavi",
            "categorie": "Bénéficiaire",
            "type": "collectif",
            "date": "2026-10-18",
            "rep1": "Bon accès",
            "rep2": "Lente (1 à 2 semaines)",
            "rep3": "Non peu transparents",
            "rep4": "3/5 - Moyen",
            "rep5": "Besoin de réparer la borne-fontaine n°3 avant la fête de la Nativité."
        },
        {
            "filename": "formulaire_terrain_02_maire_adjoint.pdf",
            "enqueteur": "Koffi Mensah (CSB)",
            "repondant": "M. Sossou (Adjoint au Maire)",
            "categorie": "Autorité Locale",
            "type": "individuel",
            "date": "2026-10-19",
            "rep1": "Très bon accès",
            "rep2": "Très rapide (< 24h)",
            "rep3": "Oui tout à fait",
            "rep4": "5/5 - Excellent",
            "rep5": "La mairie est très satisfaite du dialogue avec les équipes de CSB."
        },
        {
            "filename": "formulaire_terrain_03_cooperative_ze.pdf",
            "enqueteur": "Sabi Bio (Enquêteur)",
            "repondant": "Coopérative Maraîchère de Zè",
            "categorie": "Bénéficiaire",
            "type": "collectif",
            "date": "2026-10-20",
            "rep1": "Accès limité",
            "rep2": "Inacceptable (> 2 semaines)",
            "rep3": "Non contestés",
            "rep4": "2/5 - Faible",
            "rep5": "Le tarif de la bassine d'eau est trop élevé pour l'irrigation des légumes."
        }
    ]

    from pdf_service import EvaluatorPDF, clean_unicode

    for ps in pdf_samples:
        pdf_path = os.path.join(sample_dir, ps["filename"])
        pdf = EvaluatorPDF(title_text="Formulaire Terrain S&E-CSB", project_name=project.name)
        pdf.alias_nb_pages()
        pdf.add_page()
        pdf.set_font("helvetica", "B", 16)
        pdf.cell(0, 10, clean_unicode("FORMULAIRE D'ENQUETE DE TERRAIN - S&E-CSB"), 0, 1, "C")
        pdf.set_font("helvetica", "", 10)
        pdf.cell(0, 8, clean_unicode(f"Projet : {project.name}"), 0, 1, "C")
        pdf.ln(5)

        pdf.set_font("helvetica", "B", 11)
        pdf.cell(0, 7, clean_unicode("INFORMATIONS GENERALES DE L'ENTRETIEN :"), 0, 1, "L")
        pdf.set_font("helvetica", "", 10)
        pdf.cell(0, 6, clean_unicode(f"Enqueteur : {ps['enqueteur']}"), 0, 1, "L")
        pdf.cell(0, 6, clean_unicode(f"Repondant / Groupe : {ps['repondant']}"), 0, 1, "L")
        pdf.cell(0, 6, clean_unicode(f"Categorie d'Acteur : {ps['categorie']}"), 0, 1, "L")
        pdf.cell(0, 6, clean_unicode(f"Type de Session : {ps['type']}"), 0, 1, "L")
        pdf.cell(0, 6, clean_unicode(f"Date : {ps['date']}"), 0, 1, "L")
        pdf.ln(5)

        pdf.set_font("helvetica", "B", 11)
        pdf.cell(0, 7, clean_unicode("REPONSES DU FORMULAIRE :"), 0, 1, "L")
        pdf.set_font("helvetica", "", 10)
        pdf.multi_cell(0, 6, clean_unicode(f"1. Niveau d'acces effectif a l'eau potable : {ps['rep1']}"))
        pdf.multi_cell(0, 6, clean_unicode(f"2. Reactivite du comite de gestion en cas de panne : {ps['rep2']}"))
        pdf.multi_cell(0, 6, clean_unicode(f"3. Tarifs et cotisations transparents et equitables : {ps['rep3']}"))
        pdf.multi_cell(0, 6, clean_unicode(f"4. Note globale sur la gouvernance et le dialogue : {ps['rep4']}"))
        pdf.multi_cell(0, 6, clean_unicode(f"5. Difficultes et suggestions : {ps['rep5']}"))

        pdf.output(pdf_path)
        print(f"Fichier PDF de demonstration cree : {pdf_path}")

    print("Initialisation du jeu de donnees professionnel terminee avec succes !")
