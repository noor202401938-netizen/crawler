"""
extractors/image_extractor.py
Extracts image URLs from raw HTML.
"""

from urllib.parse import urljoin

from bs4 import BeautifulSoup

from utils.html_parser import make_soup


def extract_images(html: str, soup: BeautifulSoup | None = None, base_url: str = "") -> list:
    """Returns a list of absolute image URLs found in the page."""
    found = set()

    if soup is None:
        soup = make_soup(html)

    for img in soup.find_all("img", src=True):
        src = str(img["src"])
        if src.startswith("data:image"):
            continue

        if base_url:
            src = urljoin(base_url, src)

        found.add(src)

    return sorted(found)
