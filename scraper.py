import logging
import re
from datetime import datetime

import pandas as pd
from jobspy import scrape_jobs

import config
import database

logger = logging.getLogger(__name__)

# Track last scrape time for notifications
last_scrape_time = None


def filter_irrelevant_jobs(df):
    """Remove jobs whose titles indicate irrelevant roles.
    Keep anything that matches include keywords; drop anything matching exclude patterns."""
    if df is None or df.empty:
        return df

    include_re = re.compile(
        "|".join(re.escape(kw) for kw in config.TITLE_INCLUDE_KEYWORDS),
        re.IGNORECASE,
    )
    exclude_re = re.compile(
        "|".join(config.TITLE_EXCLUDE_PATTERNS),
        re.IGNORECASE,
    )

    def keep(title):
        if not title or str(title) in ("nan", "None", ""):
            return True  # no title info — keep by default
        t = str(title)
        if include_re.search(t):
            return True
        if exclude_re.search(t):
            return False
        return True  # default to keeping ambiguous titles

    mask = df["title"].apply(keep)
    dropped = len(df) - mask.sum()
    if dropped > 0:
        logger.info(f"Filtered out {dropped} irrelevant job(s) by title")
    return df[mask].reset_index(drop=True)


def fetch_jobs():
    """Fetch DBA jobs from all configured sites and store in database.
    Returns the count of newly inserted jobs."""
    global last_scrape_time
    before_scrape = datetime.now().isoformat()

    all_jobs = []
    for term in config.SEARCH_TERMS:
        logger.info(f"Searching for '{term}' across {config.SITES}...")
        try:
            jobs_df = scrape_jobs(
                site_name=config.SITES,
                search_term=term,
                location=config.LOCATION,
                is_remote=config.IS_REMOTE,
                hours_old=config.HOURS_OLD,
                results_wanted=config.RESULTS_WANTED,
                country_indeed=config.COUNTRY_INDEED,
            )
            if jobs_df is not None and not jobs_df.empty:
                logger.info(f"  Found {len(jobs_df)} results for '{term}'")
                all_jobs.append(jobs_df)
            else:
                logger.info(f"  No results for '{term}'")
        except Exception as e:
            logger.error(f"  Error searching '{term}': {e}")

    if not all_jobs:
        logger.info("No jobs found across all search terms.")
        last_scrape_time = before_scrape
        database.set_metadata("last_scrape_time", before_scrape)
        return 0

    combined = pd.concat(all_jobs, ignore_index=True)
    combined = combined.drop_duplicates(subset=["job_url"], keep="first")
    logger.info(f"Total unique jobs fetched: {len(combined)}")

    # Filter out irrelevant software engineering roles
    combined = filter_irrelevant_jobs(combined)
    logger.info(f"Jobs after filtering: {len(combined)}")

    new_count = database.upsert_jobs(combined)
    logger.info(f"New jobs inserted: {new_count}")

    last_scrape_time = before_scrape
    database.set_metadata("last_scrape_time", before_scrape)
    return new_count


def get_last_scrape_time():
    return last_scrape_time
