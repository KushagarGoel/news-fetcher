"""Tracxn API fetcher for startup intelligence."""

import logging
import os
from datetime import datetime, timedelta
from typing import Any

import requests

from src.fetchers.base import BaseFetcher
from src.models import Article, Category

logger = logging.getLogger(__name__)


class TracxnFetcher(BaseFetcher):
    """Fetch startup intelligence from Tracxn API."""

    BASE_URL = "https://api.tracxn.com/api/2/"
    CATEGORY = Category.COMPETITOR

    def __init__(
        self,
        api_key: str | None = None,
        name: str = "tracxn"
    ):
        """Initialize Tracxn fetcher.

        Args:
            api_key: Tracxn API key (defaults to TRACXN_API_KEY env var)
            name: Source name
        """
        super().__init__(name, self.CATEGORY)
        self.api_key = api_key or os.getenv("TRACXN_API_KEY")
        self._available = None

    def is_available(self) -> bool:
        """Check if Tracxn API is available (has API key)."""
        if self._available is not None:
            return self._available

        self._available = bool(self.api_key)
        if not self._available:
            logger.warning("Tracxn API key not found. Set TRACXN_API_KEY environment variable.")
        return self._available

    def fetch(self, max_articles: int = 20, **kwargs: Any) -> list[Article]:
        """Fetch startup intelligence from Tracxn.

        Args:
            max_articles: Maximum articles to fetch
            **kwargs: Additional parameters

        Returns:
            List of articles
        """
        if not self.is_available():
            logger.info("Tracxn fetcher skipped (no API key)")
            return []

        articles = []

        try:
            # Fetch recent funding news from Tracxn
            # Note: This is a simplified implementation - actual Tracxn API
            # may have different endpoints and authentication
            url = f"{self.BASE_URL}news"
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            params = {
                "count": max_articles,
                "days": 7,  # Last 7 days
                "topic": "funding"
            }

            response = requests.get(url, headers=headers, params=params, timeout=30)
            response.raise_for_status()

            data = response.json()

            for item in data.get("data", []):
                try:
                    article = self._parse_item(item)
                    if article:
                        articles.append(article)
                except Exception as e:
                    logger.error(f"Error parsing Tracxn item: {e}")

            logger.info(f"Tracxn fetcher: Retrieved {len(articles)} articles")

        except requests.exceptions.RequestException as e:
            logger.error(f"Tracxn API request failed: {e}")
        except Exception as e:
            logger.error(f"Tracxn fetcher error: {e}")

        return articles

    def _parse_item(self, item: dict) -> Article | None:
        """Parse a Tracxn API item into an Article.

        Args:
            item: Tracxn API item

        Returns:
            Article or None if parsing fails
        """
        title = item.get("title", "").strip()
        if not title:
            return None

        url = item.get("url", "").strip()
        if not url:
            return None

        # Parse date
        published_at = None
        date_str = item.get("published_date") or item.get("date")
        if date_str:
            try:
                published_at = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            except (ValueError, AttributeError):
                pass

        # Build content from description/summary
        content = item.get("description", "") or item.get("summary", "")

        # Get company/startup name
        company = item.get("company", "") or item.get("startup", "")

        article = self._create_article(
            title=title,
            url=url,
            content=content,
            published_at=published_at
        )

        # Add Tracxn-specific tags
        article.tags.extend(["tracxn", "startup", "funding"])
        if company:
            article.tags.append(f"company:{company}")
            article.competitor_mentions.append(company)

        # Mark as Indian content (Tracxn focuses on Indian startups)
        article.region = "IN"
        article.is_international = False

        return article
