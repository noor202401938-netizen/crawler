"""
main.py
Universal Website Discovery & Public Contact Extraction Framework.

Usage:
    python main.py
    SEED_FILE="D:\\links.txt" CONCURRENCY=8 python main.py

Pipeline:
    Phase 1: crawl each seed (listing/directory site) -> discover profile URLs
    Phase 2: visit each profile page -> extract generic metadata
    Phase 3: whenever a profile page links to an official website, store it (deduped)
    Phase 4+5: crawl every discovered website -> extract public contact info
    Phase 6: dedup/clean (also happens inline via DB UNIQUE constraints + validators)
    Phase 7: export to CSV / Excel / SQLite
"""

import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import config
from utils.logger import get_logger
from utils.checkpoint import Checkpoint
from utils.exporter import export_all
from database.sqlite_manager import SQLiteManager
from crawler.seed_loader import load_seed_urls
from crawler.directory_crawler import crawl_listing_site, process_profile_page
from crawler.website_crawler import crawl_website

logger = get_logger("main")


def run_phase_1_and_2_and_3(seeds, db, checkpoint):
    """Crawl listing sites, discover profile pages, extract metadata + websites."""
    for seed in seeds:
        if checkpoint.is_seed_done(seed):
            logger.info(f"Skipping already-completed seed: {seed}")
            continue

        logger.info(f"=== Phase 1: crawling seed {seed} ===")
        try:
            profile_links = crawl_listing_site(seed, db)
        except Exception as e:
            logger.error(f"Seed crawl failed for {seed}: {e}")
            continue

        if not profile_links:
            logger.warning(f"No profile links discovered for seed: {seed}")
            checkpoint.mark_seed_done(seed)
            continue

        logger.info(f"=== Phase 2+3: processing {len(profile_links)} profile pages for {seed} ===")
        with ThreadPoolExecutor(max_workers=config.CONCURRENCY) as pool:
            futures = {
                pool.submit(process_profile_page, url, seed, db): url
                for url in profile_links
            }
            done_count = 0
            for future in as_completed(futures):
                url = futures[future]
                try:
                    future.result()
                except Exception as e:
                    logger.error(f"Profile page failed ({url}): {e}")
                done_count += 1
                if done_count % config.CHECKPOINT_EVERY_N_ITEMS == 0:
                    logger.info(f"  ...{done_count}/{len(profile_links)} profile pages processed")

        checkpoint.mark_seed_done(seed)


def run_phase_4_and_5(db, checkpoint):
    """Crawl every discovered official website and extract public contact info."""
    websites = db.get_all_websites()
    pending = [w for w in websites if not checkpoint.is_website_done(w["canonical_url"])]

    logger.info(f"=== Phase 4+5: crawling {len(pending)} discovered websites "
                f"({len(websites) - len(pending)} already done) ===")

    with ThreadPoolExecutor(max_workers=config.CONCURRENCY) as pool:
        futures = {
            pool.submit(crawl_website, w["canonical_url"], db): w["canonical_url"]
            for w in pending
        }
        done_count = 0
        for future in as_completed(futures):
            website_url = futures[future]
            try:
                record = future.result()
                if record:
                    db.save_contact(record)
            except Exception as e:
                logger.error(f"Website crawl failed ({website_url}): {e}")
            finally:
                checkpoint.mark_website_done(website_url)
                done_count += 1
                if done_count % config.CHECKPOINT_EVERY_N_ITEMS == 0:
                    logger.info(f"  ...{done_count}/{len(pending)} websites processed")


def main():
    os.makedirs(config.OUTPUT_DIR, exist_ok=True)
    os.makedirs(config.LOG_DIR, exist_ok=True)

    start = time.time()
    logger.info("=== Universal Website Discovery & Contact Extraction Framework ===")
    logger.info(f"Seed file: {config.SEED_FILE}")
    logger.info(f"Concurrency: {config.CONCURRENCY} | Max depth: {config.MAX_CRAWL_DEPTH} | "
                f"Respect robots.txt: {config.RESPECT_ROBOTS_TXT}")

    db = SQLiteManager()
    checkpoint = Checkpoint()

    seeds = load_seed_urls()
    if not seeds:
        logger.error("No seed URLs loaded -- check config.SEED_FILE. Exiting.")
        return

    run_phase_1_and_2_and_3(seeds, db, checkpoint)
    run_phase_4_and_5(db, checkpoint)

    logger.info("=== Phase 6+7: cleaning & exporting ===")
    export_all(db)

    elapsed = time.time() - start
    logger.info(f"Done in {elapsed:.1f}s. Outputs written to '{config.OUTPUT_DIR}/'.")


if __name__ == "__main__":
    main()
