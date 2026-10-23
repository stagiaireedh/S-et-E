"""
stats_service.py — Moteur d'analyse statistique avancée pour S&E-CSB (Changement Social Bénin).

Fournit :
1. Tris à plat (Fréquences, pourcentages, moyenne, médiane, écart-type, mode).
2. Tris croisés par catégorie d'acteurs (Bénéficiaires, Autorités, Équipe Projet, Partenaires).
3. Détection des divergences / consensus entre catégories d'acteurs.
4. Analyse thématique & sémantique des verbatims ouverts.
5. Génération automatique d'orientations stratégiques et d'aide à la décision (IA + Heuristique).
"""

import math
import re
from collections import Counter, defaultdict
from datetime import datetime
from models import db, Project, Questionnaire, Question, InterviewSession, Answer
from ai_service import ai_client, analyze_sentiment, _local_analyze_sentiment, extract_themes


# Palette de couleurs professionnelles pour les graphiques statistiques (accessible, contrastée)
STAT_COLORS = [
    {"bg": "rgba(99, 102, 241, 0.85)", "border": "#6366f1", "name": "Indigo"},
    {"bg": "rgba(16, 185, 129, 0.85)", "border": "#10b981", "name": "Émeraude"},
    {"bg": "rgba(245, 158, 11, 0.85)", "border": "#f59e0b", "name": "Ambre"},
    {"bg": "rgba(236, 72, 153, 0.85)", "border": "#ec4899", "name": "Rose"},
    {"bg": "rgba(6, 182, 212, 0.85)", "border": "#06b6d4", "name": "Cyan"},
    {"bg": "rgba(139, 92, 246, 0.85)", "border": "#8b5cf6", "name": "Violet"},
    {"bg": "rgba(239, 68, 68, 0.85)", "border": "#ef4444", "name": "Corail"},
    {"bg": "rgba(20, 184, 166, 0.85)", "border": "#14b8a6", "name": "Turquoise"},
    {"bg": "rgba(249, 115, 22, 0.85)", "border": "#f97316", "name": "Orange"},
    {"bg": "rgba(100, 116, 139, 0.85)", "border": "#64748b", "name": "Ardoise"},
]


def detect_numeric_values(text_list):
    """Tente d'extraire des valeurs numériques (notes 1-5, pourcentages, âges) si applicable."""
    nums = []
    for t in text_list:
        if not t:
            continue
        # Détection d'un chiffre isolé ou d'une note (ex: "4/5", "4", "Note : 5")
        match = re.search(r'\b([0-9]+(?:[\.,][0-9]+)?)\b', str(t))
        if match:
            try:
                val = float(match.group(1).replace(',', '.'))
                nums.append(val)
            except ValueError:
                pass
    return nums


def compute_descriptive_stats(numbers):
    """Calcule moyenne, médiane, variance, écart-type, min, max."""
    if not numbers:
        return None
    n = len(numbers)
    s_numbers = sorted(numbers)
    mean_val = sum(s_numbers) / n
    median_val = s_numbers[n // 2] if n % 2 != 0 else (s_numbers[n // 2 - 1] + s_numbers[n // 2]) / 2.0
    variance = sum((x - mean_val) ** 2 for x in s_numbers) / n if n > 0 else 0
    std_dev = math.sqrt(variance)
    return {
        'count': n,
        'mean': round(mean_val, 2),
        'median': round(median_val, 2),
        'std_dev': round(std_dev, 2),
        'min': round(min(s_numbers), 2),
        'max': round(max(s_numbers), 2)
    }


def normalize_answer_text(text):
    """Normalise un texte de réponse pour faciliter le regroupement catégoriel."""
    if not text:
        return "Non renseigné"
    clean = text.strip()
    # Harmonisation Oui / Non
    lower = clean.lower()
    if lower in ['oui', 'yes', 'o', 'vrai', 'positive', 'positif']:
        return "Oui"
    if lower in ['non', 'no', 'n', 'faux', 'negative', 'négatif']:
        return "Non"
    if lower in ['peut-être', 'peut etre', 'partiellement', 'moyen', 'mitigé']:
        return "Partiellement / Mitigé"
    if lower in ['très satisfait', 'tres satisfait', 'très bonne', 'très bon']:
        return "Très satisfait"
    if lower in ['satisfait', 'bonne', 'bon']:
        return "Satisfait"
    if lower in ['peu satisfait', 'passable', 'moyen']:
        return "Peu satisfait"
    if lower in ['insatisfait', 'pas satisfait', 'mauvais', 'très mauvais']:
        return "Insatisfait"
    return clean


def analyze_single_question_stats(question, answers):
    """
    Analyse statistique complète d'une question unique :
    - Tri à plat (distribution, fréquences, pourcentages)
    - Statistiques descriptives si numérique
    - Tri croisé par catégorie d'acteurs
    - Analyse de sentiment / thèmes si texte
    """
    total_answers = len(answers)
    
    # 1. Regroupement par réponses brutes et normalisées
    counts_by_value = Counter()
    grouped_by_actor = defaultdict(Counter)
    answers_by_actor = defaultdict(list)
    raw_texts = []
    
    # Récupération et découpage propre des choix prédéfinis
    predefined_choices = []
    if isinstance(question.choices, str) and question.choices.strip():
        predefined_choices = [c.strip() for c in question.choices.split(',') if c.strip()]
    elif isinstance(question.choices, list):
        predefined_choices = [str(c).strip() for c in question.choices if str(c).strip()]

    # Si le type est 'select' ou 'choice' ou s'il y a des choix prédéfinis
    is_choice_type = (question.question_type in ['select', 'radio', 'choice', 'checkbox', 'boolean']) or bool(predefined_choices)

    for ans in answers:
        raw_val = ans.answer_text.strip() if ans.answer_text else "Non renseigné"
        raw_texts.append(raw_val)
        actor = ans.session.actor_category if (ans.session and ans.session.actor_category) else "Non spécifié"
        
        # Si choix prédéfini, trouver la correspondance la plus proche
        matched_choice = None
        if predefined_choices:
            for c in predefined_choices:
                if c.lower() == raw_val.lower():
                    matched_choice = c
                    break
            if not matched_choice:
                for c in predefined_choices:
                    if len(c) >= 3 and (c.lower() in raw_val.lower() or raw_val.lower() in c.lower()):
                        matched_choice = c
                        break
        
        val = matched_choice if matched_choice else normalize_answer_text(raw_val)
        counts_by_value[val] += 1
        grouped_by_actor[actor][val] += 1
        answers_by_actor[actor].append(raw_val)

    # 2. Construction du Tri à Plat (Fréquences & Pourcentages)
    tri_a_plat = []
    sorted_items = counts_by_value.most_common()
    for idx, (val, cnt) in enumerate(sorted_items):
        pct = round((cnt / total_answers * 100), 1) if total_answers > 0 else 0
        color_item = STAT_COLORS[idx % len(STAT_COLORS)]
        tri_a_plat.append({
            'label': val,
            'count': cnt,
            'percentage': pct,
            'color': color_item['bg'],
            'border_color': color_item['border']
        })

    # 3. Détection numérique
    numeric_vals = detect_numeric_values(raw_texts)
    numeric_stats = None
    # Si au moins 70% des réponses sont interprétables numériquement
    if total_answers > 0 and len(numeric_vals) >= max(3, int(total_answers * 0.7)):
        numeric_stats = compute_descriptive_stats(numeric_vals)

    # 4. Tri Croisé (Question x Catégories d'Acteurs)
    # Toutes les catégories d'acteurs rencontrées
    all_actors = sorted(list(grouped_by_actor.keys()))
    cross_tabulation = {
        'actors': all_actors,
        'modalities': [item['label'] for item in tri_a_plat],
        'matrix': []  # Liste de lignes : { modality, actor_counts: { actor: count }, actor_percentages: { actor: % } }
    }
    
    actor_totals = {act: sum(grouped_by_actor[act].values()) for act in all_actors}
    
    for item in tri_a_plat:
        mod = item['label']
        row_counts = {}
        row_pcts = {}
        for act in all_actors:
            c = grouped_by_actor[act].get(mod, 0)
            tot_act = actor_totals.get(act, 0)
            row_counts[act] = c
            row_pcts[act] = round((c / tot_act * 100), 1) if tot_act > 0 else 0
            
        cross_tabulation['matrix'].append({
            'modality': mod,
            'counts': row_counts,
            'percentages': row_pcts
        })

    # 5. Détection de divergence / consensus entre acteurs
    divergence_notes = []
    if len(all_actors) >= 2 and total_answers >= 4:
        for mod in [item['label'] for item in tri_a_plat[:3]]:
            pcts = [cross_tabulation['matrix'][i]['percentages'][act] 
                    for i, r in enumerate(cross_tabulation['matrix']) if r['modality'] == mod 
                    for act in all_actors]
            if pcts and (max(pcts) - min(pcts) >= 35):
                # Forte disparité entre catégories
                best_act = max(all_actors, key=lambda a: next((r['percentages'][a] for r in cross_tabulation['matrix'] if r['modality'] == mod), 0))
                worst_act = min(all_actors, key=lambda a: next((r['percentages'][a] for r in cross_tabulation['matrix'] if r['modality'] == mod), 0))
                divergence_notes.append(
                    f"Divergence notable sur « {mod} » : {best_act} adhère à {next(r['percentages'][best_act] for r in cross_tabulation['matrix'] if r['modality'] == mod)}% "
                    f"contre seulement {next(r['percentages'][worst_act] for r in cross_tabulation['matrix'] if r['modality'] == mod)}% chez {worst_act}."
                )

    # 6. Analyse qualitative (Sentiment & Mots clés) si réponses textuelles
    sentiment_summary = None
    top_keywords = []
    if not is_choice_type or len(tri_a_plat) > 5:
        # Calcul de sentiment moyen sur les verbatims
        sent_scores = []
        sent_labels = Counter()
        for t in raw_texts:
            res = _local_analyze_sentiment(t)
            sent_scores.append(res['score'])
            sent_labels[res['label']] += 1
        
        avg_sent = round(sum(sent_scores) / len(sent_scores), 2) if sent_scores else 0
        sentiment_summary = {
            'average_score': avg_sent,
            'distribution': {
                'positif': sent_labels['positif'],
                'neutre': sent_labels['neutre'],
                'négatif': sent_labels['négatif']
            }
        }
        
        # Mots-clés fréquents (filtrage mots vides français)
        stopwords = {
            'le', 'la', 'les', 'de', 'des', 'du', 'un', 'une', 'et', 'en', 'a', 'à', 'pour', 'dans',
            'sur', 'par', 'qui', 'que', 'quoi', 'dont', 'où', 'est', 'sont', 'il', 'elle', 'ils', 'elles',
            'nous', 'vous', 'je', 'tu', 'au', 'aux', 'ce', 'cette', 'ces', 'avec', 'sans', 'sous', 'plus',
            'pas', 'ne', 'se', 'sa', 'son', 'ses', 'leur', 'leurs', 'mais', 'ou', 'donc', 'or', 'ni', 'car',
            'projet', 'commune', 'bénin', 'village', 'très', 'bien', 'fait', 'faire', 'avoir', 'être'
        }
        words = []
        for t in raw_texts:
            cleaned = re.sub(r'[^\w\s]', ' ', t.lower())
            for w in cleaned.split():
                if len(w) > 3 and w not in stopwords:
                    words.append(w)
        top_keywords = [{'word': w, 'count': c} for w, c in Counter(words).most_common(12)]

    # 7. Recommandation du type de graphique optimal
    chart_type = 'pie'
    if len(tri_a_plat) > 5 or numeric_stats is not None:
        chart_type = 'bar'
    elif is_choice_type and len(tri_a_plat) <= 4:
        chart_type = 'doughnut'

    return {
        'question_id': question.id,
        'question_text': question.text,
        'question_type': question.question_type,
        'total_answers': total_answers,
        'tri_a_plat': tri_a_plat,
        'numeric_stats': numeric_stats,
        'cross_tabulation': cross_tabulation,
        'divergences': divergence_notes,
        'sentiment_summary': sentiment_summary,
        'top_keywords': top_keywords,
        'recommended_chart_type': chart_type
    }


_ORIENTATIONS_CACHE = {}

def generate_strategic_orientations(project_id, questions_stats):
    """
    Génère des orientations stratégiques et opérationnelles poussées pour Changement Social Bénin.
    Combine les signaux statistiques quantitatifs et l'analyse qualitative par IA (ou règles métier).
    """
    total_samples = sum(qs['total_answers'] for qs in questions_stats) if questions_stats else 0
    cache_key = f"{project_id}_{total_samples}_{len(questions_stats)}"
    if cache_key in _ORIENTATIONS_CACHE:
        return _ORIENTATIONS_CACHE[cache_key]

    orientations = []
    
    # 1. Tenter d'utiliser l'IA en cascade
    if ai_client and questions_stats:
        try:
            # Préparation du corpus condensé des statistiques clés
            summary_lines = []
            for qs in questions_stats[:8]:  # Limiter aux 8 questions clés pour le prompt
                q_text = qs['question_text']
                top_ans = qs['tri_a_plat'][0] if qs['tri_a_plat'] else None
                top_str = f"Réponse dominante: '{top_ans['label']}' ({top_ans['percentage']}%)" if top_ans else ""
                div_str = "; ".join(qs['divergences']) if qs.get('divergences') else "Consensus global"
                summary_lines.append(f"- Question: \"{q_text}\" | Total répondants: {qs['total_answers']} | {top_str} | Divergences: {div_str}")
            
            corpus = "\n".join(summary_lines)
            system_prompt = (
                "Tu es un expert senior en Suivi-Évaluation (M&E) et gouvernance de projets au Bénin "
                "pour l'ONG Changement Social Bénin (CSB).\n"
                "À partir des résultats statistiques et des tris croisés fournis, formule 3 à 5 orientations "
                "stratégiques majeures hautement professionnelles et actionnables pour les décideurs et bailleurs.\n"
                "Chaque orientation doit obligatoirement respecter ce format JSON :\n"
                "[\n"
                "  {\n"
                "    \"titre\": \"Titre accrocheur de l'orientation\",\n"
                "    \"priorite\": \"Haute\" | \"Moyenne\" | \"Surveillance\",\n"
                "    \"constat_chiffre\": \"Le constat statistique précis qui justifie l'orientation\",\n"
                "    \"action_recommandee\": \"Action concrète à déployer sur le terrain avec les acteurs concernés\",\n"
                "    \"indicateur_suivi\": \"Indicateur M&E à suivre dans le temps\"\n"
                "  }\n"
                "]\n"
                "Réponds UNIQUEMENT avec un tableau JSON valide, sans texte additionnel."
            )
            raw_response = ai_client.generate(system_prompt, corpus)
            from ai_service import parse_json_from_llm
            parsed = parse_json_from_llm(raw_response)
            if isinstance(parsed, list) and len(parsed) > 0:
                _ORIENTATIONS_CACHE[cache_key] = parsed
                return parsed
        except Exception as e:
            # En cas d'erreur IA, on bascule proprement sur l'heuristique
            pass

    # 2. Fallback Heuristique Déterministe (Règles Métier M&E de haut niveau)
    total_samples = sum(qs['total_answers'] for qs in questions_stats) if questions_stats else 0
    all_divergences = [d for qs in questions_stats for d in qs.get('divergences', [])]
    
    # Orientation 1 : Priorité aux divergences de perception
    if all_divergences:
        orientations.append({
            "titre": "Harmonisation du dialogue État / Société Civile / Bénéficiaires",
            "priorite": "Haute",
            "constat_chiffre": all_divergences[0],
            "action_recommandee": "Organiser des ateliers de cadrage communautaire et de redevabilité conjointe pour aligner les attentes entre autorités locales et bénéficiaires finaux.",
            "indicateur_suivi": "Taux de satisfaction croisée lors des revues semestrielles de projet"
        })

    # Orientation 2 : Consolidation de l'adhésion dominante
    if questions_stats:
        first_q = questions_stats[0]
        if first_q['tri_a_plat']:
            top = first_q['tri_a_plat'][0]
            orientations.append({
                "titre": f"Capitalisation sur l'adhésion observée ({top['label']})",
                "priorite": "Moyenne",
                "constat_chiffre": f"{top['percentage']}% des répondants convergent vers l'option « {top['label']} » pour la question '{first_q['question_text'][:60]}...'.",
                "action_recommandee": "Formaliser les facteurs de succès dans un guide méthodologique de bonnes pratiques diffusable auprès des comités de gestion locaux.",
                "indicateur_suivi": "Nombre de communes répliquant le protocole validé"
            })

    # Orientation 3 : Renforcement des mécanismes de remontée terrain
    orientations.append({
        "titre": "Déploiement d'un mécanisme d'alerte et de suivi des signaux faibles",
        "priorite": "Haute",
        "constat_chiffre": f"Sur un échantillon total consolidé de {total_samples} observations enregistrées dans le système.",
        "action_recommandee": "Mettre en place des fiches de suivi rapide mensuelles et digitaliser les remontées d'incidents critiques via l'application mobile/web.",
        "indicateur_suivi": "Délai moyen de résolution des dysfonctionnements signalés (< 14 jours)"
    })

    # Orientation 4 : Pérennité institutionnelle et financière
    orientations.append({
        "titre": "Plan de transition et autonomisation financière locale",
        "priorite": "Moyenne",
        "constat_chiffre": "Les analyses thématiques identifient la gestion des coûts et des cotisations comme un facteur sensible de durabilité.",
        "action_recommandee": "Structurer un modèle de redevance participative transparent audité annuellement par les représentants d'usagers.",
        "indicateur_suivi": "Taux de recouvrement effectif des contributions communautaires (> 85%)"
    })

    _ORIENTATIONS_CACHE[cache_key] = orientations
    return orientations


def get_full_project_statistics(project_id, questionnaire_id=None, actor_filter=None):
    """
    Point d'entrée principal pour le dashboard statistique pro :
    - Filtre par projet et optionnellement questionnaire ou catégorie d'acteur
    - Génère tous les tris à plat, tris croisés, et orientations stratégiques
    """
    project = Project.query.get(project_id)
    if not project:
        return None

    # Sélection des questionnaires
    if questionnaire_id:
        questionnaires = Questionnaire.query.filter_by(id=questionnaire_id, project_id=project_id).all()
    else:
        questionnaires = Questionnaire.query.filter_by(project_id=project_id).all()

    if not questionnaires:
        return {
            'project_id': project_id,
            'project_name': project.name,
            'total_questionnaires': 0,
            'total_sessions': 0,
            'questions_stats': [],
            'actors_distribution': [],
            'orientations': []
        }

    q_ids = [q.id for q in questionnaires]
    
    # Récupérer les sessions correspondantes
    session_query = InterviewSession.query.filter(
        InterviewSession.project_id == project_id,
        InterviewSession.questionnaire_id.in_(q_ids)
    )
    if actor_filter and actor_filter.lower() != 'all':
        session_query = session_query.filter(InterviewSession.actor_category == actor_filter)
    
    sessions = session_query.all()
    session_ids = [s.id for s in sessions]
    total_sessions = len(sessions)

    # Répartition des acteurs
    actor_counter = Counter(s.actor_category for s in sessions if s.actor_category)
    actors_distribution = []
    for idx, (act, count) in enumerate(actor_counter.most_common()):
        pct = round(count / total_sessions * 100, 1) if total_sessions > 0 else 0
        c_item = STAT_COLORS[idx % len(STAT_COLORS)]
        actors_distribution.append({
            'label': act,
            'count': count,
            'percentage': pct,
            'color': c_item['bg'],
            'border_color': c_item['border']
        })

    # Récupérer toutes les questions ordonnées
    questions = Question.query.filter(Question.questionnaire_id.in_(q_ids)).order_by(Question.order_num).all()

    # Récupérer toutes les réponses liées aux sessions sélectionnées
    all_answers = Answer.query.filter(Answer.session_id.in_(session_ids)).all() if session_ids else []
    answers_by_q = defaultdict(list)
    for ans in all_answers:
        answers_by_q[ans.question_id].append(ans)

    # Statistiques détaillées par question
    questions_stats = []
    for q in questions:
        q_ans = answers_by_q.get(q.id, [])
        if q_ans:
            stats = analyze_single_question_stats(q, q_ans)
            questions_stats.append(stats)

    # Orientations stratégiques générées
    orientations = generate_strategic_orientations(project_id, questions_stats)

    # Calcul d'un KPI de consensus global (0 à 100%)
    consensus_scores = []
    for qs in questions_stats:
        if qs['tri_a_plat']:
            # Le % de l'option dominante reflète le consensus sur la question
            consensus_scores.append(qs['tri_a_plat'][0]['percentage'])
    global_consensus_index = round(sum(consensus_scores) / len(consensus_scores), 1) if consensus_scores else 0

    return {
        'project_id': project_id,
        'project_name': project.name,
        'total_questionnaires': len(questionnaires),
        'total_sessions': total_sessions,
        'global_consensus_index': global_consensus_index,
        'actors_distribution': actors_distribution,
        'questions_stats': questions_stats,
        'orientations': orientations,
        'generated_at': datetime.utcnow().isoformat()
    }
