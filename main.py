"""
main.py
Universal Website Discovery & Public Contact Extraction Framework.

Usage:
    python main.py
    SEED_FILE="D:\\links.txt" CONCURRENCY=8 python main.py
    python main.py --extract emails,phones --custom-prompt "extract pricing tables"

Pipeline:
    Phase 1: crawl each seed (listing/directory site) -> discover profile URLs
    Phase 2: visit each profile page -> extract generic metadata
    Phase 3: whenever a profile page links to an official website, store it (deduped)
    Phase 4+5: crawl every discovered website -> extract public contact info
    Phase 6: dedup/clean (also happens inline via DB UNIQUE constraints + validators)
    Phase 7: export to CSV / Excel / SQLite
"""

import argparse
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests

import config
from crawler.directory_crawler import crawl_listing_site, process_profile_page
from crawler.seed_loader import load_seed_urls
from crawler.website_crawler import crawl_website
from database.sqlite_manager import SQLiteManager
from utils.checkpoint import Checkpoint
from utils.exporter import export_all
from utils.logger import get_logger

logger = get_logger("main")


def parse_extraction_args():
    """Parse command-line arguments for extraction goals."""
    parser = argparse.ArgumentParser(
        description="Universal Website Discovery & Public Contact Extraction Framework",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py
  python main.py --extract emails,phones
  python main.py --extract images,articles,products
  python main.py --custom-prompt "extract pricing tables"
  python main.py --extract emails --custom-prompt "find job openings"
        """,
    )
    parser.add_argument(
        "--extract",
        type=str,
        default="",
        help="Comma-separated extraction targets: emails, phones, images, articles, products",
    )
    parser.add_argument(
        "--custom-prompt",
        type=str,
        default="",
        help="Custom extraction prompt for LLM (requires GEMINI_API_KEY)",
    )
    parser.add_argument(
        "--seed-file",
        type=str,
        default=None,
        help="Path to seed URLs file (overrides SEED_FILE env var)",
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=None,
        help="Number of parallel workers (overrides CONCURRENCY env var)",
    )
    parser.add_argument(
        "--max-depth",
        type=int,
        default=None,
        help="Max crawl depth per website (overrides MAX_CRAWL_DEPTH env var)",
    )
    parser.add_argument(
        "--no-js-fallback", action="store_true", help="Disable smart JS fallback (Playwright)"
    )
    return parser.parse_args()


def apply_extraction_args(args):
    """Apply parsed arguments to config."""
    # Override config from command line
    if args.seed_file:
        config.SEED_FILE = args.seed_file
    if args.concurrency is not None:
        config.CONCURRENCY = args.concurrency
    if args.max_depth is not None:
        config.MAX_CRAWL_DEPTH = args.max_depth
    if args.no_js_fallback:
        config.USE_SMART_JS_FALLBACK = False

    # Parse extraction targets
    if args.extract:
        # Reset all standard flags to False
        config.EXTRACT_EMAILS = False
        config.EXTRACT_PHONES = False
        config.EXTRACT_IMAGES = False
        config.EXTRACT_ARTICLES = False
        config.EXTRACT_PRODUCTS = False
        config.CUSTOM_PROMPT = ""

        targets = [t.strip().lower() for t in args.extract.split(",")]
        is_custom = True

        for t in targets:
            if "email" in t:
                config.EXTRACT_EMAILS = True
                is_custom = False
            elif "phone" in t:
                config.EXTRACT_PHONES = True
                is_custom = False
            elif "image" in t:
                config.EXTRACT_IMAGES = True
                is_custom = False
            elif "article" in t:
                config.EXTRACT_ARTICLES = True
                is_custom = False
            elif "product" in t:
                config.EXTRACT_PRODUCTS = True
                is_custom = False

        # If it didn't match any standard targets, treat the whole input as a custom prompt
        if is_custom and args.extract:
            config.CUSTOM_PROMPT = args.extract

    # Apply custom prompt if provided
    if args.custom_prompt:
        config.CUSTOM_PROMPT = args.custom_prompt
        if not config.GEMINI_API_KEY:
            logger.warning(
                "Custom extraction requested but GEMINI_API_KEY is not set. "
                "Custom extraction will fail unless the key is provided."
            )

    # Print configuration
    print("\n" + "=" * 60)
    print("Universal Goal-Oriented AI Crawler")
    print("=" * 60)
    print("Starting crawl with the following goals:")
    print(f"- Emails: {config.EXTRACT_EMAILS}")
    print(f"- Phones: {config.EXTRACT_PHONES}")
    print(f"- Images: {config.EXTRACT_IMAGES}")
    print(f"- Articles: {config.EXTRACT_ARTICLES}")
    print(f"- Products: {config.EXTRACT_PRODUCTS}")
    if config.CUSTOM_PROMPT:
        print(f"- Custom Prompt: '{config.CUSTOM_PROMPT}'")
    print("=" * 60 + "\n")


def run_phase_1_and_2_and_3(seeds, db, checkpoint):
    """Crawl listing sites, discover profile pages, extract metadata + websites."""
    for seed in seeds:
        if checkpoint.is_seed_done(seed):
            logger.info(f"Skipping already-completed seed: {seed}")
            continue

        logger.info(f"=== Phase 1: crawling seed {seed} ===")
        try:
            profile_links = crawl_listing_site(seed, db)
        except (requests.RequestException, ValueError, RuntimeError) as e:
            logger.error(f"Seed crawl failed for {seed}: {e}")
            continue

        if not profile_links:
            logger.warning(f"No profile links discovered for seed: {seed}")
            checkpoint.mark_seed_done(seed)
            continue

        logger.info(f"=== Phase 2+3: processing {len(profile_links)} profile pages for {seed} ===")
        with ThreadPoolExecutor(max_workers=config.CONCURRENCY) as pool:
            futures = {
                pool.submit(process_profile_page, url, seed, db): url for url in profile_links
            }
            done_count = 0
            for future in as_completed(futures):
                url = futures[future]
                try:
                    future.result()
                except (requests.RequestException, ValueError, RuntimeError) as e:
                    logger.error(f"Profile page failed ({url}): {e}")
                done_count += 1
                if done_count % config.CHECKPOINT_EVERY_N_ITEMS == 0:
                    logger.info(f"  ...{done_count}/{len(profile_links)} profile pages processed")

        checkpoint.mark_seed_done(seed)


def run_phase_4_and_5(db, checkpoint):
    """Crawl every discovered official website and extract public contact info."""
    websites = db.get_all_websites()
    pending = [w for w in websites if not checkpoint.is_website_done(w["canonical_url"])]

    logger.info(
        f"=== Phase 4+5: crawling {len(pending)} discovered websites "
        f"({len(websites) - len(pending)} already done) ==="
    )

    with ThreadPoolExecutor(max_workers=config.CONCURRENCY) as pool:
        futures = {
            pool.submit(crawl_website, w["canonical_url"], db): w["canonical_url"] for w in pending
        }
        done_count = 0
        for future in as_completed(futures):
            website_url = futures[future]
            try:
                record = future.result()
                if record:
                    db.save_contact(record)
            except (requests.RequestException, ValueError, RuntimeError) as e:
                logger.error(f"Website crawl failed ({website_url}): {e}")
            finally:
                checkpoint.mark_website_done(website_url)
                done_count += 1
                if done_count % config.CHECKPOINT_EVERY_N_ITEMS == 0:
                    logger.info(f"  ...{done_count}/{len(pending)} websites processed")


def main():
    args = parse_extraction_args()
    apply_extraction_args(args)

    os.makedirs(config.OUTPUT_DIR, exist_ok=True)
    os.makedirs(config.LOG_DIR, exist_ok=True)

    start = time.time()
    logger.info("=== Universal Website Discovery & Contact Extraction Framework ===")
    logger.info(f"Seed file: {config.SEED_FILE}")
    logger.info(
        f"Concurrency: {config.CONCURRENCY} | Max depth: {config.MAX_CRAWL_DEPTH} | "
        f"Respect robots.txt: {config.RESPECT_ROBOTS_TXT}"
    )

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
