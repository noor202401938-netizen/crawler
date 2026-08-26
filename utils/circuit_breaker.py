"""
utils/circuit_breaker.py
Circuit breaker for per-domain failure tracking and a dead letter queue
for URLs that have permanently failed.

The circuit breaker prevents wasting time on domains that are consistently
down or blocking. After N consecutive failures, the circuit opens and all
requests to that domain are skipped for a cooldown period.

The dead letter queue tracks URLs that have been abandoned so they can be
retried later or reported to the user.
"""

import json
import os
import threading
import time
from collections import defaultdict
from enum import Enum

import config
from utils.logger import get_logger

logger = get_logger("circuit_breaker")


class CircuitState(Enum):
    CLOSED = "closed"  # Normal operation — requests allowed
    OPEN = "open"  # Too many failures — skip requests
    HALF_OPEN = "half_open"  # Cooldown expired — allow one probe request


class CircuitBreaker:
    """
    Per-domain circuit breaker using consecutive failure counting.

    States:
      CLOSED  -> normal, requests pass through
      OPEN    -> after failure_threshold consecutive failures, block all requests
      HALF_OPEN -> after cooldown_seconds, allow one probe; success -> CLOSED, failure -> OPEN
    """

    def __init__(
        self,
        failure_threshold: int | None = None,
        cooldown_seconds: float | None = None,
    ):
        self._lock = threading.Lock()
        self._failure_threshold = failure_threshold or config.CIRCUIT_BREAKER_FAILURE_THRESHOLD
        self._cooldown_seconds = cooldown_seconds or config.CIRCUIT_BREAKER_COOLDOWN_SECONDS

        # Per-domain state
        self._consecutive_failures: dict[str, int] = defaultdict(int)
        self._state: dict[str, CircuitState] = defaultdict(lambda: CircuitState.CLOSED)
        self._opened_at: dict[str, float] = {}

    def allow_request(self, domain: str) -> bool:
        """Return True if requests to this domain should proceed."""
        with self._lock:
            state = self._state[domain]

            if state == CircuitState.CLOSED:
                return True

            if state == CircuitState.OPEN:
                # Check if cooldown has elapsed
                elapsed = time.time() - self._opened_at.get(domain, 0)
                if elapsed >= self._cooldown_seconds:
                    self._state[domain] = CircuitState.HALF_OPEN
                    logger.info(
                        f"Circuit breaker HALF_OPEN for {domain} after {elapsed:.0f}s cooldown"
                    )
                    return True  # Allow one probe request
                return False

            if state == CircuitState.HALF_OPEN:
                return True  # Already in probe mode

        return True

    def record_success(self, domain: str):
        """Record a successful request — resets the failure counter."""
        with self._lock:
            self._consecutive_failures[domain] = 0
            if self._state[domain] != CircuitState.CLOSED:
                logger.info(f"Circuit breaker CLOSED for {domain} (success)")
                self._state[domain] = CircuitState.CLOSED

    def record_failure(self, domain: str):
        """Record a failed request — may trip the circuit open."""
        with self._lock:
            self._consecutive_failures[domain] += 1
            count = self._consecutive_failures[domain]

            if count >= self._failure_threshold:
                if self._state[domain] != CircuitState.OPEN:
                    logger.warning(
                        f"Circuit breaker OPEN for {domain} "
                        f"({count} consecutive failures, threshold={self._failure_threshold})"
                    )
                self._state[domain] = CircuitState.OPEN
                self._opened_at[domain] = time.time()

    def get_state(self, domain: str) -> CircuitState:
        with self._lock:
            return self._state[domain]

    def get_failure_count(self, domain: str) -> int:
        with self._lock:
            return self._consecutive_failures[domain]

    def reset(self, domain: str | None = None):
        """Reset circuit breaker state. If domain is None, reset all."""
        with self._lock:
            if domain:
                self._consecutive_failures[domain] = 0
                self._state[domain] = CircuitState.CLOSED
                self._opened_at.pop(domain, None)
            else:
                self._consecutive_failures.clear()
                self._state.clear()
                self._opened_at.clear()

    def get_stats(self) -> dict:
        """Return a summary of all domain states."""
        with self._lock:
            return {
                domain: {
                    "state": state.value,
                    "failures": self._consecutive_failures[domain],
                }
                for domain, state in self._state.items()
            }


# ---------------------------------------------------------------------------
# Dead Letter Queue — tracks permanently abandoned URLs
# ---------------------------------------------------------------------------


class DeadLetterQueue:
    """
    In-memory + file-backed queue for URLs that failed all retries.

    Persists to output/dead_letters.json so they survive restarts and can be
    retried or inspected later.
    """

    def __init__(self, path: str | None = None):
        self._lock = threading.Lock()
        self._path = path or os.path.join(config.OUTPUT_DIR, "dead_letters.json")
        self._entries: list[dict] = []
        self._load()

    def _load(self):
        if os.path.exists(self._path):
            try:
                with open(self._path, encoding="utf-8") as f:
                    self._entries = json.load(f)
            except (json.JSONDecodeError, OSError):
                self._entries = []

    def _save(self):
        os.makedirs(os.path.dirname(self._path) or ".", exist_ok=True)
        with open(self._path, "w", encoding="utf-8") as f:
            json.dump(self._entries, f, indent=2)

    def add(self, url: str, reason: str, url_type: str = "unknown"):
        """Add a URL to the dead letter queue."""
        with self._lock:
            # Deduplicate by URL
            if any(e["url"] == url for e in self._entries):
                return
            entry = {
                "url": url,
                "reason": reason,
                "url_type": url_type,
                "timestamp": time.time(),
            }
            self._entries.append(entry)
            self._save()
            logger.info(f"Dead letter: {url} ({reason})")

    def get_all(self) -> list[dict]:
        with self._lock:
            return list(self._entries)

    def get_pending(self, url_type: str | None = None) -> list[dict]:
        """Get URLs not yet retried (no 'retried' field or retried=False)."""
        with self._lock:
            entries = self._entries
            if url_type:
                entries = [e for e in entries if e.get("url_type") == url_type]
            return [e for e in entries if not e.get("retried", False)]

    def mark_retried(self, url: str):
        with self._lock:
            for e in self._entries:
                if e["url"] == url:
                    e["retried"] = True
                    break
            self._save()

    def clear(self):
        with self._lock:
            self._entries.clear()
            self._save()

    def __len__(self):
        with self._lock:
            return len(self._entries)


# Module-level singletons
_circuit_breaker: CircuitBreaker | None = None
_dead_letter_queue: DeadLetterQueue | None = None
_singleton_lock = threading.Lock()


def get_circuit_breaker() -> CircuitBreaker:
    global _circuit_breaker
    with _singleton_lock:
        if _circuit_breaker is None:
            _circuit_breaker = CircuitBreaker()
        return _circuit_breaker


def get_dead_letter_queue() -> DeadLetterQueue:
    global _dead_letter_queue
    with _singleton_lock:
        if _dead_letter_queue is None:
            _dead_letter_queue = DeadLetterQueue()
        return _dead_letter_queue
