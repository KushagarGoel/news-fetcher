#!/usr/bin/env python3
"""Test relevance checker."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from src.models import Article, Category
from src.processors.relevance_checker import RelevanceChecker

# Test articles - mix of strategic and non-strategic news
test_articles = [
    Article(
        title="Motorola Edge 70 Fusion is 'coming soon,' color options confirmed by Flipkart - GSMArena.com",
        url="https://example.com/1",
        source="GSMArena",
        category=Category.COMPETITOR
    ),
    Article(
        title="Flipkart Appoints Smita Ojha and Amit Sharma to Strengthen Leadership Team",
        url="https://example.com/2",
        source="Economic Times",
        category=Category.COMPETITOR
    ),
    Article(
        title="Boat enters Malaysia market, partners with Flipkart for distribution",
        url="https://example.com/3",
        source="Business Standard",
        category=Category.COMPETITOR
    ),
    Article(
        title="Flipkart launches new credit feature for merchants in partnership with Axis Bank",
        url="https://example.com/4",
        source="Economic Times",
        category=Category.COMPETITOR
    ),
    Article(
        title="Samsung Galaxy S25 Ultra review: Best camera phone yet",
        url="https://example.com/5",
        source="GSMArena",
        category=Category.TECH
    ),
]

print("=" * 60)
print("Testing Relevance Checker")
print("=" * 60)

checker = RelevanceChecker()
print(f"Ollama available: {checker.is_available()}")
print()

for article in test_articles:
    print(f"\nTitle: {article.title[:60]}...")
    print(f"Category: {article.category.value}")
    is_relevant = checker.check_relevance(article)
    print(f"Result: {'✓ RELEVANT' if is_relevant else '✗ FILTERED OUT'}")
    print("-" * 60)

print("\n" + "=" * 60)
print("Batch filtering test:")
print("=" * 60)
relevant = checker.filter_articles(test_articles)
print(f"\nKept {len(relevant)}/{len(test_articles)} articles")
for a in relevant:
    print(f"  ✓ {a.title[:50]}...")
