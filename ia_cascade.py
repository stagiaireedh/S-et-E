import logging
from config import Config

# Configuration du logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("IACascade")

class IACascade:
    """
    Classe orchestrant les appels aux API IA en cascade :
    Google Gemini -> Groq Cloud -> GitHub Models.
    """
    
    def __init__(self):
        # Récupération des clés chargées dans la config
        self.gemini_key = Config.GEMINI_API_KEY
        self.groq_key = Config.GROQ_API_KEY
        self.github_token = Config.GITHUB_TOKEN
        
    def generate(self, system_prompt, user_prompt):
        """
        Tente de générer une réponse en interrogeant les APIs dans l'ordre défini.
        Lève une Exception si tous les appels échouent ou si aucune clé n'est configurée.
        """
        errors = []
        
        # 1. ÉTAPE : GOOGLE GEMINI (gemini-2.5-flash)
        if self.gemini_key and not self.gemini_key.startswith("votre_cle"):
            try:
                logger.info("Tentative de génération avec Google Gemini (gemini-2.5-flash)...")
                response = self.call_gemini(system_prompt, user_prompt)
                if response:
                    logger.info("Succès avec Google Gemini.")
                    return response
            except Exception as e:
                err_msg = f"Erreur Gemini: {str(e)}"
                logger.warning(err_msg)
                errors.append(err_msg)
        else:
            logger.info("Clé Google Gemini absente ou non configurée. Passage à l'API suivante.")
            errors.append("Clé Gemini non configurée.")

        # 2. ÉTAPE : GROQ CLOUD (llama-3.3-70b-versatile)
        if self.groq_key and not self.groq_key.startswith("votre_cle"):
            try:
                logger.info("Tentative de génération avec Groq (llama-3.3-70b-versatile)...")
                response = self.call_groq(system_prompt, user_prompt)
                if response:
                    logger.info("Succès avec Groq Cloud.")
                    return response
            except Exception as e:
                err_msg = f"Erreur Groq: {str(e)}"
                logger.warning(err_msg)
                errors.append(err_msg)
        else:
            logger.info("Clé Groq Cloud absente ou non configurée. Passage à l'API suivante.")
            errors.append("Clé Groq non configurée.")

        # 3. ÉTAPE : GITHUB MODELS (gpt-4o)
        if self.github_token and not self.github_token.startswith("votre_token"):
            try:
                logger.info("Tentative de génération avec GitHub Models (gpt-4o)...")
                response = self.call_github_models(system_prompt, user_prompt)
                if response:
                    logger.info("Succès avec GitHub Models.")
                    return response
            except Exception as e:
                err_msg = f"Erreur GitHub Models: {str(e)}"
                logger.warning(err_msg)
                errors.append(err_msg)
        else:
            logger.info("Token GitHub Classic absent ou non configuré.")
            errors.append("Token GitHub non configuré.")
            
        # ÉCHEC TOTAL
        raise Exception(f"Échec total de la cascade d'IA. Détails des erreurs : {'; '.join(errors)}")

    def call_gemini(self, system_prompt, user_prompt):
        """Appelle l'API Google Gemini."""
        import google.generativeai as genai
        
        genai.configure(api_key=self.gemini_key)
        
        # Concaténation de l'instruction système pour Gemini
        model = genai.GenerativeModel(
            model_name="gemini-2.5-flash",
            system_instruction=system_prompt
        )
        
        response = model.generate_content(
            user_prompt,
            generation_config={"temperature": 0.2}
        )
        return response.text

    def call_groq(self, system_prompt, user_prompt):
        """Appelle l'API Groq Cloud."""
        from groq import Groq
        
        client = Groq(api_key=self.groq_key)
        
        completion = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.2,
            max_tokens=2048
        )
        return completion.choices[0].message.content

    def call_github_models(self, system_prompt, user_prompt):
        """Appelle l'API GitHub Models (via endpoint compatible OpenAI)."""
        from openai import OpenAI
        
        client = OpenAI(
            base_url="https://models.inference.ai.azure.com",
            api_key=self.github_token
        )
        
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.2,
            max_tokens=2048
        )
        return response.choices[0].message.content
