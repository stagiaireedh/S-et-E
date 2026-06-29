import os
from datetime import date
from app import create_app
from models import db, Project, Questionnaire, Question, InterviewSession, Answer

def init_db():
    app = create_app()
    
    with app.app_context():
        # Supprimer la base de données existante pour repartir sur des bases saines
        db_path = os.path.join(app.config['BASE_DIR'], 'suivi_evaluation.db')
        if os.path.exists(db_path):
            os.remove(db_path)
            print("Ancienne base de données supprimée.")
            
        # Créer les tables
        db.create_all()
        print("Base de données et tables créées avec succès.")
        
        # 1. Création du Projet
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
        db.session.flush() # Récupérer l'ID du projet
        
        # 2. Création du Questionnaire
        questionnaire = Questionnaire(
            project_id=project.id,
            title="Évaluation Intermédiaire - Projet AEPA",
            description="Questionnaire destiné à évaluer l'accès, le fonctionnement, la gestion financière et la satisfaction après 12 mois de mise en œuvre."
        )
        db.session.add(questionnaire)
        db.session.flush()
        
        # 3. Création des Questions
        q1 = Question(
            questionnaire_id=questionnaire.id,
            text="Quelle est votre appréciation globale de la disponibilité et de la qualité de l'eau potable ?",
            question_type="select",
            choices="Excellent, Bon, Moyen, Mauvais",
            order_num=1
        )
        q2 = Question(
            questionnaire_id=questionnaire.id,
            text="Quels sont les principaux changements constatés dans votre vie quotidienne (santé, temps de trajet, économies) ?",
            question_type="text",
            order_num=2
        )
        q3 = Question(
            questionnaire_id=questionnaire.id,
            text="Avez-vous rencontré des difficultés techniques ou des pannes récurrentes avec les nouvelles installations ?",
            question_type="text",
            order_num=3
        )
        q4 = Question(
            questionnaire_id=questionnaire.id,
            text="Selon vous, le comité de gestion local gère-t-il les cotisations et les installations de manière transparente ?",
            question_type="select",
            choices="Oui tout à fait, Oui partiellement, Non pas du tout",
            order_num=4
        )
        q5 = Question(
            questionnaire_id=questionnaire.id,
            text="Quelles sont vos recommandations prioritaires pour garantir la durabilité du service d'eau ?",
            question_type="text",
            order_num=5
        )
        
        db.session.add_all([q1, q2, q3, q4, q5])
        db.session.flush()
        
        # 4. Création des sessions d'entretiens réalistes
        # Session 1: Focus Group de Femmes (Bénéficiaires) - Sentiment Global Mitigé/Préoccupé
        s1 = InterviewSession(
            project_id=project.id,
            questionnaire_id=questionnaire.id,
            title="Focus Group - Femmes du quartier Nord",
            interviewer="Sophie Diouf (Évaluatrice)",
            interviewee_name_or_group="Groupe de discussion (12 femmes)",
            actor_category="Bénéficiaire",
            session_type="collectif",
            interview_date=date(2026, 6, 10)
        )
        db.session.add(s1)
        db.session.flush()
        
        ans_s1 = [
            Answer(session_id=s1.id, question_id=q1.id, answer_text="Moyen"),
            Answer(session_id=s1.id, question_id=q2.id, answer_text="La qualité de l'eau est très bonne et les enfants ne tombent plus malades de la diarrhée. C'est un grand changement positif pour la santé de nos familles."),
            Answer(session_id=s1.id, question_id=q3.id, answer_text="Oui, nous rencontrons des pannes récurrentes de la pompe solaire ces derniers temps. Quand elle tombe en panne, le réparateur prend plus d'une semaine pour venir car il manque de pièces de rechange."),
            Answer(session_id=s1.id, question_id=q4.id, answer_text="Oui partiellement"),
            Answer(session_id=s1.id, question_id=q5.id, answer_text="Il faut absolument former un technicien local résidant dans le village et lui donner une caisse d'outils et de pièces de rechange de base pour réparer rapidement les pannes.")
        ]
        db.session.add_all(ans_s1)
        
        # Session 2: M. Amadou Diallo, Maraîcher (Bénéficiaire) - Sentiment Global Positif
        s2 = InterviewSession(
            project_id=project.id,
            questionnaire_id=questionnaire.id,
            title="Entretien individuel - M. Amadou Diallo (Maraîcher)",
            interviewer="Sophie Diouf (Évaluatrice)",
            interviewee_name_or_group="Amadou Diallo",
            actor_category="Bénéficiaire",
            session_type="individuel",
            interview_date=date(2026, 6, 12)
        )
        db.session.add(s2)
        db.session.flush()
        
        ans_s2 = [
            Answer(session_id=s2.id, question_id=q1.id, answer_text="Excellent"),
            Answer(session_id=s2.id, question_id=q2.id, answer_text="Grâce à la borne-fontaine installée près de mes parcelles, j'ai pu augmenter ma production de salades et de tomates. Mes revenus ont augmenté de 30%."),
            Answer(session_id=s2.id, question_id=q3.id, answer_text="Pas de panne majeure de mon côté, mais la pression de l'eau baisse beaucoup en fin d'après-midi quand tout le monde vient puiser en même temps."),
            Answer(session_id=s2.id, question_id=q4.id, answer_text="Oui tout à fait"),
            Answer(session_id=s2.id, question_id=q5.id, answer_text="Il faudrait ajouter un deuxième réservoir de stockage d'eau pour maintenir une pression stable durant les heures de pointe.")
        ]
        db.session.add_all(ans_s2)
        
        # Session 3: M. Jean-Marc, Partenaire Technique (Partenaire) - Sentiment Global Neutre/Technique
        s3 = InterviewSession(
            project_id=project.id,
            questionnaire_id=questionnaire.id,
            title="Entretien technique - ONG Hydro-Solidarité (Partenaire)",
            interviewer="Abdoulaye Sow (Superviseur M&E)",
            interviewee_name_or_group="Jean-Marc Dupuy (Coordonnateur)",
            actor_category="Partenaire",
            session_type="individuel",
            interview_date=date(2026, 6, 15)
        )
        db.session.add(s3)
        db.session.flush()
        
        ans_s3 = [
            Answer(session_id=s3.id, question_id=q1.id, answer_text="Bon"),
            Answer(session_id=s3.id, question_id=q2.id, answer_text="Le transfert de compétences pour le comité de gestion local a commencé. Ils savent désormais enregistrer les pannes sur une fiche technique."),
            Answer(session_id=s3.id, question_id=q3.id, answer_text="Les installations sont bien conçues. La seule faiblesse réside dans le retard de livraison de certaines pièces de pompes importées."),
            Answer(session_id=s3.id, question_id=q4.id, answer_text="Non pas du tout"),
            Answer(session_id=s3.id, question_id=q5.id, answer_text="Nous recommandons d'exiger des rapports de caisse financiers affichés publiquement chaque trimestre, car il y a des tensions au sein de la communauté concernant l'utilisation des cotisations.")
        ]
        db.session.add_all(ans_s3)
        
        # Session 4: Madame la Secrétaire Municipale (Autorité Locale) - Sentiment Global Favorable/Institutionnel
        s4 = InterviewSession(
            project_id=project.id,
            questionnaire_id=questionnaire.id,
            title="Entretien Municipalité - Mairie de Gandon (Autorité Locale)",
            interviewer="Abdoulaye Sow (Superviseur M&E)",
            interviewee_name_or_group="Mariama Fall (Secrétaire Municipale)",
            actor_category="Autorité Locale",
            session_type="individuel",
            interview_date=date(2026, 6, 18)
        )
        db.session.add(s4)
        db.session.flush()
        
        ans_s4 = [
            Answer(session_id=s4.id, question_id=q1.id, answer_text="Bon"),
            Answer(session_id=s4.id, question_id=q2.id, answer_text="Le taux de couverture en eau potable de notre commune est passé de 45% à 62%. C'est une grande réussite sociale et politique pour nous."),
            Answer(session_id=s4.id, question_id=q3.id, answer_text="La mairie a reçu des plaintes concernant l'éloignement d'une borne-fontaine dans le sous-secteur Est. Les gens doivent encore marcher 1 km."),
            Answer(session_id=s4.id, question_id=q4.id, answer_text="Oui partiellement"),
            Answer(session_id=s4.id, question_id=q5.id, answer_text="Il faut structurer un contrat formel de délégation de service public entre la Mairie et l'ASUFOR pour assurer un contrôle réglementaire externe de l'eau.")
        ]
        db.session.add_all(ans_s4)

        # Session 5: Chef de Projet AEPA (Équipe Projet) - Sentiment Global Réaliste/Technique
        s5 = InterviewSession(
            project_id=project.id,
            questionnaire_id=questionnaire.id,
            title="Bilan interne - Équipe de Projet AEPA",
            interviewer="Abdoulaye Sow (Superviseur M&E)",
            interviewee_name_or_group="Moussa Ndiaye (Chef de Projet)",
            actor_category="Équipe Projet",
            session_type="individuel",
            interview_date=date(2026, 6, 20)
        )
        db.session.add(s5)
        db.session.flush()
        
        ans_s5 = [
            Answer(session_id=s5.id, question_id=q1.id, answer_text="Bon"),
            Answer(session_id=s5.id, question_id=q2.id, answer_text="Les indicateurs physiques du projet sont au vert. Toutes les infrastructures prévues ont été livrées à temps."),
            Answer(session_id=s5.id, question_id=q3.id, answer_text="La maintenance pose problème : le recouvrement financier par cotisation forfaitaire mensuelle est très bas (moins de 40% de payeurs), ce qui empêchera d'acheter du matériel en cas de casse lourde."),
            Answer(session_id=s5.id, question_id=q4.id, answer_text="Oui partiellement"),
            Answer(session_id=s5.id, question_id=q5.id, answer_text="Nous préconisons d'introduire des compteurs volumétriques prépayés au niveau des bornes-fontaines pour remplacer les cotisations forfaitaires inefficaces.")
        ]
        db.session.add_all(ans_s5)

        # Session 6: Mme. Fatou Binetou, Habitante (Bénéficiaire) - Sentiment Global Très Positif
        s6 = InterviewSession(
            project_id=project.id,
            questionnaire_id=questionnaire.id,
            title="Entretien individuel - Mme. Fatou Binetou (Mère de famille)",
            interviewer="Sophie Diouf (Évaluatrice)",
            interviewee_name_or_group="Fatou Binetou Sarr",
            actor_category="Bénéficiaire",
            session_type="individuel",
            interview_date=date(2026, 6, 22)
        )
        db.session.add(s6)
        db.session.flush()
        
        ans_s6 = [
            Answer(session_id=s6.id, question_id=q1.id, answer_text="Excellent"),
            Answer(session_id=s6.id, question_id=q2.id, answer_text="C'est un grand soulagement. La borne-fontaine est située à seulement 50 mètres de ma maison. Mes filles ne ratent plus l'école pour aller chercher de l'eau."),
            Answer(session_id=s6.id, question_id=q3.id, answer_text="Le système fonctionne très bien, aucun souci technique constaté jusqu'ici."),
            Answer(session_id=s6.id, question_id=q4.id, answer_text="Oui tout à fait"),
            Answer(session_id=s6.id, question_id=q5.id, answer_text="Nous devrions tous cotiser de manière plus régulière pour aider le comité à garder la pompe en bon état.")
        ]
        db.session.add_all(ans_s6)
        
        db.session.commit()
        print("Données de démonstration réalistes insérées avec succès (Projet AEPA, 6 sessions d'entretiens).")

if __name__ == "__main__":
    init_db()
