"""
crawler/bandit.py
Reinforcement Learning Multi-Armed Bandit model (Thompson Sampling)
to prioritize URL queues based on dynamic extraction goals.
"""

import json
import os
import random
import threading
from urllib.parse import urlsplit

import config
from utils.logger import get_logger

logger = get_logger("bandit")


class URLBandit:
    def __init__(self, model_path: str | None = None) -> None:
        self.model_path = model_path or config.BANDIT_MODEL_FILE
        self._lock = threading.Lock()
        # memory: dict mapping keyword -> {"successes": float, "failures": float}
        # default alpha (success) = 1.0, beta (failure) = 1.0 (uniform prior)
        self.memory: dict[str, dict[str, float]] = {}
        self._dirty = False
        self._updates_since_save = 0
        self.auto_save_interval = getattr(config, "BANDIT_AUTO_SAVE_INTERVAL", 20)
        self.load()

    def load(self) -> None:
        with self._lock:
            if os.path.exists(self.model_path):
                try:
                    with open(self.model_path, encoding="utf-8") as f:
                        self.memory = json.load(f)
                except (json.JSONDecodeError, OSError) as e:
                    logger.warning(f"Failed to load bandit model from {self.model_path}: {e}")
                    self.memory = {}
            self._dirty = False
            self._updates_since_save = 0

    def _save_locked(self) -> None:
        """Internal save assuming self._lock is already acquired."""
        os.makedirs(os.path.dirname(self.model_path), exist_ok=True)
        with open(self.model_path, "w", encoding="utf-8") as f:
            json.dump(self.memory, f, indent=2)
        self._dirty = False
        self._updates_since_save = 0

    def save(self) -> None:
        with self._lock:
            self._save_locked()

    def flush(self) -> None:
        """Persist any in-memory dirty updates to disk."""
        with self._lock:
            if self._dirty:
                self._save_locked()

    def _get_keywords(self, url: str) -> list[str]:
        path = urlsplit(url).path.lower()
        parts = [p for p in path.replace("-", "/").replace("_", "/").split("/") if p and len(p) > 2]
        return parts

    def score_url(self, url: str) -> float:
        """
        Calculates the priority score for a URL using Thompson Sampling.
        Returns a sampled value from the Beta distribution of the URL's keywords.
        Higher score means higher priority.
        """
        keywords = self._get_keywords(url)
        if not keywords:
            # Baseline exploration for root/unknown paths
            return random.betavariate(1, 1)

        scores = []
        with self._lock:
            for kw in keywords:
                stats = self.memory.get(kw, {"successes": 1.0, "failures": 1.0})
                alpha = max(float(stats.get("successes", 1.0)), 0.1)
                beta = max(float(stats.get("failures", 1.0)), 0.1)
                # Thompson sampling: random sample from Beta(successes, failures)
                sampled_score = random.betavariate(alpha, beta)
                scores.append(sampled_score)

        # Max score among keywords gives a chance to highly performant keywords
        return max(scores) if scores else random.betavariate(1, 1)

    def update_reward(self, url: str, reward: float) -> None:
        """
        Updates the success/failure counts for the URL's keywords based on the reward.
        Normalized so Beta distribution variance remains healthy without exploding alpha/beta.
        Buffers writes in-memory, auto-saving periodically and flushing on demand.
        """
        keywords = self._get_keywords(url)
        if not keywords:
            return

        with self._lock:
            for kw in keywords:
                if kw not in self.memory:
                    self.memory[kw] = {"successes": 1.0, "failures": 1.0}

                if reward > 0:
                    # Bounded increment (e.g. reward 10 -> 1.0, reward 20 -> 1.5) to keep Beta variance healthy
                    inc = min(max(reward / 10.0, 0.5), 1.5)
                    self.memory[kw]["successes"] += inc
                else:
                    self.memory[kw]["failures"] += 1.0

            self._dirty = True
            self._updates_since_save += 1
            if self._updates_since_save >= self.auto_save_interval:
                self._save_locked()
