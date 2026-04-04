"""Medium RSS feed fetcher."""

import logging
from datetime import datetime
from time import mktime
from typing import Any

import feedparser

from src.fetchers.base import BaseFetcher
from src.models import Article, Category

logger = logging.getLogger(__name__)


class MediumFetcher(BaseFetcher):
    """Fetch articles from Medium RSS feeds."""

    def __init__(
        self,
        name: str,
        tag: str | None = None,
        publication: str | None = None,
        username: str | None = None,
        category: Category = Category.TECH,
        timeout: int = 30
    ):
        """Initialize Medium fetcher.

        Args:
            name: Name of this source
            tag: Tag/topic to fetch (e.g., 'fintech', 'python')
            publication: Publication name (e.g., 'towards-data-science')
            username: Username for user feed
            category: Category for articles
            timeout: Request timeout

        Note:
            Provide exactly one of: tag, publication, or username
        """
        super().__init__(name, category)
        self.timeout = timeout

        # Build RSS URL based on source type
        if tag:
            self.feed_url = f"https://medium.com/feed/tag/{tag}"
            self.source_type = f"tag:{tag}"
        elif publication:
            self.feed_url = f"https://medium.com/feed/{publication}"
            self.source_type = f"pub:{publication}"
        elif username:
            self.feed_url = f"https://medium.com/feed/@{username}"
            self.source_type = f"user:{username}"
        else:
            raise ValueError("Must provide tag, publication, or username")

    def fetch(self, max_articles: int = 20, **kwargs: Any) -> list[Article]:
        """Fetch articles from Medium RSS feed.

        Args:
            max_articles: Maximum articles to fetch
            **kwargs: Additional parameters

        Returns:
            List of articles
        """
        articles = []

        try:
            feed = feedparser.parse(self.feed_url)

            if feed.bozo:
                logger.warning(f"Feed parsing warning: {feed.bozo_exception}")

            logger.info(f"Fetched {len(feed.entries)} entries from Medium ({self.source_type})")

            for entry in feed.entries[:max_articles]:
                try:
                    article = self._parse_entry(entry)
                    if article:
                        articles.append(article)
                except Exception as e:
                    logger.error(f"Error parsing Medium entry: {e}")

        except Exception as e:
            logger.error(f"Failed to fetch Medium feed: {e}")

        return articles

    def _parse_entry(self, entry: Any) -> Article | None:
        """Parse a feed entry into an Article.

        Args:
            entry: feedparser entry

        Returns:
            Article or None
        """
        # Get title
        title = entry.get("title", "").strip()
        if not title:
            return None

        # Get URL
        url = entry.get("link", "")
        if not url:
            return None

        # Clean up Medium URL (remove tracking params)
        url = url.split("?")[0]

        # Get published date
        published_at = None
        if entry.get("published_parsed"):
            published_at = datetime.fromtimestamp(mktime(entry.published_parsed))

        # Get content
        content = ""
        if entry.get("content"):
            content = entry.content[0].get("value", "")
        elif entry.get("summary"):
            content = entry.summary

        # Clean HTML
        content = self._clean_html(content)

        # Get author
        author = ""
        if entry.get("author"):
            author = entry.author

        # Build summary (Medium often puts a snippet in summary)
        summary = ""
        if entry.get("summary") and len(entry.summary) < 1000:
            summary = self._clean_html(entry.summary)

        return self._create_article(
            title=title,
            url=url,
            content=content,
            summary=summary,
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
            import re
            text = re.sub(r"<[^>]+>", " ", html)
            return re.sub(r"\s+", " ", text).strip()


class MediumTagFetcher(MediumFetcher):
    """Convenience fetcher for Medium tags."""

    def __init__(self, tag: str, category: Category = Category.TECH):
        """Initialize for a specific tag.

        Args:
            tag: Tag to follow (e.g., 'fintech', 'blockchain')
            category: Category for articles
        """
        super().__init__(
            name=f"medium_{tag}",
            tag=tag,
            category=category
        )
