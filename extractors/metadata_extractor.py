"""
extractors/metadata_extractor.py
Generic, layout-agnostic extraction of name/organization/address/category
from a "detail" page. Uses heuristics (headings, schema.org microdata /
JSON-LD, common class names) rather than any site-specific selector.
"""

import json
import re

from bs4 import BeautifulSoup


def _from_json_ld(soup: BeautifulSoup) -> dict:
    """Look for schema.org JSON-LD blocks (Organization, LocalBusiness, Person, etc.)"""
    data = {}
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            payload = json.loads(script.string or "{}")
        except (ValueError, TypeError):
            continue

        candidates = payload if isinstance(payload, list) else [payload]
        for item in candidates:
            if not isinstance(item, dict):
                continue
            item_type = str(item.get("@type", "")).lower()
            if item_type in ("organization", "localbusiness", "person", "church"):
                data.setdefault("name", item.get("name"))
                address = item.get("address")
                if isinstance(address, dict):
                    parts = [
                        address.get("streetAddress"),
                        address.get("addressLocality"),
                        address.get("addressRegion"),
                        address.get("postalCode"),
                        address.get("addressCountry"),
                    ]
                    data.setdefault("address", ", ".join(p for p in parts if p))
                elif isinstance(address, str):
                    data.setdefault("address", address)
                data.setdefault("phone", item.get("telephone"))
                data.setdefault("website", item.get("url"))
    return {k: v for k, v in data.items() if v}


def _guess_name(soup: BeautifulSoup) -> str:
    for tag in ("h1", "h2"):
        el = soup.find(tag)
        if el and el.get_text(strip=True):
            return el.get_text(strip=True)
    if soup.title and soup.title.get_text(strip=True):
        return soup.title.get_text(strip=True)
    return ""


def _guess_address(soup: BeautifulSoup) -> str:
    # common patterns: <address> tag, or elements with class containing "address"
    addr_tag = soup.find("address")
    if addr_tag and addr_tag.get_text(strip=True):
        return addr_tag.get_text(" ", strip=True)

    candidate = soup.find(class_=re.compile(r"address", re.I))
    if candidate and candidate.get_text(strip=True):
        return candidate.get_text(" ", strip=True)

    return ""


def _guess_category(soup: BeautifulSoup) -> str:
    candidate = soup.find(class_=re.compile(r"categor(y|ies)|denomination|type", re.I))
    if candidate and candidate.get_text(strip=True):
        return candidate.get_text(" ", strip=True)
    return ""


def extract_metadata(html: str, soup: BeautifulSoup = None) -> dict:
    if soup is None:
        soup = BeautifulSoup(html, "lxml")

    result = {
        "name": "",
        "organization": "",
        "category": "",
        "address": "",
        "website": "",
    }

    result.update(_from_json_ld(soup))

    if not result.get("name"):
        result["name"] = _guess_name(soup)
    if not result.get("address"):
        result["address"] = _guess_address(soup)
    if not result.get("category"):
        result["category"] = _guess_category(soup)

    # find first external link that looks like "the official website"
    if not result.get("website"):
        for a in soup.find_all("a", href=True):
            text = a.get_text(strip=True).lower()
            if "website" in text or "official site" in text or "visit site" in text:
                result["website"] = a["href"]
                break

    return {k: v for k, v in result.items() if v}
