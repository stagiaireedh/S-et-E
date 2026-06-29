import os
from fpdf import FPDF
from datetime import datetime
from ai_service import run_project_triangulation

class EvaluatorPDF(FPDF):
    """Classe FPDF personnalisée pour générer des rapports professionnels."""
    
    def __init__(self, title_text="Rapport d'Évaluation", project_name="Projet"):
        super().__init__()
        self.title_text = title_text
        self.project_name = project_name
        self.set_margins(15, 20, 15)
        self.set_auto_page_break(auto=True, margin=20)
        
    def header(self):
        # Dessiner une barre d'accentuation en haut
        self.set_fill_color(63, 81, 181) # Indigo #3F51B5
        self.rect(0, 0, 210, 8, 'F')
        
        # En-tête du document
        self.set_font('helvetica', 'B', 10)
        self.set_text_color(120, 120, 120)
        self.cell(0, 10, f"SYSTÈME DE SUIVI-ÉVALUATION & TRIANGULATION — {self.project_name.upper()}", 0, 1, 'L')
        self.set_draw_color(200, 200, 200)
        self.line(15, 18, 195, 18)
        self.ln(5)

    def footer(self):
        self.set_y(-15)
        self.set_font('helvetica', 'I', 8)
        self.set_text_color(150, 150, 150)
        # Date du jour
        today = datetime.now().strftime("%d/%m/%Y")
        self.cell(90, 10, f"Généré le {today} | Rapport confidentiel", 0, 0, 'L')
        # Numéro de page
        self.cell(0, 10, f"Page {self.page_no()}/{{nb}}", 0, 0, 'R')

    def chapter_title(self, label):
        self.set_font('helvetica', 'B', 14)
        self.set_fill_color(240, 243, 248) # Bleu-gris clair
        self.set_text_color(63, 81, 181) # Indigo
        self.cell(0, 10, f"  {label}", 0, 1, 'L', fill=True)
        self.ln(4)

    def add_card(self, title, text, type_card="info"):
        """Ajoute une boîte d'avertissement ou de recommandation colorée."""
        if type_card == "risk":
            bg_color = (254, 242, 242)     # Rouge clair
            border_color = (239, 68, 68)   # Rouge
            text_color = (153, 27, 27)     # Rouge foncé
        elif type_card == "rec":
            bg_color = (240, 253, 250)     # Vert turquoise clair
            border_color = (20, 184, 166)  # Turquoise
            text_color = (17, 94, 89)      # Turquoise foncé
        else: # info
            bg_color = (240, 246, 255)     # Bleu clair
            border_color = (59, 130, 246)  # Bleu
            text_color = (30, 58, 138)     # Bleu foncé
            
        self.set_fill_color(*bg_color)
        self.set_draw_color(*border_color)
        self.set_text_color(*text_color)
        self.set_line_width(0.5)
        
        # Hauteur dynamique estimée pour la carte
        self.set_font('helvetica', 'B', 10)
        # Titre
        self.cell(0, 7, f"  {title}", 'TLR', 1, 'L', fill=True)
        self.set_font('helvetica', '', 9.5)
        # Corps de la boîte
        self.multi_cell(0, 5, f"  {text}", 'BLR', 'L', fill=True)
        self.ln(4)
        # Réinitialisation
        self.set_text_color(0, 0, 0)
        self.set_line_width(0.2)

def generate_global_evaluation_pdf(project, filepath):
    """
    Génère un rapport d'évaluation complet pour un projet avec statistiques, 
    sentiments par acteur, thèmes, risques et recommandations.
    """
    # Analyse IA
    analysis = run_project_triangulation(project.id)
    
    # Création du document PDF
    pdf = EvaluatorPDF(title_text="Rapport d'Évaluation de Projet", project_name=project.name)
    pdf.alias_nb_pages()
    pdf.add_page()
    
    # Titre Principal
    pdf.set_font('helvetica', 'B', 20)
    pdf.set_text_color(33, 33, 33)
    pdf.cell(0, 15, "RAPPORT D'ÉVALUATION & TRIANGULATION", 0, 1, 'C')
    
    pdf.set_font('helvetica', '', 11)
    pdf.cell(0, 6, f"Projet : {project.name}", 0, 1, 'C')
    pdf.cell(0, 6, f"Date de génération : {datetime.now().strftime('%d/%m/%Y à %H:%M')}", 0, 1, 'C')
    pdf.ln(10)
    
    # 1. Description du Projet
    pdf.chapter_title("1. Contexte du Projet")
    pdf.set_font('helvetica', '', 10)
    desc = project.description or "Aucune description fournie pour ce projet."
    pdf.multi_cell(0, 6, desc)
    pdf.ln(6)
    
    if not analysis or not analysis.get('success'):
        pdf.chapter_title("2. Statut des Données")
        pdf.set_font('helvetica', 'I', 10)
        pdf.cell(0, 10, "Aucune donnée d'entretien n'est enregistrée pour le moment.", 0, 1, 'C')
        pdf.output(filepath)
        return
        
    # 2. Synthèse Analytique (IA)
    pdf.chapter_title("2. Synthèse Quantitative & Qualitative (IA)")
    
    sentiment_score = analysis['avg_sentiment_score']
    sentiment_label = analysis['sentiment_label'].upper()
    
    pdf.set_font('helvetica', '', 10)
    pdf.cell(90, 8, f"Nombre total d'entretiens collectés :", 0, 0)
    pdf.set_font('helvetica', 'B', 10)
    pdf.cell(0, 8, f"{len(project.sessions)} entretiens", 0, 1)
    
    pdf.set_font('helvetica', '', 10)
    pdf.cell(90, 8, f"Score de sentiment global moyen :", 0, 0)
    pdf.set_font('helvetica', 'B', 10)
    pdf.cell(0, 8, f"{sentiment_score} / 1.0  ({sentiment_label})", 0, 1)
    pdf.ln(4)
    
    # Tableau de sentiments par catégorie d'acteur
    pdf.set_font('helvetica', 'B', 9.5)
    pdf.set_fill_color(63, 81, 181)
    pdf.set_text_color(255, 255, 255)
    pdf.cell(60, 8, "  Catégorie d'Acteur", 1, 0, 'L', fill=True)
    pdf.cell(40, 8, "Nb Entretiens", 1, 0, 'C', fill=True)
    pdf.cell(40, 8, "Sentiment Moyen", 1, 0, 'C', fill=True)
    pdf.cell(40, 8, "Perception", 1, 1, 'C', fill=True)
    
    pdf.set_text_color(0, 0, 0)
    pdf.set_font('helvetica', '', 9.5)
    fill_row = False
    for actor, stats in analysis['actor_summary'].items():
        pdf.set_fill_color(248, 249, 250) if fill_row else pdf.set_fill_color(255, 255, 255)
        pdf.cell(60, 8, f"  {actor}", 1, 0, 'L', fill=True)
        pdf.cell(40, 8, str(stats['count']), 1, 0, 'C', fill=True)
        pdf.cell(40, 8, f"{stats['avg_score']}", 1, 0, 'C', fill=True)
        pdf.cell(40, 8, stats['label'], 1, 1, 'C', fill=True)
        fill_row = not fill_row
    pdf.ln(8)
    
    # 3. Thèmes Prédominants
    pdf.chapter_title("3. Thèmes Récurrents Identifiés")
    pdf.set_font('helvetica', '', 10)
    pdf.cell(0, 6, "Les thèmes ci-dessous ont été automatiquement extraits par récurrence sémantique dans les entretiens :", 0, 1)
    pdf.ln(3)
    
    for th in analysis['themes']:
        # Barre horizontale représentant le poids
        weight = th['weight']
        pdf.set_font('helvetica', 'B', 9.5)
        pdf.cell(60, 6, f"  • {th['theme']}", 0, 0)
        pdf.set_font('helvetica', '', 9.5)
        pdf.cell(30, 6, f"(Fréquence : {weight})", 0, 0)
        
        # Dessiner une petite jauge thématique
        pdf.set_fill_color(200, 200, 200)
        pdf.rect(110, pdf.get_y() + 1.5, 60, 3, 'F')
        
        # Poids relatif (plafonné à 60px)
        width_jauge = min(int(weight * 3), 60)
        pdf.set_fill_color(59, 130, 246)
        pdf.rect(110, pdf.get_y() + 1.5, width_jauge, 3, 'F')
        
        pdf.cell(0, 6, "", 0, 1)
    pdf.ln(8)
    
    # Nouvelle page pour la triangulation des risques et les recommandations
    pdf.add_page()
    
    # 4. Risques et points de vigilance
    pdf.chapter_title("4. Risques Majeurs Détectés (Triangulation)")
    pdf.set_font('helvetica', '', 10)
    pdf.cell(0, 6, "Ces alertes ont été générées par triangulation des feedbacks négatifs ou critiques :", 0, 1)
    pdf.ln(3)
    
    for r in analysis['risks']:
        desc_card = f"{r['description']}\n(Signalé par : {r['source']})"
        pdf.add_card(r['title'], desc_card, type_card="risk")
    pdf.ln(4)
    
    # 5. Recommandations
    pdf.chapter_title("5. Recommandations de Suivi-Évaluation")
    pdf.set_font('helvetica', '', 10)
    pdf.cell(0, 6, "Actions stratégiques recommandées pour améliorer les indicateurs du projet :", 0, 1)
    pdf.ln(3)
    
    for rec in analysis['recommendations']:
        desc_rec = f"{rec['description']} (Niveau d'Urgence : {rec['priority']})"
        pdf.add_card(rec['title'], desc_rec, type_card="rec")
        
    pdf.output(filepath)

def generate_session_summary_pdf(session, filepath):
    """
    Génère une fiche de compte rendu détaillée pour un entretien spécifique.
    """
    pdf = EvaluatorPDF(title_text="Fiche d'Entretien", project_name=session.project.name)
    pdf.alias_nb_pages()
    pdf.add_page()
    
    # Titre Principal
    pdf.set_font('helvetica', 'B', 18)
    pdf.set_text_color(33, 33, 33)
    pdf.cell(0, 12, f"COMPTE RENDU D'ENTRETIEN", 0, 1, 'C')
    pdf.set_font('helvetica', 'I', 11)
    pdf.cell(0, 6, f"{session.title}", 0, 1, 'C')
    pdf.ln(8)
    
    # Fiche d'identification
    pdf.chapter_title("1. Informations Générales")
    
    pdf.set_font('helvetica', 'B', 10)
    
    fields = [
        ("Projet :", session.project.name),
        ("Date de l'entretien :", session.interview_date.strftime("%d/%m/%Y")),
        ("Type d'entretien :", session.session_type.capitalize()),
        ("Catégorie d'acteurs :", session.actor_category),
        ("Interlocuteur(s) :", session.interviewee_name_or_group),
        ("Enquêteur / Évaluateur :", session.interviewer)
    ]
    
    for label, val in fields:
        pdf.set_font('helvetica', 'B', 9.5)
        pdf.cell(50, 7, f"  {label}", 0, 0)
        pdf.set_font('helvetica', '', 9.5)
        pdf.cell(0, 7, val, 0, 1)
    pdf.ln(6)
    
    # Réponses détaillées
    pdf.chapter_title("2. Réponses et Déclarations Recueillies")
    
    for answer in session.answers:
        # Question
        pdf.set_font('helvetica', 'B', 9.5)
        pdf.set_text_color(63, 81, 181)
        pdf.multi_cell(0, 5, f"Q : {answer.question.text}")
        
        # Réponse
        pdf.set_font('helvetica', '', 9.5)
        pdf.set_text_color(30, 30, 30)
        pdf.multi_cell(0, 5, f"R : \"{answer.answer_text}\"")
        pdf.ln(4)
        
    pdf.output(filepath)
