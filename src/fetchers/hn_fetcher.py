"""Hacker News API fetcher."""

import logging
from datetime import datetime
from typing import Any

import requests

from src.fetchers.base import BaseFetcher
from src.models import Article, Category

logger = logging.getLogger(__name__)


class HNFetcher(BaseFetcher):
    """Fetch articles from Hacker News API."""

    BASE_URL = "https://hacker-news.firebaseio.com/v0"

    def __init__(
        self,
        name: str = "hacker_news",
        category: Category = Category.TECH,
        timeout: int = 30,
        min_score: int = 50
    ):
        """Initialize HN fetcher.

        Args:
            name: Name of this source
            category: Category for articles
            timeout: Request timeout
            min_score: Minimum score to include article
        """
        super().__init__(name, category)
        self.timeout = timeout
        self.min_score = min_score

    def fetch(
        self,
        story_type: str = "top",
        max_articles: int = 30,
        **kwargs: Any
    ) -> list[Article]:
        """Fetch articles from Hacker News.

        Args:
            story_type: Type of stories - top, new, best, ask, show, job
            max_articles: Maximum number of articles
            **kwargs: Additional parameters

        Returns:
            List of articles
        """
        articles = []

        try:
            # Get story IDs
            story_ids = self._get_story_ids(story_type, max_articles)
            logger.info(f"Found {len(story_ids)} {story_type} stories on HN")

            # Fetch each story
            for story_id in story_ids[:max_articles * 2]:  # Fetch extra for filtering
                if len(articles) >= max_articles:
                    break

                try:
                    story = self._get_story(story_id)
                    if story:
                        article = self._convert_to_article(story)
                        # Filter by score
                        if story.get("score", 0) >= self.min_score:
                            articles.append(article)
                except Exception as e:
                    logger.error(f"Error fetching story {story_id}: {e}")

        except Exception as e:
            logger.error(f"Failed to fetch from HN: {e}")

        return articles[:max_articles]

    def _get_story_ids(self, story_type: str, limit: int) -> list[int]:
        """Get list of story IDs.

        Args:
            story_type: Type of stories
            limit: Maximum number to fetch

        Returns:
            List of story IDs
        """
        endpoints = {
            "top": "topstories",
            "new": "newstories",
            "best": "beststories",
            "ask": "askstories",
            "show": "showstories",
            "job": "jobstories"
        }

        endpoint = endpoints.get(story_type, "topstories")
        url = f"{self.BASE_URL}/{endpoint}.json"

        response = requests.get(url, timeout=self.timeout)
        response.raise_for_status()

        return response.json()[:limit]

    def _get_story(self, story_id: int) -> dict[str, Any] | None:
        """Fetch a single story by ID.

        Args:
            story_id: HN story ID

        Returns:
            Story data or None
        """
        url = f"{self.BASE_URL}/item/{story_id}.json"

        response = requests.get(url, timeout=self.timeout)
        response.raise_for_status()

        story = response.json()

        # Skip deleted or dead items
        if story.get("deleted") or story.get("dead"):
            return None

        return story

    def _convert_to_article(self, story: dict[str, Any]) -> Article:
        """Convert HN story to Article.

        Args:
            story: HN story data

        Returns:
            Article instance
        """
        title = story.get("title", "")
        url = story.get("url", "")

        # If no URL (e.g., ask HN), use HN item URL
        if not url:
            url = f"https://news.ycombinator.com/item?id={story.get('id')}"

        # Get timestamp
        time_stamp = story.get("time")
        published_at = None
        if time_stamp:
            published_at = datetime.fromtimestamp(time_stamp)

        # Build content from text and metadata
        content_parts = []
        if story.get("text"):
            content_parts.append(story["text"])

        # Add HN metadata
        score = story.get("score", 0)
        descendants = story.get("descendants", 0)
        by = story.get("by", "")

        content_parts.append(f"Score: {score} points")
        content_parts.append(f"Comments: {descendants}")
        content_parts.append(f"By: {by}")

        content = "\n".join(content_parts)

        # Add HN-specific tags
        tags = []
        if story.get("type") == "job":
            tags.append("jobs")
        if story.get("type") == "ask":
            tags.append("ask_hn")
        if score > 200:
            tags.append("high_score")

        return self._create_article(
            title=title,
            url=url,
            content=content,
            published_at=published_at,
            tags=tags
        )
