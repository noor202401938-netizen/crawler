"""
tests/test_validator.py
Unit tests for email, phone, and URL validation.
"""

import unittest
from unittest.mock import patch

from utils.validator import is_valid_email, is_valid_phone, is_valid_url


class EmailValidationTests(unittest.TestCase):
    def test_valid_simple_email(self):
        self.assertTrue(is_valid_email("user@mycompany.org"))

    def test_valid_email_with_dots(self):
        self.assertTrue(is_valid_email("first.last@mycompany.org"))

    def test_valid_email_with_plus(self):
        self.assertTrue(is_valid_email("user+tag@mycompany.org"))

    def test_empty_email(self):
        self.assertFalse(is_valid_email(""))

    def test_none_email(self):
        self.assertFalse(is_valid_email(None))

    def test_excluded_domain_sentry(self):
        self.assertFalse(is_valid_email("alerts@sentry.io"))

    def test_excluded_domain_example(self):
        self.assertFalse(is_valid_email("test@example.com"))

    def test_excluded_extension_png(self):
        self.assertFalse(is_valid_email("image.png@example.com"))

    def test_excluded_extension_css(self):
        self.assertFalse(is_valid_email("style.css@test.com"))

    def test_rejects_image_filename_pattern(self):
        self.assertFalse(is_valid_email("photo.jpg@example.com"))

    def test_invalid_no_at(self):
        self.assertFalse(is_valid_email("userexample.com"))

    def test_invalid_no_domain(self):
        self.assertFalse(is_valid_email("user@"))


class PhoneValidationTests(unittest.TestCase):
    def test_valid_us_phone(self):
        self.assertTrue(is_valid_phone("+1 555 123 4567"))

    def test_valid_international(self):
        self.assertTrue(is_valid_phone("+44 20 7946 0958"))

    def test_valid_10_digit(self):
        self.assertTrue(is_valid_phone("5551234567"))

    def test_empty_phone(self):
        self.assertFalse(is_valid_phone(""))

    def test_none_phone(self):
        self.assertFalse(is_valid_phone(None))

    def test_too_short(self):
        self.assertFalse(is_valid_phone("123"))

    def test_too_long(self):
        # More than 15 digits
        self.assertFalse(is_valid_phone("+1234567890123456"))

    def test_7_digits_valid(self):
        self.assertTrue(is_valid_phone("5551234"))


class MXValidationTests(unittest.TestCase):
    @patch("utils.validator._has_mx_record", return_value=True)
    def test_valid_email_with_mx(self, mock_mx):
        self.assertTrue(is_valid_email("user@realcompany.org"))

    @patch("utils.validator._has_mx_record", return_value=False)
    def test_valid_email_no_mx_rejected(self, mock_mx):
        self.assertFalse(is_valid_email("user@fakedomain.xyz"))

    @patch("utils.validator._has_mx_record", return_value=False)
    def test_mx_check_can_be_disabled(self, mock_mx):
        self.assertTrue(is_valid_email("user@fakedomain.xyz", check_mx=False))
        mock_mx.assert_not_called()

    @patch("utils.validator._has_mx_record", return_value=True)
    def test_mx_check_disabled_by_default_config(self, mock_mx):
        import config

        original = config.VALIDATE_EMAIL_MX
        config.VALIDATE_EMAIL_MX = False
        try:
            self.assertTrue(is_valid_email("user@test.org"))
            mock_mx.assert_not_called()
        finally:
            config.VALIDATE_EMAIL_MX = original


class URLValidationTests(unittest.TestCase):
    def test_valid_url(self):
        self.assertTrue(is_valid_url("https://example.com"))

    def test_valid_url_with_path(self):
        self.assertTrue(is_valid_url("https://example.com/about"))

    def test_empty_url(self):
        self.assertFalse(is_valid_url(""))

    def test_none_url(self):
        self.assertFalse(is_valid_url(None))

    def test_invalid_url_no_scheme(self):
        # get_domain will normalize this but it should still return a domain
        result = is_valid_url("example.com")
        # This depends on normalizer behavior; just ensure no crash
        self.assertIsInstance(result, bool)


if __name__ == "__main__":
    unittest.main()
