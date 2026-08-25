"""
tests/test_extractors.py
Unit tests for the pure-function content extractors. Each extractor takes
HTML (and optionally a base_url) and returns structured data -- easy to test
against small fixture pages, no network needed.
"""

import unittest

from extractors.article_extractor import extract_articles
from extractors.email_extractor import extract_emails
from extractors.image_extractor import extract_images
from extractors.phone_extractor import extract_phones
from extractors.product_extractor import extract_products
from extractors.social_extractor import extract_social_links


class EmailExtractorTests(unittest.TestCase):
    def test_finds_mailto_and_plaintext_and_dedupes(self):
        html = """
        <html><body>
          <a href="mailto:hello@example.org?subject=hi">Email us</a>
          <p>Contact hello@example.org or sales@example.org today.</p>
        </body></html>
        """
        self.assertEqual(extract_emails(html), ["hello@example.org", "sales@example.org"])

    def test_strips_mailto_query_string(self):
        html = '<a href="mailto:a@b.com?subject=x&cc=y">x</a>'
        self.assertEqual(extract_emails(html), ["a@b.com"])

    def test_empty_page_returns_empty_list(self):
        self.assertEqual(extract_emails("<html><body>no mail</body></html>"), [])


class PhoneExtractorTests(unittest.TestCase):
    def test_finds_tel_link(self):
        html = '<a href="tel:+15551234567">call</a>'
        result = extract_phones(html)
        self.assertEqual(len(result), 1)
        # normalizer keeps the digits; just assert the core number survived
        self.assertIn("5551234567", result[0].replace(" ", "").replace("-", ""))

    def test_no_phone_returns_empty(self):
        self.assertEqual(extract_phones("<p>nothing here</p>"), [])


class SocialExtractorTests(unittest.TestCase):
    def test_maps_platform_to_first_url(self):
        html = """
        <a href="https://facebook.com/acme">fb</a>
        <a href="https://facebook.com/acme2">fb2</a>
        <a href="https://www.instagram.com/acme">ig</a>
        """
        result = extract_social_links(html)
        self.assertEqual(result["facebook"], "https://facebook.com/acme")  # first wins
        self.assertEqual(result["instagram"], "https://www.instagram.com/acme")

    def test_ignores_non_social_links(self):
        html = '<a href="https://example.org">home</a>'
        self.assertEqual(extract_social_links(html), {})


class ImageExtractorTests(unittest.TestCase):
    def test_resolves_relative_against_base_url(self):
        html = '<img src="/img/logo.png"><img src="https://cdn.example.org/a.jpg">'
        result = extract_images(html, base_url="https://example.org/page")
        self.assertIn("https://example.org/img/logo.png", result)
        self.assertIn("https://cdn.example.org/a.jpg", result)

    def test_skips_data_uri_images(self):
        html = '<img src="data:image/png;base64,AAAA"><img src="/real.png">'
        result = extract_images(html, base_url="https://example.org")
        self.assertEqual(result, ["https://example.org/real.png"])


class ArticleExtractorTests(unittest.TestCase):
    def test_extracts_long_article_tag(self):
        body = "word " * 60  # > 200 chars
        html = f"<article>{body}</article>"
        result = extract_articles(html)
        self.assertEqual(len(result), 1)
        self.assertIn("word", result[0])

    def test_ignores_short_article(self):
        self.assertEqual(extract_articles("<article>too short</article>"), [])

    def test_falls_back_to_long_paragraphs(self):
        body = "sentence " * 40  # > 200 chars
        html = f"<div><p>{body}</p></div>"
        result = extract_articles(html)
        self.assertEqual(len(result), 1)


class ProductExtractorTests(unittest.TestCase):
    def test_parses_json_ld_product(self):
        html = """
        <script type="application/ld+json">
        {"@type": "Product", "name": "Widget",
         "offers": {"price": "9.99"}, "url": "https://shop.example.org/widget"}
        </script>
        """
        result = extract_products(html)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["name"], "Widget")
        self.assertEqual(result[0]["price"], "9.99")

    def test_html_fallback_when_no_json_ld(self):
        html = """
        <div class="product-card">
          <h2>Gadget</h2>
          <span class="price">$19.99</span>
          <a href="/p/gadget">buy</a>
        </div>
        """
        result = extract_products(html, base_url="https://shop.example.org")
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["name"], "Gadget")
        self.assertEqual(result[0]["price"], "$19.99")
        self.assertEqual(result[0]["url"], "https://shop.example.org/p/gadget")

    def test_no_product_returns_empty(self):
        self.assertEqual(extract_products("<p>just text</p>"), [])


if __name__ == "__main__":
    unittest.main()
