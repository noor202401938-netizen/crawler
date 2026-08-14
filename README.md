# Universal Website Discovery & Contact Extraction Engine

**Turn any directory or listing site into a structured, verified contact database — no code, no selectors, no maintenance.**

---

## What Is This?

A **config-driven, AI-enhanced data acquisition engine** that takes a list of seed URLs (directory sites, association listings, marketplaces, etc.) and automatically:

1. **Discovers** every profile/detail page on each listing site (handles pagination, infinite scroll, SPA)
2. **Extracts** organization metadata — name, address, category, website — using schema.org + layout-agnostic heuristics
3. **Finds** the official external website for each entity (deduplicated & canonicalized)
4. **Crawls** every discovered website, prioritizing contact/about/team pages
5. **Pulls** public contact intelligence: emails, phones, contact forms, social profiles, images, articles, products
6. **Cleans & validates** everything (format checks, false-positive filtering, dedup)
7. **Exports** to CSV, Excel, and SQLite — ready for CRM import, outreach tools, or analysis

**Zero site-specific code.** The only thing that changes between projects is your seed file.

---

## What Does It Do?

| Phase | Operation | Output |
|-------|-----------|--------|
| **0** | Load seed URLs from file | `seeds[]` |
| **1** | Crawl listing sites, follow pagination | Profile URLs discovered |
| **2** | Visit each profile, extract metadata (JSON-LD + heuristics) | Name, address, category, website |
| **3** | Identify & normalize official external website | Canonical website URLs |
| **4** | Crawl each website (priority paths → BFS, depth/page limits) | Pages visited per domain |
| **5** | Extract contacts + optional: images, articles, products, custom LLM prompts | Structured contact records |
| **6** | Dedupe, validate, filter false positives | Clean data |
| **7** | Export to `output/` | CSV, Excel, SQLite |

### Extraction Capabilities (toggleable)
- **Emails** — `mailto:` links + regex, validated (MX-ready)
- **Phones** — `tel:` links + international regex, normalized to E.164
- **Social** — Facebook, X/Twitter, LinkedIn, Instagram, YouTube, TikTok, Pinterest, Threads
- **Contact pages & forms** — Detected via path hints + form presence
- **Images** — All `<img>` src URLs (absolute, filtered)
- **Articles** — `<article>` tags or long-form `<p>` blocks
- **Products** — Schema.org Product JSON-LD + heuristic fallback
- **Custom (LLM)** — Any prompt via Google Gemini (e.g., "extract pricing tiers", "find job openings", "list certifications")

---

## Anti-Blocking & Advanced Interaction Features

| Feature | Description | Config |
|---------|-------------|--------|
| **Smart JS Fallback** | Auto-detects SPAs/anti-bot → renders with headless Chromium + stealth | `USE_SMART_JS_FALLBACK=true` |
| **Popup/Cookie Banner Dismissal** | Auto-clicks "Accept", "Agree", "Allow", GDPR buttons (15+ languages) | Built-in |
| **Load More / Infinite Scroll** | Clicks "Load more", "Show more", "View more" buttons (up to 3x/page) | Built-in |
| **Session Persistence** | Saves/restores cookies + localStorage per domain across requests | `PERSIST_SESSION=true` |
| **Login Wall Handling** | Detects 401/403 → navigates to login_url → fills form → retries original URL | `LOGIN_CREDENTIALS` |
| **Custom JS Interactions** | Per-domain sequences: click, fill, scroll, wait, wait_for_selector, wait_for_navigation | `CUSTOM_INTERACTIONS` |

---

## Who Is This For?

| Role | Use Case |
|------|----------|
| **Sales/RevOps teams** | Build territory lead lists from industry directories (Chamber of Commerce, Angie's List, Clutch, G2, etc.) |
| **Lead gen agencies** | Deliver verified prospect data to clients — whitelabel the output |
| **Market researchers / PE / VC** | Map fragmented markets (local services, niche B2B, franchises) in hours |
| **Growth / SEO teams** | Programmatic page generation: "Plumber in [City]" pages with real business data |
| **Data engineers** | Replace brittle scrapers with a maintainable, resumable pipeline |
| **Recruiters** | Extract company contacts from association directories, conference attendee lists |
| **Journalists / investigators** | Map networks of organizations, find contact points for FOIA/outreach |

---

## Quick Start

### Prerequisites
- Python 3.10+
- `playwright install chromium` (for JS rendering fallback)

### Install
```bash
git clone <this-repo>
cd crawler
pip install -r requirements.txt
playwright install chromium
```

### Configure (optional)
```bash
cp .env.example .env
# Edit .env — or use env vars at runtime
```

### Run
```bash
# Option 1: Interactive (prompts for extraction goals)
python main.py

# Option 2: Non-interactive / CI-friendly (recommended)
python main.py --extract emails,phones --custom-prompt "extract pricing tables"

# Option 3: Override config via env vars
SEED_FILE=/path/to/links.txt CONCURRENCY=8 python main.py --extract emails,phones,images
```

### CLI Reference
```bash
python main.py --help
```
```
--extract EXTRACT           Comma-separated: emails, phones, images, articles, products
--custom-prompt PROMPT      Custom LLM extraction (requires GEMINI_API_KEY)
--seed-file PATH            Override seed file path
--concurrency N             Parallel workers (default: 5)
--max-depth N               Crawl depth per website (default: 3)
--no-js-fallback            Disable Playwright fallback for SPAs/anti-bot
```

---

## Advanced Configuration Examples

### Login-Protected Sites
```python
# In config.py or .env
LOGIN_CREDENTIALS = {
    "example.com": {
        "username": "bot@example.com",
        "password": "secret123",
        "login_url": "https://example.com/login",
        "username_selector": "#email",      # optional
        "password_selector": "#password",   # optional
        "submit_selector": "button[type=submit]"  # optional
    }
}
```
On 401/403, crawler auto-navigates to `login_url`, fills form, submits, then retries the original URL.

### Custom JS Interactions (per domain)
```python
CUSTOM_INTERACTIONS = {
    "example.com": [
        {"action": "click", "selector": "#accept-cookies"},
        {"action": "scroll", "direction": "bottom"},
        {"action": "wait_for_selector", "selector": ".results-loaded"},
        {"action": "fill", "selector": "#search", "value": "query"},
        {"action": "wait_for_navigation", "timeout": 10000}
    ]
}
```
Supported actions: `click`, `fill`, `wait`, `scroll` (up/down/top/bottom), `wait_for_selector`, `wait_for_navigation`

### Session Persistence
```python
PERSIST_SESSION = True  # Default: true
```
Automatically saves/restores cookies + localStorage per domain — reuse authenticated sessions across page visits.

---

## Input Format

**Seed file** (`links.txt` or `SEED_FILE` path) — one URL per line:
```
https://www.chamberofcommerce.com/ca/los-angeles
https://www.angieslist.com/companylist/us/ca/los-angeles.htm
https://clutch.co/agencies/web-developers#listing
# Comments and blank lines ignored
```

The crawler treats each as a **listing/directory site** — it will paginate, find profile links, and follow them.

---

## Outputs (in `output/`)

| File | Description |
|------|-------------|
| `discovered_urls.csv` | All profile URLs found on listing sites + source seed |
| `websites.csv` | Canonical official websites discovered (deduped) |
| `contacts.csv` | **Master contact database** — one row per website with all extracted fields |
| `master_database.xlsx` | Excel workbook with 3 sheets: Contacts, Websites, Discovered URLs |
| `master_database.sqlite3` | Queryable SQLite DB (same data + crawl queue for resume) |
| `checkpoint.json` | Resume state (completed seeds/websites) |
| `bandit_model.json` | Learned URL-path priorities (Thompson Sampling) |

### Contact Record Schema
```csv
website, detail_page_url, source_url, name, organization, category,
address, emails, phones, social_links, images, articles, products,
custom_data, contact_page_url, crawl_status, extraction_timestamp
```
- `emails` / `phones` — comma-separated, validated
- `social_links` — JSON: `{"linkedin": "url", "twitter": "url", ...}`
- `custom_data` — JSON array from LLM prompt

---

## Configuration (all in `config.py`, override via `.env` or env vars)

| Setting | Env Var | Default | Purpose |
|---------|---------|---------|---------|
| Seed file | `SEED_FILE` | `links.txt` (OS-aware) | Input seed URLs |
| Max crawl depth | `MAX_CRAWL_DEPTH` | `3` | Internal link depth per website |
| Max pages/domain | `MAX_PAGES_PER_DOMAIN` | `40` | Hard ceiling per site |
| Max pagination | `MAX_PAGINATION_PAGES` | `50` | Per listing site |
| Concurrency | `CONCURRENCY` | `5` | Parallel workers (seeds/websites) |
| Internal concurrency | `INTERNAL_CONCURRENCY` | `3` | Threads per website |
| Smart JS fallback | `USE_SMART_JS_FALLBACK` | `true` | Playwright for SPAs/anti-bot |
| Min delay/domain | `MIN_DELAY_PER_DOMAIN` | `1.5s` | Politeness floor |
| Respect robots.txt | `RESPECT_ROBOTS_TXT` | `true` | Skip disallowed paths |
| Retry attempts | `RETRY_ATTEMPTS` | `3` | Per-request retries |
| Checkpoint interval | `CHECKPOINT_EVERY_N_ITEMS` | `10` | Save progress every N items |
| Extraction toggles | `EXTRACT_EMAILS` etc. | `true/false` | Enable/disable extractors |
| Custom prompt | `CUSTOM_PROMPT` | `""` | LLM extraction prompt |
| Gemini API key | `GEMINI_API_KEY` | `""` | Required for custom extraction |
| **Session persistence** | `PERSIST_SESSION` | `true` | Save/restore cookies+localStorage |
| **Login credentials** | `LOGIN_CREDENTIALS` | `{}` | Per-domain login config (dict) |
| **Custom interactions** | `CUSTOM_INTERACTIONS` | `{}` | Per-domain JS sequences (dict) |
| Bandit model path | `BANDIT_MODEL_FILE` | `output/bandit_model.json` | RL model storage |

---

## Architecture

```
main.py                      Orchestrates phases, manages concurrency, CLI
config.py                    All tunables — nothing site-specific

crawler/
    seed_loader.py           Phase 0: load & normalize seeds
    directory_crawler.py     Phases 1-3: listing crawl, profiles, website discovery
    website_crawler.py       Phases 4-5: site crawl, contact extraction
    bandit.py                RL bandit (Thompson Sampling) for URL prioritization

extractors/
    metadata_extractor.py    Name/org/category/address via JSON-LD + heuristics
    email_extractor.py       mailto: + regex, validated
    phone_extractor.py       tel: + regex, normalized to E.164
    social_extractor.py      Social platform links
    image_extractor.py       Image URLs
    article_extractor.py     Article text blocks
    product_extractor.py     Schema.org Product + fallback
    custom_extractor.py      Gemini LLM custom prompts

database/
    sqlite_manager.py        Schema, queue, upserts, resume support

utils/
    http_client.py           Retries, rate limiting, robots.txt, Playwright, login, sessions, custom interactions
    normalizer.py            URL/email/phone canonicalization
    validator.py             Format validation + false-positive filtering
    deduplicator.py          Thread-safe seen-sets + record-level dedup
    checkpoint.py            JSON resume tracking
    exporter.py              CSV / Excel / SQLite export
    logger.py                Shared logging
    html_parser.py           BeautifulSoup with lxml/html5lib fallback

output/                      All exports + checkpoints
logs/                        crawler.log
```

---

## Resume After Interruption

Progress is checkpointed to:
- `output/checkpoint.json` (completed seeds/websites)
- SQLite `crawl_queue` table (page-level state)

**Re-run `python main.py`** — it skips everything already finished automatically.

---

## Responsible Use

This only collects **publicly published** information (emails/phones on organizations' own contact/about pages).

- **Robots.txt respected by default** — don't disable casually
- **Rate limited** — per-domain delay floor prevents hammering small sites
- **No outreach sent** — this is a data layer; compliance (CAN-SPAM, CASL, GDPR, PECR) lives wherever you use the exported list next
- **Individual vs. organization** — rules differ; verify before emailing

---

## Extending

| Want to... | Do this |
|------------|---------|
| Add new extractor | Drop module in `extractors/`, call from `website_crawler.py` (Phase 5) or `directory_crawler.py` (Phase 2) |
| Swap fetcher for Scrapy | Replace `utils/http_client.py` — single seam |
| Tune heuristics | Edit `directory_crawler.py` — profile-link detection, pagination, website scoring are pure functions |
| Add export format | Extend `utils/exporter.py` |
| Run distributed | Replace `ThreadPoolExecutor` with Celery/Ray; SQLite → Postgres |
| Add login flow | Define in `LOGIN_CREDENTIALS` — no code changes |
| Add custom interactions | Define in `CUSTOM_INTERACTIONS` — no code changes |

---

## Requirements

```
requests>=2.31.0
beautifulsoup4>=4.12.0
lxml>=5.0.0
pandas>=2.0.0
openpyxl>=3.1.0
playwright>=1.40.0
playwright-stealth>=1.0.0
google-genai>=1.0.0
html5lib>=1.1
```

---

## License

MIT — use freely, contribute back if you improve it.

---

## Support / Contributing

- Issues: GitHub Issues
- Questions: Open a Discussion
- PRs welcome — especially new extractors, heuristic improvements, or export formats