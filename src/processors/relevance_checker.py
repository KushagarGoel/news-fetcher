"""Content relevance checker using LLM."""

import json
import logging
from typing import Optional

import requests

from src.models import Article, Category

logger = logging.getLogger(__name__)


class RelevanceChecker:
    """Check if articles are relevant to their category using LLM."""

    # Category-specific relevance criteria (used as context)
    CATEGORY_CRITERIA = {
        Category.TECH: "Fintech technology, banking infrastructure, financial platforms",
        Category.INDUSTRY: "Indian fintech sector, digital payments, lending industry",
        Category.COMPETITOR: "Competitor business intelligence - executive moves, products, partnerships",
        Category.CLIENTS: "Banking partnerships, credit products, merchant financing",
    }

    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        model: str = "llama3.2"
    ):
        """Initialize the relevance checker.

        Args:
            base_url: Ollama API base URL
            model: Model name for evaluation
        """
        self.base_url = base_url.rstrip("/")
        self.model = model
        self._available: Optional[bool] = None

    def is_available(self) -> bool:
        """Check if Ollama is available."""
        if self._available is not None:
            return self._available

        try:
            response = requests.get(
                f"{self.base_url}/api/tags",
                timeout=5
            )
            self._available = response.status_code == 200
        except Exception:
            self._available = False

        return self._available

    def check_relevance(self, article: Article) -> bool:
        """Check if article is relevant to its category.

        Args:
            article: Article to check

        Returns:
            True if relevant, False otherwise
        """
        if not self.is_available():
            # Fallback: allow all if LLM not available
            return True

        criteria = self.CATEGORY_CRITERIA.get(article.category, "")
        if not criteria:
            return True

        prompt = f"""Task: Classify if article is RELEVANT for business intelligence.

Article: "{article.title}"

Rules:
RELEVANT = executive appointments | financial products | partnerships | expansions | funding
NOT RELEVANT = consumer product sales | phone deals | gadget reviews

Output ONLY JSON - no explanation, no thinking, just JSON:
{{"relevant": true, "reason": "executive appointment"}} or {{"relevant": false, "reason": "consumer product"}}

JSON:"""

        try:
            response = requests.post(
                f"{self.base_url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {"temperature": 0.1}
                },
                timeout=15
            )
            response.raise_for_status()

            result = response.json()
            response_text = result.get("response", "").strip()

            # Extract JSON from response
            if "{" in response_text:
                json_start = response_text.find("{")
                json_end = response_text.rfind("}") + 1
                json_str = response_text[json_start:json_end]
                parsed = json.loads(json_str)
                is_relevant = parsed.get("relevant", True)
                reason = parsed.get("reason", "")

                if not is_relevant:
                    logger.info(
                        f"Filtered out irrelevant article: {article.title[:50]}... "
                        f"Reason: {reason}"
                    )

                return is_relevant

            return True

        except Exception as e:
            logger.warning(f"Relevance check failed: {e}, allowing article")
            return True

    def filter_articles(self, articles: list[Article]) -> list[Article]:
        """Filter out irrelevant articles.

        Args:
            articles: List of articles to filter

        Returns:
            List of relevant articles only
        """
        if not self.is_available():
            logger.warning("Ollama not available, skipping relevance check")
            return articles

        relevant = []
        for article in articles:
            if self.check_relevance(article):
                relevant.append(article)

        logger.info(
            f"Relevance filter: {len(relevant)}/{len(articles)} articles passed"
        )
        return relevant
