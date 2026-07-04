"""
utils/http_client.py
A shared, polite HTTP fetcher:
- per-domain rate limiting
- retries with backoff
- robots.txt compliance (optional but on by default)
"""

import threading
import time
import urllib.robotparser as robotparser
from urllib.parse import urlsplit

import requests

import config
from utils.logger import get_logger
from utils.normalizer import get_domain

logger = get_logger("http_client")

_domain_last_request = {}
_domain_locks = {}
_lock_guard = threading.Lock()

_robots_cache = {}
_robots_lock = threading.Lock()


def _get_domain_lock(domain: str) -> threading.Lock:
    with _lock_guard:
        if domain not in _domain_locks:
            _domain_locks[domain] = threading.Lock()
        return _domain_locks[domain]


def _wait_for_domain_slot(domain: str):
    lock = _get_domain_lock(domain)
    with lock:
        last = _domain_last_request.get(domain, 0)
        elapsed = time.time() - last
        if elapsed < config.MIN_DELAY_PER_DOMAIN:
            time.sleep(config.MIN_DELAY_PER_DOMAIN - elapsed)
        _domain_last_request[domain] = time.time()


def _get_robots_parser(base_url: str):
    domain = get_domain(base_url)
    with _robots_lock:
        if domain in _robots_cache:
            return _robots_cache[domain]

        rp = robotparser.RobotFileParser()
        scheme = urlsplit(base_url).scheme or "https"
        robots_url = f"{scheme}://{domain}/robots.txt"
        try:
            resp = requests.get(robots_url, timeout=config.REQUEST_TIMEOUT,
                                 headers={"User-Agent": config.USER_AGENT})
            if resp.status_code == 200:
                rp.parse(resp.text.splitlines())
            else:
                rp = None  # no robots.txt / inaccessible -> treat as "allow"
        except requests.RequestException:
            rp = None

        _robots_cache[domain] = rp
        return rp


def is_allowed_by_robots(url: str) -> bool:
    if not config.RESPECT_ROBOTS_TXT:
        return True
    try:
        rp = _get_robots_parser(url)
        if rp is None:
            return True
        return rp.can_fetch(config.USER_AGENT, url)
    except Exception:
        return True  # fail open on robots.txt parsing errors


def fetch(url: str, method: str = "GET", allow_redirects: bool = True):
    """
    Fetch a URL politely with retries. Returns a requests.Response or None.
    """
    domain = get_domain(url)

    if not is_allowed_by_robots(url):
        logger.info(f"Skipping (robots.txt disallow): {url}")
        return None

    headers = {"User-Agent": config.USER_AGENT}

    for attempt in range(1, config.RETRY_ATTEMPTS + 1):
        _wait_for_domain_slot(domain)
        try:
            resp = requests.request(
                method, url, headers=headers,
                timeout=config.REQUEST_TIMEOUT,
                allow_redirects=allow_redirects,
            )
            if resp.status_code == 429:
                # rate limited -- back off harder
                wait = config.RETRY_BACKOFF_SECONDS * attempt * 2
                logger.warning(f"429 from {domain}, backing off {wait:.1f}s")
                time.sleep(wait)
                continue
            return resp
        except requests.RequestException as e:
            logger.warning(f"Attempt {attempt}/{config.RETRY_ATTEMPTS} failed for {url}: {e}")
            if attempt < config.RETRY_ATTEMPTS:
                time.sleep(config.RETRY_BACKOFF_SECONDS * attempt)

    logger.error(f"Giving up on {url} after {config.RETRY_ATTEMPTS} attempts")
    return None
