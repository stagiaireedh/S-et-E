import re
import json
import logging
from collections import Counter
from config import Config
from models import Answer, InterviewSession, Question
from ia_cascade import IACascade


logger = logging.getLogger("AIService")

# Initialisation du client d'IA en cascade
try:
    if Config.USE_REAL_IA:
        ai_client = IACascade()
    else:
        ai_client = None
        logger.info("Mode Simulation IA activé par configuration (USE_REAL_IA = False).")
except Exception as e:
    logger.warning(f"Impossible d'initialiser ia_client au démarrage : {e}")
    ai_client = None


# Dictionnaires locaux de secours (simulation)
POSSIBLE_POSITIVES = {
    'bon', 'bonne', 'excellent', 'excellente', 'satisfait', 'satisfaite', 'très bien', 'bien',
    'progrès', 'amélioration', 'réussite', 'facile', 'rapide', 'utile', 'efficace', 'apprécie',
    'apprécier', 'merci', 'positif', 'positive', 'avantage', 'opportunité', 'constructif',
    'parfait', 'parfaite', 'réussi', 'réussie', 'super', 'génial', 'formidable', 'résolu',
    'bénéfique', 'favorable', 'encourageant', 'soutien', 'aide', 'renforcement'
}

POSSIBLE_NEGATIVES = {
    'mauvais', 'mauvaise', 'difficile', 'problème', 'panne', 'pannes', 'retard', 'retards',
    'lent', 'lente', 'inutile', 'inefficace', 'mécontent', 'mécontente', 'compliqué', 'compliquée',
    'insuffisant', 'insuffisante', 'manque', 'manquent', 'rupture', 'déçu', 'déçue', 'déception',
    'cherté', 'cher', 'chère', 'coûteux', 'coûteuse', 'faiblesse', 'risque', 'risques', 'danger',
    'bloqué', 'bloquée', 'panne', 'erreur', 'échec', 'perte', 'absent', 'absence', 'critique',
    'conflictuel', 'conflictuelle', 'tension', 'tensions', 'contrainte', 'contraintes'
}

THEMES_DICT = {
    'Accès & Infrastructure': ['eau', 'infrastructure', 'accès', 'distance', 'forage', 'puits', 'robinet', 'source', 'éloigné', 'proximité'],
    'Maintenance & Technique': ['panne', 'pannes', 'réparation', 'maintenance', 'technicien', 'pièces', 'rechange', 'pompe', 'fonctionne', 'technique'],
    'Gouvernance & Gestion': ['comité', 'gestion', 'association', 'président', 'organisation', 'règles', 'réunion', 'décision', 'bureau'],
    'Aspect Financier': ['cotisation', 'argent', 'coût', 'prix', 'payant', 'gratuit', 'tarif', 'finance', 'caisse', 'moyens'],
    'Formation & Renforcement': ['formation', 'apprendre', 'capacité', 'atelier', 'sensibilisation', 'hygiène', 'compétence', 'formé', 'formés'],
    'Impact & Satisfaction': ['satisfait', 'changement', 'santé', 'maladie', 'amélioration', 'bénéfice', 'progrès', 'mieux', 'impact']
}

def parse_json_from_llm(text):
    """Nettoie et décode la réponse JSON brute retournée par l'LLM."""
    if not text:
        return None
    cleaned = text.strip()
    if cleaned.startswith("```json"):
        cleaned = cleaned[7:]
    if cleaned.startswith("```"):
        cleaned = cleaned[3:]
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3]
    cleaned = cleaned.strip()
    return json.loads(cleaned)

# --- 1. ANALYSE DE SENTIMENT ---
def analyze_sentiment(text):
    """
    Analyse le sentiment d'un texte. Tente d'utiliser l'IA en cascade (retourne JSON),
    sinon effectue un comptage de mots-clés local en secours.
    """
    # Tentative d'utilisation de l'IA réelle
    if ai_client:
        try:
            system_prompt = (
                "Tu es un expert en analyse de sentiments pour le suivi-évaluation de projets. "
                "Analyse le texte fourni par l'utilisateur et retourne OBLIGATOIREMENT un objet JSON valide "
                "avec la structure suivante :\n"
                "{\n"
                "  \"score\": float,  // Nombre entre -1.0 (très négatif) et 1.0 (très positif)\n"
                "  \"label\": string  // Uniquement 'positif', 'négatif' ou 'neutre'\n"
                "}\n"
                "Ne retourne aucun autre texte, explication ou bloc de code autre que le JSON."
            )
            raw_response = ai_client.generate(system_prompt, f"Texte à analyser : \"{text}\"")
            result = parse_json_from_llm(raw_response)
            if result and 'score' in result and 'label' in result:
                return {
                    'score': float(result['score']),
                    'label': result['label']
                }
        except Exception as e:
            logger.warning(f"Échec de l'analyse de sentiment IA, repli sur le dictionnaire local : {e}")

    # Fallback local (simulation par dictionnaire)
    return _local_analyze_sentiment(text)

def _local_analyze_sentiment(text):
    if not text:
        return {'score': 0.0, 'label': 'neutre'}
    cleaned_text = re.sub(r'[^\w\s\-\']', ' ', text.lower())
    words = cleaned_text.split()
    pos_count = sum(1 for w in words if w in POSSIBLE_POSITIVES)
    neg_count = sum(1 for w in words if w in POSSIBLE_NEGATIVES)
    
    total_hits = pos_count + neg_count
    if total_hits == 0:
        return {'score': 0.0, 'label': 'neutre'}
    score = (pos_count - neg_count) / total_hits
    label = 'positif' if score > 0.15 else ('négatif' if score < -0.15 else 'neutre')
    return {'score': round(score, 2), 'label': label}

# --- 2. EXTRACTION DE THÈMES ---
def extract_themes(text):
    """
    Extrait les thèmes dominants d'un texte. Tente d'utiliser l'IA en cascade (JSON),
    sinon effectue une analyse de mots-clés locale en secours.
    """
    if ai_client:
        try:
            system_prompt = (
                "Tu es un expert en analyse qualitative thématique. Analyse le texte fourni par l'utilisateur "
                "et extrait ses thèmes dominants sous forme d'un tableau JSON d'objets. Chaque objet doit respecter la structure suivante :\n"
                "[\n"
                "  {\n"
                "    \"theme\": \"Nom du thème\",\n"
                "    \"weight\": int  // Score d'importance de 1 à 10\n"
                "  }\n"
                "]\n"
                "Identifie des thèmes concrets (ex: 'Aspect Financier', 'Maintenance Technique', 'Formation', 'Santé', etc.). "
                "Ne retourne aucun autre texte que le tableau JSON."
            )
            raw_response = ai_client.generate(system_prompt, f"Texte à analyser : \"{text}\"")
            result = parse_json_from_llm(raw_response)
            if isinstance(result, list):
                return result
        except Exception as e:
            logger.warning(f"Échec de l'extraction thématique IA, repli local : {e}")

    # Fallback local
    return _local_extract_themes(text)

def _local_extract_themes(text):
    if not text:
        return []
    text_lower = text.lower()
    detected_themes = {}
    for theme, keywords in THEMES_DICT.items():
        count = sum(len(re.findall(r'\b' + re.escape(keyword) + r'\w*', text_lower)) for keyword in keywords)
        if count > 0:
            detected_themes[theme] = count
    sorted_themes = sorted(detected_themes.items(), key=lambda x: x[1], reverse=True)
    return [{'theme': k, 'weight': v} for k, v in sorted_themes]

# --- 3. TRIANGULATION COMPLÈTE & IA ---
def run_project_triangulation(project_id):
    """
    Calcule la triangulation qualitative et quantitative du projet.
    Interroge l'IA en cascade pour générer une synthèse, des risques et des recommandations
    structurées, et bascule sur le mode local en cas d'erreur.
    """
    sessions = InterviewSession.query.filter_by(project_id=project_id).all()
    if not sessions:
        return {'success': False, 'message': "Aucune donnée d'entretien disponible pour ce projet."}

    # Agrégation des données pour transmission à l'IA ou calcul local
    verbatims_by_actor = {}
    all_comments = []
    
    for s in sessions:
        actor = s.actor_category
        if actor not in verbatims_by_actor:
            verbatims_by_actor[actor] = []
        for ans in s.answers:
            if ans.answer_text and len(ans.answer_text.strip()) > 5:
                verbatims_by_actor[actor].append(ans.answer_text)
                all_comments.append(ans.answer_text)

    # 1. TENTATIVE IA COMMUNE
    if ai_client:
        try:
            # Construction d'un corpus structuré d'entretiens
            corpus = "CORPUS DE TÉMOIGNAGES DU PROJET :\n\n"
            for actor, texts in verbatims_by_actor.items():
                corpus += f"--- CATÉGORIE D'ACTEUR : {actor} ---\n"
                for i, t in enumerate(texts, 1):
                    corpus += f"Témoignage {i} : \"{t}\"\n"
                corpus += "\n"
                
            system_prompt = (
                "Tu es un expert analyste de données de Suivi-Évaluation (M&E). Analyse le corpus de témoignages d'entretiens "
                "fourni pour en tirer des statistiques globales, des risques identifiés et des recommandations stratégiques. "
                "Retourne OBLIGATOIREMENT un objet JSON valide structuré EXACTEMENT de la façon suivante :\n"
                "{\n"
                "  \"avg_sentiment_score\": float,  // Score global du projet (-1.0 à 1.0)\n"
                "  \"sentiment_label\": \"positif\" | \"négatif\" | \"neutre\",\n"
                "  \"actor_summary\": {\n"
                "     \"CatégorieActeur1\": { \"avg_score\": float, \"label\": \"string\", \"count\": int },\n"
                "     ... // Pour chaque catégorie d'acteur trouvée dans le corpus (Bénéficiaire, Partenaire, Équipe Projet, Autorité Locale)\n"
                "  },\n"
                "  \"themes\": [\n"
                "     { \"theme\": \"NomTheme\", \"weight\": int } // Liste des 4 thèmes récurrents majeurs\n"
                "  ],\n"
                "  \"risks\": [\n"
                "     { \"title\": \"Titre du Risque\", \"description\": \"Détail du risque constaté\", \"source\": \"Acteur/Source\" }\n"
                "  ],  // Fournit au moins 3 risques réels constatés dans les témoignages\n"
                "  \"recommendations\": [\n"
                "     { \"title\": \"Titre Recommandation\", \"description\": \"Action recommandée\", \"priority\": \"Haute\"|\"Moyenne\" }\n"
                "  ]  // Fournit au moins 3 recommandations associées aux risques\n"
                "}\n"
                "Ne retourne aucun autre texte que le JSON."
            )
            
            raw_response = ai_client.generate(system_prompt, corpus)
            result = parse_json_from_llm(raw_response)
            
            if result and 'avg_sentiment_score' in result and 'risks' in result:
                result['success'] = True
                return result
        except Exception as e:
            logger.warning(f"Échec de la triangulation globale IA, bascule sur la logique locale : {e}")

    # 2. FALLBACK LOCAL (MOCKED/RULE-BASED)
    return _local_run_project_triangulation(project_id, sessions, verbatims_by_actor, all_comments)

def _local_run_project_triangulation(project_id, sessions, verbatims_by_actor, all_comments):
    total_sentiment_score = 0
    sentiment_count = 0
    actor_summary = {}
    risks_candidates = []
    
    # Analyse de sentiment locale
    for s in sessions:
        actor = s.actor_category
        if actor not in actor_summary:
            actor_summary[actor] = {'scores': [], 'count': 0}
            
        for ans in s.answers:
            text = ans.answer_text
            if not text or len(text.strip()) < 5:
                continue
                
            sent = _local_analyze_sentiment(text)
            total_sentiment_score += sent['score']
            sentiment_count += 1
            
            actor_summary[actor]['scores'].append(sent['score'])
            actor_summary[actor]['count'] += 1
            
            if sent['label'] == 'négatif':
                risks_candidates.append({
                    'actor': actor,
                    'text': text,
                    'session': s.title
                })
                
    avg_score = (total_sentiment_score / sentiment_count) if sentiment_count > 0 else 0.0
    
    # Formater le résumé des acteurs
    actor_summary_formatted = {}
    for actor, data in actor_summary.items():
        scores = data['scores']
        act_avg = (sum(scores) / len(scores)) if scores else 0.0
        label = 'Favorable' if act_avg > 0.15 else ('Préoccupé / Négatif' if act_avg < -0.15 else 'Mitigé / Neutre')
        actor_summary_formatted[actor] = {
            'avg_score': round(act_avg, 2),
            'label': label,
            'count': data['count']
        }
        
    combined_text = " ".join(all_comments)
    themes = _local_extract_themes(combined_text)
    
    # Risques locaux
    risks = []
    added_titles = set()
    for candidate in risks_candidates:
        words_found = [w for w in POSSIBLE_NEGATIVES if w in candidate['text'].lower()]
        title = f"Difficulté concernant : {words_found[0].capitalize()}" if words_found else "Difficulté générale"
        if title not in added_titles and len(risks) < 4:
            added_titles.add(title)
            risks.append({
                'title': title,
                'description': candidate['text'],
                'source': f"{candidate['actor']} ({candidate['session']})"
            })
            
    if not risks:
        risks.append({
            'title': "Faiblesse de maintenance",
            'description': "Possibilité de pannes non résolues par manque de techniciens formés.",
            'source': "Simulation locale"
        })
        
    # Recommandations locales
    recommendations = []
    theme_names = [t['theme'] for t in themes]
    if 'Maintenance & Technique' in theme_names:
        recommendations.append({
            'title': "Mettre en place un plan de maintenance préventive",
            'description': "Former des techniciens locaux et équiper le comité d'une boîte à outils.",
            'priority': "Haute"
        })
    if 'Aspect Financier' in theme_names:
        recommendations.append({
            'title': "Réviser le mécanisme de cotisation",
            'description': "Ajuster la participation forfaitaire aux revenus réels des familles.",
            'priority': "Moyenne"
        })
    if len(recommendations) < 2:
        recommendations.append({
            'title': "Améliorer les canaux de communication",
            'description': "Mettre en place un espace de réclamations pour les usagers.",
            'priority': "Moyenne"
        })
        
    return {
        'success': True,
        'avg_sentiment_score': round(avg_score, 2),
        'sentiment_label': 'positif' if avg_score > 0.15 else ('négatif' if avg_score < -0.15 else 'neutre'),
        'actor_summary': actor_summary_formatted,
        'themes': themes[:4],
        'risks': risks,
        'recommendations': recommendations
    }

# --- 4. ASSISTANT CHAT IA (RAG LOCAL) ---
def chat_assistant_respond(user_query, project_id):
    """
    RAG (Retrieval-Augmented Generation) local. Recherche les témoignages pertinents
    dans la base SQLite, construit le contexte et interroge l'IA.
    Bascule sur le dictionnaire de mots-clés local en cas d'erreur.
    """
    sessions = InterviewSession.query.filter_by(project_id=project_id).all()
    if not sessions:
        return "Aucune donnée d'entretien disponible pour ce projet."

    # 1. TENTATIVE AVEC IA RÉELLE
    if ai_client:
        try:
            # Construction d'un contexte de témoignages raccourci pour le prompt
            context_items = []
            for s in sessions:
                for ans in s.answers:
                    if ans.answer_text and len(ans.answer_text.strip()) > 5:
                        context_items.append(
                            f"Acteur: {s.actor_category} | Entretien: {s.title} | Citation: \"{ans.answer_text}\""
                        )
            
            # Limiter la taille du contexte pour éviter de saturer les tokens gratuits
            context_text = "\n".join(context_items[:25]) 
            
            system_prompt = (
                "Tu es un assistant IA de suivi-évaluation (M&E) expert en triangulation de données. "
                "Tu as accès aux citations extraites d'entretiens collectés sur le terrain (fournies dans le contexte).\n"
                "Réponds en français, de manière concise, structurée et professionnelle aux questions de l'utilisateur. "
                "N'affirme rien qui ne soit pas étayé par le contexte ou qui ne découle pas d'une analyse logique des verbatims."
            )
            
            user_prompt = (
                f"CONTEXTE DES ENTRETIENS :\n{context_text}\n\n"
                f"QUESTION DE L'UTILISATEUR : {user_query}\n\n"
                f"RÉPONSE ASSISTANT :"
            )
            
            response = ai_client.generate(system_prompt, user_prompt)
            if response:
                return response
        except Exception as e:
            logger.warning(f"Échec du chat assistant IA, repli sur la recherche locale : {e}")

    # 2. FALLBACK RECHERCHE LEXICALE LOCAL
    return _local_chat_assistant_respond(user_query, project_id, sessions)

def _local_chat_assistant_respond(user_query, project_id, sessions):
    query_lower = user_query.lower()
    triangulation = _local_run_project_triangulation(project_id, sessions, {}, [])
    
    if any(word in query_lower for word in ['risque', 'risques', 'problème', 'problèmes', 'panne', 'pannes', 'négatif', 'difficulté']):
        response_text = "### ⚠️ Risques et points de vigilance (Repli local) :\n\n"
        for i, r in enumerate(triangulation['risks'], 1):
            response_text += f"**{i}. {r['title']}**\n*Description* : {r['description']}\n*Source* : {r['source']}\n\n"
        return response_text
        
    elif any(word in query_lower for word in ['recommandation', 'recommandations', 'conseil', 'conseils', 'action', 'solution']):
        response_text = "### 💡 Recommandations suggérées (Repli local) :\n\n"
        for i, rec in enumerate(triangulation['recommendations'], 1):
            response_text += f"**{i}. {rec['title']}** (Urgence : {rec['priority']})\n{rec['description']}\n\n"
        return response_text
        
    elif any(word in query_lower for word in ['synthèse', 'synthese', 'résumé', 'resume', 'global', 'projet']):
        response_text = f"### 📊 Synthèse d'évaluation (Repli local) :\n\n"
        response_text += f"- **Sentiment général** : {triangulation['sentiment_label'].upper()} (Score : {triangulation['avg_sentiment_score']})\n"
        response_text += f"- **Sessions** : {len(sessions)} entretiens analysés.\n\n"
        response_text += "**Thèmes principaux :**\n"
        for t in triangulation['themes']:
            response_text += f"- {t['theme']} (Fréquence : {t['weight']})\n"
        return response_text
        
    else:
        # Recherche lexicale
        matched = []
        for s in sessions:
            for ans in s.answers:
                if query_lower in ans.answer_text.lower():
                    matched.append((s.actor_category, ans.answer_text, s.title))
        
        if matched:
            response_text = f"### 🔍 Extraits locaux trouvés pour '{user_query}' :\n\n"
            for i, match in enumerate(matched[:3], 1):
                response_text += f"{i}. *\"{match[1]}\"*\n   — **{match[0]}** ({match[2]})\n\n"
            return response_text
            
        return "Désolé, l'assistant IA est hors ligne et je n'ai pas trouvé de mention directe dans la base de données. Essayez de taper 'risques' ou 'synthèse'."
