"""
tests/test_logger.py
Unit tests for structured JSON logging and CrawlMetrics.
"""

import json
import logging
import unittest

from utils.logger import CrawlMetrics, JSONFormatter


class JSONFormatterTests(unittest.TestCase):
    def setUp(self):
        self.formatter = JSONFormatter(datefmt="%Y-%m-%dT%H:%M:%S")

    def test_basic_log_entry(self):
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="hello world",
            args=(),
            exc_info=None,
        )
        output = self.formatter.format(record)
        data = json.loads(output)
        self.assertEqual(data["level"], "INFO")
        self.assertEqual(data["logger"], "test")
        self.assertEqual(data["msg"], "hello world")
        self.assertIn("ts", data)

    def test_error_level(self):
        record = logging.LogRecord(
            name="test",
            level=logging.ERROR,
            pathname="",
            lineno=0,
            msg="something broke",
            args=(),
            exc_info=None,
        )
        output = self.formatter.format(record)
        data = json.loads(output)
        self.assertEqual(data["level"], "ERROR")

    def test_exception_included(self):
        try:
            raise ValueError("oops")
        except ValueError:
            import sys

            exc_info = sys.exc_info()

        record = logging.LogRecord(
            name="test",
            level=logging.ERROR,
            pathname="",
            lineno=0,
            msg="error occurred",
            args=(),
            exc_info=exc_info,
        )
        output = self.formatter.format(record)
        data = json.loads(output)
        self.assertIn("exception", data)
        self.assertIn("ValueError", data["exception"])


class CrawlMetricsTests(unittest.TestCase):
    def setUp(self):
        self.metrics = CrawlMetrics()
        self.metrics.reset()

    def test_initial_state(self):
        summary = self.metrics.get_summary()
        self.assertEqual(summary["requests_made"], 0)
        self.assertEqual(summary["requests_succeeded"], 0)
        self.assertEqual(summary["requests_failed"], 0)
        self.assertEqual(summary["pages_crawled"], 0)
        self.assertEqual(summary["emails_found"], 0)
        self.assertEqual(summary["phones_found"], 0)

    def test_record_request_success(self):
        self.metrics.record_request(success=True)
        self.metrics.record_request(success=True)
        summary = self.metrics.get_summary()
        self.assertEqual(summary["requests_made"], 2)
        self.assertEqual(summary["requests_succeeded"], 2)
        self.assertEqual(summary["requests_failed"], 0)

    def test_record_request_failure(self):
        self.metrics.record_request(success=False)
        summary = self.metrics.get_summary()
        self.assertEqual(summary["requests_made"], 1)
        self.assertEqual(summary["requests_failed"], 1)

    def test_record_page(self):
        self.metrics.record_page(emails=3, phones=1, bytes_down=5000)
        summary = self.metrics.get_summary()
        self.assertEqual(summary["pages_crawled"], 1)
        self.assertEqual(summary["emails_found"], 3)
        self.assertEqual(summary["phones_found"], 1)
        self.assertEqual(summary["bytes_downloaded"], 5000)

    def test_record_page_accumulates(self):
        self.metrics.record_page(emails=2, phones=1)
        self.metrics.record_page(emails=3, phones=2)
        summary = self.metrics.get_summary()
        self.assertEqual(summary["emails_found"], 5)
        self.assertEqual(summary["phones_found"], 3)
        self.assertEqual(summary["pages_crawled"], 2)

    def test_record_skipped(self):
        self.metrics.record_skipped("robots")
        self.metrics.record_skipped("robots")
        self.metrics.record_skipped("circuit")
        summary = self.metrics.get_summary()
        self.assertEqual(summary["requests_skipped_robots"], 2)
        self.assertEqual(summary["requests_skipped_circuit"], 1)

    def test_record_rate_limited(self):
        self.metrics.record_rate_limited()
        self.metrics.record_rate_limited()
        summary = self.metrics.get_summary()
        self.assertEqual(summary["rate_limited_429"], 2)

    def test_record_website_discovered(self):
        self.metrics.record_website_discovered()
        self.metrics.record_website_discovered()
        summary = self.metrics.get_summary()
        self.assertEqual(summary["websites_discovered"], 2)

    def test_requests_per_second(self):
        summary = self.metrics.get_summary()
        self.assertIn("requests_per_second", summary)
        self.assertIsInstance(summary["requests_per_second"], float)

    def test_reset(self):
        self.metrics.record_page(emails=5)
        self.metrics.reset()
        summary = self.metrics.get_summary()
        self.assertEqual(summary["emails_found"], 0)

    def test_log_summary_returns_dict(self):
        self.metrics.record_page(emails=2)
        result = self.metrics.log_summary()
        self.assertIsInstance(result, dict)
        self.assertEqual(result["emails_found"], 2)

    def test_singleton_behavior(self):
        m1 = CrawlMetrics()
        m2 = CrawlMetrics()
        self.assertIs(m1, m2)


if __name__ == "__main__":
    unittest.main()
