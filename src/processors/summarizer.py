"""LLM-based article summarizer using Ollama."""

import logging
from typing import Optional

import requests
from tenacity import retry, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)


class Summarizer:
    """Generate article summaries using local LLM via Ollama."""

    DEFAULT_PROMPT = """Summarize the following article in 2-3 sentences. Focus on the key points and main message. Be concise and informative.

Title: {title}

Content:
{content}

Summary:"""

    def __init__(
        self,
        model: str = "llama3.2",
        base_url: str = "http://localhost:11434",
        timeout: int = 60,
        max_content_length: int = 4000
    ):
        """Initialize the summarizer.

        Args:
            model: Ollama model name to use
            base_url: Base URL for Ollama API
            timeout: Request timeout in seconds
            max_content_length: Maximum content length to send to LLM
        """
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.max_content_length = max_content_length

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=True
    )
    def summarize(
        self,
        title: str,
        content: str,
        prompt_template: Optional[str] = None
    ) -> str:
        """Generate summary for article.

        Args:
            title: Article title
            content: Article content
            prompt_template: Optional custom prompt template

        Returns:
            Generated summary

        Raises:
            RuntimeError: If summarization fails
        """
        if not content:
            return ""

        # Truncate content if too long
        truncated_content = content[:self.max_content_length]
        if len(content) > self.max_content_length:
            truncated_content += "..."

        prompt = (prompt_template or self.DEFAULT_PROMPT).format(
            title=title,
            content=truncated_content
        )

        try:
            response = requests.post(
                f"{self.base_url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": 0.3,
                        "num_predict": 200  # Limit output tokens
                    }
                },
                timeout=self.timeout
            )
            response.raise_for_status()
            result = response.json()

            summary = result.get("response", "").strip()
            # Clean up the summary
            summary = self._clean_summary(summary)

            return summary

        except requests.RequestException as e:
            logger.error(f"Failed to generate summary: {e}")
            raise RuntimeError(f"Summarization failed: {e}") from e

    def _clean_summary(self, summary: str) -> str:
        """Clean up the generated summary.

        Args:
            summary: Raw summary from LLM

        Returns:
            Cleaned summary
        """
        # Remove common prefixes the model might add
        prefixes = [
            "Summary:",
            "Here's a summary:",
            "The summary is:",
            "In summary,",
        ]

        cleaned = summary.strip()
        for prefix in prefixes:
            if cleaned.lower().startswith(prefix.lower()):
                cleaned = cleaned[len(prefix):].strip()

        return cleaned

    def is_available(self) -> bool:
        """Check if Ollama is available and the model is loaded.

        Returns:
            True if available
        """
        try:
            response = requests.get(
                f"{self.base_url}/api/tags",
                timeout=5
            )
            if response.status_code != 200:
                return False

            # Check if model exists
            models = response.json().get("models", [])
            model_names = [m.get("name", "").split(":")[0] for m in models]
            return self.model in model_names

        except requests.RequestException:
            return False

    def get_fallback_summary(self, content: str, max_length: int = 200) -> str:
        """Generate a fallback extractive summary.

        Args:
            content: Article content
            max_length: Maximum summary length

        Returns:
            First few sentences as fallback
        """
        if not content:
            return ""

        # Take first paragraph or first N characters
        first_para = content.split("\n")[0]
        if len(first_para) > max_length:
            # Try to end at a sentence
            sentences = first_para.split(". ")
            summary = ""
            for sent in sentences:
                if len(summary) + len(sent) < max_length:
                    summary += sent + ". "
                else:
                    break
            return summary.strip()

        return first_para[:max_length]
