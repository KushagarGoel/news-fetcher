"""Time-based article filtering."""

import logging
from datetime import datetime, timedelta

from src.models import Article

logger = logging.getLogger(__name__)


class TimeFilter:
    """Filter articles by publication time."""

    def __init__(self, hours: int = 24):
        """Initialize the time filter.

        Args:
            hours: Number of hours to look back (default: 24)
        """
        self.hours = hours
        self.cutoff = datetime.utcnow() - timedelta(hours=hours)
        logger.info(f"TimeFilter initialized with {hours}h window (cutoff: {self.cutoff.isoformat()})")

    def is_recent(self, article: Article) -> bool:
        """Check if article is within the time window.

        Args:
            article: Article to check

        Returns:
            True if article is recent or has no date, False otherwise
        """
        if not article.published_at:
            # Include articles without dates (safer to include than exclude)
            return True

        is_recent = article.published_at >= self.cutoff

        if not is_recent:
            logger.debug(
                f"Article filtered by time: {article.title[:50]}... "
                f"(published: {article.published_at.isoformat()}, cutoff: {self.cutoff.isoformat()})"
            )

        return is_recent

    def filter_articles(self, articles: list[Article]) -> list[Article]:
        """Filter a list of articles by time.

        Args:
            articles: List of articles to filter

        Returns:
            List of recent articles
        """
        recent = [a for a in articles if self.is_recent(a)]
        filtered_count = len(articles) - len(recent)

        if filtered_count > 0:
            logger.info(f"Time filter: {len(recent)}/{len(articles)} articles passed ({filtered_count} filtered)")
        else:
            logger.info(f"Time filter: All {len(articles)} articles passed")

        return recent
