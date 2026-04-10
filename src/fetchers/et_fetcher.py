"""Economic Times RSS fetcher for Indian financial news."""

import logging
from typing import Any

from src.fetchers.rss_fetcher import RSSFetcher
from src.models import Article, Category

logger = logging.getLogger(__name__)


class EconomicTimesFetcher(RSSFetcher):
    """Fetch articles from Economic Times RSS feeds."""

    RSS_FEEDS = {
        "tech": "https://economictimes.indiatimes.com/tech/rssfeeds/13357270.cms",
        "industry": "https://economictimes.indiatimes.com/industry/rssfeeds/13352306.cms",
        "fintech": "https://economictimes.indiatimes.com/prime/fintech-and-bfsi/rssfeeds/91925810.cms",
        "companies": "https://economictimes.indiatimes.com/news/company/rssfeeds/2143429.cms",
        "all": "https://economictimes.indiatimes.com/rssfeedsdefault.cms",
    }

    def __init__(
        self,
        category: Category = Category.TECH,
        section: str | None = None,
        name: str | None = None,
        keywords: list[str] | None = None
    ):
        """Initialize Economic Times fetcher.

        Args:
            category: Category for articles
            section: RSS section to use (tech, industry, fintech, companies, all)
            name: Optional custom source name
            keywords: Optional list of keywords for relevance filtering
        """
        # Map category to default section if not specified
        if section is None:
            section = self._get_section_for_category(category)

        feed_url = self.RSS_FEEDS.get(section, self.RSS_FEEDS["all"])
        source_name = name or f"et_{section}_{category.value}"

        super().__init__(
            name=source_name,
            feed_url=feed_url,
            category=category
        )
        self.section = section
        self.keywords = keywords or []

    def _get_section_for_category(self, category: Category) -> str:
        """Map category to default RSS section.

        Args:
            category: Article category

        Returns:
            RSS section name
        """
        # Use fintech feed for industry - much more relevant than generic industry feed
        mapping = {
            Category.TECH: "tech",
            Category.INDUSTRY: "fintech",  # Use fintech-specific feed
            Category.COMPETITOR: "companies",  # Will filter by keywords
            Category.CLIENTS: "companies",     # Will filter by keywords
        }
        return mapping.get(category, "all")

    def _is_relevant(self, article: Article) -> bool:
        """Check if article is fintech/lending relevant.

        Args:
            article: Article to check

        Returns:
            True if relevant to fintech/lending
        """
        if not self.keywords:
            return True  # No filtering if no keywords provided

        text = (article.title + " " + article.content).lower()

        for keyword in self.keywords:
            if keyword.lower() in text:
                return True

        return False

    def fetch(self, max_articles: int = 20, **kwargs: Any) -> list[Article]:
        """Fetch articles from Economic Times.

        Args:
            max_articles: Maximum articles to fetch
            **kwargs: Additional parameters

        Returns:
            List of articles
        """
        articles = super().fetch(max_articles=max_articles * 2, **kwargs)  # Fetch more for filtering

        # Filter for fintech/lending relevance (for companies section)
        if self.section in ("companies", "industry", "all"):
            original_count = len(articles)
            articles = [a for a in articles if self._is_relevant(a)]
            filtered_count = original_count - len(articles)
            if filtered_count > 0:
                logger.info(f"Economic Times filtered {filtered_count} non-relevant articles")

        # Limit to requested max after filtering
        articles = articles[:max_articles]

        # Tag all articles
        for article in articles:
            if "economic_times" not in article.tags:
                article.tags.append("economic_times")
            if self.section not in article.tags:
                article.tags.append(self.section)
            # Mark as Indian content
            article.region = "IN"
            article.is_international = False

        logger.info(f"Economic Times fetcher ({self.section}): Retrieved {len(articles)} articles")
        return articles
