"""LLM-based semantic duplicate grouping for articles."""

import json
import logging
from typing import Optional

import requests

from src.models import Article

logger = logging.getLogger(__name__)


class DuplicateGrouper:
    """Group semantically similar articles using LLM."""

    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        model: str = "llama3.2"
    ):
        """Initialize the duplicate grouper.

        Args:
            base_url: Ollama API base URL
            model: Model name for comparison
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

    def _extract_company(self, title: str) -> set[str]:
        """Extract potential company names from title.

        Args:
            title: Article title

        Returns:
            Set of potential company names (capitalized words)
        """
        words = title.split()
        companies = set()

        for word in words:
            # Clean and check if capitalized (potential company name)
            clean = ''.join(c for c in word if c.isalnum())
            if clean and clean[0].isupper() and len(clean) > 1:
                companies.add(clean.lower())

        return companies

    def _extract_funding_amount(self, title: str) -> list[str]:
        """Extract funding amounts from title.

        Args:
            title: Article title

        Returns:
            List of normalized funding amounts
        """
        import re
        amounts = []

        # Match patterns like $35m, $35 million, USD 35 Million, etc.
        patterns = [
            r'\$\s*(\d+(?:\.\d+)?)\s*[Mm](?:illion)?',
            r'USD\s*(\d+(?:\.\d+)?)\s*[Mm](?:illion)?',
            r'(\d+(?:\.\d+)?)\s*million',
            r'(\d+(?:\.\d+)?)\s*billion',
            r'(\d+(?:,\d+)*)\s*crore',
        ]

        for pattern in patterns:
            matches = re.findall(pattern, title, re.IGNORECASE)
            for match in matches:
                # Normalize: remove commas, convert to float
                if isinstance(match, str):
                    normalized = match.replace(',', '').replace(' ', '')
                    amounts.append(normalized)

        return amounts

    def _extract_event_type(self, title: str) -> str | None:
        """Extract event type from title.

        Args:
            title: Article title

        Returns:
            Event type keyword or None
        """
        title_lower = title.lower()

        event_keywords = {
            'funding': ['funding', 'raises', 'secured', 'investment', 'backs', 'bags'],
            'acquisition': ['acquires', 'acquired', 'acquisition', 'buys', 'buys out'],
            'revenue': ['revenue', 'profit', 'earnings', 'sales', 'turnover'],
            'product': ['launches', 'unveils', 'introduces', 'debuts'],
            'ipo': ['ipo', 'public offering', 'going public'],
            'layoffs': ['layoffs', 'lays off', 'job cuts'],
        }

        for event_type, keywords in event_keywords.items():
            if any(kw in title_lower for kw in keywords):
                return event_type

        return None

    def _compare_titles(self, title1: str, title2: str) -> bool:
        """Check if two titles refer to the same news using heuristics.

        Args:
            title1: First article title
            title2: Second article title

        Returns:
            True if titles are likely the same news
        """
        # Extract components
        companies1 = self._extract_company(title1)
        companies2 = self._extract_company(title2)

        # Must share at least one company name
        if not (companies1 & companies2):
            return False

        # Must be same event type
        event1 = self._extract_event_type(title1)
        event2 = self._extract_event_type(title2)

        if event1 and event2 and event1 != event2:
            # Different event types = different stories
            # Exception: funding news can have different phrasings
            return False

        # For funding news, check if amounts match
        if event1 == 'funding' or event2 == 'funding':
            amounts1 = self._extract_funding_amount(title1)
            amounts2 = self._extract_funding_amount(title2)

            # If both have amounts, they should match
            if amounts1 and amounts2:
                # Check for any overlap in normalized amounts
                if not (set(amounts1) & set(amounts2)):
                    return False
                # Same company + funding + same amount = likely same story
                return True

        # High word overlap = likely same story
        similarity = self._simple_similarity(title1, title2)
        if similarity > 0.6:
            return True

        # Same company + same event type but couldn't verify amount
        if event1 and event1 == event2:
            return True

        return False

    def _simple_similarity(self, s1: str, s2: str) -> float:
        """Simple word overlap similarity as fallback.

        Args:
            s1: First string
            s2: Second string

        Returns:
            Similarity score 0-1
        """
        words1 = set(s1.lower().split())
        words2 = set(s2.lower().split())

        if not words1 or not words2:
            return 0.0

        intersection = words1 & words2
        union = words1 | words2

        return len(intersection) / len(union)

    def group_articles(self, articles: list[Article]) -> list[list[Article]]:
        """Group articles by semantic similarity.

        Args:
            articles: List of articles to group

        Returns:
            List of article groups (each group is a list of similar articles)
        """
        if not articles:
            return []

        groups: list[list[Article]] = []
        ungrouped = articles.copy()

        while ungrouped:
            current = ungrouped.pop(0)
            current_group = [current]

            # Find all similar articles
            i = 0
            while i < len(ungrouped):
                other = ungrouped[i]

                if self._compare_titles(current.title, other.title):
                    current_group.append(other)
                    ungrouped.pop(i)
                else:
                    i += 1

            groups.append(current_group)

        return groups

    def mark_duplicates(
        self,
        articles: list[Article],
        prefer_source: Optional[str] = None
    ) -> list[Article]:
        """Mark articles for email sending, keeping one per duplicate group.

        Args:
            articles: List of articles to process
            prefer_source: Preferred source name to keep (e.g., "The Arc Web")

        Returns:
            Articles with send_in_mail flag set on one per group
        """
        if not articles:
            return []

        groups = self.group_articles(articles)
        result = []

        for group in groups:
            if len(group) == 1:
                # No duplicates, send this one
                group[0].send_in_mail = True
                group[0].duplicate_group_id = None
            else:
                # Multiple duplicates - pick best one to send
                selected = self._select_best_article(group, prefer_source)

                for article in group:
                    article.duplicate_group_id = group[0].id
                    article.send_in_mail = (article.id == selected.id)

            result.extend(group)

        logger.info(
            f"Grouped {len(articles)} articles into {len(groups)} groups, "
            f"{sum(1 for a in result if a.send_in_mail)} will be emailed"
        )

        return result

    def _select_best_article(
        self,
        group: list[Article],
        prefer_source: Optional[str] = None
    ) -> Article:
        """Select the best article from a duplicate group.

        Args:
            group: List of duplicate articles
            prefer_source: Preferred source name

        Returns:
            Best article to send
        """
        # Priority: preferred source > has summary > first in list
        if prefer_source:
            for article in group:
                if prefer_source.lower() in article.source.lower():
                    return article

        # Prefer articles with summaries
        for article in group:
            if article.summary and len(article.summary) > 50:
                return article

        # Default to first
        return group[0]
