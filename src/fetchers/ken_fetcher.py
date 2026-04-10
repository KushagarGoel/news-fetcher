"""The Ken RSS fetcher for premium Indian business news."""

import logging
from typing import Any

from src.fetchers.rss_fetcher import RSSFetcher
from src.models import Article, Category

logger = logging.getLogger(__name__)


class TheKenFetcher(RSSFetcher):
    """Fetch articles from The Ken RSS feed."""

    RSS_URL = "https://the-ken.com/feed/"

    def __init__(self, category: Category = Category.TECH, name: str | None = None, keywords: list[str] | None = None):
        """Initialize The Ken fetcher.

        Args:
            category: Category for articles (default: TECH)
            name: Optional custom source name
            keywords: Optional list of keywords for relevance filtering
        """
        source_name = name or f"the_ken_{category.value}"
        super().__init__(
            name=source_name,
            feed_url=self.RSS_URL,
            category=category
        )
        self.keywords = keywords or []

    def _is_relevant(self, article: Article) -> bool:
        """Check if article is fintech/lending relevant.

        Args:
            article: Article to check

        Returns:
            True if relevant
        """
        if not self.keywords:
            return True  # No filtering if no keywords provided

        text = (article.title + " " + article.content).lower()

        for keyword in self.keywords:
            if keyword.lower() in text:
                return True

        return False

    def fetch(self, max_articles: int = 20, **kwargs: Any) -> list[Article]:
        """Fetch articles from The Ken.

        Args:
            max_articles: Maximum articles to fetch
            **kwargs: Additional parameters

        Returns:
            List of articles
        """
        articles = super().fetch(max_articles=max_articles * 2, **kwargs)  # Fetch more for filtering

        # Filter for relevance if keywords provided
        if self.keywords:
            original_count = len(articles)
            articles = [a for a in articles if self._is_relevant(a)]
            filtered_count = original_count - len(articles)
            if filtered_count > 0:
                logger.info(f"The Ken filtered {filtered_count} non-relevant articles")

        # Limit to requested max after filtering
        articles = articles[:max_articles]

        # Tag all articles
        for article in articles:
            if "the_ken" not in article.tags:
                article.tags.append("the_ken")
            if "premium" not in article.tags:
                article.tags.append("premium")
            # Mark as Indian content
            article.region = "IN"
            article.is_international = False

        logger.info(f"The Ken fetcher: Retrieved {len(articles)} articles")
        return articles
