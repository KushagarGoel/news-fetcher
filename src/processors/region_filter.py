"""Region-based article filtering."""

import logging
from urllib.parse import urlparse

from src.models import Article

logger = logging.getLogger(__name__)


class RegionFilter:
    """Filter and score articles by region relevance."""

    # Domains that indicate Indian origin
    INDIAN_DOMAINS = [
        ".in",
        "india",
        "indian",
        "hindu",
        "timesofindia",
        "economictimes",
        "business-standard",
        "inc42",
        "the-ken",
        "yourstory",
        "livemint",
        "moneycontrol",
        "financialexpress",
        "rbi",
        "sebi",
        "paytm",
        "phonepe",
        "razorpay",
        "cred",
        "bhim",
        "upi",
        "juspay",
        "jupiter",
        "fi",
        "slice",
        "zestmoney",
        "earlysalary",
    ]

    # International sources that need high relevance threshold
    INTERNATIONAL_SOURCES = [
        "bloomberg",
        "reuters",
        "wsj",
        "ft.com",
        "nytimes",
        "washingtonpost",
        "techcrunch",
        "theverge",
        "wired",
        "arxiv",
    ]

    # Minimum relevance score for international articles to be included
    INTERNATIONAL_THRESHOLD = 0.8

    def detect_region(self, article: Article) -> str:
        """Detect region from URL and content.

        Args:
            article: Article to analyze

        Returns:
            ISO country code ("IN" for India, "INT" for international)
        """
        url = article.url.lower() if article.url else ""
        content = (article.title + " " + article.content).lower()

        # Check for Indian domain indicators
        parsed = urlparse(url)
        domain = parsed.netloc.lower()

        for indicator in self.INDIAN_DOMAINS:
            if indicator in domain or indicator in content[:500]:
                return "IN"

        # Check for international sources
        for source in self.INTERNATIONAL_SOURCES:
            if source in domain:
                return "INT"

        # Default to India for unknown sources (safe default for Indian fintech focus)
        return "IN"

    def is_international_source(self, article: Article) -> bool:
        """Check if article is from an international source.

        Args:
            article: Article to check

        Returns:
            True if from international source
        """
        url = article.url.lower() if article.url else ""
        parsed = urlparse(url)
        domain = parsed.netloc.lower()

        for source in self.INTERNATIONAL_SOURCES:
            if source in domain:
                return True

        return False

    def should_include(self, article: Article, min_relevance: float | None = None) -> bool:
        """Determine if article should be included based on region and relevance.

        Args:
            article: Article to evaluate
            min_relevance: Override the default international threshold

        Returns:
            True if article should be included
        """
        from src.models import Priority

        threshold = min_relevance or self.INTERNATIONAL_THRESHOLD

        # Always include Indian content
        if article.region == "IN" and not article.is_international:
            return True

        # For international content, only include if CRITICAL priority
        if article.is_international:
            # Only include international articles if they are CRITICAL priority
            if article.email_routing.priority == Priority.CRITICAL:
                logger.info(
                    f"Including international article (CRITICAL priority): "
                    f"{article.title[:50]}..."
                )
                return True
            else:
                logger.debug(
                    f"Filtering out international article (not CRITICAL): "
                    f"{article.title[:50]}..."
                )
                return False

        return True

    def apply_region_tags(self, article: Article) -> Article:
        """Apply region detection to an article in-place.

        Args:
            article: Article to tag

        Returns:
            The same article with region fields populated
        """
        article.region = self.detect_region(article)
        article.is_international = self.is_international_source(article)
        return article

    def filter_articles(self, articles: list[Article]) -> list[Article]:
        """Filter articles by region criteria.

        Args:
            articles: List of articles to filter

        Returns:
            Filtered list of articles
        """
        # First, apply region tags to all articles
        for article in articles:
            self.apply_region_tags(article)

        # Then filter based on region + relevance
        included = [a for a in articles if self.should_include(a)]
        filtered_count = len(articles) - len(included)

        if filtered_count > 0:
            logger.info(f"Region filter: {len(included)}/{len(articles)} articles passed ({filtered_count} filtered)")
        else:
            logger.info(f"Region filter: All {len(articles)} articles passed")

        return included
