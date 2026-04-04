"""Ollama embedding integration for local embeddings."""

import logging
from typing import Optional

import requests
from tenacity import retry, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)


class OllamaEmbedder:
    """Client for generating embeddings using Ollama local models."""

    def __init__(
        self,
        model: str = "nomic-embed-text",
        base_url: str = "http://localhost:11434",
        timeout: int = 30
    ):
        """Initialize the Ollama embedder.

        Args:
            model: Name of the Ollama model to use
            base_url: Base URL for Ollama API
            timeout: Request timeout in seconds
        """
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._check_model()

    def _check_model(self) -> None:
        """Check if the model is available in Ollama."""
        try:
            response = requests.get(
                f"{self.base_url}/api/tags",
                timeout=self.timeout
            )
            response.raise_for_status()
            models = response.json().get("models", [])
            model_names = [m.get("name", "").split(":")[0] for m in models]

            if self.model not in model_names:
                logger.warning(
                    f"Model '{self.model}' not found in Ollama. "
                    f"Available models: {model_names}. "
                    f"Run: ollama pull {self.model}"
                )
        except requests.RequestException as e:
            logger.error(f"Cannot connect to Ollama at {self.base_url}: {e}")
            raise ConnectionError(
                f"Ollama is not running at {self.base_url}. "
                "Please start Ollama first."
            ) from e

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=True
    )
    def embed(self, text: str) -> list[float]:
        """Generate embedding for a single text.

        Args:
            text: Text to embed

        Returns:
            List of floats representing the embedding vector

        Raises:
            ConnectionError: If Ollama is not available
            RuntimeError: If embedding generation fails
        """
        if not text or not text.strip():
            raise ValueError("Cannot embed empty text")

        # Truncate very long texts
        text = text[:8000]

        try:
            response = requests.post(
                f"{self.base_url}/api/embeddings",
                json={
                    "model": self.model,
                    "prompt": text
                },
                timeout=self.timeout
            )
            response.raise_for_status()
            result = response.json()
            return result["embedding"]
        except requests.RequestException as e:
            logger.error(f"Failed to generate embedding: {e}")
            raise RuntimeError(f"Embedding generation failed: {e}") from e

    def embed_batch(self, texts: list[str], batch_size: int = 8) -> list[list[float]]:
        """Generate embeddings for multiple texts.

        Args:
            texts: List of texts to embed
            batch_size: Number of texts to process at once

        Returns:
            List of embedding vectors
        """
        embeddings = []
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            for text in batch:
                try:
                    embedding = self.embed(text)
                    embeddings.append(embedding)
                except Exception as e:
                    logger.error(f"Failed to embed text: {e}")
                    # Return zero vector as fallback
                    dim = self.get_embedding_dimension()
                    embeddings.append([0.0] * dim)
        return embeddings

    def get_embedding_dimension(self) -> int:
        """Get the dimension of embeddings from this model.

        Returns:
            Embedding dimension
        """
        # Common Ollama embedding model dimensions
        dimensions = {
            "nomic-embed-text": 768,
            "mxbai-embed-large": 1024,
            "snowflake-arctic-embed": 1024,
            "all-minilm": 384,
        }
        return dimensions.get(self.model, 768)

    def is_available(self) -> bool:
        """Check if Ollama is available and the model is loaded.

        Returns:
            True if available, False otherwise
        """
        try:
            response = requests.get(
                f"{self.base_url}/api/tags",
                timeout=5
            )
            return response.status_code == 200
        except requests.RequestException:
            return False
