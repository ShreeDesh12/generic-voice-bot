from abc import ABC, abstractmethod


class LLMProvider(ABC):
    """Abstract base class for LLM providers."""

    @abstractmethod
    def generate(self, prompt: str, context: str) -> str:
        """Generate a response given a user prompt and context.

        Args:
            prompt: The user's question or instruction.
            context: Parsed content from the uploaded file or URL.

        Returns:
            The LLM's response text.
        """

    def generate_portfolio(
        self, prompt: str, context: str, contact_details: dict
    ) -> str:
        """Generate a roleplay response as the portfolio person.

        Default implementation falls back to generate().
        Subclasses can override for specialized behavior.
        """
        return self.generate(prompt, context)
