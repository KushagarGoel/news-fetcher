#!/usr/bin/env python3
"""Debug script to test summarization and tagging."""

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

from src.models import Article, Category
from src.processors.summarizer import Summarizer
from src.processors.tagger import Tagger
from src.processors.url_checker import URLChecker

# Test article
test_article = Article(
    title="Paytm launches new credit feature for merchants",
    url="https://economictimes.indiatimes.com/tech/startups/paytm-launches-credit-feature/articleshow/123456789.cms",
    content="Paytm has announced a new credit feature for small businesses and merchants. The feature allows merchants to get instant loans based on their transaction history. This is part of Paytm's strategy to expand its financial services portfolio and compete with other fintech players in the market.",
    source="test"
)

print("=" * 60)
print("Testing URL Checker")
print("=" * 60)
url_checker = URLChecker()
is_accessible = url_checker.is_accessible(test_article.url)
print(f"URL accessible: {is_accessible}")

print("\n" + "=" * 60)
print("Testing Summarizer")
print("=" * 60)
summarizer = Summarizer()
print(f"Summarizer available: {summarizer.is_available()}")

try:
    summary = summarizer.summarize(
        title=test_article.title,
        content=test_article.content
    )
    print(f"Summary generated: {summary}")
    test_article.summary = summary
except Exception as e:
    print(f"ERROR: {e}")

print("\n" + "=" * 60)
print("Testing Tagger")
print("=" * 60)
tagger = Tagger()
tags = tagger.tag(test_article)
print(f"Tags: {tags}")

print("\n" + "=" * 60)
print("Final Article State")
print("=" * 60)
print(f"Title: {test_article.title}")
print(f"Summary: {test_article.summary}")
print(f"Tags: {test_article.tags}")
print(f"Embedding text: {test_article.get_embedding_text()}")
