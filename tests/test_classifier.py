"""Tests for article classifier."""

import pytest

from src.models import Article, Category
from src.processors.classifier import Classifier


class TestClassifier:
    """Test the classifier."""

    @pytest.fixture
    def classifier(self):
        """Create classifier fixture."""
        return Classifier()

    def test_detect_competitors(self, classifier):
        """Test competitor detection."""
        article = Article(
            title="Paytm launches new credit feature",
            url="http://example.com/1",
            content="Paytm Credit is expanding its lending business in India."
        )

        mentions = classifier.detect_competitors(article)
        assert "Paytm" in mentions

    def test_detect_clients(self, classifier):
        """Test client detection."""
        article = Article(
            title="HDFC Bank partners with fintech",
            url="http://example.com/2",
            content="HDFC Bank announces new partnership with lending platform."
        )

        mentions = classifier.detect_clients(article)
        assert any(m["name"] == "HDFC Bank" for m in mentions)
        assert any(m["type"] == "lender" for m in mentions)

    def test_classify_competitor(self, classifier):
        """Test competitor classification."""
        article = Article(
            title="PhonePe raises $100M",
            url="http://example.com/3",
            content="PhonePe has raised new funding for expansion."
        )

        category = classifier.classify(article)
        assert category == Category.COMPETITOR
        assert "PhonePe" in article.competitor_mentions

    def test_classify_industry(self, classifier):
        """Test industry classification."""
        article = Article(
            title="RBI announces new lending guidelines",
            url="http://example.com/4",
            content="The Reserve Bank of India has issued new guidelines."
        )

        category = classifier.classify(article)
        assert category == Category.INDUSTRY
