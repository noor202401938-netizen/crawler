"""
utils/logger.py
Centralized logger setup used across every module.

Supports two formats:
  - Human-readable (default): for terminal/file output
  - Structured JSON: when LOG_FORMAT=json, for machine consumption
"""

import json
import logging
import os
import sys
import time
from threading import Lock

import config

# ---------------------------------------------------------------------------
# Structured JSON formatter
# ---------------------------------------------------------------------------


class JSONFormatter(logging.Formatter):
    """Emit each log line as a single JSON object."""

    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "ts": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        if record.exc_info and record.exc_info[0] is not None:
            log_entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_entry, default=str)


# ---------------------------------------------------------------------------
# Logger factory
# ---------------------------------------------------------------------------


def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    if logger.handlers:
        # Already configured (avoid duplicate handlers on repeated calls)
        return logger

    logger.setLevel(getattr(logging, config.LOG_LEVEL.upper(), logging.INFO))

    os.makedirs(config.LOG_DIR, exist_ok=True)

    fmt = getattr(config, "LOG_FORMAT", "text").lower()

    if fmt == "json":
        formatter = JSONFormatter(datefmt="%Y-%m-%dT%H:%M:%S")
    else:
        formatter = logging.Formatter(
            "%(asctime)s | %(levelname)-8s | %(name)-25s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

    file_handler = logging.FileHandler(config.LOG_FILE, encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    return logger


# ---------------------------------------------------------------------------
# Crawl metrics — lightweight in-memory counters, exported at the end
# ---------------------------------------------------------------------------


class CrawlMetrics:
    """
    Track request-level and phase-level metrics during a crawl run.

    Thread-safe. Call ``get_summary()`` at the end of a run for a
    machine-readable dict, or ``log_summary()`` to emit it via the logger.
    """

    _instance = None
    _lock = Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self._lock2 = Lock()
        self.reset()

    def reset(self):
        with self._lock2:
            self._start_time = time.time()
            self._requests_made = 0
            self._requests_succeeded = 0
            self._requests_failed = 0
            self._requests_skipped_robots = 0
            self._requests_skipped_circuit = 0
            self._rate_limited_429 = 0
            self._pages_crawled = 0
            self._emails_found = 0
            self._phones_found = 0
            self._websites_discovered = 0
            self._domains_circuit_opened = set()
            self._bytes_downloaded = 0

    # -- mutators --

    def record_request(self, success: bool = True):
        with self._lock2:
            self._requests_made += 1
            if success:
                self._requests_succeeded += 1
            else:
                self._requests_failed += 1

    def record_skipped(self, reason: str):
        with self._lock2:
            if reason == "robots":
                self._requests_skipped_robots += 1
            elif reason == "circuit":
                self._requests_skipped_circuit += 1

    def record_rate_limited(self):
        with self._lock2:
            self._rate_limited_429 += 1

    def record_page(self, emails: int = 0, phones: int = 0, bytes_down: int = 0):
        with self._lock2:
            self._pages_crawled += 1
            self._emails_found += emails
            self._phones_found += phones
            self._bytes_downloaded += bytes_down

    def record_website_discovered(self):
        with self._lock2:
            self._websites_discovered += 1

    def record_circuit_open(self, domain: str):
        with self._lock2:
            self._domains_circuit_opened.add(domain)

    # -- accessors --

    def get_summary(self) -> dict:
        with self._lock2:
            elapsed = time.time() - self._start_time
            return {
                "elapsed_seconds": round(elapsed, 2),
                "requests_made": self._requests_made,
                "requests_succeeded": self._requests_succeeded,
                "requests_failed": self._requests_failed,
                "requests_skipped_robots": self._requests_skipped_robots,
                "requests_skipped_circuit": self._requests_skipped_circuit,
                "rate_limited_429": self._rate_limited_429,
                "pages_crawled": self._pages_crawled,
                "emails_found": self._emails_found,
                "phones_found": self._phones_found,
                "websites_discovered": self._websites_discovered,
                "domains_circuit_opened": len(self._domains_circuit_opened),
                "bytes_downloaded": self._bytes_downloaded,
                "requests_per_second": round(self._requests_made / max(elapsed, 0.1), 2),
            }

    def log_summary(self, logger_name: str = "metrics"):
        summary = self.get_summary()
        log = get_logger(logger_name)
        log.info("=== Crawl Metrics ===")
        for k, v in summary.items():
            log.info(f"  {k}: {v}")
        return summary
