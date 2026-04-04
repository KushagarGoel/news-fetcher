"""Hybrid search combining semantic and keyword search per category."""

import logging
from typing import Any

from src.models import Article, Category, SearchResult
from src.processors.embedder import OllamaEmbedder
from src.storage.vector_store import VectorStore

logger = logging.getLogger(__name__)


class HybridSearch:
    """Hybrid semantic + keyword search within category collections."""

    def __init__(
        self,
        vector_store: VectorStore,
        embedder: OllamaEmbedder,
        semantic_weight: float = 0.7,
        keyword_weight: float = 0.3
    ):
        """Initialize hybrid search.

        Args:
            vector_store: ChromaDB vector store
            embedder: Ollama embedder for query embeddings
            semantic_weight: Weight for semantic search (0-1)
            keyword_weight: Weight for keyword search (0-1)
        """
        self.vector_store = vector_store
        self.embedder = embedder
        self.semantic_weight = semantic_weight
        self.keyword_weight = keyword_weight

    def search(
        self,
        query: str,
        category: Category,
        n_results: int = 10,
        filters: dict[str, Any] | None = None,
        client_type: str | None = None
    ) -> list[SearchResult]:
        """Perform hybrid search within a category.

        Args:
            query: Search query
            category: Category to search in
            n_results: Number of results to return
            filters: Optional metadata filters
            client_type: Filter by client type (lender/merchant)

        Returns:
            List of search results
        """
        # Build where clause for filters
        where_clause = self._build_where_clause(filters, client_type)

        # Get semantic results
        semantic_results = self._semantic_search(
            query, category, n_results * 2, where_clause
        )

        # Get keyword results
        keyword_results = self._keyword_search(
            query, category, n_results * 2
        )

        # Combine and rank results
        combined = self._combine_results(
            semantic_results, keyword_results, n_results
        )

        return combined

    def _build_where_clause(
        self,
        filters: dict[str, Any] | None,
        client_type: str | None
    ) -> dict[str, Any] | None:
        """Build ChromaDB where clause from filters.

        Args:
            filters: Filter dictionary
            client_type: Client type filter

        Returns:
            Where clause dict or None
        """
        where = {}

        if filters:
            where.update(filters)

        if client_type:
            # Filter by client type in client_mentions
            where["client_type"] = client_type

        return where if where else None

    def _semantic_search(
        self,
        query: str,
        category: Category,
        n_results: int,
        where: dict[str, Any] | None
    ) -> dict[str, dict[str, Any]]:
        """Perform semantic search using embeddings.

        Args:
            query: Search query
            category: Category to search
            n_results: Number of results
            where: Where clause

        Returns:
            Dict mapping article IDs to result data
        """
        results = {}

        try:
            # Generate query embedding
            query_embedding = self.embedder.embed(query)

            # Search in vector store
            search_results = self.vector_store.search_by_embedding(
                embedding=query_embedding,
                category=category,
                n_results=n_results,
                where=where
            )

            # Convert to dict with scores
            for result in search_results:
                article_id = result.get("id")
                # Convert distance to similarity score (cosine distance)
                distance = result.get("distance", 1.0)
                similarity = 1.0 - distance  # Higher is better

                results[article_id] = {
                    "article_id": article_id,
                    "semantic_score": similarity,
                    "title": result.get("title", ""),
                    "url": result.get("url", ""),
                    "source": result.get("source", ""),
                    "content": result.get("content", "")
                }

        except Exception as e:
            logger.error(f"Semantic search failed: {e}")

        return results

    def _keyword_search(
        self,
        query: str,
        category: Category,
        n_results: int
    ) -> dict[str, dict[str, Any]]:
        """Perform keyword-based search.

        Args:
            query: Search query
            category: Category to search
           _results: Number of results

        Returns:
            Dict mapping article IDs to result data
        """
        results = {}

        try:
            # Search in vector store with text query
            search_results = self.vector_store.search_by_keyword(
                category=category,
                keyword=query,
                n_results=n_results
            )

            # Calculate keyword match scores
            query_terms = set(query.lower().split())

            for result in search_results:
                article_id = result.get("id")
                content = result.get("content", "").lower()
                title = result.get("title", "").lower()

                # Simple keyword matching score
                title_matches = sum(1 for term in query_terms if term in title)
                content_matches = sum(1 for term in query_terms if term in content)

                # Normalize score (0-1)
                max_matches = len(query_terms) * 2  # title + content
                keyword_score = min(1.0, (title_matches * 2 + content_matches) / max_matches)

                results[article_id] = {
                    "article_id": article_id,
                    "keyword_score": keyword_score,
                    "title": result.get("title", ""),
                    "url": result.get("url", ""),
                    "source": result.get("source", ""),
                    "content": result.get("content", "")
                }

        except Exception as e:
            logger.error(f"Keyword search failed: {e}")

        return results

    def _combine_results(
        self,
        semantic_results: dict[str, dict[str, Any]],
        keyword_results: dict[str, dict[str, Any]],
        n_results: int
    ) -> list[SearchResult]:
        """Combine semantic and keyword results.

        Args:
            semantic_results: Results from semantic search
            keyword_results: Results from keyword search
            n_results: Number of results to return

        Returns:
            Combined and ranked search results
        """
        # Get all unique article IDs
        all_ids = set(semantic_results.keys()) | set(keyword_results.keys())

        combined = []
        for article_id in all_ids:
            sem = semantic_results.get(article_id, {})
            key = keyword_results.get(article_id, {})

            # Get scores (default to 0 if not present)
            semantic_score = sem.get("semantic_score", 0)
            keyword_score = key.get("keyword_score", 0)

            # If only in one result set, still include it
            if not sem:
                semantic_score = 0
            if not key:
                keyword_score = 0

            # Calculate combined score
            combined_score = (
                semantic_score * self.semantic_weight +
                keyword_score * self.keyword_weight
            )

            # Get article data (prefer semantic result for metadata)
            article_data = sem if sem else key

            # Create Article object
            article = Article(
                id=article_id,
                title=article_data.get("title", ""),
                url=article_data.get("url", ""),
                source=article_data.get("source", ""),
                content=article_data.get("content", "")[:500]
            )

            combined.append(SearchResult(
                article=article,
                semantic_score=semantic_score,
                keyword_score=keyword_score,
                combined_score=combined_score
            ))

        # Sort by combined score and return top N
        combined.sort(key=lambda x: x.combined_score, reverse=True)
        return combined[:n_results]

    def search_by_entity(
        self,
        entity_name: str,
        category: Category,
        n_results: int = 10
    ) -> list[SearchResult]:
        """Search for articles mentioning a specific entity.

        Args:
            entity_name: Name of entity to search for
            category: Category to search
            n_results: Number of results

        Returns:
            List of search results
        """
        # Build where clause for entity
        where = {
            "$or": [
                {"competitor_mentions": {"$contains": entity_name}},
                {"client_mentions": {"$contains": entity_name}}
            ]
        }

        try:
            # Search for entity name as keyword
            results = self.vector_store.search_by_keyword(
                category=category,
                keyword=entity_name,
                n_results=n_results
            )

            # Convert to SearchResult objects
            search_results = []
            for result in results:
                article = Article(
                    id=result.get("id"),
                    title=result.get("title", ""),
                    url=result.get("url", ""),
                    source=result.get("source", ""),
                    content=result.get("content", "")[:500]
                )

                search_results.append(SearchResult(
                    article=article,
                    semantic_score=0,
                    keyword_score=1.0,
                    combined_score=1.0
                ))

            return search_results

        except Exception as e:
            logger.error(f"Entity search failed: {e}")
            return []

    def search_by_client_type(
        self,
        client_type: str,
        query: str,
        n_results: int = 10
    ) -> list[SearchResult]:
        """Search within clients collection filtered by client type.

        Args:
            client_type: Client type (lender/merchant)
            query: Search query
            n_results: Number of results

        Returns:
            List of search results
        """
        return self.search(
            query=query,
            category=Category.CLIENTS,
            n_results=n_results,
            client_type=client_type
        )
