"""
tests/test_http_client.py
Unit tests for utils/http_client.py (mocked network calls).
"""

import unittest
from unittest.mock import MagicMock, patch

import requests

from utils.http_client import fetch, is_allowed_by_robots


class RobotsTests(unittest.TestCase):
    @patch("utils.http_client.config")
    def test_allowed_when_no_parser(self, mock_config):
        mock_config.RESPECT_ROBOTS_TXT = True
        mock_config.USER_AGENT = "test"
        with patch("utils.http_client._get_robots_parser", return_value=None):
            self.assertTrue(is_allowed_by_robots("https://example.com/page"))

    @patch("utils.http_client.config")
    def test_disallowed_by_robots(self, mock_config):
        mock_config.RESPECT_ROBOTS_TXT = True
        mock_config.USER_AGENT = "test"
        mock_rp = MagicMock()
        mock_rp.can_fetch.return_value = False
        with patch("utils.http_client._get_robots_parser", return_value=mock_rp):
            self.assertFalse(is_allowed_by_robots("https://example.com/private"))

    @patch("utils.http_client.config")
    def test_allowed_by_robots(self, mock_config):
        mock_config.RESPECT_ROBOTS_TXT = True
        mock_config.USER_AGENT = "test"
        mock_rp = MagicMock()
        mock_rp.can_fetch.return_value = True
        with patch("utils.http_client._get_robots_parser", return_value=mock_rp):
            self.assertTrue(is_allowed_by_robots("https://example.com/public"))

    @patch("utils.http_client.config")
    def test_bypass_when_disabled(self, mock_config):
        mock_config.RESPECT_ROBOTS_TXT = False
        self.assertTrue(is_allowed_by_robots("https://example.com/anything"))


class FetchTests(unittest.TestCase):
    @patch("utils.http_client.is_allowed_by_robots", return_value=False)
    def test_fetch_skips_disallowed(self, _mock_robots):
        result = fetch("https://example.com/private")
        self.assertIsNone(result)

    @patch("utils.http_client.is_allowed_by_robots", return_value=True)
    @patch("utils.http_client.requests.request")
    def test_fetch_returns_response(self, mock_request, _mock_robots):
        resp = requests.Response()
        resp.status_code = 200
        resp._content = b"<html>ok</html>"
        mock_request.return_value = resp

        result = fetch("https://example.com/page")
        self.assertIsNotNone(result)
        self.assertEqual(result.status_code, 200)

    @patch("utils.http_client.is_allowed_by_robots", return_value=True)
    @patch("utils.http_client.requests.request")
    def test_fetch_returns_403_immediately(self, mock_request, _mock_robots):
        resp = requests.Response()
        resp.status_code = 403
        resp._content = b"forbidden"
        mock_request.return_value = resp

        result = fetch("https://example.com/page")
        self.assertEqual(result.status_code, 403)
        # Should not retry on 403
        self.assertEqual(mock_request.call_count, 1)

    @patch("utils.http_client.is_allowed_by_robots", return_value=True)
    @patch("utils.http_client.requests.request")
    def test_fetch_returns_404_immediately(self, mock_request, _mock_robots):
        resp = requests.Response()
        resp.status_code = 404
        resp._content = b""
        mock_request.return_value = resp

        result = fetch("https://example.com/page")
        self.assertEqual(result.status_code, 404)
        self.assertEqual(mock_request.call_count, 1)

    @patch("utils.http_client.is_allowed_by_robots", return_value=True)
    @patch(
        "utils.http_client.requests.request",
        side_effect=requests.exceptions.ConnectionError("fail"),
    )
    def test_fetch_retries_on_connection_error(self, mock_request, _mock_robots):
        result = fetch("https://example.com/page")
        self.assertIsNone(result)
        # Should have retried
        self.assertGreater(mock_request.call_count, 1)

    @patch("utils.http_client.is_allowed_by_robots", return_value=True)
    @patch(
        "utils.http_client.requests.request", side_effect=requests.exceptions.InvalidURL("bad url")
    )
    def test_fetch_no_retry_on_invalid_url(self, mock_request, _mock_robots):
        result = fetch("https:///")
        self.assertIsNone(result)
        self.assertEqual(mock_request.call_count, 1)

    @patch("utils.http_client.is_allowed_by_robots", return_value=True)
    @patch("utils.http_client.requests.request")
    def test_fetch_handles_429_with_backoff(self, mock_request, _mock_robots):
        rate_limited = requests.Response()
        rate_limited.status_code = 429
        rate_limited._content = b""

        ok = requests.Response()
        ok.status_code = 200
        ok._content = b"<html>ok</html>"

        mock_request.side_effect = [rate_limited, ok]

        result = fetch("https://example.com/page")
        self.assertIsNotNone(result)
        self.assertEqual(result.status_code, 200)


if __name__ == "__main__":
    unittest.main()
