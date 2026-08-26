"""
utils/validator.py
Validates emails/phones/URLs and filters out obvious false positives.
"""

import re
import socket
from functools import lru_cache

import config
from utils.logger import get_logger
from utils.normalizer import get_domain, normalize_email

logger = get_logger("validator")

_EMAIL_RE = re.compile(r"^" + config.EMAIL_REGEX + r"$")


@lru_cache(maxsize=1024)
def _has_mx_record(domain: str) -> bool:
    """Check if a domain has valid MX records. Cached to avoid repeated DNS lookups."""
    try:
        result = socket.getaddrinfo(domain, 25, socket.AF_INET, socket.SOCK_STREAM)
        return len(result) > 0
    except (socket.gaierror, socket.herror, OSError):
        return False


def is_valid_email(email: str, check_mx: bool | None = None) -> bool:
    if not email:
        return False
    email = normalize_email(email)

    if not _EMAIL_RE.match(email):
        return False

    domain = email.split("@")[-1]
    if domain in config.EMAIL_EXCLUDE_DOMAINS:
        return False

    for ext in config.EMAIL_EXCLUDE_EXTENSIONS:
        if email.endswith(ext):
            return False

    # reject emails that are clearly image/font filenames caught by a loose regex
    if re.search(r"\.(png|jpe?g|gif|svg|webp|css|js)@", email):
        return False

    # MX record validation: verify the domain can actually receive email
    if check_mx is None:
        check_mx = config.VALIDATE_EMAIL_MX
    if check_mx and not _has_mx_record(domain):
        logger.debug(f"Email rejected (no MX record): {email}")
        return False

    return True


def is_valid_phone(phone: str) -> bool:
    if not phone:
        return False
    digits = re.sub(r"\D", "", phone)
    # Most real phone numbers are 7-15 digits (E.164 max is 15)
    return 7 <= len(digits) <= 15


def is_valid_url(url: str) -> bool:
    if not url:
        return False
    return bool(get_domain(url))
