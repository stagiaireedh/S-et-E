"""
statistical_export_service.py — Générateur d'exports statistiques avancés pour S&E-CSB.

Génère :
1. Un classeur Excel professionnel multi-feuilles avec formatage soigné (Openpyxl / Pandas).
2. Un rapport PDF analytique haute définition pour les bailleurs de fonds (FPDF2).
"""

import io
import os
from datetime import datetime
import openpyxl
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
from openpyxl.utils import get_column_letter

from fpdf import FPDF
from stats_service import get_full_project_statistics, STAT_COLORS
from pdf_service import EvaluatorPDF, clean_unicode


def export_advanced_statistics_to_excel(project_id, questionnaire_id=None):
    """
    Génère un classeur Excel complet multi-onglets contenant :
    - Feuille 1 : Vue d'ensemble & KPIs
    - Feuille 2 : Tris à Plat (Fréquences & Pourcentages)
    - Feuille 3 : Tris Croisés par Catégorie d'Acteurs
    - Feuille 4 : Orientations Stratégiques IA
    - Feuille 5 : Données Brutes Normalisées
    """
    stats_data = get_full_project_statistics(project_id, questionnaire_id)
    if not stats_data:
        return None

    wb = openpyxl.Workbook()
    # Supprimer la feuille par défaut
    wb.remove(wb.active)

    # Styles réutilisables
    font_title = Font(name="Calibri", size=16, bold=True, color="1E1B4B")
    font_section = Font(name="Calibri", size=13, bold=True, color="312E81")
    font_header = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
    font_bold = Font(name="Calibri", size=11, bold=True)
    font_normal = Font(name="Calibri", size=11)
    font_muted = Font(name="Calibri", size=9, italic=True, color="64748B")

    fill_indigo = PatternFill(start_color="4338CA", end_color="4338CA", fill_type="solid")
    fill_purple = PatternFill(start_color="6D28D9", end_color="6D28D9", fill_type="solid")
    fill_teal = PatternFill(start_color="0F766E", end_color="0F766E", fill_type="solid")
    fill_amber = PatternFill(start_color="B45309", end_color="B45309", fill_type="solid")
    fill_subtle_gray = PatternFill(start_color="F8FAFC", end_color="F8FAFC", fill_type="solid")
    fill_zebra = PatternFill(start_color="F1F5F9", end_color="F1F5F9", fill_type="solid")

    thin_border_side = Side(border_style="thin", color="CBD5E1")
    border_all = Border(left=thin_border_side, right=thin_border_side, top=thin_border_side, bottom=thin_border_side)

    # ==========================================
    # ONGLET 1 : SYNTHÈSE & RÉPARTITION
    # ==========================================
    ws_kpi = wb.create_sheet(title="Vue d'Ensemble")
    ws_kpi.views.sheetView[0].showGridLines = True

    ws_kpi["A1"] = f"RAPPORT STATISTIQUE GLOBAL — {stats_data['project_name'].upper()}"
    ws_kpi["A1"].font = font_title
    ws_kpi["A2"] = f"Généré le {datetime.now().strftime('%d/%m/%Y à %H:%M')} | Système S&E Changement Social Bénin"
    ws_kpi["A2"].font = font_muted

    # Bloc KPI
    kpi_headers = ["Indicateur Clé", "Valeur"]
    for col_idx, h in enumerate(kpi_headers, 1):
        cell = ws_kpi.cell(row=4, column=col_idx, value=h)
        cell.font = font_header
        cell.fill = fill_indigo
        cell.alignment = Alignment(horizontal="center", vertical="center")

    kpis = [
        ("Total Formulaires / Entretiens Analysés", stats_data['total_sessions']),
        ("Nombre de Questionnaires Associés", stats_data['total_questionnaires']),
        ("Questions Analysées", len(stats_data['questions_stats'])),
        ("Indice Global de Consensus", f"{stats_data['global_consensus_index']}%"),
    ]

    for idx, (lbl, val) in enumerate(kpis, 5):
        c1 = ws_kpi.cell(row=idx, column=1, value=lbl)
        c2 = ws_kpi.cell(row=idx, column=2, value=val)
        c1.font = font_normal
        c2.font = font_bold
        c2.alignment = Alignment(horizontal="center")
        c1.border = border_all
        c2.border = border_all
        if idx % 2 == 0:
            c1.fill = fill_subtle_gray
            c2.fill = fill_subtle_gray

    # Répartition des acteurs
    start_row_actors = len(kpis) + 7
    ws_kpi.cell(row=start_row_actors - 1, column=1, value="Répartition des Enquêtés par Catégorie d'Acteur").font = font_section
    
    actor_headers = ["Catégorie d'Acteur", "Effectif (N)", "Pourcentage (%)"]
    for col_idx, h in enumerate(actor_headers, 1):
        cell = ws_kpi.cell(row=start_row_actors, column=col_idx, value=h)
        cell.font = font_header
        cell.fill = fill_purple
        cell.alignment = Alignment(horizontal="center")

    curr_r = start_row_actors + 1
    for act in stats_data['actors_distribution']:
        c1 = ws_kpi.cell(row=curr_r, column=1, value=act['label'])
        c2 = ws_kpi.cell(row=curr_r, column=2, value=act['count'])
        c3 = ws_kpi.cell(row=curr_r, column=3, value=f"{act['percentage']}%")
        for c in [c1, c2, c3]:
            c.font = font_normal
            c.border = border_all
        c2.alignment = Alignment(horizontal="right")
        c3.alignment = Alignment(horizontal="right")
        curr_r += 1

    # Total Acteurs
    c_tot1 = ws_kpi.cell(row=curr_r, column=1, value="TOTAL")
    c_tot2 = ws_kpi.cell(row=curr_r, column=2, value=stats_data['total_sessions'])
    c_tot3 = ws_kpi.cell(row=curr_r, column=3, value="100.0%")
    for c in [c_tot1, c_tot2, c_tot3]:
        c.font = font_bold
        c.border = border_all
        c.fill = fill_subtle_gray

    # ==========================================
    # ONGLET 2 : TRIS À PLAT (PAR QUESTION)
    # ==========================================
    ws_plat = wb.create_sheet(title="Tris à Plat (Questions)")
    ws_plat.views.sheetView[0].showGridLines = True

    ws_plat["A1"] = "RÉSULTATS DES TRIS À PLAT PAR QUESTION"
    ws_plat["A1"].font = font_title

    r_idx = 3
    for idx_q, qs in enumerate(stats_data['questions_stats'], 1):
        ws_plat.cell(row=r_idx, column=1, value=f"Question {idx_q} : {qs['question_text']}").font = font_section
        r_idx += 1
        ws_plat.cell(row=r_idx, column=1, value=f"Total répondants : {qs['total_answers']}").font = font_muted
        r_idx += 1

        headers = ["Modalité de Réponse", "Effectif (N)", "Fréquence (%)"]
        for c_i, h in enumerate(headers, 1):
            cell = ws_plat.cell(row=r_idx, column=c_i, value=h)
            cell.font = font_header
            cell.fill = fill_indigo
            cell.alignment = Alignment(horizontal="center")
        r_idx += 1

        for item in qs['tri_a_plat']:
            c1 = ws_plat.cell(row=r_idx, column=1, value=item['label'])
            c2 = ws_plat.cell(row=r_idx, column=2, value=item['count'])
            c3 = ws_plat.cell(row=r_idx, column=3, value=f"{item['percentage']}%")
            for c in [c1, c2, c3]:
                c.font = font_normal
                c.border = border_all
            c2.alignment = Alignment(horizontal="right")
            c3.alignment = Alignment(horizontal="right")
            r_idx += 1

        if qs.get('numeric_stats'):
            ns = qs['numeric_stats']
            c_num = ws_plat.cell(row=r_idx, column=1, value=f"Statistiques numériques : Moyenne = {ns['mean']} | Médiane = {ns['median']} | Écart-type = {ns['std_dev']} (Min: {ns['min']}, Max: {ns['max']})")
            c_num.font = font_muted
            r_idx += 1

        r_idx += 2  # Espace entre questions

    # ==========================================
    # ONGLET 3 : TRIS CROISÉS (PAR CATÉGORIE)
    # ==========================================
    ws_crois = wb.create_sheet(title="Tris Croisés (Acteurs)")
    ws_crois.views.sheetView[0].showGridLines = True

    ws_crois["A1"] = "MATRICES DE TRIS CROISÉS (RÉPONSES x CATÉGORIES D'ACTEURS)"
    ws_crois["A1"].font = font_title

    r_c_idx = 3
    for idx_q, qs in enumerate(stats_data['questions_stats'], 1):
        ct = qs['cross_tabulation']
        actors = ct['actors']
        if not actors:
            continue

        ws_crois.cell(row=r_c_idx, column=1, value=f"Question {idx_q} : {qs['question_text']}").font = font_section
        r_c_idx += 1

        # En-têtes : Modalité, puis pour chaque acteur [N, %]
        headers_crois = ["Modalité de Réponse"]
        for act in actors:
            headers_crois.extend([f"{act} (N)", f"{act} (%)"])

        for c_i, h in enumerate(headers_crois, 1):
            cell = ws_crois.cell(row=r_c_idx, column=c_i, value=h)
            cell.font = font_header
            cell.fill = fill_teal
            cell.alignment = Alignment(horizontal="center")
        r_c_idx += 1

        for row_data in ct['matrix']:
            c1 = ws_crois.cell(row=r_c_idx, column=1, value=row_data['modality'])
            c1.font = font_normal
            c1.border = border_all
            c_offset = 2
            for act in actors:
                cnt = row_data['counts'].get(act, 0)
                pct = row_data['percentages'].get(act, 0.0)
                cell_cnt = ws_crois.cell(row=r_c_idx, column=c_offset, value=cnt)
                cell_pct = ws_crois.cell(row=r_c_idx, column=c_offset + 1, value=f"{pct}%")
                for c in [cell_cnt, cell_pct]:
                    c.font = font_normal
                    c.border = border_all
                    c.alignment = Alignment(horizontal="right")
                c_offset += 2
            r_c_idx += 1

        # Divergences
        if qs.get('divergences'):
            for div in qs['divergences']:
                c_div = ws_crois.cell(row=r_c_idx, column=1, value=f"⚠️ {div}")
                c_div.font = Font(name="Calibri", size=10, italic=True, color="B91C1C")
                r_c_idx += 1

        r_c_idx += 2

    # ==========================================
    # ONGLET 4 : ORIENTATIONS STRATÉGIQUES IA
    # ==========================================
    ws_ori = wb.create_sheet(title="Orientations Stratégiques")
    ws_ori.views.sheetView[0].showGridLines = True

    ws_ori["A1"] = "ORIENTATIONS STRATÉGIQUES & PLAN D'ACTION (IA M&E)"
    ws_ori["A1"].font = font_title

    headers_ori = ["Priorité", "Titre de l'Orientation", "Constat Chiffré", "Action Recommandée", "Indicateur de Suivi"]
    for c_i, h in enumerate(headers_ori, 1):
        cell = ws_ori.cell(row=3, column=c_i, value=h)
        cell.font = font_header
        cell.fill = fill_amber
        cell.alignment = Alignment(horizontal="center")

    r_ori = 4
    for ori in stats_data.get('orientations', []):
        c1 = ws_ori.cell(row=r_ori, column=1, value=ori.get('priorite', 'Moyenne'))
        c2 = ws_ori.cell(row=r_ori, column=2, value=ori.get('titre', ''))
        c3 = ws_ori.cell(row=r_ori, column=3, value=ori.get('constat_chiffre', ''))
        c4 = ws_ori.cell(row=r_ori, column=4, value=ori.get('action_recommandee', ''))
        c5 = ws_ori.cell(row=r_ori, column=5, value=ori.get('indicateur_suivi', ''))
        for c in [c1, c2, c3, c4, c5]:
            c.font = font_normal
            c.border = border_all
            c.alignment = Alignment(vertical="top", wrap_text=True)
        c1.alignment = Alignment(horizontal="center", vertical="top")
        r_ori += 1

    # Auto-ajustement des largeurs de colonnes sur toutes les feuilles
    for ws in wb.worksheets:
        for col in ws.columns:
            max_len = max(len(str(cell.value or '')) for cell in col)
            col_letter = get_column_letter(col[0].column)
            ws.column_dimensions[col_letter].width = min(max(max_len + 3, 12), 55)

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    return output


def generate_advanced_statistics_pdf(project_id, filepath, questionnaire_id=None):
    """
    Génère un rapport PDF haute résolution avec graphiques de répartition en barres vectorielles,
    tableaux statistiques complets et orientations stratégiques formulées.
    """
    stats_data = get_full_project_statistics(project_id, questionnaire_id)
    if not stats_data:
        return False

    pdf = EvaluatorPDF(title_text="Rapport Statistique Analytique", project_name=stats_data['project_name'])
    pdf.alias_nb_pages()
    pdf.add_page()

    # Titre de la page
    pdf.set_font('helvetica', 'B', 18)
    pdf.set_text_color(30, 27, 75)
    pdf.cell(0, 12, "RAPPORT D'ANALYSE STATISTIQUE & ORIENTATIONS", 0, 1, 'C')
    
    pdf.set_font('helvetica', '', 10)
    pdf.set_text_color(100, 116, 139)
    pdf.cell(0, 6, f"Projet : {stats_data['project_name']} | Échantillon : N = {stats_data['total_sessions']} répondants", 0, 1, 'C')
    pdf.cell(0, 6, f"Date de génération : {datetime.now().strftime('%d/%m/%Y à %H:%M')} — Changement Social Bénin", 0, 1, 'C')
    pdf.ln(6)

    # 1. TABLEAU DE BORD EXÉCUTIF
    pdf.chapter_title("1. Tableau de Bord Exécutif & Répartition")
    pdf.set_font('helvetica', '', 9.5)
    pdf.set_text_color(33, 33, 33)

    # Grille de KPIs (4 boîtes)
    kpi_w = 43
    pdf.set_fill_color(243, 244, 246)
    pdf.set_draw_color(209, 213, 219)
    
    # Ligne 1
    pdf.set_font('helvetica', 'B', 12)
    pdf.cell(kpi_w, 8, f"  {stats_data['total_sessions']}", 1, 0, 'C', fill=True)
    pdf.cell(5, 8, "", 0, 0)
    pdf.cell(kpi_w, 8, f"  {stats_data['total_questionnaires']}", 1, 0, 'C', fill=True)
    pdf.cell(5, 8, "", 0, 0)
    pdf.cell(kpi_w, 8, f"  {len(stats_data['questions_stats'])}", 1, 0, 'C', fill=True)
    pdf.cell(5, 8, "", 0, 0)
    pdf.cell(kpi_w, 8, f"  {stats_data['global_consensus_index']}%", 1, 1, 'C', fill=True)

    pdf.set_font('helvetica', '', 8)
    pdf.set_text_color(107, 114, 128)
    pdf.cell(kpi_w, 5, "Entretiens Réalisés", 0, 0, 'C')
    pdf.cell(5, 5, "", 0, 0)
    pdf.cell(kpi_w, 5, "Questionnaires", 0, 0, 'C')
    pdf.cell(5, 5, "", 0, 0)
    pdf.cell(kpi_w, 5, "Questions Analysées", 0, 0, 'C')
    pdf.cell(5, 5, "", 0, 0)
    pdf.cell(kpi_w, 5, "Indice Consensus", 0, 1, 'C')
    pdf.ln(6)

    # Tableau Répartition des Acteurs avec barres horizontales visuelles
    pdf.set_font('helvetica', 'B', 10)
    pdf.set_text_color(67, 56, 202)
    pdf.cell(0, 6, "Répartition de l'échantillon par catégorie d'acteur :", 0, 1, 'L')
    pdf.ln(2)

    for act in stats_data['actors_distribution']:
        pdf.set_font('helvetica', '', 9)
        pdf.set_text_color(33, 33, 33)
        pdf.cell(55, 6, f"{act['label']} :", 0, 0, 'L')
        pdf.cell(20, 6, f"{act['count']} ({act['percentage']}%)", 0, 0, 'R')
        pdf.cell(5, 6, "", 0, 0)
        
        # Barre graphique vectorielle
        bar_max_w = 95
        bar_w = max(2, (act['percentage'] / 100.0) * bar_max_w)
        pdf.set_fill_color(79, 70, 229)  # Indigo
        pdf.rect(pdf.get_x(), pdf.get_y() + 1.5, bar_w, 3.5, 'F')
        pdf.ln(6)
    pdf.ln(6)

    # 2. RÉSULTATS DÉTAILLÉS PAR QUESTION (TRIS À PLAT)
    pdf.chapter_title("2. Analyse Détaillée des Questions (Tris à Plat)")
    
    for idx_q, qs in enumerate(stats_data['questions_stats'], 1):
        # Vérifier si besoin de nouvelle page
        if pdf.get_y() > 230:
            pdf.add_page()

        pdf.set_font('helvetica', 'B', 10.5)
        pdf.set_text_color(30, 27, 75)
        pdf.multi_cell(0, 5, f"Q{idx_q}. {qs['question_text']}")
        pdf.set_font('helvetica', 'I', 8)
        pdf.set_text_color(107, 114, 128)
        pdf.cell(0, 4, f"Effectif total : N = {qs['total_answers']} répondants", 0, 1, 'L')
        pdf.ln(2)

        # Tableau des réponses
        pdf.set_font('helvetica', 'B', 8.5)
        pdf.set_fill_color(224, 231, 255)
        pdf.set_text_color(30, 27, 75)
        pdf.cell(85, 5, "  Modalité", 1, 0, 'L', fill=True)
        pdf.cell(25, 5, "Effectif (N)", 1, 0, 'C', fill=True)
        pdf.cell(25, 5, "Part (%)", 1, 0, 'C', fill=True)
        pdf.cell(45, 5, "Distribution Visuelle", 1, 1, 'L', fill=True)

        pdf.set_font('helvetica', '', 8.5)
        pdf.set_text_color(33, 33, 33)
        for item in qs['tri_a_plat']:
            pdf.cell(85, 5, f"  {item['label'][:45]}", 1, 0, 'L')
            pdf.cell(25, 5, f"{item['count']}", 1, 0, 'C')
            pdf.cell(25, 5, f"{item['percentage']}%", 1, 0, 'C')
            
            # Mini-barre dans la cellule
            x_pos = pdf.get_x()
            y_pos = pdf.get_y()
            pdf.cell(45, 5, "", 1, 1, 'L')
            b_w = max(1, (item['percentage'] / 100.0) * 40)
            pdf.set_fill_color(16, 185, 129) # Émeraude
            pdf.rect(x_pos + 2, y_pos + 1.2, b_w, 2.6, 'F')

        # Divergences signalées
        if qs.get('divergences'):
            pdf.set_font('helvetica', 'I', 8)
            pdf.set_text_color(185, 28, 28)
            for d in qs['divergences']:
                pdf.multi_cell(0, 4, f"  [!] {d}")
        pdf.ln(4)

    # 3. ORIENTATIONS STRATÉGIQUES & PLAN D'ACTION (NOUVELLE PAGE)
    pdf.add_page()
    pdf.chapter_title("3. Orientations Stratégiques & Plan d'Action (M&E / Bailleurs)")
    pdf.set_font('helvetica', '', 9.5)
    pdf.set_text_color(50, 50, 50)
    pdf.multi_cell(0, 5, "Sur la base de la triangulation des données quantitatives et qualitatives collectées, "
                          "le système formule les recommandations stratégiques prioritaires suivantes pour Changement Social Bénin et ses partenaires techniques et financiers :")
    pdf.ln(4)

    for ori in stats_data.get('orientations', []):
        prio = ori.get('priorite', 'Moyenne')
        badge_type = 'risk' if prio == 'Haute' else ('rec' if prio == 'Moyenne' else 'info')
        title_box = f"[{prio.upper()}] {ori.get('titre', 'Orientation')}"
        body_box = (
            f"Constat statistique : {ori.get('constat_chiffre', '')}\n"
            f"Action recommandée : {ori.get('action_recommandee', '')}\n"
            f"Indicateur de suivi : {ori.get('indicateur_suivi', '')}"
        )
        pdf.add_card(title_box, body_box, type_card=badge_type)

    # Sauvegarde sur le disque
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    pdf.output(filepath)
    return True
