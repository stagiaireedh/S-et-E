import logging
import httpx
import urllib3
from config import Config

# Désactivation des alertes InsecureRequestWarning en environnement local
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("IACascade")


class IACascade:
    """
    Classe orchestrant les appels aux API IA en cascade :
    1. Groq Cloud (qwen/qwen3.8-27b) - Ultra rapide, faible latence
    2. Google Gemini (gemini-1.5-flash)
    3. GitHub Models (gpt-4o)
    """

    def __init__(self):
        self.groq_key = Config.GROQ_API_KEY
        self.gemini_key = Config.GEMINI_API_KEY
        self.github_token = Config.GITHUB_TOKEN

    def generate(self, system_prompt, user_prompt):
        """Tente de générer une réponse en cascade."""
        errors = []

        # 1. ÉTAPE : GROQ CLOUD (qwen/qwen3.8-27b)
        if self.groq_key and not self.groq_key.startswith("votre_cle"):
            try:
                logger.info("Tentative de génération avec Groq (qwen/qwen3.8-27b)...")
                response = self.call_groq(system_prompt, user_prompt)
                if response:
                    logger.info("Succès avec Groq Cloud.")
                    return response
            except Exception as e:
                err_msg = f"Erreur Groq: {str(e)}"
                logger.warning(err_msg)
                errors.append(err_msg)

        # 2. ÉTAPE : GOOGLE GEMINI (gemini-1.5-flash)
        if self.gemini_key and not self.gemini_key.startswith("votre_cle"):
            try:
                logger.info("Tentative de génération avec Google Gemini...")
                response = self.call_gemini(system_prompt, user_prompt)
                if response:
                    logger.info("Succès avec Google Gemini.")
                    return response
            except Exception as e:
                err_msg = f"Erreur Gemini: {str(e)}"
                logger.warning(err_msg)
                errors.append(err_msg)

        # 3. ÉTAPE : GITHUB MODELS (gpt-4o)
        if self.github_token and not self.github_token.startswith("votre_token"):
            try:
                logger.info("Tentative de génération avec GitHub Models...")
                response = self.call_github_models(system_prompt, user_prompt)
                if response:
                    logger.info("Succès avec GitHub Models.")
                    return response
            except Exception as e:
                err_msg = f"Erreur GitHub Models: {str(e)}"
                logger.warning(err_msg)
                errors.append(err_msg)

        raise Exception(f"Échec total de la cascade d'IA. Détails : {'; '.join(errors)}")

    def call_groq(self, system_prompt, user_prompt):
        """Appelle l'API Groq Cloud via httpx avec verify=False et bascule rapide."""
        from groq import Groq
        http_client = httpx.Client(verify=False, timeout=12.0)
        client = Groq(api_key=self.groq_key, http_client=http_client, max_retries=0)

        completion = client.chat.completions.create(
            model="qwen/qwen3.8-27b",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.2,
            max_tokens=2048
        )
        return completion.choices[0].message.content

    def call_gemini(self, system_prompt, user_prompt):
        """Appelle l'API Google Gemini via REST."""
        import google.generativeai as genai
        genai.configure(api_key=self.gemini_key, transport="rest")
        model = genai.GenerativeModel(
            model_name="gemini-1.5-flash",
            system_instruction=system_prompt
        )
        response = model.generate_content(
            user_prompt,
            generation_config={"temperature": 0.2},
            request_options={"timeout": 12}
        )
        return response.text

    def call_github_models(self, system_prompt, user_prompt):
        """Appelle l'API GitHub Models."""
        from openai import OpenAI
        http_client = httpx.Client(verify=False, timeout=15.0)
        client = OpenAI(
            base_url="https://models.inference.ai.azure.com",
            api_key=self.github_token,
            http_client=http_client
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
