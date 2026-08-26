"""
tests/test_circuit_breaker.py
Unit tests for circuit breaker pattern and dead letter queue.
"""

import os
import tempfile
import time
import unittest

from utils.circuit_breaker import CircuitBreaker, CircuitState, DeadLetterQueue


class CircuitBreakerTests(unittest.TestCase):
    def setUp(self):
        self.cb = CircuitBreaker(failure_threshold=3, cooldown_seconds=0.1)

    def test_allows_requests_when_closed(self):
        self.assertTrue(self.cb.allow_request("example.com"))
        self.assertEqual(self.cb.get_state("example.com"), CircuitState.CLOSED)

    def test_opens_after_threshold_failures(self):
        for _ in range(3):
            self.cb.record_failure("example.com")
        self.assertEqual(self.cb.get_state("example.com"), CircuitState.OPEN)
        self.assertFalse(self.cb.allow_request("example.com"))

    def test_half_open_after_cooldown(self):
        for _ in range(3):
            self.cb.record_failure("example.com")
        self.assertFalse(self.cb.allow_request("example.com"))

        time.sleep(0.15)  # Wait for cooldown

        self.assertTrue(self.cb.allow_request("example.com"))
        self.assertEqual(self.cb.get_state("example.com"), CircuitState.HALF_OPEN)

    def test_success_resets_to_closed(self):
        for _ in range(3):
            self.cb.record_failure("example.com")
        self.assertEqual(self.cb.get_state("example.com"), CircuitState.OPEN)

        time.sleep(0.15)
        self.cb.allow_request("example.com")  # Moves to HALF_OPEN
        self.cb.record_success("example.com")

        self.assertEqual(self.cb.get_state("example.com"), CircuitState.CLOSED)
        self.assertEqual(self.cb.get_failure_count("example.com"), 0)

    def test_failure_in_half_open_reopens(self):
        for _ in range(3):
            self.cb.record_failure("example.com")
        time.sleep(0.15)
        self.cb.allow_request("example.com")  # HALF_OPEN
        self.cb.record_failure("example.com")  # Fail during probe

        self.assertEqual(self.cb.get_state("example.com"), CircuitState.OPEN)

    def test_independent_domains(self):
        for _ in range(3):
            self.cb.record_failure("bad.com")
        self.assertFalse(self.cb.allow_request("bad.com"))
        self.assertTrue(self.cb.allow_request("good.com"))

    def test_reset_single_domain(self):
        for _ in range(3):
            self.cb.record_failure("example.com")
        self.cb.reset("example.com")
        self.assertEqual(self.cb.get_state("example.com"), CircuitState.CLOSED)
        self.assertEqual(self.cb.get_failure_count("example.com"), 0)

    def test_reset_all(self):
        self.cb.record_failure("a.com")
        self.cb.record_failure("b.com")
        self.cb.reset()
        self.assertEqual(self.cb.get_stats(), {})

    def test_get_stats(self):
        # Trip a.com circuit open so it appears in state
        for _ in range(3):
            self.cb.record_failure("a.com")
        self.cb.record_success("b.com")
        stats = self.cb.get_stats()
        self.assertIn("a.com", stats)
        self.assertIn("b.com", stats)
        self.assertEqual(stats["a.com"]["failures"], 3)
        self.assertEqual(stats["a.com"]["state"], "open")

    def test_failure_count_tracking(self):
        self.cb.record_failure("a.com")
        self.cb.record_failure("a.com")
        self.assertEqual(self.cb.get_failure_count("a.com"), 2)
        self.cb.record_success("a.com")
        self.assertEqual(self.cb.get_failure_count("a.com"), 0)


class DeadLetterQueueTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.dlq_path = os.path.join(self.tmpdir, "dlq.json")
        self.dlq = DeadLetterQueue(path=self.dlq_path)

    def tearDown(self):
        if os.path.exists(self.dlq_path):
            os.remove(self.dlq_path)
        os.rmdir(self.tmpdir)

    def test_add_entry(self):
        self.dlq.add("https://dead.com", reason="all fetches failed", url_type="website")
        entries = self.dlq.get_all()
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["url"], "https://dead.com")
        self.assertEqual(entries[0]["reason"], "all fetches failed")

    def test_deduplicates_by_url(self):
        self.dlq.add("https://dead.com", reason="first")
        self.dlq.add("https://dead.com", reason="second")
        self.assertEqual(len(self.dlq.get_all()), 1)

    def test_persists_to_disk(self):
        self.dlq.add("https://dead.com", reason="fail")
        dlq2 = DeadLetterQueue(path=self.dlq_path)
        self.assertEqual(len(dlq2.get_all()), 1)

    def test_mark_retried(self):
        self.dlq.add("https://dead.com", reason="fail")
        self.dlq.mark_retried("https://dead.com")
        pending = self.dlq.get_pending()
        self.assertEqual(len(pending), 0)

    def test_get_pending_excludes_retried(self):
        self.dlq.add("https://a.com", reason="fail")
        self.dlq.add("https://b.com", reason="fail")
        self.dlq.mark_retried("https://a.com")
        pending = self.dlq.get_pending()
        self.assertEqual(len(pending), 1)
        self.assertEqual(pending[0]["url"], "https://b.com")

    def test_clear(self):
        self.dlq.add("https://a.com", reason="fail")
        self.dlq.add("https://b.com", reason="fail")
        self.dlq.clear()
        self.assertEqual(len(self.dlq), 0)

    def test_len(self):
        self.assertEqual(len(self.dlq), 0)
        self.dlq.add("https://a.com", reason="fail")
        self.assertEqual(len(self.dlq), 1)

    def test_corrupt_file_starts_fresh(self):
        with open(self.dlq_path, "w") as f:
            f.write("not json")
        dlq = DeadLetterQueue(path=self.dlq_path)
        self.assertEqual(len(dlq), 0)

    def test_filtered_by_type(self):
        self.dlq.add("https://a.com", reason="fail", url_type="website")
        self.dlq.add("https://b.com", reason="fail", url_type="seed")
        pending = self.dlq.get_pending(url_type="website")
        self.assertEqual(len(pending), 1)


if __name__ == "__main__":
    unittest.main()
