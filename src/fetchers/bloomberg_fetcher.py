"""Bloomberg RSS fetcher for international business news."""

import logging
from typing import Any

from src.fetchers.rss_fetcher import RSSFetcher
from src.models import Article, Category

logger = logging.getLogger(__name__)


class BloombergFetcher(RSSFetcher):
    """Fetch from Bloomberg RSS with international content marking."""

    RSS_URL = "https://feeds.bloomberg.com/business/news.rss"
    CATEGORY = Category.TECH

    def __init__(self, name: str = "bloomberg"):
        """Initialize Bloomberg fetcher."""
        super().__init__(
            name=name,
            feed_url=self.RSS_URL,
            category=self.CATEGORY
        )

    def fetch(self, max_articles: int = 20, **kwargs: Any) -> list[Article]:
        """Fetch articles from Bloomberg.

        Args:
            max_articles: Maximum articles to fetch
            **kwargs: Additional parameters

        Returns:
            List of articles
        """
        articles = super().fetch(max_articles=max_articles, **kwargs)

        # Tag all articles as international
        for article in articles:
            if "bloomberg" not in article.tags:
                article.tags.append("bloomberg")
            if "international" not in article.tags:
                article.tags.append("international")

            # Mark as international content
            article.region = "INT"
            article.is_international = True

            # Set initial relevance score (will be refined by RelevanceChecker)
            article.relevance_score = 0.5

        logger.info(f"Bloomberg fetcher: Retrieved {len(articles)} articles (international)")
        return articles
