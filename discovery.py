
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse, urlunparse

from dotenv import load_dotenv
from firecrawl import Firecrawl

load_dotenv()

MAX_WEBSITES = 10
MAX_PAGES_PER_WEBSITE = 4

OUTPUT_DIR = Path("data/raw")
OUTPUT_FILE = OUTPUT_DIR / "scraped_websites.json"

SEARCH_QUERY = (
    "India corporate gifting companies "
    "promotional merchandise customized bags bulk orders"
)

# Pages likely to contain useful business and buying-intent information.
RELEVANT_KEYWORDS = [
    "contact",
    "about",
    "corporate-gift",
    "corporate-gifting",
    "promotional",
    "bulk",
    "custom",
    "bag",
    "product",
    "service",
    "employee",
    "welcome-kit",
    "business",
]

BLOCKED_DOMAINS = (
    "linkedin.com",
    "facebook.com",
    "instagram.com",
    "youtube.com",
    "wikipedia.org",
)

IGNORED_EXTENSIONS = (
    ".jpg", ".jpeg", ".png", ".gif", ".svg",
    ".pdf", ".zip", ".mp4", ".webp",
)


def get_value(obj, key, default=None):
    """Read a field from a dictionary or SDK response object."""
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def get_domain(url):
    """Return a normalized hostname."""
    return urlparse(url).netloc.lower().removeprefix("www.")


def normalize_url(url):
    """Remove fragments and query parameters for deduplication."""
    try:
        parsed = urlparse(url.strip())

        if parsed.scheme not in ("http", "https") or not parsed.netloc:
            return None

        return urlunparse((
            parsed.scheme.lower(),
            parsed.netloc.lower(),
            parsed.path.rstrip("/") or "/",
            "",
            "",
            "",
        ))
    except (ValueError, AttributeError):
        return None


def is_allowed_url(url, expected_domain):
    """Accept only relevant URLs from the target website."""
    normalized = normalize_url(url)

    if not normalized:
        return False

    parsed = urlparse(normalized)
    domain = get_domain(normalized)

    if domain != expected_domain:
        return False

    if any(
        domain == blocked or domain.endswith("." + blocked)
        for blocked in BLOCKED_DOMAINS
    ):
        return False

    if parsed.path.lower().endswith(IGNORED_EXTENSIONS):
        return False

    return True


def relevance_score(url):
    """Rank likely useful pages ahead of unrelated pages."""
    path = urlparse(url).path.lower()
    score = 0

    for keyword in RELEVANT_KEYWORDS:
        if keyword in path:
            score += 2

    if path in ("", "/"):
        score += 1

    return score


def extract_links(map_result):
    """Handle common Firecrawl SDK map response formats."""
    links = get_value(map_result, "links", []) or []
    urls = []

    for item in links:
        if isinstance(item, str):
            urls.append(item)
        else:
            url = get_value(item, "url")
            if url:
                urls.append(url)

    return urls


def discover_pages(app, candidate):
    """Find a small set of useful pages within one website."""
    original_url = normalize_url(candidate["url"])
    domain = candidate["domain"]

    if not original_url:
        return []

    candidates = {original_url}

    # Map discovers URLs; it does not replace scraping the page content.
    try:
        root_url = f"https://{domain}/"

        print("  Discovering internal page links...")

        map_result = app.map(
            root_url,
            limit=100,
        )

        for url in extract_links(map_result):
            normalized = normalize_url(url)

            if normalized and is_allowed_url(normalized, domain):
                candidates.add(normalized)

    except Exception as exc:
        print(f"  Link discovery unavailable: {str(exc)[:200]}")
        print("  Continuing with the original search-result URL.")

    # Always prioritize the original URL, then the most relevant pages.
    remaining = sorted(
        candidates - {original_url},
        key=lambda url: (-relevance_score(url), len(url), url),
    )

    selected_urls = [original_url]
    selected_urls.extend(remaining[:MAX_PAGES_PER_WEBSITE - 1])

    return selected_urls


def discover_and_scrape():
    api_key = os.getenv("FIRECRAWL_API_KEY")

    if not api_key:
        raise ValueError("FIRECRAWL_API_KEY is missing from .env")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    app = Firecrawl(api_key=api_key)

    print("Searching for relevant business websites...")

    search_results = app.search(SEARCH_QUERY, limit=10)
    web_results = get_value(search_results, "web", []) or []

    selected = []
    seen_domains = set()

    for result in web_results:
        url = get_value(result, "url")
        title = get_value(result, "title", "") or ""

        if not url:
            continue

        domain = get_domain(url)

        if not domain or domain in seen_domains:
            continue

        if any(
            domain == blocked or domain.endswith("." + blocked)
            for blocked in BLOCKED_DOMAINS
        ):
            continue

        seen_domains.add(domain)

        selected.append({
            "domain": domain,
            "url": url,
            "title": title,
            "description": get_value(result, "description", "") or "",
        })

        if len(selected) >= MAX_WEBSITES:
            break

    print(f"Unique candidate websites selected: {len(selected)}")

    records = []

    for site_index, candidate in enumerate(selected, start=1):
        print(
            f"\n[{site_index}/{len(selected)}] "
            f"Processing {candidate['domain']}..."
        )

        page_urls = discover_pages(app, candidate)
        print(f"  Pages selected for scraping: {len(page_urls)}")

        for page_index, page_url in enumerate(page_urls, start=1):
            print(
                f"  [{page_index}/{len(page_urls)}] "
                f"Scraping {page_url}"
            )

            record = {
                **candidate,
                "page_url": page_url,
                "page_title": "",
                "source_url": page_url,
                "markdown": "",
                "status": "pending",
                "error": None,
                "collected_at": datetime.now(timezone.utc).isoformat(),
            }

            try:
                page = app.scrape(
                    page_url,
                    formats=["markdown"],
                )

                markdown = get_value(page, "markdown", "") or ""
                metadata = get_value(page, "metadata", {}) or {}

                record["markdown"] = markdown
                record["page_title"] = (
                    get_value(metadata, "title", "")
                    or candidate["title"]
                )
                record["source_url"] = (
                    get_value(metadata, "source_url", "")
                    or get_value(metadata, "sourceURL", "")
                    or page_url
                )
                record["status"] = (
                    "success" if markdown.strip() else "empty_content"
                )

            except Exception as exc:
                record["status"] = "failed"
                record["error"] = str(exc)[:500]
                print(f"    Failed: {record['error']}")

            records.append(record)

    with OUTPUT_FILE.open("w", encoding="utf-8") as file:
        json.dump(records, file, ensure_ascii=False, indent=2)

    successful = sum(r["status"] == "success" for r in records)

    print("\nDiscovery and scraping complete.")
    print(f"Websites selected: {len(selected)}")
    print(f"Total pages attempted: {len(records)}")
    print(f"Pages with content: {successful}")
    print(f"Pages failed or empty: {len(records) - successful}")
    print(f"Saved results to: {OUTPUT_FILE}")


if __name__ == "__main__":
    discover_and_scrape()
