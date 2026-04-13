import logging
import google.generativeai as genai
from llm.base import LLMProvider
from llm.factory import LLMFactory
import config

logger = logging.getLogger(__name__)


class GeminiProvider(LLMProvider):
    """Google Gemini LLM provider."""

    def __init__(self, **kwargs):
        api_key = kwargs.get("api_key", config.GOOGLE_API_KEY)
        if not api_key:
            raise ValueError("GOOGLE_API_KEY is required for Gemini provider.")
        logger.info("Configuring Gemini provider with model gemma-3-1b-it")
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel("gemma-3-1b-it")

    def generate(self, prompt: str, context: str) -> str:
        system_prompt = (
            "You are a helpful assistant. Use the following context to answer "
            "the user's question. If the context doesn't contain relevant "
            "information, say so and answer based on your general knowledge.\n\n"
            f"--- Context ---\n{context}\n--- End Context ---"
        )
        full_prompt = f"{system_prompt}\n\nUser: {prompt}"
        logger.info("Generating response for prompt: %s", prompt[:80])
        response = self.model.generate_content(full_prompt)
        logger.info("Generated response: %d characters", len(response.text))
        return response.text

    def generate_portfolio(
        self, prompt: str, context: str, contact_details: dict
    ) -> str:
        contact_str = "\n".join(f"  {k}: {v}" for k, v in contact_details.items())
        system_prompt = (
            "You are roleplaying as the person described in the portfolio/resume below. "
            "Respond in first person as if you ARE this person.\n\n"
            "IMPORTANT RULES:\n"
            "- Keep responses short and concise (1-3 sentences). Only answer what is asked. Do not overexplain.\n"
            "- Always stay in character as the portfolio person.\n"
            "- ALWAYS derive your answers from the resume/portfolio content below. "
            "Look for relevant experience, companies, skills, and projects that relate to the question.\n"
            "- When the user asks if you can help with something (e.g. 'can you help me build a sales company?'), "
            "check the resume for related experience. If found, reference specific companies, roles, or projects "
            "from your resume and offer to discuss further. Example: 'Yes, I worked at [Company] in a similar role "
            "where I [relevant experience]. What specifically do you need help with?'\n"
            "- When asked about contact details, share them from the info below.\n"
            "- When asked to draft an email, compose a professional email addressed "
            "TO the contact email shown below (as if someone is writing to this person). "
            "Include a subject line, greeting, body, and sign-off.\n"
            "- If asked something truly not related to anything in the portfolio, say you'd prefer to discuss "
            "what's on your portfolio and direct them to reach out via your contact details.\n\n"
            f"--- Contact Details ---\n{contact_str}\n--- End Contact Details ---\n\n"
            f"--- Portfolio Content ---\n{context}\n--- End Portfolio Content ---"
        )
        full_prompt = f"{system_prompt}\n\nUser: {prompt}"
        logger.info("Generating portfolio response for prompt: %s", prompt[:80])
        response = self.model.generate_content(full_prompt)
        logger.info("Generated portfolio response: %d characters", len(response.text))
        return response.text


LLMFactory.register("gemini", GeminiProvider)
