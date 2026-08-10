# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Initial open source release preparation
- MIT License, Contributing guide, Security policy, Code of Conduct
- GitHub Actions CI workflow
- pyproject.toml for modern packaging
- Pre-commit configuration
- Issue and PR templates

### Changed
- Replaced deprecated `google.generativeai` with `google.genai`
- Made `SEED_FILE` default cross-platform
- Replaced blocking `input()` with argparse CLI
- Lowered `INTERNAL_CONCURRENCY` default from 20 to 3
- Made bandit model path configurable
- Fixed Playwright resource leak with atexit cleanup
- Replaced bare `except Exception:` with specific exceptions

### Fixed
- Various bare exception handlers
- Resource cleanup for Playwright instances

## [0.1.0] - 2024-01-XX

### Added
- Universal Website Discovery & Contact Extraction Engine
- 7-phase pipeline: seed loading → listing crawl → profile extraction → website discovery → site crawl → contact extraction → export
- Heuristic-based profile link detection (no site-specific selectors)
- JSON-LD / schema.org metadata extraction with fallback heuristics
- Email extraction (mailto: + regex) with validation
- Phone extraction (tel: + regex) with E.164 normalization
- Social media link extraction (8 platforms)
- Image, article, product extraction
- Custom LLM extraction via Google Gemini
- Smart JS fallback (Playwright) for SPAs and anti-bot pages
- Per-domain rate limiting & robots.txt compliance
- Resumable crawls via SQLite queue + JSON checkpoints
- Thompson Sampling bandit for URL prioritization
- Export to CSV, Excel (.xlsx), SQLite
- Thread-safe deduplication
- Comprehensive logging
- Cross-platform support (Windows, macOS, Linux)

### Security
- Robots.txt respect enabled by default
- Per-domain minimum delay (1.5s) enforced
- Retry logic with exponential backoff
- Terminal exception detection (no retry on invalid URLs, SSL errors, etc.)

---

## Release Template

### [X.Y.Z] - YYYY-MM-DD

#### Added
- New features

#### Changed
- Changes in existing functionality

#### Deprecated
- Soon-to-be removed features

#### Removed
- Removed features

#### Fixed
- Bug fixes

#### Security
- Vulnerability fixes