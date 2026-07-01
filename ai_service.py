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
        
    # 1. Extraction des thèmes locaux
    combined_text = " ".join(all_comments)
    themes = _local_extract_themes(combined_text)
    
    # 2. Construction dynamique des Risques
    risks = []
    added_sentences = set()
    for comment in all_comments:
        sentences = re.split(r'[.!?]\s*', comment)
        for sent in sentences:
            sent_clean = sent.strip()
            if len(sent_clean) > 20 and sent_clean.lower() not in added_sentences:
                # Mots clés de problèmes
                keywords = ['problème', 'difficulté', 'manque', 'retard', 'lent', 'compliqué', 'absent', 'insuffisant', 'mauvais', 'échoué', 'faiblesse', 'critique', 'dysfonctionnement', 'faute']
                if any(kw in sent_clean.lower() for kw in keywords):
                    added_sentences.add(sent_clean.lower())
                    # Trouver l'acteur et le titre pour ce commentaire
                    actor_role = "Bénéficiaire"
                    session_title = "Entretien"
                    for s in sessions:
                        for ans in s.answers:
                            if ans.answer_text == comment:
                                actor_role = s.actor_category
                                session_title = s.title
                                break
                    risks.append({
                        'title': f"Difficulté signalée : {sent_clean[:35]}...",
                        'description': sent_clean,
                        'source': f"{actor_role} ({session_title})"
                    })
                    if len(risks) >= 3:
                        break
        if len(risks) >= 3:
            break
            
    # Fallback si aucun risque extrait
    if not risks:
        from models import Project
        project = Project.query.get(project_id)
        proj_name = project.name.lower() if project else ""
        
        if any(k in proj_name for k in ['éduc', 'scol', 'enseig', 'élèv', 'appren', 'redevabilité']):
            risks.append({
                'title': "Risque d'absentéisme des acteurs clés",
                'description': "Faiblesse de participation ou de suivi régulier par manque d'animation ou de ressources.",
                'source': "Analyse thématique locale"
            })
            risks.append({
                'title': "Déficit de redevabilité ou de communication",
                'description': "Manque de canaux transparents pour remonter les réclamations ou partager les décisions.",
                'source': "Analyse thématique locale"
            })
        elif any(k in proj_name for k in ['sant', 'médic', 'clin', 'soin']):
            risks.append({
                'title': "Rupture de stock ou logistique",
                'description': "Risque de retard d'approvisionnement en fournitures ou outils de travail.",
                'source': "Analyse thématique locale"
            })
            risks.append({
                'title': "Surcharge des équipes de terrain",
                'description': "Risque d'épuisement ou de baisse de qualité de l'accompagnement par manque d'effectif.",
                'source': "Analyse thématique locale"
            })
        else:
            risks.append({
                'title': "Retard dans le calendrier des activités",
                'description': "Risque de décalage dans la mise en œuvre opérationnelle des jalons clés du projet.",
                'source': "Analyse thématique locale"
            })
            risks.append({
                'title': "Faible engagement communautaire",
                'description': "Risque de sous-utilisation des services ou de manque d'appropriation locale par les bénéficiaires.",
                'source': "Analyse thématique locale"
            })
            
    # 3. Construction dynamique des Recommandations
    recommendations = []
    added_rec_sentences = set()
    for comment in all_comments:
        sentences = re.split(r'[.!?]\s*', comment)
        for sent in sentences:
            sent_clean = sent.strip()
            if len(sent_clean) > 20 and sent_clean.lower() not in added_rec_sentences:
                # Mots clés de suggestion/recommandation
                keywords = ['il faut', 'devrait', 'suggère', 'recommande', 'besoin', 'nécessaire', 'améliorer', 'renforcer', 'former', 'sensibiliser', 'devoir']
                if any(kw in sent_clean.lower() for kw in keywords):
                    added_rec_sentences.add(sent_clean.lower())
                    recommendations.append({
                        'title': f"Action recommandée : {sent_clean[:35]}...",
                        'description': sent_clean,
                        'priority': 'Haute' if any(kw in sent_clean.lower() for kw in ['urgent', 'impératif', 'faut', 'nécessaire']) else 'Moyenne'
                    })
                    if len(recommendations) >= 3:
                        break
        if len(recommendations) >= 3:
            break
            
    # Fallback si aucune recommandation extraite
    if not recommendations:
        from models import Project
        project = Project.query.get(project_id)
        proj_name = project.name.lower() if project else ""
        
        if any(k in proj_name for k in ['éduc', 'scol', 'enseig', 'élèv', 'appren', 'redevabilité']):
            recommendations.append({
                'title': "Renforcer les mécanismes de redevabilité",
                'description': "Instaurer des comités de suivi transparents et inclusifs impliquant les parents et le personnel.",
                'priority': "Haute"
            })
            recommendations.append({
                'title': "Former en continu les animateurs et encadrants",
                'description': "Organiser des ateliers périodiques de renforcement des compétences et d'auto-évaluation.",
                'priority': "Moyenne"
            })
        elif any(k in proj_name for k in ['sant', 'médic', 'clin', 'soin']):
            recommendations.append({
                'title': "Sécuriser l'accès aux intrants de base",
                'description': "Instaurer un inventaire hebdomadaire et des alertes automatiques de seuil critique.",
                'priority': "Haute"
            })
            recommendations.append({
                'title': "Renforcer la communication communautaire",
                'description': "Planifier des campagnes d'information régulières pour inciter à l'utilisation des services.",
                'priority': "Moyenne"
            })
        else:
            recommendations.append({
                'title': "Mettre en place un calendrier de suivi de proximité",
                'description': "Planifier des visites régulières de l'équipe projet sur le terrain pour accompagner les acteurs.",
                'priority': "Haute"
            })
            recommendations.append({
                'title': "Organiser des ateliers de restitution communautaire",
                'description': "Restituer périodiquement les résultats de l'analyse qualitative aux populations et acteurs concernés.",
                'priority': "Moyenne"
            })
            
    # Assurer au moins 2 recommandations
    if len(recommendations) < 2:
        recommendations.append({
            'title': "Renforcer la communication entre les parties prenantes",
            'description': "Créer un espace d'échange régulier (réunion mensuelle ou canal numérique partagé) pour suivre les progrès.",
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

# --- GÉNÉRATION DE QUESTIONNAIRE PAR IA ---
def generate_questionnaire_from_prompt(prompt):
    """
    Génère un questionnaire structuré en blocs à partir d'un prompt utilisateur.
    Tente d'appeler l'IA, sinon utilise un système de simulation locale.
    """
    if ai_client:
        try:
            system_prompt = (
                "Tu es un expert en suivi-évaluation et conception de formulaires d'enquête. "
                "Génère un questionnaire structuré et cohérent sous forme de blocs JSON à partir de la demande de l'utilisateur. "
                "Retourne OBLIGATOIREMENT un objet JSON valide avec cette structure exacte, sans markdown, sans ```json, juste le JSON brute :\n"
                "{\n"
                "  \"title\": \"Titre du questionnaire\",\n"
                "  \"description\": \"Description de l'objectif\",\n"
                "  \"blocks\": [\n"
                "    {\n"
                "      \"block_type\": \"title\" | \"text\" | \"section\" | \"question\" | \"table\" | \"photo\" | \"signature\" | \"gps\" | \"file\" | \"ai\" | \"matrix\" | \"checkbox\" | \"comment\",\n"
                "      \"content\": {\n"
                "         // pour 'title' : { \"title\": \"Titre\", \"description\": \"Détails\" }\n"
                "         // pour 'text' : { \"text\": \"Texte explicatif\" }\n"
                "         // pour 'section' : { \"title\": \"Nom de section\" }\n"
                "         // pour 'question' : { \"label\": \"Texte de question\", \"question_type\": \"text\"|\"select\"|\"checkbox\"|\"radio\", \"choices\": [\"Option 1\", \"Option 2\"], \"is_required\": true/false, \"help_text\": \"Texte d'aide\" }\n"
                "         // pour 'table' : { \"label\": \"Titre tableau\", \"columns\": [\"Colonne 1\", \"Colonne 2\"] }\n"
                "         // pour 'matrix' : { \"label\": \"Titre matrice\", \"rows\": [\"Ligne 1\"], \"columns\": [\"Col 1\"] }\n"
                "         // pour 'checkbox' : { \"label\": \"Checklist\", \"options\": [\"Option A\", \"Option B\"] }\n"
                "         // pour 'signature' ou 'gps' ou 'photo' : { \"label\": \"Titre du champ\", \"help_text\": \"Aide\" }\n"
                "      }\n"
                "    }\n"
                "  ]\n"
                "}\n"
                "Fournis au moins 5 à 10 questions/sections logiques."
            )
            raw_response = ai_client.generate(system_prompt, f"Génère un questionnaire pour : \"{prompt}\"")
            result = parse_json_from_llm(raw_response)
            if result and 'title' in result and 'blocks' in result:
                return result
        except Exception as e:
            logger.warning(f"Échec de génération IA de questionnaire, repli simulation : {e}")

    # Fallback local simulé
    return _local_generate_questionnaire(prompt)

def _local_generate_questionnaire(prompt):
    p_lower = prompt.lower()
    
    # 1. Cas thématique : Formation
    if any(k in p_lower for k in ['formation', 'atelier', 'apprentissage', 'cours', 'enseignant']):
        title = "Évaluation de la Session de Formation"
        desc = "Formulaire destiné à mesurer l'acquisition des compétences et la satisfaction des participants."
        blocks = [
            {"block_type": "title", "content": {"title": title, "description": desc}},
            {"block_type": "section", "content": {"title": "1. Profil du Participant"}},
            {"block_type": "question", "content": {"label": "Nom & Prénoms", "question_type": "text", "is_required": True, "help_text": "Nom complet"}},
            {"block_type": "question", "content": {"label": "Années d'expérience professionnelle", "question_type": "select", "choices": ["Moins de 2 ans", "Entre 2 et 5 ans", "Plus de 5 ans"], "is_required": False}},
            {"block_type": "section", "content": {"title": "2. Satisfaction & Contenu"}},
            {"block_type": "question", "content": {"label": "Les objectifs de la formation étaient-ils clairs ?", "question_type": "select", "choices": ["Tout à fait d'accord", "Partiellement d'accord", "Pas d'accord"], "is_required": True}},
            {"block_type": "question", "content": {"label": "Qualité de l'animateur et de la pédagogie", "question_type": "select", "choices": ["Excellent", "Satisfaisant", "À améliorer"], "is_required": True}},
            {"block_type": "question", "content": {"label": "Verbatim libre sur les points forts", "question_type": "text", "is_required": False}},
            {"block_type": "section", "content": {"title": "3. Clôture & Signature"}},
            {"block_type": "gps", "content": {"label": "Lieu de l'évaluation", "help_text": "Coordonnées GPS terrain"}},
            {"block_type": "signature", "content": {"label": "Signature de l'évaluateur"}}
        ]
        
    # 2. Cas thématique : Santé
    elif any(k in p_lower for k in ['santé', 'medical', 'clinique', 'hôpital', 'medecin', 'soins']):
        title = "Audit de Visite - Centre de Santé"
        desc = "Mesurer la qualité de l'accueil, la disponibilité des intrants et les temps d'attente."
        blocks = [
            {"block_type": "title", "content": {"title": title, "description": desc}},
            {"block_type": "section", "content": {"title": "1. Identification de la Structure"}},
            {"block_type": "question", "content": {"label": "Nom du district ou centre de santé", "question_type": "text", "is_required": True}},
            {"block_type": "gps", "content": {"label": "Coordonnées géographiques de la clinique"}},
            {"block_type": "section", "content": {"title": "2. Disponibilité & Qualité des Services"}},
            {"block_type": "question", "content": {"label": "Disponibilité des médicaments essentiels ce jour", "question_type": "select", "choices": ["Tous disponibles", "Rupture partielle", "Rupture totale"], "is_required": True}},
            {"block_type": "question", "content": {"label": "Temps d'attente estimé avant consultation", "question_type": "select", "choices": ["Moins de 30 min", "30 min à 2h", "Plus de 2h"], "is_required": False}},
            {"block_type": "photo", "content": {"label": "Photo de la pharmacie ou stock", "help_text": "Optionnel"}},
            {"block_type": "section", "content": {"title": "3. Validation"}},
            {"block_type": "signature", "content": {"label": "Signature du médecin chef"}}
        ]
        
    # 3. Par défaut : Structure générique
    else:
        title = f"Enquête : {prompt[:40]}..." if len(prompt) > 40 else f"Enquête : {prompt}"
        desc = "Questionnaire généré automatiquement par l'assistant S&E-CSB."
        blocks = [
            {"block_type": "title", "content": {"title": title, "description": desc}},
            {"block_type": "section", "content": {"title": "1. Renseignements Généraux"}},
            {"block_type": "question", "content": {"label": "Nom du répondant", "question_type": "text", "is_required": True}},
            {"block_type": "gps", "content": {"label": "Localisation GPS de l'entretien"}},
            {"block_type": "section", "content": {"title": "2. Questions Thématiques"}},
            {"block_type": "question", "content": {"label": "Niveau de satisfaction globale sur l'activité", "question_type": "select", "choices": ["Très Satisfait", "Neutre", "Insatisfait"], "is_required": True}},
            {"block_type": "question", "content": {"label": "Quelles sont les principales difficultés rencontrées ?", "question_type": "text", "is_required": False}},
            {"block_type": "section", "content": {"title": "3. Clôture"}},
            {"block_type": "signature", "content": {"label": "Signature"}}
        ]
        
    return {"title": title, "description": desc, "blocks": blocks}

# --- IMPORTATION IA (DEPUIS TEXTE BRUT DE FICHIER) ---
def import_questionnaire_from_text(file_text, file_name):
    """
    Analyse le texte extrait d'un fichier Word/PDF/Excel avec l'IA en cascade
    pour en déduire une structure cohérente de blocs.
    """
    if ai_client and file_text:
        try:
            system_prompt = (
                "Tu es un assistant IA de suivi-évaluation. Ton rôle est d'analyser le texte brut fourni (qui provient d'un document Word/PDF/Excel) "
                "et de le structurer sous la forme d'un questionnaire composé de blocs.\n"
                "Détecte le titre principal, la description éventuelle, les titres de sections et crée des questions adaptées (texte, choix multiples, signature, etc.).\n"
                "Retourne OBLIGATOIREMENT un objet JSON valide avec cette structure brute (sans ```json, pas d'explication) :\n"
                "{\n"
                "  \"title\": \"Titre du questionnaire extrait\",\n"
                "  \"description\": \"Description ou objectif extrait\",\n"
                "  \"blocks\": [\n"
                "     { \"block_type\": \"section\", \"content\": { \"title\": \"Nom section\" } },\n"
                "     { \"block_type\": \"question\", \"content\": { \"label\": \"Texte de la question\", \"question_type\": \"text\"|\"select\", \"choices\": [\"choix1\", \"choix2\"], \"is_required\": false } }\n"
                "  ]\n"
                "}"
            )
            # Tronquer le texte si trop long pour éviter les limites de tokens
            truncated_text = file_text[:6000]
            raw_response = ai_client.generate(system_prompt, f"Fichier: {file_name}\nContenu du document :\n{truncated_text}")
            result = parse_json_from_llm(raw_response)
            if result and 'title' in result and 'blocks' in result:
                return result
        except Exception as e:
            logger.warning(f"Échec de l'analyse d'import IA, repli local : {e}")

    # Fallback local par parsing heuristique basique
    return _local_parse_questionnaire_from_text(file_text, file_name)

def _local_parse_questionnaire_from_text(file_text, file_name):
    title = f"Import - {file_name.split('.')[0]}"
    desc = "Questionnaire extrait automatiquement par analyse textuelle locale."
    
    blocks = [
        {"block_type": "title", "content": {"title": title, "description": desc}},
        {"block_type": "section", "content": {"title": "Questions Extraites"}}
    ]
    
    if not file_text:
        blocks.append({"block_type": "question", "content": {"label": "Question exemple issue de l'import", "question_type": "text", "is_required": False}})
        return {"title": title, "description": desc, "blocks": blocks}
        
    lines = file_text.split('\n')
    question_count = 0
    
    for line in lines:
        line_clean = line.strip()
        if len(line_clean) < 6:
            continue
        
        # Heuristique : si la ligne se termine par un point d'interrogation, c'est une question
        if line_clean.endswith('?') or any(line_clean.lower().startswith(q) for q in ['quelle', 'quel', 'comment', 'pourquoi', 'qui', 'avez-vous', 'est-ce']):
            blocks.append({
                "block_type": "question",
                "content": {
                    "label": line_clean,
                    "question_type": "text",
                    "is_required": False,
                    "help_text": "Détecté par analyse textuelle"
                }
            })
            question_count += 1
            if question_count >= 12: # Limiter
                break
                
    if question_count == 0:
        # Prendre les 5 premières lignes significatives comme questions
        significant_lines = [l.strip() for l in lines if len(l.strip()) > 15][:5]
        for sl in significant_lines:
            blocks.append({
                "block_type": "question",
                "content": {
                    "label": sl,
                    "question_type": "text",
                    "is_required": False
                }
            })
            
    return {"title": title, "description": desc, "blocks": blocks}

