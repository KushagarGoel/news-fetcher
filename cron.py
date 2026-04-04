"""Scheduled job runner for news aggregator."""

import logging
import sys
from datetime import datetime
from pathlib import Path

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

sys.path.insert(0, str(Path(__file__).parent))

from src.models import Category
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


def run_fetch_job():
    """Run the fetch job for all categories."""
    logger.info("="*60)
    logger.info(f"Starting scheduled fetch at {datetime.now()}")
    logger.info("="*60)

    service = NewsService()
    all_new_articles = 0

    for category in Category:
        try:
            logger.info(f"Fetching {category.value}...")
            results = service.fetch_category(
                category=category,
                max_articles=20,
                send_emails=True
            )

            total_added = sum(r.articles_added for r in results)
            total_dupes = sum(r.articles_duplicated for r in results)

            logger.info(
                f"{category.value}: Added {total_added}, Duplicates {total_dupes}"
            )
            all_new_articles += total_added

        except Exception as e:
            logger.error(f"Error fetching {category.value}: {e}", exc_info=True)

    # Log final stats
    stats = service.get_stats()
    logger.info("-"*60)
    logger.info("Fetch complete!")
    logger.info(f"New articles: {all_new_articles}")
    for cat, count in stats.items():
        logger.info(f"  {cat}: {count} articles")
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
