"""
utils/http_client.py
A shared, polite HTTP fetcher:
- per-domain rate limiting
- retries with backoff
- robots.txt compliance (optional but on by default)
"""

import atexit
import threading
import time
import urllib.robotparser as robotparser
from urllib.parse import urlsplit

import requests
from requests.exceptions import InvalidSchema, InvalidURL, MissingSchema, SSLError, TooManyRedirects

try:
    from playwright.sync_api import sync_playwright
    from playwright_stealth import Stealth

    HAS_PLAYWRIGHT = True
except ImportError:
    HAS_PLAYWRIGHT = False

import config
from utils.logger import get_logger
from utils.normalizer import get_domain

logger = get_logger("http_client")

_stealth = Stealth() if HAS_PLAYWRIGHT else None

_domain_last_request: dict = {}
_domain_locks: dict = {}
_lock_guard = threading.Lock()

_robots_cache: dict = {}
_robots_lock = threading.Lock()

_playwright_local = threading.local()
_playwright_instances: list = []
_playwright_lock = threading.Lock()

# Session persistence: store cookies and localStorage per domain
_domain_sessions: dict = {}
_session_lock = threading.Lock()


def _cleanup_playwright():
    """Clean up all Playwright instances on exit."""
    with _playwright_lock:
        for pw in _playwright_instances:
            try:
                if hasattr(pw, "context") and pw.context:
                    pw.context.close()
                if hasattr(pw, "browser") and pw.browser:
                    pw.browser.close()
                if hasattr(pw, "playwright") and pw.playwright:
                    pw.playwright.stop()
            except Exception:  # nosec B110
                pass
        _playwright_instances.clear()


atexit.register(_cleanup_playwright)


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

        rp: robotparser.RobotFileParser | None = robotparser.RobotFileParser()
        scheme = urlsplit(base_url).scheme or "https"
        robots_url = f"{scheme}://{domain}/robots.txt"
        try:
            resp = requests.get(
                robots_url,
                timeout=config.REQUEST_TIMEOUT,
                headers={"User-Agent": config.USER_AGENT},
            )
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
    except (requests.RequestException, ValueError) as e:
        logger.debug(f"Robots.txt check failed for {url}: {e}")
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

    def _is_terminal_exception(exc: Exception) -> bool:
        if isinstance(exc, (InvalidURL, MissingSchema, InvalidSchema, TooManyRedirects, SSLError)):
            return True
        message = str(exc).lower()
        terminal_markers = (
            "invalid url",
            "no host supplied",
            "name or service not known",
            "getaddrinfo failed",
            "nameresolutionerror",
            "certificate verify failed",
            "hostname mismatch",
            "exceeded 30 redirects",
        )
        return any(marker in message for marker in terminal_markers)

    def _push_domain_cooldown(wait_seconds: float):
        lock = _get_domain_lock(domain)
        with lock:
            _domain_last_request[domain] = time.time() + wait_seconds

    for attempt in range(1, config.RETRY_ATTEMPTS + 1):
        _wait_for_domain_slot(domain)
        try:
            resp = requests.request(
                method,
                url,
                headers=headers,
                timeout=config.REQUEST_TIMEOUT,
                allow_redirects=allow_redirects,
            )
            if resp.status_code == 429:
                # rate limited -- back off harder
                wait = config.RETRY_BACKOFF_SECONDS * attempt * 2
                logger.warning(f"429 from {domain}, backing off {wait:.1f}s")
                _push_domain_cooldown(wait)
                time.sleep(wait)
                continue
            if resp.status_code in (403, 404, 410):
                return resp
            return resp
        except requests.RequestException as e:
            logger.warning(f"Attempt {attempt}/{config.RETRY_ATTEMPTS} failed for {url}: {e}")
            if _is_terminal_exception(e):
                break
            if attempt < config.RETRY_ATTEMPTS:
                time.sleep(config.RETRY_BACKOFF_SECONDS * attempt)

    logger.error(f"Giving up on {url} after {config.RETRY_ATTEMPTS} attempts")
    return None


_playwright_local = threading.local()


class MockResponse:
    def __init__(self, text, status_code, headers):
        self.text = text
        self.status_code = status_code
        self.headers = headers


def _get_playwright_page():
    if not hasattr(_playwright_local, "playwright"):
        pw = sync_playwright().start()
        browser = pw.chromium.launch(headless=True)
        context = browser.new_context(user_agent=config.USER_AGENT, ignore_https_errors=True)
        _playwright_local.playwright = pw
        _playwright_local.browser = browser
        _playwright_local.context = context
        with _playwright_lock:
            _playwright_instances.append(_playwright_local)
    page = _playwright_local.context.new_page()
    _stealth.apply_stealth_sync(page)
    return page


def _save_session(domain: str, context):
    """Persist cookies and localStorage for a domain."""
    if not config.PERSIST_SESSION:
        return
    try:
        cookies = context.cookies()
        # Get localStorage via evaluate
        local_storage = context.evaluate("() => JSON.stringify(localStorage)")
        with _session_lock:
            _domain_sessions[domain] = {
                "cookies": cookies,
                "localStorage": local_storage,
                "timestamp": time.time(),
            }
        logger.debug(f"Saved session for {domain}: {len(cookies)} cookies")
    except Exception as e:
        logger.debug(f"Failed to save session for {domain}: {e}")


def _load_session(domain: str, context):
    """Restore cookies and localStorage for a domain."""
    if not config.PERSIST_SESSION:
        return
    with _session_lock:
        session = _domain_sessions.get(domain)
    if not session:
        return
    try:
        if session.get("cookies"):
            context.add_cookies(session["cookies"])
        if session.get("localStorage"):
            context.evaluate(
                f"() => {{ const data = {session['localStorage']}; for (const [k, v] of Object.entries(data)) localStorage.setItem(k, v); }}"
            )
        logger.debug(f"Restored session for {domain}: {len(session.get('cookies', []))} cookies")
    except Exception as e:
        logger.debug(f"Failed to load session for {domain}: {e}")


def _perform_login(page, domain: str):
    """Perform login using configured credentials for a domain."""
    creds = config.LOGIN_CREDENTIALS.get(domain)
    if not creds:
        return False

    login_url = creds.get("login_url")
    if not login_url:
        logger.debug(f"No login_url configured for {domain}")
        return False

    try:
        logger.info(f"Attempting login for {domain} at {login_url}")
        # Navigate to login page
        response = page.goto(
            login_url, wait_until="domcontentloaded", timeout=config.REQUEST_TIMEOUT * 1000
        )
        if not response or response.status >= 400:
            logger.warning(
                f"Login page load failed for {domain}: {response.status if response else 'no response'}"
            )
            return False

        # Fill username
        username_selector = creds.get(
            "username_selector",
            "input[name=username], input[name=email], input[type=email], #username, #email",
        )
        password_selector = creds.get(
            "password_selector", "input[name=password], input[type=password], #password"
        )
        submit_selector = creds.get(
            "submit_selector",
            "button[type=submit], input[type=submit], button:has-text('Login'), button:has-text('Sign in'), button:has-text('Sign In')",
        )

        try:
            page.fill(username_selector, creds["username"], timeout=3000)
            page.fill(password_selector, creds["password"], timeout=3000)
            page.click(submit_selector, timeout=3000)
            page.wait_for_load_state("networkidle", timeout=10000)
            logger.info(f"Login submitted for {domain}")
            return True
        except Exception as e:
            logger.warning(f"Login form interaction failed for {domain}: {e}")
            return False
    except Exception as e:
        logger.warning(f"Login failed for {domain}: {e}")
        return False


def _execute_custom_interactions(page, domain: str):
    """Execute custom interaction sequence for a domain."""
    interactions = config.CUSTOM_INTERACTIONS.get(domain, [])
    if not interactions:
        return

    for i, interaction in enumerate(interactions):
        action = interaction.get("action")
        selector = interaction.get("selector")
        timeout = interaction.get("timeout", 5000)
        try:
            if action == "click":
                if selector:
                    page.click(selector, timeout=timeout)
                else:
                    logger.warning(f"Click action requires selector for {domain} interaction {i}")
            elif action == "fill":
                value = interaction.get("value", "")
                if selector:
                    page.fill(selector, value, timeout=timeout)
                else:
                    logger.warning(f"Fill action requires selector for {domain} interaction {i}")
            elif action == "wait":
                page.wait_for_timeout(timeout)
            elif action == "scroll":
                direction = interaction.get("direction", "down")
                if direction == "down":
                    page.evaluate("() => window.scrollBy(0, window.innerHeight)")
                elif direction == "up":
                    page.evaluate("() => window.scrollBy(0, -window.innerHeight)")
                elif direction == "bottom":
                    page.evaluate("() => window.scrollTo(0, document.body.scrollHeight)")
                elif direction == "top":
                    page.evaluate("() => window.scrollTo(0, 0)")
                page.wait_for_timeout(500)
            elif action == "wait_for_selector":
                if selector:
                    page.wait_for_selector(selector, timeout=timeout)
                else:
                    logger.warning(
                        f"wait_for_selector requires selector for {domain} interaction {i}"
                    )
            elif action == "wait_for_navigation":
                page.wait_for_load_state("networkidle", timeout=timeout)
            else:
                logger.warning(f"Unknown action '{action}' for {domain} interaction {i}")
        except Exception as e:
            logger.debug(f"Custom interaction {i} ({action}) failed for {domain}: {e}")


def _dismiss_popups(page):
    """Dismiss common cookie banners, consent dialogs, and popups."""
    # Common selectors for cookie/consent buttons
    dismiss_selectors = [
        # Generic accept buttons
        'button:has-text("Accept")',
        'button:has-text("Accept All")',
        'button:has-text("Accept all")',
        'button:has-text("Agree")',
        'button:has-text("Allow")',
        'button:has-text("Allow All")',
        'button:has-text("Allow all")',
        'button:has-text("Consent")',
        'button:has-text("I Agree")',
        'button:has-text("I Accept")',
        'button:has-text("Got it")',
        'button:has-text("Okay")',
        'button:has-text("OK")',
        'button:has-text("Continue")',
        # GDPR / EU common
        'button:has-text("Accepteren")',  # Dutch
        'button:has-text("Akzeptieren")',  # German
        'button:has-text("Accepter")',  # French
        'button:has-text("Aceptar")',  # Spanish
        'button:has-text("Accetto")',  # Italian
        'button:has-text("Aceitar")',  # Portuguese
        # Close buttons
        'button[aria-label="Close"]',
        'button[aria-label="Dismiss"]',
        'button[aria-label="close"]',
        'button[aria-label="dismiss"]',
        '[data-testid="cookie-banner-accept"]',
        '[data-testid="consent-accept"]',
        "#onetrust-accept-btn-handler",
        ".onetrust-close-btn-handler",
        "#cookie-banner button",
        ".cookie-banner button",
        "#consent-banner button",
        ".consent-banner button",
        '[id*="cookie"] button',
        '[class*="cookie"] button',
        '[id*="consent"] button',
        '[class*="consent"] button',
        '[id*="gdpr"] button',
        '[class*="gdpr"] button',
    ]

    for selector in dismiss_selectors:
        try:
            # Try to click if visible
            locator = page.locator(selector).first
            if locator.is_visible(timeout=500):
                locator.click(timeout=1000)
                logger.debug(f"Dismissed popup with selector: {selector}")
                page.wait_for_timeout(300)  # Brief wait for animation
                return True
        except Exception:  # nosec B112
            continue
    return False


def _handle_load_more(page, max_clicks: int = 3):
    """Click 'Load more' / 'Show more' buttons to reveal additional content."""
    load_more_selectors = [
        'button:has-text("Load more")',
        'button:has-text("Load More")',
        'button:has-text("Show more")',
        'button:has-text("Show More")',
        'button:has-text("View more")',
        'button:has-text("View More")',
        'button:has-text("See more")',
        'button:has-text("See More")',
        'a:has-text("Load more")',
        'a:has-text("Show more")',
        '[data-testid="load-more"]',
        '[data-action="load-more"]',
        ".load-more button",
        ".show-more button",
        ".load-more a",
        ".show-more a",
    ]

    clicks = 0
    while clicks < max_clicks:
        clicked = False
        for selector in load_more_selectors:
            try:
                locator = page.locator(selector).first
                if locator.is_visible(timeout=500):
                    # Scroll into view first
                    locator.scroll_into_view_if_needed(timeout=1000)
                    page.wait_for_timeout(300)
                    locator.click(timeout=2000)
                    logger.debug(f"Clicked load-more with selector: {selector}")
                    page.wait_for_timeout(1000)  # Wait for content to load
                    clicked = True
                    clicks += 1
                    break
            except Exception:  # nosec B112
                continue
        if not clicked:
            break


def fetch_with_js(url: str):
    if not HAS_PLAYWRIGHT:
        logger.error(
            "Playwright not installed! Use 'pip install playwright' and 'playwright install'"
        )
        return None

    domain = get_domain(url)
    if not is_allowed_by_robots(url):
        return None

    _wait_for_domain_slot(domain)

    page = None
    try:
        page = _get_playwright_page()
        context = page.context

        # Load persisted session (cookies + localStorage)
        _load_session(domain, context)

        # Timeout in milliseconds
        response = page.goto(
            url, wait_until="domcontentloaded", timeout=config.REQUEST_TIMEOUT * 1000
        )

        if not response:
            return None

        status = response.status
        if status == 429:
            # Same backoff logic...
            wait = config.RETRY_BACKOFF_SECONDS * 2
            lock = _get_domain_lock(domain)
            with lock:
                _domain_last_request[domain] = time.time() + wait
            time.sleep(wait)
            return None

        # Check if we need to login (401/403 on protected pages)
        if status in (401, 403):
            logger.info(f"Got {status} for {url}, attempting login for {domain}")
            if _perform_login(page, domain):
                # Retry the original URL after login
                response = page.goto(
                    url, wait_until="domcontentloaded", timeout=config.REQUEST_TIMEOUT * 1000
                )
                if not response:
                    return None
                status = response.status

        # Dismiss common cookie/consent banners and popups
        _dismiss_popups(page)

        # Execute custom interactions for this domain
        _execute_custom_interactions(page, domain)

        # Give it a tiny bit of time for SPA to render
        try:
            page.wait_for_load_state("networkidle", timeout=3000)
        except Exception as e:
            logger.debug(f"Network idle timeout for {url}: {e}")

        # Handle infinite scroll / "load more" buttons (basic)
        _handle_load_more(page)

        # Save session for reuse
        _save_session(domain, context)

        html = page.content()
        headers = response.all_headers()

        return MockResponse(html, status, headers)
    except Exception as e:
        logger.warning(f"Playwright fetch failed for {url}: {e}")
        return None
    finally:
        if page:
            try:
                page.close()
            except Exception as e:
                logger.debug(f"Error closing Playwright page: {e}")


def fetch_smart(url: str, method: str = "GET", allow_redirects: bool = True):
    """
    Intelligently fetch a URL. Tries standard requests first.
    If it looks like an SPA or Anti-bot challenge, falls back to JS rendering.
    """
    resp = fetch(url, method, allow_redirects)

    if not config.USE_SMART_JS_FALLBACK or not HAS_PLAYWRIGHT:
        return resp

    if resp is None:
        return None

    text_lower = resp.text.lower()

    # Check for anti-bot
    if resp.status_code in (401, 403, 503):
        logger.info(f"Detected anti-bot/forbidden at {url}. Falling back to Playwright.")
        return fetch_with_js(url)

    # Check for SPA
    content_length = len(resp.text)
    if resp.status_code == 200 and content_length < 3000:
        # A very small body with a root div often indicates a React/Vue SPA
        if 'id="root"' in text_lower or 'id="app"' in text_lower or "<app-root>" in text_lower:
            logger.info(f"Detected SPA at {url}. Falling back to Playwright.")
            return fetch_with_js(url)

    return resp
