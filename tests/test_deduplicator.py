"""
tests/test_deduplicator.py
Unit tests for SeenSet and record deduplication.
"""

import threading
import unittest

from utils.deduplicator import SeenSet, dedup_records


class SeenSetTests(unittest.TestCase):
    def test_add_if_new_returns_true_first_time(self):
        s = SeenSet()
        self.assertTrue(s.add_if_new("a"))

    def test_add_if_new_returns_false_second_time(self):
        s = SeenSet()
        s.add_if_new("a")
        self.assertFalse(s.add_if_new("a"))

    def test_empty_key_returns_false(self):
        s = SeenSet()
        self.assertFalse(s.add_if_new(""))
        self.assertFalse(s.add_if_new(None))

    def test_contains(self):
        s = SeenSet()
        s.add_if_new("x")
        self.assertIn("x", s)
        self.assertNotIn("y", s)

    def test_len(self):
        s = SeenSet()
        self.assertEqual(len(s), 0)
        s.add_if_new("a")
        s.add_if_new("b")
        self.assertEqual(len(s), 2)

    def test_thread_safety(self):
        s = SeenSet()
        results = []

        def worker(key):
            results.append(s.add_if_new(key))

        threads = [threading.Thread(target=worker, args=(f"item-{i}",)) for i in range(50)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # All 50 unique keys should be added exactly once
        self.assertEqual(sum(results), 50)
        self.assertEqual(len(s), 50)

    def test_concurrent_same_key(self):
        s = SeenSet()
        results = []

        def worker():
            results.append(s.add_if_new("shared"))

        threads = [threading.Thread(target=worker) for _ in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Only one thread should get True
        self.assertEqual(sum(results), 1)
        self.assertEqual(len(s), 1)


class DedupRecordsTests(unittest.TestCase):
    def test_dedup_by_single_key(self):
        records = [
            {"id": "1", "name": "Alice"},
            {"id": "2", "name": "Bob"},
            {"id": "1", "name": "Alice Updated"},
        ]
        result = dedup_records(records, "id")
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["name"], "Alice")
        self.assertEqual(result[1]["name"], "Bob")

    def test_dedup_by_composite_key(self):
        records = [
            {"domain": "a.com", "url": "/p1", "data": "first"},
            {"domain": "a.com", "url": "/p1", "data": "second"},
            {"domain": "a.com", "url": "/p2", "data": "third"},
        ]
        result = dedup_records(records, ["domain", "url"])
        self.assertEqual(len(result), 2)

    def test_merges_empty_fields(self):
        records = [
            {"id": "1", "name": "Alice", "email": ""},
            {"id": "1", "name": "", "email": "alice@test.com"},
        ]
        result = dedup_records(records, "id")
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["name"], "Alice")
        self.assertEqual(result[0]["email"], "alice@test.com")

    def test_empty_list(self):
        self.assertEqual(dedup_records([], "id"), [])

    def test_no_duplicates(self):
        records = [{"id": "1"}, {"id": "2"}]
        result = dedup_records(records, "id")
        self.assertEqual(len(result), 2)


if __name__ == "__main__":
    unittest.main()
