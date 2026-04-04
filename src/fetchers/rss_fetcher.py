"""RSS feed fetcher for Google News and other RSS sources."""

import logging
from datetime import datetime
from time import mktime
from typing import Any

import feedparser
import requests

from src.fetchers.base import BaseFetcher
from src.models import Article, Category

logger = logging.getLogger(__name__)


class RSSFetcher(BaseFetcher):
    """Fetch articles from RSS feeds."""

    def __init__(
        self,
        name: str,
        feed_url: str,
        category: Category,
        timeout: int = 30
    ):
        """Initialize RSS fetcher.

        Args:
            name: Name of this source
            feed_url: URL of the RSS feed
            category: Category for articles
            timeout: Request timeout in seconds
        """
        super().__init__(name, category)
        self.feed_url = feed_url
        self.timeout = timeout

    def fetch(self, max_articles: int = 20, **kwargs: Any) -> list[Article]:
        """Fetch articles from the RSS feed.

        Args:
            max_articles: Maximum number of articles to fetch
            **kwargs: Additional parameters (ignored)

        Returns:
            List of articles
        """
        articles = []

        try:
            # Parse the feed
            feed = feedparser.parse(self.feed_url)

            if feed.bozo:
                logger.warning(f"Feed parsing warning for {self.name}: {feed.bozo_exception}")

            logger.info(f"Fetched {len(feed.entries)} entries from {self.name}")

            for entry in feed.entries[:max_articles]:
                try:
                    article = self._parse_entry(entry)
                    if article:
                        articles.append(article)
                except Exception as e:
                    logger.error(f"Error parsing entry from {self.name}: {e}")

        except Exception as e:
            logger.error(f"Failed to fetch RSS from {self.name}: {e}")

        return articles

    def _parse_entry(self, entry: Any) -> Article | None:
        """Parse a feed entry into an Article.

        Args:
            entry: feedparser entry

        Returns:
            Article or None if parsing fails
        """
        # Get title
        title = entry.get("title", "").strip()
        if not title:
            return None

        # Get URL
        url = ""
        if entry.get("link"):
            url = entry.link
        elif entry.get("id"):
            url = entry.id

        if not url:
            return None

        # Get published date
        published_at = None
        if entry.get("published_parsed"):
            published_at = datetime.fromtimestamp(mktime(entry.published_parsed))
        elif entry.get("updated_parsed"):
            published_at = datetime.fromtimestamp(mktime(entry.updated_parsed))

        # Get content/summary
        content = ""
        if entry.get("content"):
            content = entry.content[0].get("value", "")
        elif entry.get("summary"):
            content = entry.summary
        elif entry.get("description"):
            content = entry.description

        # Clean HTML from content if needed
        content = self._clean_html(content)

        return self._create_article(
            title=title,
            url=url,
            content=content,
            published_at=published_at
        )

    def _clean_html(self, html: str) -> str:
        """Remove HTML tags from text.

        Args:
            html: HTML content

        Returns:
            Plain text
        """
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html, "html.parser")
            return soup.get_text(separator=" ", strip=True)
        except ImportError:
            # Fallback: simple regex
            import re
            text = re.sub(r"<[^>]+>", " ", html)
            return re.sub(r"\s+", " ", text).strip()


class GoogleNewsFetcher(RSSFetcher):
    """Specialized fetcher for Google News RSS feeds."""

    def __init__(
        self,
        name: str,
        search_query: str,
        category: Category,
        region: str = "IN",
        language: str = "en"
    ):
        """Initialize Google News fetcher.

        Args:
            name: Name of this source
            search_query: Search query string
            category: Category for articles
            region: Region code (default: IN for India)
            language: Language code (default: en)
        """
        # Build Google News RSS URL
        import urllib.parse
        encoded_query = urllib.parse.quote(search_query)
        feed_url = f"https://news.google.com/rss/search?q={encoded_query}&hl={language}-{region}&gl={region}&ceid={region}:{language}"

        super().__init__(name, feed_url, category)
        self.search_query = search_query

    def _parse_entry(self, entry: Any) -> Article | None:
        """Parse entry, handling Google News specific fields.

        Args:
            entry: feedparser entry

        Returns:
            Article or None
        """
        article = super()._parse_entry(entry)

        if article and entry.get("source"):
            # Google News includes source in the feed
            if hasattr(entry.source, "title"):
                article.source = f"{self.name} - {entry.source.title}"

        return article
