"""Scheduled job runner for news aggregator."""

import logging
import sys
from datetime import datetime
from pathlib import Path

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

sys.path.insert(0, str(Path(__file__).parent))

from src.models import Category, Priority
from src.news_service import NewsService

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(Path(__file__).parent / "data" / "cron.log")
    ]
)
logger = logging.getLogger(__name__)


def select_articles_for_digest(articles, max_total=15, critical_reserved=5):
    """Select articles for digest ensuring critical articles get priority.

    Args:
        articles: List of articles to select from
        max_total: Maximum total articles in digest
        critical_reserved: Number of slots reserved for critical priority articles

    Returns:
        List of selected articles
    """
    # Separate critical and non-critical articles
    critical = [a for a in articles if a.email_routing.priority == Priority.CRITICAL]
    others = [a for a in articles if a.email_routing.priority != Priority.CRITICAL]

    # Sort by priority within each group
    priority_order = {Priority.CRITICAL: 0, Priority.HIGH: 1, Priority.MEDIUM: 2, Priority.LOW: 3}
    critical.sort(key=lambda a: priority_order.get(a.email_routing.priority, 2))
    others.sort(key=lambda a: priority_order.get(a.email_routing.priority, 2))

    # Take up to critical_reserved critical articles
    selected_critical = critical[:critical_reserved]

    # Fill remaining slots with other articles
    remaining_slots = max_total - len(selected_critical)
    selected_others = others[:remaining_slots]

    return selected_critical + selected_others


def run_fetch_job():
    """Run the fetch job for all categories."""
    logger.info("="*60)
    logger.info(f"Starting scheduled fetch at {datetime.now()}")
    logger.info("="*60)

    service = NewsService()

    for category in Category:
        try:
            logger.info(f"Fetching {category.value}...")
            results = service.fetch_category(
                category=category,
                max_articles=20,
                send_emails=False  # Don't send emails per category
            )

            total_added = sum(r.articles_added for r in results)
            total_dupes = sum(r.articles_duplicated for r in results)

            logger.info(
                f"{category.value}: Added {total_added}, Duplicates {total_dupes}"
            )


        except Exception as e:
            logger.error(f"Error fetching {category.value}: {e}", exc_info=True)

    # Log final stats
    stats = service.get_stats()
    total_count = sum(stats.values())
    logger.info("-"*60)
    logger.info("Fetch complete!")
    logger.info(f"Total articles in database: {total_count}")
    for cat, count in stats.items():
        logger.info(f"  {cat}: {count} articles")

    # Get all accumulated new articles
    all_new_articles = service.get_and_clear_new_articles()

    # Send consolidated digest email
    articles_to_email = [a for a in all_new_articles if a.send_in_mail]
    if articles_to_email and service.email_notifier.is_configured():
        logger.info(f"Preparing consolidated digest with {len(articles_to_email)} articles...")

        # Select articles (max 15, 5 critical reserved)
        selected = select_articles_for_digest(articles_to_email, max_total=15, critical_reserved=5)

        # Get all recipients
        all_recipients = set()
        for article in selected:
            routing = service.email_router.compute_routing(article)
            all_recipients.update(routing.recipients)

        if all_recipients and selected:
            try:
                categories = set(a.category.value for a in selected)
                cat_str = ", ".join(sorted(categories))
                critical_count = sum(1 for a in selected if a.email_routing.priority == Priority.CRITICAL)
                subject = f"[Daily News Digest - {cat_str}] {len(selected)} articles ({critical_count} critical)"

                service.email_notifier.send_digest(
                    articles=selected,
                    recipients=list(all_recipients),
                    subject=subject
                )
                logger.info(f"Sent consolidated digest: {len(selected)} articles to {len(all_recipients)} recipients")
                if len(articles_to_email) > 15:
                    logger.info(f"Note: {len(articles_to_email) - 15} articles were not included (max 15 limit)")
            except Exception as e:
                logger.error(f"Error sending consolidated digest: {e}")

    logger.info("="*60)


def main():
    """Main entry point for cron runner."""
    import argparse

    parser = argparse.ArgumentParser(description="News aggregator cron runner")
    parser.add_argument(
        "--run-once",
        action="store_true",
        help="Run once and exit (don't schedule)"
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=3,
        help="Run interval in hours (default: 3)"
    )

    args = parser.parse_args()

    if args.run_once:
        run_fetch_job()
        return

    # Set up scheduler
    scheduler = BlockingScheduler()

    # Schedule job to run every N hours
    trigger = CronTrigger(hour=f"*/{args.interval}")

    scheduler.add_job(
        run_fetch_job,
        trigger=trigger,
        id="news_fetch",
        name="Fetch news from all sources",
        replace_existing=True
    )

    logger.info(f"Scheduler started. Will run every {args.interval} hours.")
    logger.info("Press Ctrl+C to exit.")

    try:
        scheduler.start()
    except KeyboardInterrupt:
        logger.info("Shutting down scheduler...")
        scheduler.shutdown()
        logger.info("Scheduler stopped.")


if __name__ == "__main__":
    main()
