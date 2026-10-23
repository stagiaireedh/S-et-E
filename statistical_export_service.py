"""
statistical_export_service.py — Générateur d'exports statistiques avancés pour S&E-CSB.

Génère :
1. Un classeur Excel institutionnel 7 feuilles modélisé sur la rigueur d'audit statistique (Openpyxl / Pandas).
2. Un rapport PDF analytique haute définition respectant les 8 piliers méthodologiques,
   ENRICHI DE GRAPHIQUES HAUTE DÉFINITION (Camemberts/Donuts, Barres groupées, Histogrammes colorés) (FPDF2 + Matplotlib).
"""

import io
import os
import tempfile
from datetime import datetime
import openpyxl
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
from openpyxl.utils import get_column_letter

# Configuration Matplotlib en mode headless (sans interface graphique)
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

from fpdf import FPDF
from stats_service import get_full_project_statistics, STAT_COLORS
from pdf_service import EvaluatorPDF, clean_unicode


# Palette de couleurs graphiques professionnelles harmonisées
PALETTE_HEX = ['#4f46e5', '#10b981', '#f59e0b', '#ec4899', '#06b6d4', '#8b5cf6', '#ef4444', '#14b8a6', '#f97316', '#64748b']
ACTOR_HEX = {
    'Bénéficiaire': '#4f46e5',
    'Autorité Locale': '#10b981',
    'Équipe Projet': '#f59e0b',
    'Partenaire': '#ec4899'
}


# =============================================================================
# FONCTIONS DE GÉNÉRATION DE GRAPHIQUES HD (MATPLOTLIB) POUR LE PDF
# =============================================================================

def generate_donut_chart_img(labels, values, title, temp_dir, filename="donut_chart.png"):
    """Génère un camembert / donut chart moderne haute résolution en couleurs avec pourcentages et légende."""
    if not labels or not values or sum(values) == 0:
        return None
    
    fig, ax = plt.subplots(figsize=(6.5, 3.8), dpi=200)
    colors = PALETTE_HEX[:len(labels)]
    
    # Donut chart
    wedges, texts, autotexts = ax.pie(
        values,
        labels=None,
        autopct='%1.1f%%',
        startangle=140,
        colors=colors,
        pctdistance=0.75,
        wedgeprops=dict(width=0.45, edgecolor='white', linewidth=2)
    )
    
    # Styliser les pourcentages sur le camembert
    for autotext in autotexts:
        autotext.set_color('white')
        autotext.set_fontsize(9.5)
        autotext.set_weight('bold')
    
    # Légende soignée sur le côté
    legend_labels = [f"{lbl} ({val} - {round(val/sum(values)*100, 1)}%)" for lbl, val in zip(labels, values)]
    ax.legend(
        wedges, legend_labels,
        title="Profils d'Acteurs",
        title_fontsize=9.5,
        loc="center left",
        bbox_to_anchor=(0.95, 0, 0.5, 1),
        fontsize=8.5,
        frameon=True,
        facecolor='#f8fafc',
        edgecolor='#cbd5e1'
    )
    
    ax.set_title(title, fontsize=12, fontweight='bold', color='#1e1b4b', pad=15)
    plt.tight_layout()
    
    filepath = os.path.join(temp_dir, filename)
    plt.savefig(filepath, format='png', dpi=200, bbox_inches='tight')
    plt.close(fig)
    return filepath


def generate_question_pie_chart_img(tri_a_plat, title, temp_dir, filename="question_pie.png"):
    """Génère un camembert HD pour le tri à plat d'une question à choix."""
    if not tri_a_plat:
        return None
    
    labels = [t['label'][:25] for t in tri_a_plat]
    values = [t['count'] for t in tri_a_plat]
    if sum(values) == 0:
        return None

    fig, ax = plt.subplots(figsize=(6.2, 3.4), dpi=200)
    colors = PALETTE_HEX[:len(labels)]
    
    wedges, texts, autotexts = ax.pie(
        values,
        labels=None,
        autopct='%1.1f%%',
        startangle=90,
        colors=colors,
        pctdistance=0.72,
        wedgeprops=dict(edgecolor='white', linewidth=2)
    )
    
    for autotext in autotexts:
        autotext.set_color('white')
        autotext.set_fontsize(9)
        autotext.set_weight('bold')
        
    legend_labels = [f"{t['label'][:30]} : {t['count']} ({t['percentage']}%)" for t in tri_a_plat]
    ax.legend(
        wedges, legend_labels,
        title="Modalités de Réponse",
        title_fontsize=9,
        loc="center left",
        bbox_to_anchor=(0.95, 0, 0.5, 1),
        fontsize=8,
        frameon=True,
        facecolor='#f8fafc',
        edgecolor='#cbd5e1'
    )
    
    ax.set_title(title[:60] + ('...' if len(title) > 60 else ''), fontsize=11, fontweight='bold', color='#1e1b4b', pad=12)
    plt.tight_layout()
    
    filepath = os.path.join(temp_dir, filename)
    plt.savefig(filepath, format='png', dpi=200, bbox_inches='tight')
    plt.close(fig)
    return filepath


def generate_horizontal_bar_chart_img(tri_a_plat, title, temp_dir, filename="horizontal_bar.png"):
    """Génère un diagramme en barres horizontales colorées avec étiquettes de pourcentages."""
    if not tri_a_plat:
        return None
    
    labels = [t['label'][:35] for t in reversed(tri_a_plat[:7])]
    percentages = [t['percentage'] for t in reversed(tri_a_plat[:7])]
    counts = [t['count'] for t in reversed(tri_a_plat[:7])]
    
    fig, ax = plt.subplots(figsize=(6.5, 3.2), dpi=200)
    bars = ax.barh(labels, percentages, color='#4f46e5', height=0.55, edgecolor='none')
    
    # Colorer les barres en dégradé ou palette
    for idx, bar in enumerate(bars):
        bar.set_color(PALETTE_HEX[idx % len(PALETTE_HEX)])
        
    ax.set_xlim(0, max(100, max(percentages) + 15) if percentages else 100)
    ax.set_xlabel('Part des répondants (%)', fontsize=8.5, color='#64748b', labelpad=8)
    ax.set_title(title[:60] + ('...' if len(title) > 60 else ''), fontsize=10.5, fontweight='bold', color='#1e1b4b', pad=12)
    
    # Affichage des étiquettes de données
    for bar, pct, cnt in zip(bars, percentages, counts):
        width = bar.get_width()
        ax.text(width + 1.5, bar.get_y() + bar.get_height() / 2, f"{pct}% (N={cnt})",
                va='center', ha='left', fontsize=8.5, fontweight='bold', color='#1e1b4b')
        
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['left'].set_color('#cbd5e1')
    ax.spines['bottom'].set_color('#cbd5e1')
    ax.xaxis.grid(True, linestyle='--', alpha=0.4, color='#cbd5e1')
    ax.set_axisbelow(True)
    plt.tight_layout()
    
    filepath = os.path.join(temp_dir, filename)
    plt.savefig(filepath, format='png', dpi=200, bbox_inches='tight')
    plt.close(fig)
    return filepath


def generate_crosstab_grouped_bar_img(question_stats, temp_dir, filename="crosstab_grouped_bar.png"):
    """Génère un grand diagramme en barres groupées comparatives par catégorie d'acteur."""
    ct = question_stats.get('cross_tabulation')
    if not ct or not ct.get('actors'):
        return None
    
    actors = ct['actors']
    categories = ct.get('categories', [])[:5]  # Top 5 modalités
    if not categories:
        return None
    
    import numpy as np
    x = np.arange(len(categories))
    width = min(0.18, 0.75 / len(actors))
    
    fig, ax = plt.subplots(figsize=(7.2, 3.6), dpi=200)
    
    for i, act in enumerate(actors):
        pcts = [ct['row_percentages'].get(cat, {}).get(act, 0) for cat in categories]
        color = ACTOR_HEX.get(act, PALETTE_HEX[i % len(PALETTE_HEX)])
        rects = ax.bar(x + (i - len(actors)/2 + 0.5) * width, pcts, width, label=act, color=color, edgecolor='white', linewidth=1)
        
        # Étiquettes de pourcentages au-dessus des barres
        for r in rects:
            h = r.get_height()
            if h > 8:
                ax.annotate(f"{int(round(h))}%",
                            xy=(r.get_x() + r.get_width() / 2, h),
                            xytext=(0, 2), textcoords="offset points",
                            ha='center', va='bottom', fontsize=7, fontweight='bold', color='#334155')

    ax.set_ylabel('Adhésion au sein du groupe (%)', fontsize=8.5, color='#64748b')
    ax.set_title(f"Tris Croisés : « {question_stats['question_text'][:65]}... »", fontsize=10.5, fontweight='bold', color='#1e1b4b', pad=12)
    ax.set_xticks(x)
    ax.set_xticklabels([c[:20] for c in categories], fontsize=8.5, fontweight='600', color='#1e1b4b')
    ax.set_ylim(0, 115)
    
    ax.legend(loc='upper right', fontsize=8, frameon=True, facecolor='#f8fafc', edgecolor='#cbd5e1')
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['left'].set_color('#cbd5e1')
    ax.spines['bottom'].set_color('#cbd5e1')
    ax.yaxis.grid(True, linestyle='--', alpha=0.4, color='#cbd5e1')
    ax.set_axisbelow(True)
    plt.tight_layout()
    
    filepath = os.path.join(temp_dir, filename)
    plt.savefig(filepath, format='png', dpi=200, bbox_inches='tight')
    plt.close(fig)
    return filepath


def generate_temporal_trend_chart_img(trend_data, temp_dir, filename="temporal_trend.png"):
    """Génère un histogramme d'évolution temporelle de la collecte."""
    if not trend_data or not trend_data.get('monthly_trend'):
        return None
    
    items = trend_data['monthly_trend']
    periods = [it['period'] for it in items]
    counts = [it['count'] for it in items]
    
    fig, ax = plt.subplots(figsize=(6.5, 2.8), dpi=200)
    bars = ax.bar(periods, counts, color='#6366f1', width=0.5, edgecolor='none')
    
    for bar, cnt in zip(bars, counts):
        h = bar.get_height()
        ax.annotate(f"{cnt}",
                    xy=(bar.get_x() + bar.get_width() / 2, h),
                    xytext=(0, 3), textcoords="offset points",
                    ha='center', va='bottom', fontsize=8.5, fontweight='bold', color='#1e1b4b')
        
    ax.set_ylabel("Nombre d'entretiens", fontsize=8.5, color='#64748b')
    ax.set_title("Rythme de Collecte & Distribution Temporelle", fontsize=10.5, fontweight='bold', color='#1e1b4b', pad=10)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['left'].set_color('#cbd5e1')
    ax.spines['bottom'].set_color('#cbd5e1')
    ax.yaxis.grid(True, linestyle='--', alpha=0.4, color='#cbd5e1')
    ax.set_axisbelow(True)
    plt.tight_layout()
    
    filepath = os.path.join(temp_dir, filename)
    plt.savefig(filepath, format='png', dpi=200, bbox_inches='tight')
    plt.close(fig)
    return filepath


# =============================================================================
# EXPORT EXCEL PROFESSIONNEL (7 ONGLETS)
# =============================================================================

def export_advanced_statistics_to_excel(project_id, questionnaire_id=None):
    """Génère le classeur Excel 7 feuilles structuré selon les 8 piliers."""
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
    wb.remove(wb.active)

    font_main_title = Font(name="Calibri", size=15, bold=True, color="1E1B4B")
    font_subtitle = Font(name="Calibri", size=10, italic=True, color="64748B")
    font_section = Font(name="Calibri", size=12, bold=True, color="312E81")
    font_table_hdr = Font(name="Calibri", size=10.5, bold=True, color="FFFFFF")
    font_bold = Font(name="Calibri", size=10.5, bold=True)
    font_normal = Font(name="Calibri", size=10.5)
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
        left=Side(style="thin", color="CBD5E1"), right=Side(style="thin", color="CBD5E1"),
        top=Side(style="thin", color="CBD5E1"), bottom=Side(style="thin", color="CBD5E1")
    )

    # 1. Contexte & Métadonnées
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

    start_r_dict = len(ctx_items) + 7
    ws_ctx.cell(row=start_r_dict - 1, column=1, value="Dictionnaire des Variables & Typologie Statistique").font = font_section
    dict_headers = ["Code Variable", "Libellé de la Question", "Type dans l'App", "Nature Statistique", "Échelle / Modalités", "Obligatoire"]
    for c_i, h in enumerate(dict_headers, 1):
        c = ws_ctx.cell(row=start_r_dict, column=c_i, value=h)
        c.font = font_table_hdr
        c.fill = fill_indigo
        c.alignment = Alignment(horizontal="center")

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
        curr_r += 1

    # 2. Audit & Nettoyage
    ws_aud = wb.create_sheet(title="2. Audit & Nettoyage")
    ws_aud.views.sheetView[0].showGridLines = True
    ws_aud["A1"] = "INSPECTION QUALITÉ, AUDIT D'INTÉGRITÉ & NETTOYAGE DES DONNÉES"
    ws_aud["A1"].font = font_main_title

    audit_metrics = [
        ("Nombre de lignes (Observations N)", audit.get('rows_count', 0)),
        ("Nombre de colonnes (Variables P)", audit.get('columns_count', 0)),
        ("Volume total de cellules (N x P)", audit.get('total_cells', 0)),
        ("Cellules renseignées valides", audit.get('filled_cells', 0)),
        ("Taux global de complétude", f"{audit.get('completeness_rate', 0)}%"),
        ("Taux global de données manquantes", f"{audit.get('missing_rate', 0)}%"),
        ("Doublons détectés", audit.get('duplicate_sessions_detected', 0)),
        ("Score global de santé des données", f"{audit.get('quality_score', 0)} / 100"),
        ("Diagnostic d'intégrité", audit.get('data_health_status', 'Validé')),
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

    # 3. Statistiques Descriptives
    ws_desc = wb.create_sheet(title="3. Stats Descriptives")
    ws_desc.views.sheetView[0].showGridLines = True
    ws_desc["A1"] = "STATISTIQUES DESCRIPTIVES UNIVARIÉES"
    ws_desc["A1"].font = font_main_title

    curr_row = 4
    for idx_q, qs in enumerate(q_stats, 1):
        ws_desc.cell(row=curr_row, column=1, value=f"Q{idx_q}. {qs['question_text']}").font = font_section
        curr_row += 1
        hdrs_f = ["Modalité", "Effectif (n_i)", "Fréquence (%)"]
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
            curr_row += 1

        num_s = qs.get('numeric_stats')
        if num_s:
            curr_row += 1
            ws_desc.cell(row=curr_row, column=1, value="Métrique Numérique").font = font_bold
            ws_desc.cell(row=curr_row, column=2, value="Valeur").font = font_bold
            curr_row += 1
            for k_lbl, v_val in [('Moyenne', num_s['mean']), ('Médiane', num_s['median']), ('Q1', num_s['q1']), ('Q3', num_s['q3']), ('IQR', num_s['iqr']), ('Écart-type', num_s['std_dev'])]:
                ws_desc.cell(row=curr_row, column=1, value=k_lbl).border = thin_border
                ws_desc.cell(row=curr_row, column=2, value=v_val).border = thin_border
                curr_row += 1
        curr_row += 2

    # 4. Tris Croisés & Contingence
    ws_crois = wb.create_sheet(title="4. Tris Croisés & Contingence")
    ws_crois.views.sheetView[0].showGridLines = True
    ws_crois["A1"] = "RELATIONS BIVARIÉES : QUESTIONS x CATÉGORIES D'ACTEURS"
    ws_crois["A1"].font = font_main_title
    ws_crois["A2"] = "Rappel : Une relation observée ne démontre pas automatiquement une causalité directe."
    ws_crois["A2"].font = font_italic_red

    r_c = 4
    for idx_q, qs in enumerate(q_stats, 1):
        ct = qs.get('cross_tabulation')
        if not ct or not ct.get('actors'):
            continue
        ws_crois.cell(row=r_c, column=1, value=f"Q{idx_q}. {qs['question_text']}").font = font_section
        r_c += 1
        actors = ct['actors']
        headers = ["Modalité"] + [f"{act} (Effectif)" for act in actors] + [f"{act} (% Ligne)" for act in actors]
        for c_i, h in enumerate(headers, 1):
            cell = ws_crois.cell(row=r_c, column=c_i, value=h)
            cell.font = font_table_hdr
            cell.fill = fill_purple
            cell.alignment = Alignment(horizontal="center")
        r_c += 1
        for cat in ct.get('categories', []):
            ws_crois.cell(row=r_c, column=1, value=cat).border = thin_border
            for a_idx, act in enumerate(actors, 2):
                cnt = ct['matrix'].get(cat, {}).get(act, 0)
                ws_crois.cell(row=r_c, column=a_idx, value=cnt).border = thin_border
            col_offset = 2 + len(actors)
            for a_idx, act in enumerate(actors):
                row_pct = ct['row_percentages'].get(cat, {}).get(act, 0)
                c_p = ws_crois.cell(row=r_c, column=col_offset + a_idx, value=f"{row_pct}%")
                c_p.border = thin_border
                if row_pct >= 50.0:
                    c_p.fill = fill_highlight
            r_c += 1
        r_c += 2

    # 5. Note Exploratoire
    ws_hyp = wb.create_sheet(title="5. Note Exploratoire")
    ws_hyp.views.sheetView[0].showGridLines = True
    ws_hyp["A1"] = "NOTE EXPLORATOIRE D'ANALYSE & HYPOTHÈSES"
    ws_hyp["A1"].font = font_main_title
    r_h = 4
    for finding in note.get('main_findings', []):
        ws_hyp.cell(row=r_h, column=1, value=f"• {finding}").font = font_normal
        r_h += 1
    r_h += 1
    for hyp in hypotheses:
        ws_hyp.cell(row=r_h, column=1, value=hyp.get('theme', '')).font = font_bold
        ws_hyp.cell(row=r_h, column=2, value=hyp.get('question_exploratoire', '')).font = font_normal
        ws_hyp.cell(row=r_h, column=3, value=hyp.get('hypothese_explicative', '')).font = font_normal
        r_h += 1

    # 6. Solutions & Plan d'Action
    ws_sol = wb.create_sheet(title="6. Solutions & Plan d'Action")
    ws_sol.views.sheetView[0].showGridLines = True
    ws_sol["A1"] = "PROPOSITIONS DE SOLUTIONS & PLAN D'ACTION (M&E / BAILLEURS)"
    ws_sol["A1"].font = font_main_title
    sol_hdrs = ["ID", "Axe", "Problème Identifié", "Solution Préconisée", "Priorité", "Responsables", "Calendrier", "Indicateur d'Impact"]
    for c_i, h in enumerate(sol_hdrs, 1):
        c = ws_sol.cell(row=4, column=c_i, value=h)
        c.font = font_table_hdr
        c.fill = fill_navy
        c.alignment = Alignment(horizontal="center")
    r_s = 5
    for sol in solutions:
        for c_i, key in enumerate(['id', 'axe', 'probleme_identifie', 'solution_preconisee', 'priorite', 'acteurs_responsables', 'calendrier', 'indicateur_impact'], 1):
            cell = ws_sol.cell(row=r_s, column=c_i, value=sol.get(key, ''))
            cell.font = font_normal
            cell.border = thin_border
            cell.alignment = Alignment(vertical="top", wrap_text=True)
        r_s += 1

    for ws in wb.worksheets:
        for col in ws.columns:
            max_len = max(len(str(cell.value or '')) for cell in col)
            col_letter = get_column_letter(col[0].column)
            ws.column_dimensions[col_letter].width = min(max(max_len + 3, 12), 60)

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    return output


# =============================================================================
# RAPPORT PDF AVANCÉ AVEC GRAPHIQUES & CAMEMBERTS HAUTE DÉFINITION (FPDF2)
# =============================================================================

def generate_advanced_statistics_pdf(project_id, filepath, questionnaire_id=None):
    """
    Génère le rapport PDF institutionnel enrichi de graphiques colorés et camemberts haute définition :
    - Donut Chart HD de la répartition des acteurs
    - Camemberts / Pie Charts des questions clés
    - Histogrammes et barres horizontales avec pourcentages
    - Diagrammes en barres groupées comparatives de tris croisés
    - Boîtes de KPIs et cartes d'orientations stratégiques
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

    # Répertoire temporaire pour les rendus graphiques PNG
    temp_dir = tempfile.mkdtemp(prefix="csb_charts_")

    try:
        # 1. Génération du Donut Chart HD Répartition Acteurs
        actor_labels = [a['label'] for a in stats_data['actors_distribution']]
        actor_counts = [a['count'] for a in stats_data['actors_distribution']]
        actors_chart_path = generate_donut_chart_img(
            actor_labels, actor_counts,
            "Répartition de l'Échantillon par Catégorie d'Acteur",
            temp_dir, "donut_actors.png"
        )

        # 2. Génération des graphiques par question (Camembert ou Barres horizontales)
        question_charts = {}
        for idx_q, qs in enumerate(q_stats[:6], 1):  # 6 questions clés
            if qs.get('tri_a_plat'):
                if len(qs['tri_a_plat']) <= 4:
                    q_chart_file = generate_question_pie_chart_img(
                        qs['tri_a_plat'],
                        f"Q{idx_q}. Distribution des Réponses",
                        temp_dir, f"q_{idx_q}_pie.png"
                    )
                else:
                    q_chart_file = generate_horizontal_bar_chart_img(
                        qs['tri_a_plat'],
                        f"Q{idx_q}. Distribution des Réponses",
                        temp_dir, f"q_{idx_q}_bar.png"
                    )
                if q_chart_file:
                    question_charts[qs['question_id']] = q_chart_file

        # 3. Génération du Diagramme de Tris Croisés en Barres Groupées (Question la plus divergente)
        crosstab_chart_path = None
        divergent_q = next((qs for qs in q_stats if qs.get('divergences')), (q_stats[0] if q_stats else None))
        if divergent_q:
            crosstab_chart_path = generate_crosstab_grouped_bar_img(
                divergent_q, temp_dir, "crosstab_divergence.png"
            )

        # 4. Génération de la Tendance Temporelle
        temporal_chart_path = None
        if stats_data.get('temporal_analysis'):
            temporal_chart_path = generate_temporal_trend_chart_img(
                stats_data['temporal_analysis'], temp_dir, "temporal_trend.png"
            )

        # Construction du PDF avec FPDF2
        pdf = EvaluatorPDF(title_text="Rapport d'Analyse Statistique & Graphiques", project_name=stats_data['project_name'])
        pdf.alias_nb_pages()
        pdf.add_page()

        # En-tête Prestigieux
        pdf.set_font('helvetica', 'B', 17)
        pdf.set_text_color(30, 27, 75)
        pdf.cell(0, 11, "RAPPORT D'ANALYSE STATISTIQUE & ORIENTATIONS STRATÉGIQUES", 0, 1, 'C')
        
        pdf.set_font('helvetica', '', 9.5)
        pdf.set_text_color(100, 116, 139)
        pdf.cell(0, 5, f"Projet : {stats_data['project_name']} | Échantillon consolidé : N = {stats_data['total_sessions']} répondants", 0, 1, 'C')
        pdf.cell(0, 5, f"Généré le {datetime.now().strftime('%d/%m/%Y à %H:%M')} — Changement Social Bénin (CSB)", 0, 1, 'C')
        pdf.ln(5)

        # =====================================================================
        # CHAPITRE 1 : CONTEXTE DES DONNÉES & CAMEMBERT DE POPULATION
        # =====================================================================
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

        # Insertion du Camembert / Donut Chart HD des Acteurs
        if actors_chart_path and os.path.exists(actors_chart_path):
            pdf.ln(2)
            # Centrer l'image
            img_w = 145
            x_center = (210 - img_w) / 2
            pdf.image(actors_chart_path, x=x_center, y=pdf.get_y(), w=img_w)
            pdf.ln(80)  # Hauteur occupée par l'image
        pdf.ln(4)

        # =====================================================================
        # CHAPITRE 2 : INSPECTION, AUDIT QUALITÉ & NETTOYAGE DES DONNÉES
        # =====================================================================
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

        # =====================================================================
        # CHAPITRE 3 : STATISTIQUES DESCRIPTIVES AVEC CAMEMBERTS & DIAGRAMMES
        # =====================================================================
        pdf.add_page()
        pdf.chapter_title("3. Statistiques Descriptives Univariées (Graphiques & Tris à Plat)")

        for idx_q, qs in enumerate(q_stats, 1):
            if pdf.get_y() > 185:
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
            pdf.cell(90, 4.8, "  Modalité / Option de Réponse", 1, 0, 'L', fill=True)
            pdf.cell(25, 4.8, "Effectif (N)", 1, 0, 'C', fill=True)
            pdf.cell(25, 4.8, "Part (%)", 1, 1, 'C', fill=True)

            pdf.set_font('helvetica', '', 8)
            pdf.set_text_color(33, 33, 33)
            for item in qs['tri_a_plat']:
                pdf.cell(90, 4.5, f"  {item['label'][:45]}", 1, 0, 'L')
                pdf.cell(25, 4.5, f"{item['count']}", 1, 0, 'C')
                pdf.cell(25, 4.5, f"{item['percentage']}%", 1, 1, 'C')

            # Insertion du Camembert ou Diagramme en Barres pour cette question
            q_chart = question_charts.get(qs['question_id'])
            if q_chart and os.path.exists(q_chart):
                if pdf.get_y() > 200:
                    pdf.add_page()
                pdf.ln(2)
                img_w = 135
                x_center = (210 - img_w) / 2
                pdf.image(q_chart, x=x_center, y=pdf.get_y(), w=img_w)
                pdf.ln(70)

            # Paramètres numériques si applicables
            num_s = qs.get('numeric_stats')
            if num_s:
                pdf.set_font('helvetica', 'B', 7.5)
                pdf.set_text_color(67, 56, 202)
                pdf.cell(0, 4.5, (
                    f"Paramètres numériques : Moyenne = {num_s['mean']} | Médiane = {num_s['median']} | "
                    f"Q1 = {num_s['q1']} | Q3 = {num_s['q3']} | IQR = {num_s['iqr']} | Écart-type = {num_s['std_dev']} | "
                    f"Étendue = [{num_s['min']} - {num_s['max']}]"
                ), 0, 1, 'L')

            pdf.ln(4)

        # =====================================================================
        # CHAPITRE 4 : RELATIONS BIVARIÉES AVEC DIAGRAMME EN BARRES GROUPÉES
        # =====================================================================
        pdf.add_page()
        pdf.chapter_title("4. Exploration des Relations Bivariées & Tris Croisés")
        
        pdf.set_font('helvetica', 'B', 8.5)
        pdf.set_text_color(185, 28, 28)
        pdf.cell(0, 5, "[!] MISE EN GARDE MÉTHODOLOGIQUE :", 0, 1, 'L')
        pdf.set_font('helvetica', 'I', 8)
        pdf.set_text_color(60, 60, 60)
        pdf.multi_cell(0, 4, (
            "Les croisements de variables ci-dessous décrivent les associations empiriques entre les catégories d'acteurs et les choix de réponses. "
            "Une corrélation ou divergence statistique observée ne constitue pas automatiquement une relation de cause à effet directe."
        ))
        pdf.ln(3)

        # Insertion du Diagramme en Barres Groupées des Tris Croisés
        if crosstab_chart_path and os.path.exists(crosstab_chart_path):
            img_w = 155
            x_center = (210 - img_w) / 2
            pdf.image(crosstab_chart_path, x=x_center, y=pdf.get_y(), w=img_w)
            pdf.ln(78)
            pdf.ln(3)

        for idx_q, qs in enumerate(q_stats, 1):
            ct = qs.get('cross_tabulation')
            if not ct or not ct.get('actors'):
                continue

            if pdf.get_y() > 230:
                pdf.add_page()

            pdf.set_font('helvetica', 'B', 9)
            pdf.set_text_color(30, 27, 75)
            pdf.multi_cell(0, 4.5, f"Croisement Q{idx_q} : « {qs['question_text'][:80]}... »")
            
            if qs.get('divergences'):
                pdf.set_font('helvetica', 'I', 7.5)
                pdf.set_text_color(185, 28, 28)
                for d in qs['divergences']:
                    pdf.multi_cell(0, 3.8, f"  * {d}")
            pdf.ln(1)

            actors = ct['actors'][:4]
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

        # =====================================================================
        # CHAPITRE 5 : NOTE EXPLORATOIRE & HYPOTHÈSES ANALYTIQUES
        # =====================================================================
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

        # Insertion du graphique temporel si disponible
        if temporal_chart_path and os.path.exists(temporal_chart_path):
            if pdf.get_y() > 210:
                pdf.add_page()
            pdf.ln(2)
            img_w = 145
            x_center = (210 - img_w) / 2
            pdf.image(temporal_chart_path, x=x_center, y=pdf.get_y(), w=img_w)
            pdf.ln(60)

        # Limites des données
        pdf.set_font('helvetica', 'B', 9.5)
        pdf.set_text_color(67, 56, 202)
        pdf.cell(0, 5, "Limites méthodologiques & précautions d'interprétation :", 0, 1, 'L')
        pdf.set_font('helvetica', '', 8.5)
        pdf.set_text_color(40, 40, 40)
        for lim in note.get('limits', []):
            pdf.multi_cell(0, 4.2, f"  - {lim}")
        pdf.ln(4)

        # =====================================================================
        # CHAPITRE 6 : SOLUTIONS & PLAN D'ACTION OPÉRATIONNEL
        # =====================================================================
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

    finally:
        # Nettoyage des fichiers temporaires
        try:
            for f in os.listdir(temp_dir):
                os.remove(os.path.join(temp_dir, f))
            os.rmdir(temp_dir)
        except Exception:
            pass
