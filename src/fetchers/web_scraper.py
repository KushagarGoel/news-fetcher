"""Web scraper using Playwright for dynamic content."""

import logging
from datetime import datetime
from typing import Any

from src.fetchers.base import BaseFetcher
from src.models import Article, Category

logger = logging.getLogger(__name__)


class WebScraper(BaseFetcher):
    """Scrape articles from websites using Playwright."""

    def __init__(
        self,
        name: str,
        base_url: str,
        category: Category,
        article_selector: str,
        title_selector: str = "h1, h2, .title",
        content_selector: str = "article, .content, .post-content",
        link_selector: str = "a",
        timeout: int = 30000,
        headless: bool = True
    ):
        """Initialize web scraper.

        Args:
            name: Name of this source
            base_url: Base URL to scrape
            category: Category for articles
            article_selector: CSS selector for article containers
            title_selector: CSS selector for article titles
            content_selector: CSS selector for article content
            link_selector: CSS selector for article links
            timeout: Page load timeout in milliseconds
            headless: Run browser in headless mode
        """
        super().__init__(name, category)
        self.base_url = base_url
        self.article_selector = article_selector
        self.title_selector = title_selector
        self.content_selector = content_selector
        self.link_selector = link_selector
        self.timeout = timeout
        self.headless = headless

    def fetch(self, max_articles: int = 10, **kwargs: Any) -> list[Article]:
        """Scrape articles from the website.

        Args:
            max_articles: Maximum articles to fetch
            **kwargs: Additional parameters

        Returns:
            List of articles
        """
        articles = []

        try:
            from playwright.sync_api import sync_playwright

            with sync_playwright() as p:
                browser = p.chromium.launch(headless=self.headless)
                context = browser.new_context(
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                )
                page = context.new_page()

                try:
                    page.goto(self.base_url, timeout=self.timeout, wait_until="networkidle")
                    page.wait_for_load_state("domcontentloaded")

                    # Find all article elements
                    article_elements = page.query_selector_all(self.article_selector)
                    logger.info(f"Found {len(article_elements)} articles on {self.name}")

                    for element in article_elements[:max_articles]:
                        try:
                            article = self._parse_article_element(element, page)
                            if article:
                                articles.append(article)
                        except Exception as e:
                            logger.error(f"Error parsing article element: {e}")

                finally:
                    browser.close()

        except ImportError:
            logger.error("Playwright not installed. Run: playwright install")
        except Exception as e:
            logger.error(f"Failed to scrape {self.name}: {e}")

        return articles

    def _parse_article_element(self, element, page) -> Article | None:
        """Parse an article element into an Article.

        Args:
            element: Playwright element handle
            page: Playwright page

        Returns:
            Article or None
        """
        # Get title
        title_elem = element.query_selector(self.title_selector)
        title = ""
        if title_elem:
            title = title_elem.inner_text().strip()

        if not title:
            return None

        # Get link
        url = ""
        link_elem = element.query_selector(self.link_selector)
        if link_elem:
            href = link_elem.get_attribute("href") or ""
            url = self._resolve_url(href)

        if not url:
            return None

        # Get content preview
        content = ""
        content_elem = element.query_selector(self.content_selector)
        if content_elem:
            content = content_elem.inner_text().strip()

        return self._create_article(
            title=title,
            url=url,
            content=content[:1000]  # Limit initial content
        )

    def _resolve_url(self, href: str) -> str:
        """Resolve relative URL to absolute.

        Args:
            href: URL (possibly relative)

        Returns:
            Absolute URL
        """
        if not href:
            return ""

        if href.startswith("http"):
            return href

        from urllib.parse import urljoin
        return urljoin(self.base_url, href)

    def scrape_article_content(self, url: str) -> str:
        """Scrape full content from a single article URL.

        Args:
            url: Article URL

        Returns:
            Article content as text
        """
        try:
            from playwright.sync_api import sync_playwright

            with sync_playwright() as p:
                browser = p.chromium.launch(headless=self.headless)
                context = browser.new_context()
                page = context.new_page()

                try:
                    page.goto(url, timeout=self.timeout, wait_until="networkidle")

                    # Try to extract with readability
                    content = page.evaluate("""
                        () => {
                            // Simple readability-like extraction
                            const article = document.querySelector('article');
                            if (article) return article.innerText;

                            const main = document.querySelector('main');
                            if (main) return main.innerText;

                            // Fallback: find largest text block
                            const paragraphs = document.querySelectorAll('p');
                            let maxText = '';
                            paragraphs.forEach(p => {
                                if (p.innerText.length > maxText.length) {
                                    maxText = p.innerText;
                                }
                            });
                            return maxText;
                        }
                    """)

                    return content or ""

                finally:
                    browser.close()

        except Exception as e:
            logger.error(f"Failed to scrape article content from {url}: {e}")
            return ""

    def fetch_with_full_content(self, max_articles: int = 5) -> list[Article]:
        """Fetch articles with full content extraction.

        Args:
            max_articles: Maximum articles to fetch

        Returns:
            List of articles with full content
        """
        articles = self.fetch(max_articles=max_articles)

        for article in articles:
            if article.url:
                full_content = self.scrape_article_content(article.url)
                if full_content:
                    article.content = full_content

        return articles


class GenericScraper(BaseFetcher):
    """Generic scraper for simple HTML sites using requests."""

    def __init__(
        self,
        name: str,
        url: str,
        category: Category,
        article_selector: str = "article, .post, .entry",
        title_selector: str = "h1, h2, .entry-title",
        link_selector: str = "a",
        content_selector: str = ".entry-content, .post-content, .content"
    ):
        """Initialize generic scraper.

        Args:
            name: Source name
            url: URL to scrape
            category: Article category
            article_selector: CSS selector for articles
            title_selector: CSS selector for titles
            link_selector: CSS selector for links
            content_selector: CSS selector for content
        """
        super().__init__(name, category)
        self.url = url
        self.article_selector = article_selector
        self.title_selector = title_selector
        self.link_selector = link_selector
        self.content_selector = content_selector

    def fetch(self, max_articles: int = 10, **kwargs: Any) -> list[Article]:
        """Fetch articles using requests and BeautifulSoup.

        Args:
            max_articles: Maximum articles
            **kwargs: Additional parameters

        Returns:
            List of articles
        """
        import requests
        from bs4 import BeautifulSoup

        articles = []

        try:
            response = requests.get(
                self.url,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                },
                timeout=30
            )
            response.raise_for_status()

            soup = BeautifulSoup(response.content, "html.parser")
            article_elements = soup.select(self.article_selector)

            logger.info(f"Found {len(article_elements)} articles on {self.name}")

            for element in article_elements[:max_articles]:
                try:
                    # Get title
                    title_elem = element.select_one(self.title_selector)
                    title = title_elem.get_text(strip=True) if title_elem else ""

                    if not title:
                        continue

                    # Get URL
                    link_elem = element.select_one(self.link_selector)
                    href = link_elem.get("href", "") if link_elem else ""
                    url = self._resolve_url(href)

                    if not url:
                        continue

                    # Get content preview
                    content_elem = element.select_one(self.content_selector)
                    content = content_elem.get_text(strip=True) if content_elem else ""

                    article = self._create_article(
                        title=title,
                        url=url,
                        content=content[:1000]
                    )
                    articles.append(article)

                except Exception as e:
                    logger.error(f"Error parsing article: {e}")

        except Exception as e:
            logger.error(f"Failed to fetch from {self.name}: {e}")

        return articles

    def _resolve_url(self, href: str) -> str:
        """Resolve relative URL to absolute.

        Args:
            href: URL (possibly relative)

        Returns:
            Absolute URL
        """
        if not href:
            return ""

        if href.startswith("http"):
            return href

        from urllib.parse import urljoin
        return urljoin(self.url, href)
