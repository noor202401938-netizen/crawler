# Contributing to Universal Crawler

Thank you for your interest in contributing! This document outlines the process and guidelines for contributing to this project.

## Code of Conduct

By participating, you agree to abide by our [Code of Conduct](CODE_OF_CONDUCT.md). Please read it before contributing.

## How to Contribute

### Reporting Bugs
1. Check [existing issues](https://github.com/your-org/universal-crawler/issues) first
2. Open a new issue using the **Bug Report** template
3. Include: OS, Python version, steps to reproduce, expected vs actual behavior, logs

### Suggesting Features
1. Open an issue using the **Feature Request** template
2. Describe the use case and proposed solution
3. We'll discuss feasibility and scope before implementation

### Pull Requests
1. Fork the repository
2. Create a feature branch: `git checkout -b feat/your-feature-name`
3. Make your changes
4. Run tests and linting: `make check` (or `ruff check . && black --check . && mypy . && pytest`)
5. Commit with conventional commits: `feat: add new extractor for JSON-LD events`
6. Push and open a PR against `main`

## Development Setup

```bash
# Clone your fork
git clone https://github.com/your-username/universal-crawler.git
cd universal-crawler

# Install dependencies
pip install -e ".[dev]"

# Install Playwright browsers
playwright install chromium

# Install pre-commit hooks
pre-commit install

# Run tests
pytest tests/ -v
```

## Code Standards

| Tool | Config | Purpose |
|------|--------|---------|
| **ruff** | `pyproject.toml` | Fast linting, import sorting |
| **black** | `pyproject.toml` | Code formatting (100 char line length) |
| **mypy** | `pyproject.toml` | Static type checking (strict mode) |
| **bandit** | - | Security linting |
| **pytest** | `tests/` | Unit & regression tests |

All checks must pass before merge.

## Commit Message Format

Use [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>[optional scope]: <description>

[optional body]

[optional footer(s)]
```

Types: `feat`, `fix`, `docs`, `style`, `refactor`, `perf`, `test`, `chore`, `build`, `ci`

Examples:
```
feat(extractors): add support for Schema.org Event extraction
fix(http_client): handle 429 retry-after header correctly
docs: update CLI reference in README
chore(deps): update playwright to 1.42
```

## Developer Certificate of Origin (DCO)

By contributing, you certify that:

> (a) The contribution was created in whole or in part by me and I have the right to submit it under the open source license indicated in the file; or
>
> (b) The contribution is based upon previous work that, to the best of my knowledge, is covered under an appropriate open source license and I have the right under that license to submit that work with modifications, whether created in whole or in part by me, under the same open source license (unless I am permitted to submit under a different license), as indicated in the file; or
>
> (c) The contribution was provided directly to me by some other person who certified (a), (b) or (c) and I have not modified it.
>
> (d) I understand and agree that this project and the contribution are public and that a record of the contribution (including all personal information I submit with it, including my sign-off) is maintained indefinitely and may be redistributed consistent with this project or the open source license(s) involved.

**Sign off your commits:** `git commit -s`

## Adding New Extractors

1. Create `extractors/your_extractor.py` with `extract_your_data(html, soup, ...)`
2. Follow existing patterns: return `list` of validated items
3. Add to `crawler/website_crawler.py` (Phase 5) or `crawler/directory_crawler.py` (Phase 2)
4. Add config toggle in `config.py` if needed
5. Add tests in `tests/test_extractors.py`
6. Update README extraction capabilities table

## Testing Guidelines

- Unit tests for pure functions (heuristics, normalizers, validators)
- Mock HTTP responses — no network calls in tests
- Test edge cases: empty HTML, malformed JSON-LD, missing elements
- Regression tests for known issues

## Release Process

Maintainers only:
1. Update `CHANGELOG.md`
2. Bump version in `pyproject.toml`
3. Tag: `git tag v0.x.y`
4. GitHub Actions builds & publishes to PyPI
5. Create GitHub Release with changelog

## Questions?

Open a [Discussion](https://github.com/your-org/universal-crawler/discussions) or ask in the PR.