# Security Policy

## Supported Versions

| Version | Supported |
|---------|-----------|
| 0.1.x   | ✅        |
| < 0.1   | ❌        |

## Reporting a Vulnerability

**Do not open a public issue for security vulnerabilities.**

Please report security issues privately via:

- **Email**: noor.202401938@gmail.com
- - **GitHub Security Advisories**: [Private vulnerability reporting](https://github.com/your-org/universal-crawler/security/advisories/new)

### What to Include

1. Description of the vulnerability
2. Steps to reproduce (if applicable)
3. Affected versions
4. Potential impact
5. Suggested fix (if known)

## Response Timeline

| Severity | Initial Response | Fix Target |
|----------|------------------|------------|
| Critical (RCE, data exposure) | 24 hours | 72 hours |
| High (auth bypass, SSRF) | 48 hours | 1 week |
| Medium (XSS, info disclosure) | 1 week | 2 weeks |
| Low (minor issues) | 2 weeks | Next release |

## Security Best Practices for Users

- **Never commit `.env` files** — contains API keys
- **Rotate `GEMINI_API_KEY`** regularly if used
- **Run with least privilege** — dedicated user, no root
- **Monitor `crawler.log`** for unusual activity
- **Respect `robots.txt`** — enabled by default, don't disable in production
- **Rate limits** — `MIN_DELAY_PER_DOMAIN=1.5s` minimum; increase for sensitive targets

## Known Security Considerations

| Area | Risk | Mitigation |
|------|------|------------|
| Playwright JS rendering | RCE via malicious sites | Runs headless, isolated context, `ignore_https_errors` only for certs |
| Custom LLM extraction | Prompt injection | System instruction enforces JSON-only output; user prompt sanitized |
| SQLite database | Local file access | File permissions; no network exposure |
| Seed file input | Path traversal | `normalize_url` validates schemes; no local file reads |

## Disclosure Policy

- Coordinated disclosure preferred
- Credit given in release notes (unless reporter requests anonymity)
- CVE requested for significant vulnerabilities
