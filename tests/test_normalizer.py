"""
tests/test_normalizer.py
Unit tests for URL, email, and phone normalization.
"""

import unittest

from utils.normalizer import get_domain, normalize_email, normalize_phone, normalize_url


class NormalizeUrlTests(unittest.TestCase):
    def test_strips_www(self):
        self.assertEqual(normalize_url("https://www.example.com/"), "https://example.com/")

    def test_lowercases_host(self):
        self.assertEqual(normalize_url("https://EXAMPLE.COM/"), "https://example.com/")

    def test_strips_trailing_slash(self):
        self.assertEqual(normalize_url("https://example.com/page/"), "https://example.com/page")

    def test_strips_default_port_80(self):
        self.assertEqual(normalize_url("https://example.com:80/path"), "https://example.com/path")

    def test_strips_default_port_443(self):
        self.assertEqual(normalize_url("https://example.com:443/path"), "https://example.com/path")

    def test_keeps_non_default_port(self):
        self.assertEqual(
            normalize_url("https://example.com:8080/path"), "https://example.com:8080/path"
        )

    def test_strips_fragment(self):
        result = normalize_url("https://example.com/page#section")
        self.assertNotIn("#", result)

    def test_resolves_relative_url(self):
        result = normalize_url("/about", base="https://example.com/page/1")
        self.assertEqual(result, "https://example.com/about")

    def test_resolves_relative_url_with_parent(self):
        result = normalize_url("../contact", base="https://example.com/a/b/page")
        self.assertEqual(result, "https://example.com/a/contact")

    def test_empty_string_returns_empty(self):
        self.assertEqual(normalize_url(""), "")

    def test_normalizes_scheme_to_https(self):
        self.assertTrue(normalize_url("http://example.com").startswith("https://"))

    def test_preserves_query_string(self):
        result = normalize_url("https://example.com/search?q=test")
        self.assertIn("q=test", result)

    def test_normalizes_full_url(self):
        result = normalize_url("http://WWW.Example.COM:80/path/to/page/")
        self.assertEqual(result, "https://example.com/path/to/page")


class GetDomainTests(unittest.TestCase):
    def test_extracts_domain(self):
        self.assertEqual(get_domain("https://example.com/page"), "example.com")

    def test_strips_www(self):
        self.assertEqual(get_domain("https://www.example.com"), "example.com")

    def test_empty_url_returns_empty(self):
        self.assertEqual(get_domain(""), "")

    def test_with_port(self):
        self.assertEqual(get_domain("https://example.com:8080/path"), "example.com:8080")


class NormalizeEmailTests(unittest.TestCase):
    def test_lowercases(self):
        self.assertEqual(normalize_email("User@Example.COM"), "user@example.com")

    def test_strips_mailto_prefix(self):
        self.assertEqual(normalize_email("mailto:user@example.com"), "user@example.com")

    def test_strips_surrounding_punctuation(self):
        self.assertEqual(normalize_email("<user@example.com>"), "user@example.com")
        self.assertEqual(normalize_email('"user@example.com"'), "user@example.com")
        self.assertEqual(normalize_email("user@example.com."), "user@example.com")

    def test_strips_whitespace(self):
        self.assertEqual(normalize_email("  user@example.com  "), "user@example.com")

    def test_empty_returns_empty(self):
        self.assertEqual(normalize_email(""), "")


class NormalizePhoneTests(unittest.TestCase):
    def test_keeps_plus_prefix(self):
        self.assertEqual(normalize_phone("+1 555 123 4567"), "+15551234567")

    def test_strips_dashes_and_parens(self):
        self.assertEqual(normalize_phone("(555) 123-4567"), "5551234567")

    def test_empty_returns_empty(self):
        self.assertEqual(normalize_phone(""), "")

    def test_no_digits_returns_empty(self):
        self.assertEqual(normalize_phone("abc"), "")

    def test_international_format(self):
        self.assertEqual(normalize_phone("+44 20 7946 0958"), "+442079460958")


if __name__ == "__main__":
    unittest.main()
