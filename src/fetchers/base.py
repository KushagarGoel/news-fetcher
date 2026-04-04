"""Abstract base class for news fetchers."""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any

from src.models import Article, Category, FetchResult


class BaseFetcher(ABC):
    """Abstract base class for news fetchers."""

    def __init__(self, name: str, category: Category):
        """Initialize the fetcher.

        Args:
            name: Name of this fetcher/source
            category: Default category for articles from this source
        """
        self.name = name
        self.category = category

    @abstractmethod
    def fetch(self, **kwargs: Any) -> list[Article]:
        """Fetch articles from the source.

        Args:
            **kwargs: Additional fetch parameters

        Returns:
            List of fetched articles
        """
        pass

    def fetch_with_result(self, **kwargs: Any) -> FetchResult:
        """Fetch articles and return structured result.

        Args:
            **kwargs: Additional fetch parameters

        Returns:
            FetchResult with details
        """
        result = FetchResult(
            source=self.name,
            category=self.category,
            articles_found=0,
            articles_added=0,
            articles_duplicated=0
        )

        try:
            articles = self.fetch(**kwargs)
            result.articles_found = len(articles)
        except Exception as e:
            result.errors.append(str(e))

        return result

    def _create_article(
        self,
        title: str,
        url: str,
        content: str = "",
        published_at: datetime | None = None,
        **kwargs: Any
    ) -> Article:
        """Create an Article instance with common fields.

        Args:
            title: Article title
            url: Article URL
            content: Article content/body
            published_at: Publication datetime
            **kwargs: Additional article fields

        Returns:
            Article instance
        """
        return Article(
            title=title,
            url=url,
            source=self.name,
            content=content,
            published_at=published_at,
            category=self.category,
            **kwargs
        )
