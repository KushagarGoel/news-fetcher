"""RBI (Reserve Bank of India) RSS fetcher for regulatory announcements."""

import logging
from typing import Any

from src.fetchers.rss_fetcher import RSSFetcher
from src.models import Article, Category

logger = logging.getLogger(__name__)


class RBIFetcher(RSSFetcher):
    """Fetch RBI press releases and notifications."""

    RSS_URL = "https://www.rbi.org.in/Scripts/RSSFeed.aspx?type=PR"
    CATEGORY = Category.INDUSTRY

    def __init__(self, name: str = "rbi_press"):
        """Initialize RBI fetcher."""
        super().__init__(
            name=name,
            feed_url=self.RSS_URL,
            category=self.CATEGORY
        )

    def fetch(self, max_articles: int = 20, **kwargs: Any) -> list[Article]:
        """Fetch RBI press releases.

        Args:
            max_articles: Maximum articles to fetch
            **kwargs: Additional parameters

        Returns:
            List of articles
        """
        articles = super().fetch(max_articles=max_articles, **kwargs)

        # Tag all articles as regulatory
        for article in articles:
            if "regulatory" not in article.tags:
                article.tags.append("regulatory")
            if "rbi" not in article.tags:
                article.tags.append("rbi")
            if "policy" not in article.tags:
                article.tags.append("policy")
            # Mark as Indian content
            article.region = "IN"
            article.is_international = False

        logger.info(f"RBI fetcher: Retrieved {len(articles)} press releases")
        return articles
