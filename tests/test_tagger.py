"""Tests for article tagger."""

import pytest

from src.models import Article, Priority
from src.processors.tagger import Tagger


class TestTagger:
    """Test the tagger."""

    @pytest.fixture
    def tagger(self):
        """Create tagger fixture."""
        return Tagger()

    def test_tag_funding(self, tagger):
        """Test funding tag detection."""
        article = Article(
            title="Startup raises $50M in Series B",
            url="http://example.com/1",
            content="The company announced a new funding round today."
        )

        tags = tagger.tag(article)
        assert "funding" in tags

    def test_tag_acquisition(self, tagger):
        """Test acquisition tag detection."""
        article = Article(
            title="Company X acquires Company Y",
            url="http://example.com/2",
            content="The acquisition was announced today."
        )

        tags = tagger.tag(article)
        assert "acquisition" in tags

    def test_get_priority(self, tagger):
        """Test priority determination."""
        assert tagger.get_priority(["funding"]) == Priority.HIGH
        assert tagger.get_priority(["acquisition"]) == Priority.CRITICAL
        assert tagger.get_priority(["partnership"]) == Priority.MEDIUM
        assert tagger.get_priority([]) == Priority.LOW

    def test_tag_rbi_regulation(self, tagger):
        """Test RBI regulation tag."""
        article = Article(
            title="RBI issues new guidelines",
            url="http://example.com/3",
            content="The Reserve Bank of India announced new regulations."
        )

        tags = tagger.tag(article)
        assert "RBI_regulation" in tags
