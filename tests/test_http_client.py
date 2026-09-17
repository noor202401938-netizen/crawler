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

    @patch("utils.http_client.is_allowed_by_robots", return_value=True)
    @patch("utils.http_client.get_requests_proxies")
    @patch("utils.http_client.requests.request")
    def test_fetch_passes_proxy_kwargs(self, mock_request, mock_get_proxies, _mock_robots):
        mock_get_proxies.return_value = {
            "http": "http://proxy.test:8080",
            "https": "http://proxy.test:8080",
        }
        resp = requests.Response()
        resp.status_code = 200
        resp._content = b"ok"
        mock_request.return_value = resp

        result = fetch("https://example.com/page")
        self.assertIsNotNone(result)
        mock_request.assert_called_once()
        _, kwargs = mock_request.call_args
        self.assertEqual(
            kwargs.get("proxies"),
            {"http": "http://proxy.test:8080", "https": "http://proxy.test:8080"},
        )


class ProxyTests(unittest.TestCase):
    @patch("utils.http_client.config")
    def test_get_next_proxy_none_when_empty(self, mock_config):
        mock_config.PROXY_LIST = []
        mock_config.PROXY_URL = ""
        from utils.http_client import get_next_proxy

        self.assertIsNone(get_next_proxy())

    @patch("utils.http_client.config")
    def test_get_next_proxy_single_static(self, mock_config):
        mock_config.PROXY_LIST = ["http://proxy1:8080"]
        mock_config.PROXY_URL = "http://proxy1:8080"
        mock_config.ROTATE_PROXIES = False
        from utils.http_client import get_next_proxy

        self.assertEqual(get_next_proxy(), "http://proxy1:8080")

    @patch("utils.http_client.config")
    def test_get_next_proxy_rotation(self, mock_config):
        mock_config.PROXY_LIST = ["http://p1:8080", "http://p2:8080"]
        mock_config.ROTATE_PROXIES = True
        import utils.http_client as hc

        hc._proxy_index = 0
        p1 = hc.get_next_proxy()
        p2 = hc.get_next_proxy()
        p3 = hc.get_next_proxy()
        self.assertEqual(p1, "http://p1:8080")
        self.assertEqual(p2, "http://p2:8080")
        self.assertEqual(p3, "http://p1:8080")

    def test_get_requests_proxies(self):
        from utils.http_client import get_requests_proxies

        self.assertIsNone(get_requests_proxies(""))
        self.assertEqual(
            get_requests_proxies("http://p.com:8080"),
            {"http": "http://p.com:8080", "https": "http://p.com:8080"},
        )

    def test_get_playwright_proxy_parsing(self):
        from utils.http_client import get_playwright_proxy

        # None case
        self.assertIsNone(get_playwright_proxy(""))

        # Simple case
        pw_simple = get_playwright_proxy("http://proxy.com:8080")
        self.assertEqual(pw_simple, {"server": "http://proxy.com:8080"})

        # Authenticated proxy
        pw_auth = get_playwright_proxy("http://admin:secret123@proxy.org:3128")
        self.assertEqual(
            pw_auth,
            {"server": "http://proxy.org:3128", "username": "admin", "password": "secret123"},
        )

        # Implicit scheme
        pw_implicit = get_playwright_proxy("1.2.3.4:9090")
        self.assertEqual(pw_implicit, {"server": "http://1.2.3.4:9090"})


if __name__ == "__main__":
    unittest.main()
