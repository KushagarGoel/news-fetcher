"""URL accessibility checker."""

import logging
from urllib.parse import urlparse

import requests

logger = logging.getLogger(__name__)


class URLChecker:
    """Check if a URL is accessible before processing."""

    def __init__(self, timeout: int = 10, max_redirects: int = 5):
        """Initialize URL checker.

        Args:
            timeout: Request timeout in seconds
            max_redirects: Maximum number of redirects to follow
        """
        self.timeout = timeout
        self.max_redirects = max_redirects
        self._session = requests.Session()
        self._session.max_redirects = max_redirects

    def is_accessible(self, url: str) -> bool:
        """Check if URL is accessible (returns 200 OK).

        Args:
            url: URL to check

        Returns:
            True if accessible, False otherwise
        """
        if not url:
            return False

        # Skip non-HTTP URLs
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            return False

        try:
            response = self._session.head(
                url,
                timeout=self.timeout,
                allow_redirects=True,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                }
            )
            # Accept 2xx status codes
            return 200 <= response.status_code < 300

        except requests.RequestException as e:
            logger.debug(f"URL not accessible (HEAD): {url} - {e}")
            # Try GET if HEAD fails (some servers don't support HEAD)
            return self._try_get(url)

    def _try_get(self, url: str) -> bool:
        """Fallback GET request to check accessibility.

        Args:
            url: URL to check

        Returns:
            True if accessible
        """
        try:
            response = self._session.get(
                url,
                timeout=self.timeout,
                stream=True,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                }
            )
            # Just check status, don't download full content
            response.close()
            return 200 <= response.status_code < 300

        except requests.RequestException as e:
            logger.debug(f"URL not accessible (GET): {url} - {e}")
            return False

    def check_batch(self, urls: list[str]) -> dict[str, bool]:
        """Check accessibility of multiple URLs.

        Args:
            urls: List of URLs to check

        Returns:
            Dict mapping URL to accessibility status
        """
        return {url: self.is_accessible(url) for url in urls}
