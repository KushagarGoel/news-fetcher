"""Category-wise ChromaDB storage for articles."""

import hashlib
import logging
from pathlib import Path
from typing import Optional

import chromadb
from chromadb.config import Settings

from src.models import Article, Category

logger = logging.getLogger(__name__)


class VectorStore:
    """ChromaDB vector store with category-wise collections."""

    COLLECTION_NAMES = {
        Category.TECH: "tech_articles",
        Category.INDUSTRY: "industry_articles",
        Category.COMPETITOR: "competitor_articles",
        Category.CLIENTS: "clients_articles",
    }

    def __init__(
        self,
        persist_directory: str = "./data/chroma_db",
        embedding_dimension: int = 768
    ):
        """Initialize the vector store.

        Args:
            persist_directory: Directory to persist ChromaDB data
            embedding_dimension: Dimension of embedding vectors
        """
        self.persist_directory = Path(persist_directory)
        self.persist_directory.mkdir(parents=True, exist_ok=True)
        self.embedding_dimension = embedding_dimension

        # Initialize ChromaDB client
        self.client = chromadb.PersistentClient(
            path=str(self.persist_directory),
            settings=Settings(
                anonymized_telemetry=False,
                allow_reset=True
            )
        )

        # Initialize collections
        self._collections = {}
        self._init_collections()

    def _init_collections(self) -> None:
        """Initialize all category collections."""
        for category, name in self.COLLECTION_NAMES.items():
            try:
                collection = self.client.get_or_create_collection(
                    name=name,
                    metadata={"category": category.value, "hnsw:space": "cosine"}
                )
                self._collections[category] = collection
                logger.debug(f"Initialized collection: {name}")
            except Exception as e:
                logger.error(f"Failed to initialize collection {name}: {e}")
                raise

    def get_collection(self, category: Category):
        """Get the collection for a specific category.

        Args:
            category: Article category

        Returns:
            ChromaDB collection
        """
        return self._collections.get(category)

    def _generate_content_hash(self, content: str) -> str:
        """Generate hash for content deduplication.

        Args:
            content: Article content

        Returns:
            MD5 hash of content
        """
        return hashlib.md5(content.encode()).hexdigest()

    def article_exists(self, url: str, category: Category) -> bool:
        """Check if an article with the given URL exists in the category.

        Args:
            url: Article URL
            category: Article category

        Returns:
            True if article exists, False otherwise
        """
        collection = self.get_collection(category)
        if not collection:
            return False

        try:
            result = collection.get(
                where={"url": url},
                limit=1
            )
            return len(result.get("ids", [])) > 0
        except Exception as e:
            logger.error(f"Error checking article existence: {e}")
            return False

    def semantic_duplicate(
        self,
        embedding: list[float],
        category: Category,
        threshold: float = 0.95
    ) -> bool:
        """Check if a semantically similar article exists.

        Args:
            embedding: Article embedding vector
            category: Article category
            threshold: Similarity threshold (0-1, higher = more similar)

        Returns:
            True if similar article exists, False otherwise
        """
        collection = self.get_collection(category)
        if not collection:
            return False

        try:
            # ChromaDB uses cosine distance, so lower is more similar
            # Convert similarity threshold to distance threshold
            distance_threshold = 1.0 - threshold

            results = collection.query(
                query_embeddings=[embedding],
                n_results=1,
                include=["distances"]
            )

            if results.get("distances") and results["distances"][0]:
                distance = results["distances"][0][0]
                return distance < distance_threshold

            return False
        except Exception as e:
            logger.error(f"Error checking semantic duplicate: {e}")
            return False

    def add_article(
        self,
        article: Article,
        skip_duplicates: bool = True
    ) -> bool:
        """Add an article to the appropriate collection.

        Args:
            article: Article to add
            skip_duplicates: Whether to skip duplicate articles

        Returns:
            True if article was added, False if skipped or failed
        """
        collection = self.get_collection(article.category)
        if not collection:
            logger.error(f"No collection for category: {article.category}")
            return False

        # Check for URL duplicate
        if skip_duplicates and self.article_exists(article.url, article.category):
            logger.debug(f"Skipping duplicate URL: {article.url}")
            return False

        # Check for semantic duplicate
        if skip_duplicates and article.embedding:
            if self.semantic_duplicate(article.embedding, article.category):
                logger.debug(f"Skipping semantic duplicate: {article.url}")
                return False

        # Generate content hash if not set
        content_hash = article.content_hash or self._generate_content_hash(
            article.content or article.title
        )

        # Prepare metadata
        metadata = {
            "title": article.title,
            "url": article.url,
            "source": article.source,
            "category": article.category.value,
            "content_hash": content_hash,
            "tags": ",".join(article.tags),
            "competitor_mentions": ",".join(article.competitor_mentions),
            "client_mentions": ",".join(
                c.get("name", "") for c in article.client_mentions
            ),
            "send_in_mail": article.send_in_mail,
            "duplicate_group_id": str(article.duplicate_group_id) if article.duplicate_group_id else "",
        }

        # Add published date if available
        if article.published_at:
            metadata["published_at"] = article.published_at.isoformat()

        # Prepare document text for keyword search (title + summary, NOT full content)
        document_text = article.title
        if article.summary:
            document_text += f"\n{article.summary}"

        try:
            collection.add(
                ids=[str(article.id)],
                documents=[document_text],
                embeddings=[article.embedding] if article.embedding else None,
                metadatas=[metadata]
            )
            logger.debug(f"Added article: {article.title[:50]}...")
            return True
        except Exception as e:
            logger.error(f"Failed to add article: {e}")
            return False

    def get_article(self, article_id: str, category: Category) -> Optional[Article]:
        """Get an article by ID.

        Args:
            article_id: Article UUID
            category: Article category

        Returns:
            Article if found, None otherwise
        """
        collection = self.get_collection(category)
        if not collection:
            return None

        try:
            result = collection.get(
                ids=[article_id],
                include=["documents", "metadatas", "embeddings"]
            )

            if not result.get("ids"):
                return None

            metadata = result["metadatas"][0]
            return Article(
                id=article_id,
                title=metadata.get("title", ""),
                url=metadata.get("url", ""),
                source=metadata.get("source", ""),
                content=result.get("documents", [""])[0],
                embedding=result.get("embeddings", [None])[0],
                category=category,
                tags=metadata.get("tags", "").split(",") if metadata.get("tags") else [],
                competitor_mentions=metadata.get("competitor_mentions", "").split(",")
                if metadata.get("competitor_mentions") else [],
            )
        except Exception as e:
            logger.error(f"Error getting article: {e}")
            return None

    def search_by_embedding(
        self,
        embedding: list[float],
        category: Category,
        n_results: int = 10,
        where: Optional[dict] = None
    ) -> list[dict]:
        """Search articles by semantic similarity.

        Args:
            embedding: Query embedding vector
            category: Category to search in
            n_results: Number of results to return
            where: Optional filter conditions

        Returns:
            List of search results with metadata
        """
        collection = self.get_collection(category)
        if not collection:
            return []

        try:
            results = collection.query(
                query_embeddings=[embedding],
                n_results=n_results,
                where=where,
                include=["documents", "metadatas", "distances"]
            )

            output = []
            for i, doc_id in enumerate(results.get("ids", [[]])[0]):
                metadata = results["metadatas"][0][i]
                output.append({
                    "id": doc_id,
                    "title": metadata.get("title", ""),
                    "url": metadata.get("url", ""),
                    "source": metadata.get("source", ""),
                    "distance": results["distances"][0][i],
                    "content": results["documents"][0][i] if results.get("documents") else "",
                })
            return output
        except Exception as e:
            logger.error(f"Error searching articles: {e}")
            return []

    def search_by_keyword(
        self,
        category: Category,
        keyword: str,
        n_results: int = 10
    ) -> list[dict]:
        """Search articles by keyword in content.

        Args:
            category: Category to search in
            keyword: Keyword to search for
            n_results: Number of results to return

        Returns:
            List of matching articles
        """
        collection = self.get_collection(category)
        if not collection:
            return []

        try:
            results = collection.query(
                query_texts=[keyword],
                n_results=n_results,
                include=["documents", "metadatas", "distances"]
            )

            output = []
            for i, doc_id in enumerate(results.get("ids", [[]])[0]):
                metadata = results["metadatas"][0][i]
                output.append({
                    "id": doc_id,
                    "title": metadata.get("title", ""),
                    "url": metadata.get("url", ""),
                    "source": metadata.get("source", ""),
                    "distance": results["distances"][0][i],
                    "content": results["documents"][0][i] if results.get("documents") else "",
                })
            return output
        except Exception as e:
            logger.error(f"Error searching by keyword: {e}")
            return []

    def get_collection_stats(self) -> dict:
        """Get statistics for all collections.

        Returns:
            Dictionary with collection counts
        """
        stats = {}
        for category, collection in self._collections.items():
            try:
                count = collection.count()
                stats[category.value] = count
            except Exception as e:
                logger.error(f"Error getting stats for {category}: {e}")
                stats[category.value] = 0
        return stats

    def delete_old_articles(self, category: Category, before_date: str) -> int:
        """Delete articles older than a specific date.

        Args:
            category: Category to clean up
            before_date: ISO format date string

        Returns:
            Number of articles deleted
        """
        collection = self.get_collection(category)
        if not collection:
            return 0

        try:
            # Get all articles before the date
            results = collection.get(
                where={"published_at": {"$lt": before_date}}
            )

            if results.get("ids"):
                collection.delete(ids=results["ids"])
                return len(results["ids"])
            return 0
        except Exception as e:
            logger.error(f"Error deleting old articles: {e}")
            return 0
