"""
statistical_export_service.py — Générateur d'exports statistiques avancés pour S&E-CSB.

Génère :
1. Un classeur Excel institutionnel 7 feuilles modélisé sur la rigueur d'audit statistique (Openpyxl / Pandas).
2. Un rapport PDF analytique haute définition respectant les 8 piliers méthodologiques (FPDF2).
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
    Génère un classeur Excel complet multi-onglets structuré selon les 8 piliers méthodologiques :
    - Feuille 1 : Contexte & Métadonnées (Source, période, population, dictionnaire des variables)
    - Feuille 2 : Audit Qualité & Nettoyage (Complétude, doublons, dimensions, taux de manquants)
    - Feuille 3 : Statistiques Descriptives (Tris à plat, pourcentages, moyenne, médiane, quartiles, IQR, écart-type)
    - Feuille 4 : Tris Croisés & Contingence (Matrices d'acteurs, % lignes, % colonnes, divergences)
    - Feuille 5 : Note Exploratoire & Hypothèses (Questions clés exploitables, anomalies, limites)
    - Feuille 6 : Plan d'Action & Solutions (Matrice des solutions, priorités, acteurs, calendrier, indicateurs)
    - Feuille 7 : Données Brutes Normalisées
    """
    stats_data = get_full_project_statistics(project_id, questionnaire_id)
    if not stats_data:
        return None

    context = stats_data.get('context', {})
    audit = stats_data.get('data_audit', {})
    hypotheses = stats_data.get('hypotheses', [])
    note = stats_data.get('exploratory_note', {})
    solutions = stats_data.get('solutions', [])
    q_stats = stats_data.get('questions_stats', [])

    wb = openpyxl.Workbook()
    wb.remove(wb.active)  # Supprimer la feuille par défaut

    # Typographie & Styles
    font_main_title = Font(name="Calibri", size=15, bold=True, color="1E1B4B")
    font_subtitle = Font(name="Calibri", size=10, italic=True, color="64748B")
    font_section = Font(name="Calibri", size=12, bold=True, color="312E81")
    font_table_hdr = Font(name="Calibri", size=10.5, bold=True, color="FFFFFF")
    font_bold = Font(name="Calibri", size=10.5, bold=True)
    font_normal = Font(name="Calibri", size=10.5)
    font_small = Font(name="Calibri", size=9.5)
    font_italic_red = Font(name="Calibri", size=9.5, italic=True, color="B91C1C")
    font_italic_muted = Font(name="Calibri", size=9.5, italic=True, color="64748B")

    fill_navy = PatternFill(start_color="1E1B4B", end_color="1E1B4B", fill_type="solid")
    fill_indigo = PatternFill(start_color="4338CA", end_color="4338CA", fill_type="solid")
    fill_purple = PatternFill(start_color="6D28D9", end_color="6D28D9", fill_type="solid")
    fill_teal = PatternFill(start_color="0F766E", end_color="0F766E", fill_type="solid")
    fill_amber = PatternFill(start_color="B45309", end_color="B45309", fill_type="solid")
    fill_subtle_gray = PatternFill(start_color="F8FAFC", end_color="F8FAFC", fill_type="solid")
    fill_highlight = PatternFill(start_color="EEF2FF", end_color="EEF2FF", fill_type="solid")

    thin_border = Border(
        left=Side(style="thin", color="CBD5E1"),
        right=Side(style="thin", color="CBD5E1"),
        top=Side(style="thin", color="CBD5E1"),
        bottom=Side(style="thin", color="CBD5E1")
    )

    # =========================================================================
    # FEUILLE 1 : CONTEXTE DES DONNÉES & DICTIONNAIRE DES VARIABLES
    # =========================================================================
    ws_ctx = wb.create_sheet(title="1. Contexte & Métadonnées")
    ws_ctx.views.sheetView[0].showGridLines = True

    ws_ctx["A1"] = f"CADRE MÉTHODOLOGIQUE & CONTEXTE DES DONNÉES — {stats_data['project_name'].upper()}"
    ws_ctx["A1"].font = font_main_title
    ws_ctx["A2"] = f"Généré le {datetime.now().strftime('%d/%m/%Y à %H:%M')} | Système Intégré S&E Changement Social Bénin"
    ws_ctx["A2"].font = font_subtitle

    ctx_items = [
        ("Source des données", context.get('source', 'Plateforme S&E-CSB')),
        ("Projet concerné", f"{context.get('project_name', '')} (ID: {context.get('project_id', '')})"),
        ("Période de collecte couverte", f"Du {context.get('period_start', 'N/A')} au {context.get('period_end', 'N/A')}"),
        ("Unité d'observation", context.get('observation_unit', 'Session individuelle ou collective')),
        ("Volume de l'échantillon analysé", f"N = {context.get('total_records', 0)} formulaires/entretiens"),
        ("Population cible & profils concernés", context.get('population_target', 'Acteurs multiples')),
        ("Nombre de variables d'évaluation", f"{context.get('variables_count', 0)} variables"),
    ]

    ws_ctx.cell(row=4, column=1, value="Paramètre Contextuel").font = font_table_hdr
    ws_ctx.cell(row=4, column=1).fill = fill_navy
    ws_ctx.cell(row=4, column=2, value="Description / Valeur").font = font_table_hdr
    ws_ctx.cell(row=4, column=2).fill = fill_navy

    for r_idx, (k, v) in enumerate(ctx_items, 5):
        c1 = ws_ctx.cell(row=r_idx, column=1, value=k)
        c2 = ws_ctx.cell(row=r_idx, column=2, value=v)
        c1.font = font_bold
        c2.font = font_normal
        c1.border = thin_border
        c2.border = thin_border
        if r_idx % 2 == 0:
            c1.fill = fill_subtle_gray
            c2.fill = fill_subtle_gray

    # Dictionnaire des Variables
    start_r_dict = len(ctx_items) + 7
    ws_ctx.cell(row=start_r_dict - 1, column=1, value="Dictionnaire des Variables & Typologie Statistique").font = font_section

    dict_headers = ["Code Variable", "Libellé de la Question", "Type dans l'App", "Nature Statistique", "Échelle / Modalités", "Obligatoire"]
    for c_i, h in enumerate(dict_headers, 1):
        c = ws_ctx.cell(row=start_r_dict, column=c_i, value=h)
        c.font = font_table_hdr
        c.fill = fill_indigo
        c.alignment = Alignment(horizontal="center", vertical="center")

    curr_r = start_r_dict + 1
    for var in context.get('variables_dictionary', []):
        c1 = ws_ctx.cell(row=curr_r, column=1, value=var['code'])
        c2 = ws_ctx.cell(row=curr_r, column=2, value=var['question_text'])
        c3 = ws_ctx.cell(row=curr_r, column=3, value=var['question_type'])
        c4 = ws_ctx.cell(row=curr_r, column=4, value=var['statistical_type'])
        c5 = ws_ctx.cell(row=curr_r, column=5, value=str(var['choices'])[:60])
        c6 = ws_ctx.cell(row=curr_r, column=6, value="Oui" if var['required'] else "Non")
        for cell in [c1, c2, c3, c4, c5, c6]:
            cell.font = font_normal
            cell.border = thin_border
        c1.alignment = Alignment(horizontal="center")
        c6.alignment = Alignment(horizontal="center")
        curr_r += 1

    # =========================================================================
    # FEUILLE 2 : AUDIT QUALITÉ, INSPECTION & NETTOYAGE
    # =========================================================================
    ws_aud = wb.create_sheet(title="2. Audit & Nettoyage")
    ws_aud.views.sheetView[0].showGridLines = True

    ws_aud["A1"] = "INSPECTION QUALITÉ, AUDIT D'INTÉGRITÉ & NETTOYAGE DES DONNÉES"
    ws_aud["A1"].font = font_main_title
    ws_aud["A2"] = "Contrôle des dimensions de la matrice, des taux de complétude, des doublons et des valeurs manquantes"
    ws_aud["A2"].font = font_subtitle

    audit_metrics = [
        ("Nombre de lignes (Observations / Entretiens N)", audit.get('rows_count', 0)),
        ("Nombre de colonnes (Variables / Questions P)", audit.get('columns_count', 0)),
        ("Volume total de cellules de données (N x P)", audit.get('total_cells', 0)),
        ("Cellules renseignées valides", audit.get('filled_cells', 0)),
        ("Taux global de complétude des données", f"{audit.get('completeness_rate', 0)}%"),
        ("Taux global de données manquantes (Attrition)", f"{audit.get('missing_rate', 0)}%"),
        ("Doublons potentiels détectés", audit.get('duplicate_sessions_detected', 0)),
        ("Score global de santé des données", f"{audit.get('quality_score', 0)} / 100"),
        ("Diagnostic d'intégrité", audit.get('data_health_status', 'Non évalué')),
    ]

    ws_aud.cell(row=4, column=1, value="Indicateur d'Audit & Qualité").font = font_table_hdr
    ws_aud.cell(row=4, column=1).fill = fill_teal
    ws_aud.cell(row=4, column=2, value="Mesure Constatée").font = font_table_hdr
    ws_aud.cell(row=4, column=2).fill = fill_teal

    for idx, (lbl, val) in enumerate(audit_metrics, 5):
        c1 = ws_aud.cell(row=idx, column=1, value=lbl)
        c2 = ws_aud.cell(row=idx, column=2, value=val)
        c1.font = font_bold
        c2.font = font_normal
        c1.border = thin_border
        c2.border = thin_border
        c2.alignment = Alignment(horizontal="center")
        if idx % 2 == 0:
            c1.fill = fill_subtle_gray
            c2.fill = fill_subtle_gray

    # Détail des données manquantes par question
    start_r_miss = len(audit_metrics) + 7
    ws_aud.cell(row=start_r_miss - 1, column=1, value="Taux de Non-Réponse par Variable (Attrition Spécifique)").font = font_section

    miss_hdrs = ["Code Variable", "Intitulé de la Variable", "Nombre de Manquants", "Taux de Manquants (%)"]
    for c_i, h in enumerate(miss_hdrs, 1):
        c = ws_aud.cell(row=start_r_miss, column=c_i, value=h)
        c.font = font_table_hdr
        c.fill = fill_teal
        c.alignment = Alignment(horizontal="center")

    curr_r_m = start_r_miss + 1
    for code, m_info in audit.get('missing_by_question', {}).items():
        c1 = ws_aud.cell(row=curr_r_m, column=1, value=code)
        c2 = ws_aud.cell(row=curr_r_m, column=2, value=m_info['question_text'])
        c3 = ws_aud.cell(row=curr_r_m, column=3, value=m_info['missing_count'])
        c4 = ws_aud.cell(row=curr_r_m, column=4, value=f"{m_info['missing_pct']}%")
        for cell in [c1, c2, c3, c4]:
            cell.font = font_normal
            cell.border = thin_border
        c1.alignment = Alignment(horizontal="center")
        c3.alignment = Alignment(horizontal="right")
        c4.alignment = Alignment(horizontal="right")
        curr_r_m += 1

    # =========================================================================
    # FEUILLE 3 : STATISTIQUES DESCRIPTIVES UNIVARIÉES
    # =========================================================================
    ws_desc = wb.create_sheet(title="3. Stats Descriptives")
    ws_desc.views.sheetView[0].showGridLines = True

    ws_desc["A1"] = "STATISTIQUES DESCRIPTIVES UNIVARIÉES (TRIS À PLAT & PARAMÈTRES NUMÉRIQUES)"
    ws_desc["A1"].font = font_main_title
    ws_desc["A2"] = "Distributions, pourcentages, mode, indice de diversité et indicateurs de dispersion"
    ws_desc["A2"].font = font_subtitle

    curr_row = 4
    for idx_q, qs in enumerate(q_stats, 1):
        ws_desc.cell(row=curr_row, column=1, value=f"Q{idx_q}. {qs['question_text']} (Type: {qs['question_type']})").font = font_section
        curr_row += 1

        # Tableau des fréquences
        hdrs_f = ["Modalité / Catégorie", "Effectif (n_i)", "Fréquence (%)"]
        for c_i, h in enumerate(hdrs_f, 1):
            c = ws_desc.cell(row=curr_row, column=c_i, value=h)
            c.font = font_table_hdr
            c.fill = fill_indigo
            c.alignment = Alignment(horizontal="center")
        curr_row += 1

        for item in qs['tri_a_plat']:
            c1 = ws_desc.cell(row=curr_row, column=1, value=item['label'])
            c2 = ws_desc.cell(row=curr_row, column=2, value=item['count'])
            c3 = ws_desc.cell(row=curr_row, column=3, value=f"{item['percentage']}%")
            for c in [c1, c2, c3]:
                c.font = font_normal
                c.border = thin_border
            c2.alignment = Alignment(horizontal="right")
            c3.alignment = Alignment(horizontal="right")
            curr_row += 1

        # Métriques catégorielles avancées
        cat_m = qs.get('categorical_metrics', {})
        if cat_m:
            ws_desc.cell(row=curr_row, column=1, value=f"Mode : « {cat_m.get('mode')} » ({cat_m.get('mode_freq_percent')}% des réponses) | Indice de Diversité d'Entropie : {cat_m.get('diversity_index')}").font = font_italic_muted
            curr_row += 1

        # Paramètres numériques si applicables
        num_s = qs.get('numeric_stats')
        if num_s:
            ws_desc.cell(row=curr_row, column=1, value="Paramètres Statistiques Numériques :").font = font_bold
            curr_row += 1
            num_hdrs = ["Moyenne", "Médiane", "Quartile Q1", "Quartile Q3", "Écart IQR", "Écart-type", "Min", "Max", "Étendue", "Coeff. Variation", "Outliers"]
            for c_i, h in enumerate(num_hdrs, 1):
                c = ws_desc.cell(row=curr_row, column=c_i, value=h)
                c.font = font_bold
                c.fill = fill_highlight
                c.alignment = Alignment(horizontal="center")
                c.border = thin_border
            curr_row += 1
            num_vals = [
                num_s['mean'], num_s['median'], num_s['q1'], num_s['q3'], num_s['iqr'],
                num_s['std_dev'], num_s['min'], num_s['max'], num_s['range'], f"{num_s['cv_percent']}%",
                f"{num_s['outliers_count']} détecté(s)"
            ]
            for c_i, val in enumerate(num_vals, 1):
                c = ws_desc.cell(row=curr_row, column=c_i, value=val)
                c.font = font_normal
                c.alignment = Alignment(horizontal="center")
                c.border = thin_border
            curr_row += 1

        curr_row += 2

    # =========================================================================
    # FEUILLE 4 : TRIS CROISÉS & CONTINGENCE (STATISTIQUES BIVARIÉES)
    # =========================================================================
    ws_crois = wb.create_sheet(title="4. Tris Croisés & Contingence")
    ws_crois.views.sheetView[0].showGridLines = True

    ws_crois["A1"] = "EXPLORATION DES RELATIONS BIVARIÉES : QUESTIONS x CATÉGORIES D'ACTEURS"
    ws_crois["A1"].font = font_main_title
    ws_crois["A2"] = "Tableaux de contingence, pourcentages en ligne (% au sein de la catégorie) et analyse des fractures d'opinion"
    ws_crois["A2"].font = font_subtitle

    # Avertissement méthodologique formel
    ws_crois["A3"] = "RAPPEL MÉTHODOLOGIQUE : Une relation ou corrélation statistique observée n'implique pas automatiquement une causalité directe."
    ws_crois["A3"].font = font_italic_red

    r_c = 5
    for idx_q, qs in enumerate(q_stats, 1):
        ct = qs.get('cross_tabulation')
        if not ct or not ct.get('actors'):
            continue

        ws_crois.cell(row=r_c, column=1, value=f"Q{idx_q}. {qs['question_text']}").font = font_section
        r_c += 1

        # Tableau des effectifs et % en ligne
        actors = ct['actors']
        headers = ["Modalité de Réponse"] + [f"{act} (Effectif)" for act in actors] + [f"{act} (% Ligne)" for act in actors]
        for c_i, h in enumerate(headers, 1):
            cell = ws_crois.cell(row=r_c, column=c_i, value=h)
            cell.font = font_table_hdr
            cell.fill = fill_purple
            cell.alignment = Alignment(horizontal="center")
        r_c += 1

        for cat in ct.get('categories', []):
            c_lbl = ws_crois.cell(row=r_c, column=1, value=cat)
            c_lbl.font = font_normal
            c_lbl.border = thin_border

            # Effectifs
            for a_idx, act in enumerate(actors, 2):
                cnt = ct['matrix'].get(cat, {}).get(act, 0)
                c_cnt = ws_crois.cell(row=r_c, column=a_idx, value=cnt)
                c_cnt.font = font_normal
                c_cnt.border = thin_border
                c_cnt.alignment = Alignment(horizontal="right")

            # % en ligne
            col_offset = 2 + len(actors)
            for a_idx, act in enumerate(actors):
                row_pct = ct['row_percentages'].get(cat, {}).get(act, 0)
                c_pct = ws_crois.cell(row=r_c, column=col_offset + a_idx, value=f"{row_pct}%")
                c_pct.font = font_normal
                c_pct.border = thin_border
                c_pct.alignment = Alignment(horizontal="right")
                if row_pct >= 50.0:
                    c_pct.fill = fill_highlight
            r_c += 1

        # Divergences détectées
        if qs.get('divergences'):
            for div in qs['divergences']:
                c_div = ws_crois.cell(row=r_c, column=1, value=f"⚠️ {div}")
                c_div.font = font_italic_red
                r_c += 1

        r_c += 2

    # =========================================================================
    # FEUILLE 5 : NOTE EXPLORATOIRE & HYPOTHÈSES STATISTIQUES
    # =========================================================================
    ws_hyp = wb.create_sheet(title="5. Note Exploratoire")
    ws_hyp.views.sheetView[0].showGridLines = True

    ws_hyp["A1"] = "NOTE EXPLORATOIRE D'ANALYSE & FORMULATION D'HYPOTHÈSES"
    ws_hyp["A1"].font = font_main_title
    ws_hyp["A2"] = "Constats majeurs, anomalies identifiées, hypothèses explicatives et limites méthodologiques"
    ws_hyp["A2"].font = font_subtitle

    # Section 1 : Constats Majeurs
    ws_hyp.cell(row=4, column=1, value="1. Principaux Constats & Régularités Statistiques").font = font_section
    r_h = 5
    for finding in note.get('main_findings', []):
        ws_hyp.cell(row=r_h, column=1, value=f"• {finding}").font = font_normal
        r_h += 1
    r_h += 1

    # Section 2 : Hypothèses statistiques
    ws_hyp.cell(row=r_h, column=1, value="2. Hypothèses Statistiques Exploitables").font = font_section
    r_h += 1
    hyp_hdrs = ["Axe / Thème", "Question Exploratoire Exploitée", "Hypothèse Explicative Probable", "Vérification / Approfondissement Recommandé"]
    for c_i, h in enumerate(hyp_hdrs, 1):
        c = ws_hyp.cell(row=r_h, column=c_i, value=h)
        c.font = font_table_hdr
        c.fill = fill_amber
        c.alignment = Alignment(horizontal="center")
    r_h += 1

    for hyp in hypotheses:
        c1 = ws_hyp.cell(row=r_h, column=1, value=hyp.get('theme', ''))
        c2 = ws_hyp.cell(row=r_h, column=2, value=hyp.get('question_exploratoire', ''))
        c3 = ws_hyp.cell(row=r_h, column=3, value=hyp.get('hypothese_explicative', ''))
        c4 = ws_hyp.cell(row=r_h, column=4, value=hyp.get('verification_recommandee', ''))
        for cell in [c1, c2, c3, c4]:
            cell.font = font_normal
            cell.border = thin_border
            cell.alignment = Alignment(vertical="top", wrap_text=True)
        r_h += 1
    r_h += 1

    # Section 3 : Limites des données
    ws_hyp.cell(row=r_h, column=1, value="3. Limites Méthodologiques & Précautions d'Interprétation").font = font_section
    r_h += 1
    for lim in note.get('limits', []):
        ws_hyp.cell(row=r_h, column=1, value=f"• {lim}").font = font_normal
        r_h += 1

    # =========================================================================
    # FEUILLE 6 : PLAN D'ACTION & PROPOSITIONS DE SOLUTIONS
    # =========================================================================
    ws_sol = wb.create_sheet(title="6. Solutions & Plan d'Action")
    ws_sol.views.sheetView[0].showGridLines = True

    ws_sol["A1"] = "PROPOSITIONS DE SOLUTIONS & PLAN D'ACTION OPÉRATIONNEL (M&E / BAILLEURS)"
    ws_sol["A1"].font = font_main_title
    ws_sol["A2"] = "Matrice décisionnelle formalisée pour Changement Social Bénin et les partenaires techniques et financiers"
    ws_sol["A2"].font = font_subtitle

    sol_hdrs = ["Identifiant", "Axe d'Intervention", "Problème Statistique Identifié", "Solution / Action Recommandée", "Priorité", "Acteurs Responsables", "Calendrier", "Indicateur d'Impact"]
    for c_i, h in enumerate(sol_hdrs, 1):
        c = ws_sol.cell(row=4, column=c_i, value=h)
        c.font = font_table_hdr
        c.fill = fill_navy
        c.alignment = Alignment(horizontal="center")

    r_s = 5
    for sol in solutions:
        c1 = ws_sol.cell(row=r_s, column=1, value=sol.get('id', ''))
        c2 = ws_sol.cell(row=r_s, column=2, value=sol.get('axe', ''))
        c3 = ws_sol.cell(row=r_s, column=3, value=sol.get('probleme_identifie', ''))
        c4 = ws_sol.cell(row=r_s, column=4, value=sol.get('solution_preconisee', ''))
        c5 = ws_sol.cell(row=r_s, column=5, value=sol.get('priorite', ''))
        c6 = ws_sol.cell(row=r_s, column=6, value=sol.get('acteurs_responsables', ''))
        c7 = ws_sol.cell(row=r_s, column=7, value=sol.get('calendrier', ''))
        c8 = ws_sol.cell(row=r_s, column=8, value=sol.get('indicateur_impact', ''))
        for cell in [c1, c2, c3, c4, c5, c6, c7, c8]:
            cell.font = font_normal
            cell.border = thin_border
            cell.alignment = Alignment(vertical="top", wrap_text=True)
        c1.alignment = Alignment(horizontal="center", vertical="top")
        c5.alignment = Alignment(horizontal="center", vertical="top")
        r_s += 1

    # Ajustement automatique des largeurs de colonnes sur toutes les feuilles
    for ws in wb.worksheets:
        for col in ws.columns:
            max_len = max(len(str(cell.value or '')) for cell in col)
            col_letter = get_column_letter(col[0].column)
            ws.column_dimensions[col_letter].width = min(max(max_len + 3, 12), 60)

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    return output


def generate_advanced_statistics_pdf(project_id, filepath, questionnaire_id=None):
    """
    Génère un rapport d'analyse statistique institutionnel et décisionnel de haute facture (PDF),
    structuré rigoureusement selon les 8 étapes méthodologiques :
    1. Couverture et Contexte Général
    2. Audit Qualité, Inspection & Nettoyage des Données
    3. Statistiques Descriptives Univariées (Graphiques vectoriels, tableaux, dispersion)
    4. Exploration des Relations Bivariées & Tris Croisés (Mise en garde corrélation/causalité)
    5. Note Exploratoire & Hypothèses Analytiques Exploitables
    6. Propositions de Solutions & Plan d'Action Opérationnel M&E
    """
    stats_data = get_full_project_statistics(project_id, questionnaire_id)
    if not stats_data:
        return False

    context = stats_data.get('context', {})
    audit = stats_data.get('data_audit', {})
    hypotheses = stats_data.get('hypotheses', [])
    note = stats_data.get('exploratory_note', {})
    solutions = stats_data.get('solutions', [])
    q_stats = stats_data.get('questions_stats', [])

    pdf = EvaluatorPDF(title_text="Rapport Statistique & Audit Décisionnel", project_name=stats_data['project_name'])
    pdf.alias_nb_pages()
    pdf.add_page()

    # Titre institutionnel
    pdf.set_font('helvetica', 'B', 17)
    pdf.set_text_color(30, 27, 75)
    pdf.cell(0, 11, "RAPPORT D'ANALYSE STATISTIQUE & ORIENTATIONS STRATÉGIQUES", 0, 1, 'C')
    
    pdf.set_font('helvetica', '', 9.5)
    pdf.set_text_color(100, 116, 139)
    pdf.cell(0, 5, f"Projet : {stats_data['project_name']} | Échantillon consolidé : N = {stats_data['total_sessions']} répondants", 0, 1, 'C')
    pdf.cell(0, 5, f"Généré le {datetime.now().strftime('%d/%m/%Y à %H:%M')} — Changement Social Bénin (CSB)", 0, 1, 'C')
    pdf.ln(5)

    # =========================================================================
    # CHAPITRE 1 : CONTEXTE DES DONNÉES & POPULATION ÉTUDIÉE
    # =========================================================================
    pdf.chapter_title("1. Contexte des Données & Cadre Méthodologique")
    pdf.set_font('helvetica', '', 9)
    pdf.set_text_color(40, 40, 40)
    pdf.multi_cell(0, 4.5, (
        f"Le présent rapport synthétise l'audit statistique et l'évaluation quantitative conduits par Changement Social Bénin. "
        f"L'unité d'observation correspond aux {context.get('observation_unit', 'entretiens de terrain')}, recueillis sur la période "
        f"allant du {context.get('period_start', 'N/A')} au {context.get('period_end', 'N/A')}. "
        f"L'analyse porte sur un échantillon total de N = {context.get('total_records', 0)} formulaires structurés autour de "
        f"{context.get('variables_count', 0)} variables d'évaluation clés."
    ))
    pdf.ln(3)

    # Tableau Répartition des Acteurs avec barres horizontales vectorielles
    pdf.set_font('helvetica', 'B', 9.5)
    pdf.set_text_color(67, 56, 202)
    pdf.cell(0, 5.5, "Ventilation de la population d'enquête par profil d'acteur :", 0, 1, 'L')
    pdf.ln(1.5)

    for act in stats_data['actors_distribution']:
        pdf.set_font('helvetica', '', 8.5)
        pdf.set_text_color(33, 33, 33)
        pdf.cell(50, 5.5, f"{act['label']} :", 0, 0, 'L')
        pdf.cell(22, 5.5, f"{act['count']} ({act['percentage']}%)", 0, 0, 'R')
        pdf.cell(4, 5.5, "", 0, 0)
        
        # Barre vectorielle proportionnelle
        bar_max_w = 100
        bar_w = max(2, (act['percentage'] / 100.0) * bar_max_w)
        pdf.set_fill_color(79, 70, 229)
        pdf.rect(pdf.get_x(), pdf.get_y() + 1.2, bar_w, 3.2, 'F')
        pdf.ln(5.5)
    pdf.ln(4)

    # =========================================================================
    # CHAPITRE 2 : INSPECTION, AUDIT QUALITÉ & NETTOYAGE DES DONNÉES
    # =========================================================================
    pdf.chapter_title("2. Audit Qualité, Inspection & Nettoyage des Données")
    pdf.set_font('helvetica', '', 9)
    pdf.set_text_color(40, 40, 40)
    pdf.multi_cell(0, 4.5, (
        f"Avant tout traitement décisionnel, une phase d'audit d'intégrité a été réalisée sur la matrice brute de "
        f"{audit.get('rows_count', 0)} lignes x {audit.get('columns_count', 0)} colonnes ({audit.get('total_cells', 0)} cellules). "
        f"Le taux de complétude global s'établit à {audit.get('completeness_rate', 0)}% (taux d'attrition de {audit.get('missing_rate', 0)}%). "
        f"Le contrôle de redondance signale {audit.get('duplicate_sessions_detected', 0)} doublon(s) potentiel(s). "
        f"Le score de santé globale des données s'élève à {audit.get('quality_score', 0)} / 100 ({audit.get('data_health_status', 'Validé')})."
    ))
    pdf.ln(3)

    # Boîtes de synthèse de l'audit
    kpi_w = 44
    pdf.set_fill_color(243, 244, 246)
    pdf.set_font('helvetica', 'B', 10.5)
    pdf.cell(kpi_w, 7, f" {audit.get('completeness_rate', 0)}%", 1, 0, 'C', fill=True)
    pdf.cell(4, 7, "", 0, 0)
    pdf.cell(kpi_w, 7, f" {audit.get('missing_rate', 0)}%", 1, 0, 'C', fill=True)
    pdf.cell(4, 7, "", 0, 0)
    pdf.cell(kpi_w, 7, f" {audit.get('duplicate_sessions_detected', 0)}", 1, 0, 'C', fill=True)
    pdf.cell(4, 7, "", 0, 0)
    pdf.cell(kpi_w, 7, f" {audit.get('quality_score', 0)}/100", 1, 1, 'C', fill=True)

    pdf.set_font('helvetica', '', 7.5)
    pdf.set_text_color(107, 114, 128)
    pdf.cell(kpi_w, 4, "Taux de Complétude", 0, 0, 'C')
    pdf.cell(4, 4, "", 0, 0)
    pdf.cell(kpi_w, 4, "Taux de Manquants", 0, 0, 'C')
    pdf.cell(4, 4, "", 0, 0)
    pdf.cell(kpi_w, 4, "Doublons Détectés", 0, 0, 'C')
    pdf.cell(4, 4, "", 0, 0)
    pdf.cell(kpi_w, 4, "Score Santé Données", 0, 1, 'C')
    pdf.ln(6)

    # =========================================================================
    # CHAPITRE 3 : STATISTIQUES DESCRIPTIVES UNIVARIÉES (TRIS À PLAT)
    # =========================================================================
    pdf.chapter_title("3. Statistiques Descriptives Univariées (Tris à Plat)")

    for idx_q, qs in enumerate(q_stats, 1):
        if pdf.get_y() > 225:
            pdf.add_page()

        pdf.set_font('helvetica', 'B', 10)
        pdf.set_text_color(30, 27, 75)
        pdf.multi_cell(0, 4.5, f"Q{idx_q}. {qs['question_text']}")
        
        pdf.set_font('helvetica', 'I', 8)
        pdf.set_text_color(107, 114, 128)
        cat_m = qs.get('categorical_metrics', {})
        cat_info = f"Mode : « {cat_m.get('mode')} » ({cat_m.get('mode_freq_percent')}%) | Diversité : {cat_m.get('diversity_index')}" if cat_m else ""
        pdf.cell(0, 4, f"Effectif total : N = {qs['total_answers']} | {cat_info}", 0, 1, 'L')
        pdf.ln(1.5)

        # Tableau des fréquences
        pdf.set_font('helvetica', 'B', 8)
        pdf.set_fill_color(224, 231, 255)
        pdf.set_text_color(30, 27, 75)
        pdf.cell(85, 4.8, "  Modalité / Option de Réponse", 1, 0, 'L', fill=True)
        pdf.cell(24, 4.8, "Effectif (N)", 1, 0, 'C', fill=True)
        pdf.cell(24, 4.8, "Part (%)", 1, 0, 'C', fill=True)
        pdf.cell(47, 4.8, "Répartition Graphique", 1, 1, 'L', fill=True)

        pdf.set_font('helvetica', '', 8)
        pdf.set_text_color(33, 33, 33)
        for item in qs['tri_a_plat']:
            pdf.cell(85, 4.8, f"  {item['label'][:45]}", 1, 0, 'L')
            pdf.cell(24, 4.8, f"{item['count']}", 1, 0, 'C')
            pdf.cell(24, 4.8, f"{item['percentage']}%", 1, 0, 'C')
            
            x_pos = pdf.get_x()
            y_pos = pdf.get_y()
            pdf.cell(47, 4.8, "", 1, 1, 'L')
            b_w = max(1, (item['percentage'] / 100.0) * 42)
            pdf.set_fill_color(16, 185, 129)
            pdf.rect(x_pos + 2, y_pos + 1.1, b_w, 2.6, 'F')

        # Indicateurs numériques
        num_s = qs.get('numeric_stats')
        if num_s:
            pdf.set_font('helvetica', 'B', 7.5)
            pdf.set_text_color(67, 56, 202)
            pdf.cell(0, 4.5, (
                f"Paramètres numériques : Moyenne = {num_s['mean']} | Médiane = {num_s['median']} | "
                f"Q1 = {num_s['q1']} | Q3 = {num_s['q3']} | IQR = {num_s['iqr']} | Écart-type = {num_s['std_dev']} | "
                f"Étendue = [{num_s['min']} - {num_s['max']}] | Outliers = {num_s['outliers_count']}"
            ), 0, 1, 'L')

        pdf.ln(3)

    # =========================================================================
    # CHAPITRE 4 : EXPLORATION DES RELATIONS BIVARIÉES & TRIS CROISÉS
    # =========================================================================
    pdf.add_page()
    pdf.chapter_title("4. Exploration des Relations Bivariées & Tris Croisés")
    
    # Avertissement méthodologique formel
    pdf.set_font('helvetica', 'B', 8.5)
    pdf.set_text_color(185, 28, 28)
    pdf.cell(0, 5, "[!] MISE EN GARDE MÉTHODOLOGIQUE :", 0, 1, 'L')
    pdf.set_font('helvetica', 'I', 8)
    pdf.multi_cell(0, 4, (
        "Les croisements de variables ci-dessous décrivent les associations empiriques entre les catégories d'acteurs et les choix de réponses. "
        "Une corrélation ou divergence statistique observée ne constitue pas automatiquement une relation de cause à effet directe."
    ))
    pdf.ln(3)

    for idx_q, qs in enumerate(q_stats, 1):
        ct = qs.get('cross_tabulation')
        if not ct or not ct.get('actors'):
            continue

        if pdf.get_y() > 230:
            pdf.add_page()

        pdf.set_font('helvetica', 'B', 9.5)
        pdf.set_text_color(30, 27, 75)
        pdf.multi_cell(0, 4.5, f"Croisement Q{idx_q} x Acteurs : « {qs['question_text'][:80]}... »")
        
        # Divergences signalées
        if qs.get('divergences'):
            pdf.set_font('helvetica', 'I', 7.5)
            pdf.set_text_color(185, 28, 28)
            for d in qs['divergences']:
                pdf.multi_cell(0, 3.8, f"  * {d}")
        pdf.ln(1)

        # Tableau croisé condensé avec % en ligne
        actors = ct['actors'][:4]  # Maximum 4 acteurs pour la largeur PDF
        col_w = min(28, int(115 / max(1, len(actors))))
        
        pdf.set_font('helvetica', 'B', 7.5)
        pdf.set_fill_color(237, 233, 254)
        pdf.set_text_color(49, 46, 129)
        pdf.cell(65, 4.5, "Modalité de Réponse", 1, 0, 'L', fill=True)
        for act in actors:
            pdf.cell(col_w, 4.5, act[:15], 1, 0, 'C', fill=True)
        pdf.ln()

        pdf.set_font('helvetica', '', 7.5)
        pdf.set_text_color(33, 33, 33)
        for cat in ct.get('categories', [])[:5]:
            pdf.cell(65, 4.2, f"  {cat[:32]}", 1, 0, 'L')
            for act in actors:
                cnt = ct['matrix'].get(cat, {}).get(act, 0)
                row_pct = ct['row_percentages'].get(cat, {}).get(act, 0)
                pdf.cell(col_w, 4.2, f"{cnt} ({row_pct}%)", 1, 0, 'C')
            pdf.ln()

        pdf.ln(3)

    # =========================================================================
    # CHAPITRE 5 : NOTE EXPLORATOIRE & HYPOTHÈSES ANALYTIQUES
    # =========================================================================
    pdf.add_page()
    pdf.chapter_title("5. Note Exploratoire & Formulation d'Hypothèses")
    pdf.set_font('helvetica', '', 9)
    pdf.set_text_color(40, 40, 40)
    pdf.multi_cell(0, 4.5, (
        "À partir des régularités et des fractures constatées dans les données, l'équipe M&E pose les questions "
        "exploratoires suivantes afin d'éclairer les mécanismes sous-jacents :"
    ))
    pdf.ln(2.5)

    for idx_h, hyp in enumerate(hypotheses, 1):
        title_hyp = f"Hypothèse {idx_h} : {hyp.get('theme', 'Axe Analytique')}"
        body_hyp = (
            f"Question exploratoire : {hyp.get('question_exploratoire', '')}\n"
            f"Hypothèse explicative : {hyp.get('hypothese_explicative', '')}\n"
            f"Vérification recommandée : {hyp.get('verification_recommandee', '')}"
        )
        pdf.add_card(title_hyp, body_hyp, type_card='info')

    # Limites des données
    pdf.set_font('helvetica', 'B', 9.5)
    pdf.set_text_color(67, 56, 202)
    pdf.cell(0, 5, "Limites méthodologiques & précautions d'interprétation :", 0, 1, 'L')
    pdf.set_font('helvetica', '', 8.5)
    pdf.set_text_color(40, 40, 40)
    for lim in note.get('limits', []):
        pdf.multi_cell(0, 4.2, f"  - {lim}")
    pdf.ln(4)

    # =========================================================================
    # CHAPITRE 6 : SOLUTIONS & PLAN D'ACTION OPÉRATIONNEL
    # =========================================================================
    pdf.add_page()
    pdf.chapter_title("6. Propositions de Solutions & Plan d'Action Opérationnel (M&E / Bailleurs)")
    pdf.set_font('helvetica', '', 9)
    pdf.set_text_color(40, 40, 40)
    pdf.multi_cell(0, 4.5, (
        "En réponse directe aux constats statistiques et aux hypothèses formulées, voici la matrice opérationnelle "
        "des mesures d'ingénierie de projet priorisées pour Changement Social Bénin :"
    ))
    pdf.ln(3)

    for sol in solutions:
        prio = sol.get('priorite', 'Moyenne')
        badge_type = 'risk' if prio == 'Haute' else ('rec' if prio == 'Moyenne' else 'info')
        title_box = f"[{prio.upper()}] {sol.get('id', 'SOL')} — {sol.get('axe', 'Axe')}"
        body_box = (
            f"Problème identifié : {sol.get('probleme_identifie', '')}\n"
            f"Solution préconisée : {sol.get('solution_preconisee', '')}\n"
            f"Acteurs responsables : {sol.get('acteurs_responsables', '')}\n"
            f"Calendrier indicatif : {sol.get('calendrier', '')}\n"
            f"Indicateur d'impact : {sol.get('indicateur_impact', '')}"
        )
        pdf.add_card(title_box, body_box, type_card=badge_type)

    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    pdf.output(filepath)
    return True
