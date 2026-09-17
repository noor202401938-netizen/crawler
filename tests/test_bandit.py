"""
tests/test_bandit.py
Unit tests for URLBandit (Thompson Sampling Multi-Armed Bandit),
verifying URL keyword scoring, reward normalization, and buffered disk persistence.
"""

import json
import os
import tempfile
import unittest

from crawler.bandit import URLBandit


class TestURLBandit(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.mkdtemp()
        self.model_path = os.path.join(self.temp_dir, "test_bandit_model.json")
        self.bandit = URLBandit(model_path=self.model_path)
        # Set auto-save interval to 5 for predictable test assertions
        self.bandit.auto_save_interval = 5

    def tearDown(self) -> None:
        if os.path.exists(self.model_path):
            try:
                os.remove(self.model_path)
            except PermissionError:
                pass
        if os.path.exists(self.temp_dir):
            try:
                os.rmdir(self.temp_dir)
            except OSError:
                pass

    def test_keywords_extraction(self) -> None:
        kw = self.bandit._get_keywords("https://example.com/about-us/team_members")
        self.assertIn("about", kw)
        self.assertIn("team", kw)
        self.assertIn("members", kw)

    def test_score_url_returns_valid_probability(self) -> None:
        score = self.bandit.score_url("https://example.com/contact")
        self.assertGreaterEqual(score, 0.0)
        self.assertLessEqual(score, 1.0)

    def test_reward_normalization_bounds_increments(self) -> None:
        """Massive reward like +20 should be bounded so alpha does not explode."""
        url = "https://example.com/products/view"
        self.bandit.update_reward(url, 20.0)
        self.assertIn("products", self.bandit.memory)
        stats = self.bandit.memory["products"]
        # Success should start at 1.0 and increase by at most 1.5
        self.assertLessEqual(stats["successes"], 2.5)
        self.assertGreaterEqual(stats["successes"], 2.0)

    def test_buffered_persistence_and_flush(self) -> None:
        """Updates should be buffered and only written to disk upon flush or reaching interval."""
        # 1. First 4 updates (under interval of 5)
        for i in range(4):
            self.bandit.update_reward(f"https://example.com/path{i}", 1.0)

        # File should NOT exist yet on disk
        self.assertFalse(os.path.exists(self.model_path))

        # 2. Explicit flush() should write to disk
        self.bandit.flush()
        self.assertTrue(os.path.exists(self.model_path))

        with open(self.model_path, encoding="utf-8") as f:
            data = json.load(f)
        self.assertIn("path0", data)

        # 3. 5th update reaches interval (5 updates since last save)
        for i in range(5):
            self.bandit.update_reward(f"https://example.com/batch{i}", 1.0)

        # File exists and contains batch data
        with open(self.model_path, encoding="utf-8") as f:
            data2 = json.load(f)
        self.assertIn("batch4", data2)
