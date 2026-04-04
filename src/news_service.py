"""News service orchestrating all components."""

import logging
from pathlib import Path
from typing import Any

import yaml

from src.fetchers.hn_fetcher import HNFetcher
from src.fetchers.medium_fetcher import MediumTagFetcher
from src.fetchers.rss_fetcher import RSSFetcher, GoogleNewsFetcher
from src.models import Article, Category, ClientType, FetchResult
from src.notifications.email_notifier import EmailNotifier
from src.processors.classifier import Classifier
from src.processors.duplicate_grouper import DuplicateGrouper
from src.processors.email_router import EmailRouter
from src.processors.embedder import OllamaEmbedder
from src.processors.relevance_checker import RelevanceChecker
from src.processors.summarizer import Summarizer
from src.processors.tagger import Tagger
from src.processors.url_checker import URLChecker
from src.search.hybrid_search import HybridSearch
from src.storage.vector_store import VectorStore

logger = logging.getLogger(__name__)


class NewsService:
    """Orchestrates news fetching, processing, storage, and notifications."""

    def __init__(
        self,
        config_dir: str = "config",
        data_dir: str = "data"
    ):
        """Initialize the news service.

        Args:
            config_dir: Directory containing configuration files
            data_dir: Directory for data storage
        """
        self.base_path = Path(__file__).parent.parent
        self.config_dir = self.base_path / config_dir
        self.data_dir = self.base_path / data_dir

        # Initialize components
        self.embedder = OllamaEmbedder()
        self.vector_store = VectorStore(
            persist_directory=str(self.data_dir / "chroma_db"),
            embedding_dimension=self.embedder.get_embedding_dimension()
        )
        self.classifier = Classifier(
            competitors_file=str(self.config_dir / "competitors.yaml"),
            clients_file=str(self.config_dir / "clients.yaml"),
            keywords_file=str(self.config_dir / "keywords.yaml")
        )
        self.tagger = Tagger()
        self.url_checker = URLChecker()
        self.summarizer = Summarizer()
        self.duplicate_grouper = DuplicateGrouper()
        self.relevance_checker = RelevanceChecker()
        self.email_router = EmailRouter(str(self.config_dir / "email.yaml"))
        self.email_notifier = EmailNotifier(str(self.config_dir / "email.yaml"))
        self.hybrid_search = HybridSearch(
            vector_store=self.vector_store,
            embedder=self.embedder
        )

        # Load source configurations
        self.sources_config = self._load_sources_config()

    def _load_sources_config(self) -> dict[str, Any]:
        """Load sources configuration from YAML."""
        try:
            with open(self.config_dir / "sources.yaml", "r") as f:
                return yaml.safe_load(f)
        except Exception as e:
            logger.error(f"Failed to load sources config: {e}")
            return {}

    def _create_fetchers(self, category: Category) -> list:
        """Create fetchers for a category."""
        fetchers = []
        cat_config = self.sources_config.get(category.value, {})

        # Get RSS feeds from config
        rss_feeds = cat_config.get("rss_feeds") or []
        for feed in rss_feeds:
            name = feed.get("name", "unnamed")
            url = feed.get("url", "")

            if not url:
                continue

            if "news.google.com" in url:
                import urllib.parse
                query = urllib.parse.unquote(url.split("q=")[1].split("&")[0]) if "q=" in url else ""
                fetchers.append(GoogleNewsFetcher(
                    name=name, search_query=query, category=category
                ))
            elif "news.ycombinator.com" in url:
                fetchers.append(HNFetcher(category=category))
            elif "medium.com" in url and "/tag/" in url:
                tag = url.split("/tag/")[-1].split("/")[0]
                fetchers.append(MediumTagFetcher(tag=tag, category=category))
            else:
                fetchers.append(RSSFetcher(
                    name=name, feed_url=url, category=category
                ))

        # Auto-generate Google News feeds from config files
        if category == Category.TECH:
            keyword_fetchers = self._create_keyword_fetchers(Category.TECH)
            fetchers.extend(keyword_fetchers)
        elif category == Category.INDUSTRY:
            keyword_fetchers = self._create_keyword_fetchers(Category.INDUSTRY)
            fetchers.extend(keyword_fetchers)
        elif category == Category.COMPETITOR:
            competitor_fetchers = self._create_competitor_fetchers()
            fetchers.extend(competitor_fetchers)
        elif category == Category.CLIENTS:
            client_fetchers = self._create_client_fetchers()
            fetchers.extend(client_fetchers)

        return fetchers

    def _create_competitor_fetchers(self) -> list:
        """Create Google News fetchers for each competitor.

        Returns:
            List of GoogleNewsFetcher instances for competitors
        """
        fetchers = []
        for competitor in self.classifier.competitors:
            # Use first keyword (usually the main name) for search
            search_term = competitor.keywords[0] if competitor.keywords else competitor.name
            fetchers.append(GoogleNewsFetcher(
                name=f"google_news_{competitor.name.lower().replace(' ', '_')}",
                search_query=search_term,
                category=Category.COMPETITOR
            ))
        return fetchers

    def _create_client_fetchers(self) -> list:
        """Create Google News fetchers for each client.

        Returns:
            List of GoogleNewsFetcher instances for clients
        """
        fetchers = []
        all_clients = self.classifier.lenders + self.classifier.merchants

        for client in all_clients:
            # Use first keyword for search
            search_term = client.keywords[0] if client.keywords else client.name
            fetchers.append(GoogleNewsFetcher(
                name=f"google_news_{client.name.lower().replace(' ', '_')}",
                search_query=search_term,
                category=Category.CLIENTS
            ))
        return fetchers

    def _create_keyword_fetchers(self, category: Category) -> list:
        """Create Google News fetchers for tech/industry keywords.

        Args:
            category: Category to create fetchers for (TECH or INDUSTRY)

        Returns:
            List of GoogleNewsFetcher instances for keywords
        """
        fetchers = []

        # Get keywords based on category
        if category == Category.TECH:
            keywords = self.classifier.tech_keywords
            search_prefix = "tech"
        elif category == Category.INDUSTRY:
            keywords = self.classifier.industry_keywords
            search_prefix = "industry"
        else:
            return fetchers

        for keyword in keywords:
            # Create safe name from keyword
            safe_name = keyword.lower().replace(" ", "_").replace("-", "_")[:30]
            fetchers.append(GoogleNewsFetcher(
                name=f"google_news_{search_prefix}_{safe_name}",
                search_query=keyword,
                category=category
            ))

        return fetchers

    def process_article(
        self,
        article: Article,
        check_url: bool = True,
        generate_summary: bool = True
    ) -> Article | None:
        """Process a single article: check URL, summarize, classify, tag, embed, route.

        Args:
            article: Article to process
            check_url: Whether to check URL accessibility before processing
            generate_summary: Whether to generate LLM summary if URL is accessible

        Returns:
            Processed article or None if should be skipped
        """
        try:
            # Check URL accessibility if enabled
            # Skip check for Google News URLs (they often redirect)
            is_google_news = "news.google.com" in (article.url or "")
            if check_url and article.url and not is_google_news:
                is_accessible = self.url_checker.is_accessible(article.url)
                if not is_accessible:
                    logger.debug(f"Skipping article with inaccessible URL: {article.url}")
                    return None
                logger.debug(f"URL accessible: {article.url}")

            # Generate summary if URL was accessible (or check_url is False)
            if generate_summary and (not check_url or article.url):
                try:
                    # Only summarize if we have content
                    content_to_summarize = article.content or article.summary
                    if content_to_summarize:
                        article.summary = self.summarizer.summarize(
                            title=article.title,
                            content=content_to_summarize
                        )
                        logger.debug(f"Generated summary for: {article.title[:50]}...")
                except Exception as e:
                    logger.warning(f"Failed to generate summary: {e}")
                    # Continue without summary - embedding will use title only

            # Classify
            article.category = self.classifier.classify(article)
            article.competitor_mentions = self.classifier.detect_competitors(article)
            article.client_mentions = self.classifier.detect_clients(article)
            self.tagger.tag(article)

            # Generate embedding (uses title + summary only)
            try:
                article.embedding = self.embedder.embed(article.get_embedding_text())
            except Exception as e:
                logger.warning(f"Failed to generate embedding: {e}")
                article.embedding = None

            self.email_router.compute_routing(article)
            return article

        except Exception as e:
            logger.error(f"Error processing article: {e}")
            return None

    def store_article(self, article: Article, skip_duplicates: bool = True) -> bool:
        """Store article in vector store.

        Args:
            article: Article to store
            skip_duplicates: Whether to skip URL/semantic duplicates

        Returns:
            True if stored successfully
        """
        try:
            return self.vector_store.add_article(article, skip_duplicates=skip_duplicates)
        except Exception as e:
            logger.error(f"Error storing article: {e}")
            return False

    def fetch_category(
        self,
        category: Category,
        max_articles: int = 20,
        client_type: ClientType | None = None,
        send_emails: bool = True
    ) -> list[FetchResult]:
        """Fetch and process all sources for a category."""
        fetchers = self._create_fetchers(category)
        results = []
        processed_articles = []

        for fetcher in fetchers:
            try:
                logger.info(f"Fetching from {fetcher.name}...")
                articles = fetcher.fetch(max_articles=max_articles)

                result = FetchResult(
                    source=fetcher.name,
                    category=category,
                    articles_found=len(articles),
                    articles_added=0,
                    articles_duplicated=0
                )

                for article in articles:
                    processed = self.process_article(article)
                    if not processed:
                        continue

                    if client_type and category == Category.CLIENTS:
                        matching_clients = [
                            c for c in processed.client_mentions
                            if c.get("type") == client_type.value
                        ]
                        if not matching_clients:
                            continue

                    processed_articles.append(processed)
                    result.articles_added += 1

                results.append(result)
                logger.info(
                    f"{fetcher.name}: Found {result.articles_found}, "
                    f"Processed {result.articles_added}"
                )

            except Exception as e:
                logger.error(f"Error fetching from {fetcher.name}: {e}")
                results.append(FetchResult(
                    source=fetcher.name, category=category,
                    articles_found=0, articles_added=0,
                    articles_duplicated=0, errors=[str(e)]
                ))

        # Apply duplicate grouping and relevance filtering
        new_articles = []
        if processed_articles:
            # First: check relevance
            relevant_articles = self.relevance_checker.filter_articles(processed_articles)

            # Second: group duplicates
            marked_articles = self.duplicate_grouper.mark_duplicates(relevant_articles)

            # Store articles (skip duplicates based on URL/embedding)
            for article in marked_articles:
                if self.store_article(article, skip_duplicates=True):
                    new_articles.append(article)
                else:
                    # Update result counts for duplicates
                    for result in results:
                        if result.source == article.source:
                            result.articles_added -= 1
                            result.articles_duplicated += 1

        if send_emails and new_articles and self.email_notifier.is_configured():
            # Only send articles marked for email
            articles_to_email = [a for a in new_articles if a.send_in_mail]
            if articles_to_email:
                self._send_notifications(articles_to_email)

        return results

    def _send_notifications(self, articles: list[Article]) -> None:
        """Send email notifications for new articles (batched, max 10 per email)."""
        immediate = []
        digest = []

        for article in articles:
            if self.email_router.should_send_immediately(article):
                immediate.append(article)
            else:
                digest.append(article)

        # Batch immediate alerts (max 10 per email)
        max_per_email = 10
        for i in range(0, len(immediate), max_per_email):
            batch = immediate[i:i + max_per_email]
            try:
                # Get unique recipients for this batch
                all_recipients = set()
                for article in batch:
                    routing = self.email_router.compute_routing(article)
                    all_recipients.update(routing.recipients)

                if all_recipients:
                    categories = set(a.category.value for a in batch)
                    cat_str = ", ".join(sorted(categories))
                    subject = f"[News Alert - {cat_str}] {len(batch)} articles"
                    self.email_notifier.send_digest(
                        articles=batch,
                        recipients=list(all_recipients),
                        subject=subject
                    )
                    logger.info(f"Sent immediate batch with {len(batch)} articles to {len(all_recipients)} recipients")
            except Exception as e:
                logger.error(f"Error sending immediate batch: {e}")

        # Send digests (also batched by recipient)
        if digest:
            recipient_articles = self.email_router.get_recipients_for_digest(digest)
            for recipient, articles_list in recipient_articles.items():
                # Batch per recipient if more than 10
                for i in range(0, len(articles_list), max_per_email):
                    batch = articles_list[i:i + max_per_email]
                    try:
                        self.email_notifier.send_digest(
                            articles=batch, recipients=[recipient]
                        )
                        logger.info(f"Sent digest with {len(batch)} articles to {recipient}")
                    except Exception as e:
                        logger.error(f"Error sending digest to {recipient}: {e}")

    def search(
        self,
        query: str,
        category: Category,
        n_results: int = 10,
        client_type: ClientType | None = None
    ) -> list:
        """Search articles."""
        return self.hybrid_search.search(
            query=query, category=category, n_results=n_results,
            client_type=client_type.value if client_type else None
        )

    def get_stats(self) -> dict[str, int]:
        """Get database statistics."""
        return self.vector_store.get_collection_stats()
