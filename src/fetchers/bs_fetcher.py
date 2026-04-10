"""Business Standard RSS fetcher for Indian business news."""

import logging
from typing import Any

from src.fetchers.rss_fetcher import RSSFetcher
from src.models import Article, Category

logger = logging.getLogger(__name__)


class BusinessStandardFetcher(RSSFetcher):
    """Fetch articles from Business Standard RSS feeds."""

    RSS_FEEDS = {
        "tech": "https://www.business-standard.com/rss/technology-101.rss",
        "companies": "https://www.business-standard.com/rss/companies-101.rss",
        "finance": "https://www.business-standard.com/rss/finance-101.rss",
        "economy": "https://www.business-standard.com/rss/economy-102.rss",
        "all": "https://www.business-standard.com/rss/latest.rss",
    }

    def __init__(
        self,
        category: Category = Category.TECH,
        section: str | None = None,
        name: str | None = None,
        keywords: list[str] | None = None
    ):
        """Initialize Business Standard fetcher.

        Args:
            category: Category for articles
            section: RSS section to use (tech, companies, finance, economy, all)
            name: Optional custom source name
            keywords: Optional list of keywords for relevance filtering
        """
        # Map category to default section if not specified
        if section is None:
            section = self._get_section_for_category(category)

        feed_url = self.RSS_FEEDS.get(section, self.RSS_FEEDS["all"])
        source_name = name or f"bs_{section}_{category.value}"

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
        mapping = {
            Category.TECH: "tech",
            Category.INDUSTRY: "finance",  # Use finance section for industry
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
        """Fetch articles from Business Standard.

        Args:
            max_articles: Maximum articles to fetch
            **kwargs: Additional parameters

        Returns:
            List of articles
        """
        articles = super().fetch(max_articles=max_articles * 2, **kwargs)  # Fetch more for filtering

        # Filter for fintech/lending relevance (for companies/economy sections)
        if self.section in ("companies", "economy", "all"):
            original_count = len(articles)
            articles = [a for a in articles if self._is_relevant(a)]
            filtered_count = original_count - len(articles)
            if filtered_count > 0:
                logger.info(f"Business Standard filtered {filtered_count} non-relevant articles")

        # Limit to requested max after filtering
        articles = articles[:max_articles]

        # Tag all articles
        for article in articles:
            if "business_standard" not in article.tags:
                article.tags.append("business_standard")
            if self.section not in article.tags:
                article.tags.append(self.section)
            # Mark as Indian content
            article.region = "IN"
            article.is_international = False

        logger.info(f"Business Standard fetcher ({self.section}): Retrieved {len(articles)} articles")
        return articles
