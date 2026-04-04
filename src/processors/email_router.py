"""Email routing decision engine."""

import logging
from pathlib import Path
from typing import Any

import yaml

from src.models import Article, Category, ClientType, EmailRouting, Priority

logger = logging.getLogger(__name__)


class EmailRouter:
    """Compute email routing decisions based on entities and tags."""

    def __init__(self, config_file: str = "config/email.yaml"):
        """Initialize the email router.

        Args:
            config_file: Path to email configuration YAML
        """
        self.config: dict[str, Any] = {}
        self._load_config(config_file)

    def _load_config(self, config_file: str) -> None:
        """Load email routing configuration."""
        base_path = Path(__file__).parent.parent.parent

        try:
            with open(base_path / config_file, "r") as f:
                data = yaml.safe_load(f)
                self.config = data.get("routing", {})
            logger.info("Loaded email routing configuration")
        except Exception as e:
            logger.error(f"Failed to load email config: {e}")
            self.config = {}

    def _get_category_default(self, category: Category) -> dict[str, Any]:
        """Get default routing for a category.

        Args:
            category: Article category

        Returns:
            Routing configuration dict
        """
        defaults = self.config.get("category_defaults", {})
        return defaults.get(category.value, {
            "recipients": [],
            "digest_mode": True
        })

    def _get_entity_routing(
        self,
        entity_name: str,
        entity_type: str
    ) -> dict[str, Any]:
        """Get routing for a specific entity.

        Args:
            entity_name: Name of competitor or client
            entity_type: "competitors" or "clients"

        Returns:
            Routing configuration dict
        """
        entities = self.config.get("entities", {}).get(entity_type, {})
        return entities.get(entity_name, {})

    def _get_tag_routing(self, tag: str) -> dict[str, Any]:
        """Get routing for a specific tag.

        Args:
            tag: Tag name

        Returns:
            Routing configuration dict
        """
        tags = self.config.get("tags", {})
        return tags.get(tag, {})

    def compute_routing(self, article: Article) -> EmailRouting:
        """Compute email routing decision for an article.

        Routing priority:
        1. Entity-specific (competitor/client) - highest
        2. Tag-based rules
        3. Category default - fallback

        Args:
            article: Article to route

        Returns:
            Email routing decision
        """
        routing = EmailRouting()
        recipients = set()
        priorities = []
        digest_modes = []

        # 1. Entity-specific routing (highest priority)
        if article.category == Category.COMPETITOR and article.competitor_mentions:
            for competitor in article.competitor_mentions:
                entity_config = self._get_entity_routing(competitor, "competitors")
                if entity_config:
                    recipients.update(entity_config.get("recipients", []))
                    digest_modes.append(entity_config.get("digest_mode", False))
                    routing.matched_entities.append(competitor)

        elif article.category == Category.CLIENTS and article.client_mentions:
            for client in article.client_mentions:
                client_name = client.get("name", "")
                entity_config = self._get_entity_routing(client_name, "clients")
                if entity_config:
                    recipients.update(entity_config.get("recipients", []))
                    digest_modes.append(entity_config.get("digest_mode", False))
                    routing.matched_entities.append(client_name)

        # 2. Tag-based routing
        for tag in article.tags:
            tag_config = self._get_tag_routing(tag)
            if tag_config:
                recipients.update(tag_config.get("recipients", []))
                tag_priority = tag_config.get("priority", "medium")
                priorities.append(Priority(tag_priority))
                routing.matched_tags.append(tag)

        # 3. Category default (fallback if no specific matches)
        if not recipients:
            default = self._get_category_default(article.category)
            recipients.update(default.get("recipients", []))
            digest_modes.append(default.get("digest_mode", True))

        # Determine final priority (highest from all sources)
        if priorities:
            routing.priority = max(priorities, key=lambda p: list(Priority).index(p))
        else:
            routing.priority = Priority.MEDIUM

        # Determine digest mode (False if any entity says instant)
        routing.digest_mode = all(digest_modes) if digest_modes else True

        # Critical priority overrides digest mode
        if routing.priority == Priority.CRITICAL:
            routing.digest_mode = False

        routing.recipients = list(recipients)

        # Store routing in article
        article.email_routing = routing

        logger.debug(
            f"Routing for '{article.title[:30]}...': "
            f"entities={routing.matched_entities}, "
            f"tags={routing.matched_tags}, "
            f"recipients={len(routing.recipients)}, "
            f"priority={routing.priority.value}"
        )

        return routing

    def should_send_immediately(self, article: Article) -> bool:
        """Check if article should trigger immediate notification.

        Args:
            article: Article to check

        Returns:
            True if should send immediately
        """
        routing = article.email_routing

        # Critical priority always sends immediately
        if routing.priority == Priority.CRITICAL:
            return True

        # Competitor news sends immediately
        if article.category == Category.COMPETITOR:
            return True

        # Check entity-specific digest settings
        if not routing.digest_mode:
            return True

        return False

    def format_subject(self, article: Article) -> str:
        """Format email subject line based on article.

        Args:
            article: Article to format subject for

        Returns:
            Formatted subject line
        """
        routing = article.email_routing
        parts = []

        # Category/Entity prefix
        if routing.matched_entities:
            if len(routing.matched_entities) == 1:
                entity = routing.matched_entities[0]
                if article.category == Category.COMPETITOR:
                    parts.append(f"[Competitor: {entity}]")
                elif article.category == Category.CLIENTS:
                    # Include client type
                    client_type = ""
                    for c in article.client_mentions:
                        if c.get("name") == entity:
                            client_type = c.get("type", "")
                            break
                    if client_type:
                        parts.append(f"[Client: {entity}/{client_type}]")
                    else:
                        parts.append(f"[Client: {entity}]")
                else:
                    parts.append(f"[{entity}]")
            else:
                parts.append(f"[Multi: {', '.join(routing.matched_entities[:2])}]")
        else:
            parts.append(f"[{article.category.value.title()}]")

        # Tag indicators
        if routing.matched_tags:
            critical_tags = [t for t in routing.matched_tags
                           if t in ["acquisition", "merger", "RBI_regulation", "data_breach"]]
            if critical_tags:
                parts.append(f"[{critical_tags[0].upper()}]")

        # Article title snippet
        title_snippet = article.title[:50] + "..." if len(article.title) > 50 else article.title
        parts.append(title_snippet)

        # Priority indicator
        if routing.priority == Priority.CRITICAL:
            parts.append("[!CRITICAL]")
        elif routing.priority == Priority.HIGH:
            parts.append("[HIGH]")

        return " ".join(parts)

    def get_recipients_for_digest(
        self,
        articles: list[Article]
    ) -> dict[str, list[Article]]:
        """Group articles by recipient for digest sending.

        Args:
            articles: List of articles to group

        Returns:
            Dict mapping recipient email to list of articles
        """
        recipient_articles: dict[str, list[Article]] = {}

        for article in articles:
            for recipient in article.email_routing.recipients:
                if recipient not in recipient_articles:
                    recipient_articles[recipient] = []
                recipient_articles[recipient].append(article)

        return recipient_articles
