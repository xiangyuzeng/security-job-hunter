#!/usr/bin/env python3
"""Standalone scraper entry point for GitHub Actions or manual runs.
Connects to Turso (if configured) or local SQLite, runs the scraper,
and sends email notifications if configured."""

import logging
from datetime import datetime

import database
import scraper
import notifier

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def main():
    logger.info("Initializing database...")
    database.init_db()

    logger.info("Starting job scrape...")
    before = datetime.now().isoformat()
    new_count = scraper.fetch_jobs()

    logger.info(f"Scrape complete: {new_count} new jobs inserted.")

    if new_count > 0 and notifier.is_configured():
        new_jobs = database.get_new_jobs_since(before)
        notifier.send_notification(new_jobs)
        logger.info(f"Email notification sent for {len(new_jobs)} new jobs.")

    logger.info("Done.")


if __name__ == "__main__":
    main()
