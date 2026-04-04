#!/usr/bin/env python3
"""Test duplicate grouping functionality."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from src.models import Article, Category
from src.processors.duplicate_grouper import DuplicateGrouper

# Test articles with similar headlines (like the Fibe example)
test_articles = [
    Article(
        title="Fibe Bags USD 35 Million in New Funding Round Backed by IFC - Elets BFSI",
        url="https://example.com/1",
        source="Elets BFSI",
        category=Category.COMPETITOR
    ),
    Article(
        title="Lending app Fibe's revenue rises 49% to Rs 1,228 crore, profit up 13% - The Arc Web",
        url="https://example.com/2",
        source="The Arc Web",
        category=Category.COMPETITOR
    ),
    Article(
        title="India-based Fibe secures $35m from IFC - FinTech Global",
        url="https://example.com/3",
        source="FinTech Global",
        category=Category.COMPETITOR
    ),
    Article(
        title="Paytm launches new credit card feature for merchants",
        url="https://example.com/4",
        source="Economic Times",
        category=Category.COMPETITOR
    ),
]

print("=" * 60)
print("Testing Duplicate Grouper")
print("=" * 60)

grouper = DuplicateGrouper()
print(f"Ollama available: {grouper.is_available()}")
print()

print("Input articles:")
for i, article in enumerate(test_articles, 1):
    print(f"  {i}. {article.title}")
print()

# Group articles
groups = grouper.group_articles(test_articles)

print(f"Found {len(groups)} groups:")
for i, group in enumerate(groups, 1):
    print(f"\n  Group {i}:")
    for article in group:
        print(f"    - {article.title[:60]}...")

# Mark duplicates
print("\n" + "=" * 60)
print("Marking duplicates for email")
print("=" * 60)

marked = grouper.mark_duplicates(test_articles)

print("\nEmail decisions:")
for article in marked:
    status = "SEND" if article.send_in_mail else "skip (duplicate)"
    print(f"  [{status}] {article.title[:50]}...")
