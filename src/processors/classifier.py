"""Article classifier for category and entity detection."""

import logging
import re
from pathlib import Path
from typing import Any, Optional

import yaml

from src.models import Article, Category, ClientConfig, ClientType, Competitor

logger = logging.getLogger(__name__)


class Classifier:
    """Classify articles into categories and detect entities."""

    def __init__(
        self,
        competitors_file: str = "config/competitors.yaml",
        clients_file: str = "config/clients.yaml",
        keywords_file: str = "config/keywords.yaml"
    ):
        """Initialize the classifier with configuration files.

        Args:
            competitors_file: Path to competitors YAML config
            clients_file: Path to clients YAML config
            keywords_file: Path to keywords YAML config
        """
        self.competitors: list[Competitor] = []
        self.lenders: list[ClientConfig] = []
        self.merchants: list[ClientConfig] = []
        self.industry_keywords: list[str] = []
        self.tech_keywords: list[str] = []

        self._load_configs(competitors_file, clients_file, keywords_file)

    def _load_configs(
        self,
        competitors_file: str,
        clients_file: str,
        keywords_file: str
    ) -> None:
        """Load all configuration files."""
        base_path = Path(__file__).parent.parent.parent

        # Load competitors
        try:
            with open(base_path / competitors_file, "r") as f:
                data = yaml.safe_load(f)
                for comp in data.get("competitors", []):
                    self.competitors.append(Competitor(**comp))
            logger.info(f"Loaded {len(self.competitors)} competitors")
        except Exception as e:
            logger.error(f"Failed to load competitors: {e}")

        # Load clients
        try:
            with open(base_path / clients_file, "r") as f:
                data = yaml.safe_load(f)
                for lender in data.get("lenders", []):
                    self.lenders.append(
                        ClientConfig(client_type=ClientType.LENDER, **lender)
                    )
                for merchant in data.get("merchants", []):
                    self.merchants.append(
                        ClientConfig(client_type=ClientType.MERCHANT, **merchant)
                    )
            logger.info(f"Loaded {len(self.lenders)} lenders, {len(self.merchants)} merchants")
        except Exception as e:
            logger.error(f"Failed to load clients: {e}")

        # Load keywords
        try:
            with open(base_path / keywords_file, "r") as f:
                data = yaml.safe_load(f)
                self.industry_keywords = data.get("industry", [])
                self.tech_keywords = data.get("tech", [])
            logger.info(
                f"Loaded {len(self.industry_keywords)} industry, "
                f"{len(self.tech_keywords)} tech keywords"
            )
        except Exception as e:
            logger.error(f"Failed to load keywords: {e}")

    def _count_keyword_matches(self, text: str, keywords: list[str]) -> int:
        """Count how many keywords appear in the text (case-insensitive).

        Args:
            text: Text to search in
            keywords: List of keywords to match

        Returns:
            Number of matching keywords
        """
        text_lower = text.lower()
        count = 0
        for keyword in keywords:
            # Use word boundary for multi-word keywords
            if " " in keyword:
                if keyword.lower() in text_lower:
                    count += 1
            else:
                # Simple substring match for single words
                if keyword.lower() in text_lower:
                    count += 1
        return count

    def detect_competitors(self, article: Article) -> list[str]:
        """Detect which competitors are mentioned in the article.

        Args:
            article: Article to analyze

        Returns:
            List of competitor names mentioned
        """
        text = f"{article.title} {article.content}".lower()
        mentions = []

        for competitor in self.competitors:
            for keyword in competitor.keywords:
                if keyword.lower() in text:
                    mentions.append(competitor.name)
                    break

        return mentions

    def detect_clients(self, article: Article) -> list[dict[str, Any]]:
        """Detect which clients are mentioned in the article.

        Args:
            article: Article to analyze

        Returns:
            List of dicts with client name and type
        """
        text = f"{article.title} {article.content}".lower()
        mentions = []
        found_names = set()

        # Check lenders
        for lender in self.lenders:
            for keyword in lender.keywords:
                if keyword.lower() in text and lender.name not in found_names:
                    mentions.append({
                        "name": lender.name,
                        "type": ClientType.LENDER.value
                    })
                    found_names.add(lender.name)
                    break

        # Check merchants
        for merchant in self.merchants:
            for keyword in merchant.keywords:
                if keyword.lower() in text and merchant.name not in found_names:
                    mentions.append({
                        "name": merchant.name,
                        "type": ClientType.MERCHANT.value
                    })
                    found_names.add(merchant.name)
                    break

        return mentions

    def classify(self, article: Article) -> Category:
        """Classify article into a category based on content.

        Priority: competitor > clients > industry > tech

        Args:
            article: Article to classify

        Returns:
            Assigned category
        """
        text = f"{article.title} {article.content}"

        # Check for competitor mentions (highest priority)
        competitor_mentions = self.detect_competitors(article)
        if competitor_mentions:
            article.competitor_mentions = competitor_mentions
            article.matched_keywords = competitor_mentions
            return Category.COMPETITOR

        # Check for client mentions
        client_mentions = self.detect_clients(article)
        if client_mentions:
            article.client_mentions = client_mentions
            article.matched_keywords = [c["name"] for c in client_mentions]
            return Category.CLIENTS

        # Check industry keywords
        industry_matches = self._count_keyword_matches(text, self.industry_keywords)
        tech_matches = self._count_keyword_matches(text, self.tech_keywords)

        if industry_matches > 0 or tech_matches > 0:
            # Assign matched keywords
            if industry_matches >= tech_matches:
                matched = [
                    k for k in self.industry_keywords
                    if k.lower() in text.lower()
                ][:5]
                article.matched_keywords = matched
                return Category.INDUSTRY
            else:
                matched = [
                    k for k in self.tech_keywords
                    if k.lower() in text.lower()
                ][:5]
                article.matched_keywords = matched
                return Category.TECH

        # Default to industry if no clear match
        return Category.INDUSTRY

    def get_client_type(self, client_name: str) -> Optional[ClientType]:
        """Get the type of a client by name.

        Args:
            client_name: Name of the client

        Returns:
            ClientType if found, None otherwise
        """
        for lender in self.lenders:
            if lender.name == client_name:
                return ClientType.LENDER
        for merchant in self.merchants:
            if merchant.name == client_name:
                return ClientType.MERCHANT
        return None

    def get_all_competitor_names(self) -> list[str]:
        """Get list of all competitor names.

        Returns:
            List of competitor names
        """
        return [c.name for c in self.competitors]

    def get_all_client_names(self) -> list[str]:
        """Get list of all client names.

        Returns:
            List of client names
        """
        return [c.name for c in self.lenders + self.merchants]
