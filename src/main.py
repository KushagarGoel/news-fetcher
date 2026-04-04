"""CLI entry point for news aggregator."""

import argparse
import logging
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.models import Category, ClientType
from src.news_service import NewsService

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def cmd_fetch(args):
    """Handle fetch command."""
    service = NewsService()

    categories = []
    if args.all:
        categories = list(Category)
    elif args.category:
        categories = [Category(args.category)]
    else:
        categories = list(Category)

    for category in categories:
        print(f"\n{'='*60}")
        print(f"Fetching: {category.value.upper()}")
        print('='*60)

        client_type = ClientType(args.client_type) if args.client_type else None

        results = service.fetch_category(
            category=category,
            max_articles=args.max_articles,
            client_type=client_type,
            send_emails=not args.no_email
        )

        for result in results:
            status = "OK" if not result.errors else "ERROR"
            print(f"\n[{status}] {result.source}")
            print(f"  Found: {result.articles_found}")
            print(f"  Added: {result.articles_added}")
            print(f"  Duplicates: {result.articles_duplicated}")
            if result.errors:
                for error in result.errors:
                    print(f"  Error: {error}")

    print("\n" + "="*60)
    print("Fetch complete!")
    stats = service.get_stats()
    for cat, count in stats.items():
        print(f"  {cat}: {count} articles")


def cmd_search(args):
    """Handle search command."""
    service = NewsService()

    category = Category(args.category)
    client_type = ClientType(args.client_type) if args.client_type else None

    print(f"\nSearching in {category.value}...")
    if client_type:
        print(f"Client type: {client_type.value}")

    results = service.search(
        query=args.query,
        category=category,
        n_results=args.limit,
        client_type=client_type
    )

    print(f"\nFound {len(results)} results:\n")
    for i, result in enumerate(results, 1):
        print(f"{i}. {result.article.title}")
        print(f"   URL: {result.article.url}")
        print(f"   Semantic Score: {result.semantic_score:.3f}")
        print(f"   Keyword Score: {result.keyword_score:.3f}")
        print(f"   Combined Score: {result.combined_score:.3f}")
        print()


def cmd_stats(args):
    """Handle stats command."""
    service = NewsService()
    stats = service.get_stats()

    print("\nDatabase Statistics:")
    print("="*40)
    total = 0
    for category, count in stats.items():
        print(f"  {category:15} {count:>6} articles")
        total += count
    print("-"*40)
    print(f"  {'TOTAL':15} {total:>6} articles")


def cmd_test_email(args):
    """Handle test-email command."""
    service = NewsService()

    recipient = args.recipient
    if not recipient:
        print("Error: No recipient specified. Use --recipient or set in config.")
        sys.exit(1)

    print(f"Sending test email to {recipient}...")

    if not service.email_notifier.is_configured():
        print("Error: Email not configured. Check config/email.yaml")
        sys.exit(1)

    success = service.email_notifier.send_test_email(recipient)

    if success:
        print("Test email sent successfully!")
    else:
        print("Failed to send test email. Check logs for details.")
        sys.exit(1)


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        prog="news-aggregator",
        description="News aggregation system for Indian fintech"
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Fetch command
    fetch_parser = subparsers.add_parser("fetch", help="Fetch news articles")
    fetch_parser.add_argument(
        "--all", "-a",
        action="store_true",
        help="Fetch all categories"
    )
    fetch_parser.add_argument(
        "--category", "-c",
        choices=[c.value for c in Category],
        help="Category to fetch"
    )
    fetch_parser.add_argument(
        "--client-type",
        choices=[t.value for t in ClientType],
        help="Filter by client type (for clients category)"
    )
    fetch_parser.add_argument(
        "--max-articles", "-n",
        type=int,
        default=20,
        help="Max articles per source (default: 20)"
    )
    fetch_parser.add_argument(
        "--no-email",
        action="store_true",
        help="Skip sending email notifications"
    )
    fetch_parser.set_defaults(func=cmd_fetch)

    # Search command
    search_parser = subparsers.add_parser("search", help="Search articles")
    search_parser.add_argument(
        "--category", "-c",
        required=True,
        choices=[c.value for c in Category],
        help="Category to search in"
    )
    search_parser.add_argument(
        "--client-type",
        choices=[t.value for t in ClientType],
        help="Filter by client type"
    )
    search_parser.add_argument(
        "--limit", "-n",
        type=int,
        default=10,
        help="Number of results (default: 10)"
    )
    search_parser.add_argument(
        "query",
        nargs="+",
        help="Search query"
    )
    search_parser.set_defaults(func=cmd_search)

    # Stats command
    stats_parser = subparsers.add_parser("stats", help="Show database statistics")
    stats_parser.set_defaults(func=cmd_stats)

    # Test email command
    email_parser = subparsers.add_parser("test-email", help="Send test email")
    email_parser.add_argument(
        "--recipient", "-r",
        help="Email recipient"
    )
    email_parser.set_defaults(func=cmd_test_email)

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    # Join query args into single string
    if hasattr(args, "query") and args.query:
        args.query = " ".join(args.query)

    args.func(args)


if __name__ == "__main__":
    main()
