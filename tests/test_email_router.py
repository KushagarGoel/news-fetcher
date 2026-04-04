"""Tests for email router."""

import pytest

from src.models import Article, Category, EmailRouting, Priority
from src.processors.email_router import EmailRouter


class TestEmailRouter:
    """Test the email router."""

    @pytest.fixture
    def router(self):
        """Create router fixture."""
        return EmailRouter()

    def test_compute_routing_competitor(self, router):
        """Test routing for competitor article."""
        article = Article(
            title="Paytm news",
            url="http://example.com/1",
            category=Category.COMPETITOR,
            competitor_mentions=["Paytm"]
        )

        routing = router.compute_routing(article)
        assert isinstance(routing, EmailRouting)
        assert "Paytm" in routing.matched_entities

    def test_format_subject(self, router):
        """Test subject formatting."""
        article = Article(
            title="Paytm raises funding",
            url="http://example.com/1",
            category=Category.COMPETITOR,
            competitor_mentions=["Paytm"]
        )
        router.compute_routing(article)

        subject = router.format_subject(article)
        assert "Paytm" in subject
        assert "Competitor" in subject or "[Competitor" in subject

    def test_should_send_immediately_critical(self, router):
        """Test immediate sending for critical articles."""
        article = Article(
            title="Data breach at bank",
            url="http://example.com/1",
            category=Category.INDUSTRY
        )
        article.email_routing.priority = Priority.CRITICAL

        assert router.should_send_immediately(article)
