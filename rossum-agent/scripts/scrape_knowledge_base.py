#!/usr/bin/env python3
"""Scrape Rossum Knowledge Base articles and produce a JSON file for local search.

Usage:
    # Write to local file
    python scripts/scrape_knowledge_base.py --output kb_articles.json

    # Upload directly to S3
    python scripts/scrape_knowledge_base.py --output s3://bucket/path/kb_articles.json

The script:
1. Fetches the sitemap index from knowledge-base.rossum.ai
2. Parses all article URLs from the sitemaps
3. Fetches each article via Jina Reader (renders JavaScript SPAs)
4. Builds a JSON file with all articles
5. Optionally uploads to S3
"""

from __future__ import annotations

import argparse
import json
import logging
import subprocess
import sys
import tempfile
import time
from datetime import UTC, datetime
from pathlib import Path

import httpx
from defusedxml import ElementTree  # ty: ignore[unresolved-import]
from tqdm import tqdm  # ty: ignore[unresolved-import] - runtime dependency

logger = logging.getLogger(__name__)

SITEMAP_INDEX_URL = "https://knowledge-base.rossum.ai/sitemap_index.xml"
JINA_READER_PREFIX = "https://r.jina.ai/"
FETCH_TIMEOUT = 30
MAX_RETRIES = 3
RETRY_BASE_DELAY = 2.0
DELAY_BETWEEN_PAGES = 2.0
DELAY_EVERY_NTH_PAGE = 5.0
NTH_PAGE = 10

# Sitemap XML namespace
_SITEMAP_NS = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}


def _parse_sitemap_locs(xml_text: str) -> list[str]:
    """Parse sitemap XML and return all <loc> URLs."""
    root = ElementTree.fromstring(xml_text)
    return [loc.text for loc in root.findall(".//sm:loc", _SITEMAP_NS) if loc.text]


# Both sitemap index and sitemap share the same <loc> structure
parse_sitemap_index = _parse_sitemap_locs
parse_sitemap = _parse_sitemap_locs


def url_to_slug(url: str) -> str:
    """Extract article slug from URL."""
    return url.rstrip("/").split("/")[-1]


def extract_title_from_markdown(content: str) -> str:
    """Extract the first H1 heading from markdown content as the title."""
    for line in content.split("\n"):
        stripped = line.strip()
        if stripped.startswith("# "):
            return stripped[2:].strip()
    return ""


def fetch_article(client: httpx.Client, url: str) -> dict[str, str] | None:
    """Fetch a single article via Jina Reader with retry on 429."""
    jina_url = f"{JINA_READER_PREFIX}{url}"
    for attempt in range(MAX_RETRIES + 1):
        try:
            response = client.get(jina_url, timeout=FETCH_TIMEOUT)
            response.raise_for_status()
            content = response.text
            slug = url_to_slug(url)
            title = extract_title_from_markdown(content)
            logger.info(f"Fetched: {slug} ({len(content)} chars)")
            return {"slug": slug, "url": url, "title": title, "content": content}
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429 and attempt < MAX_RETRIES:
                delay = RETRY_BASE_DELAY * (2**attempt)
                logger.info(f"Rate limited on {url}, retrying in {delay}s (attempt {attempt + 1}/{MAX_RETRIES})")
                time.sleep(delay)
                continue
            logger.warning(f"Failed to fetch {url}: {e}")
            return None
        except httpx.HTTPError as e:
            logger.warning(f"Failed to fetch {url}: {e}")
            return None
    return None


def fetch_all_articles(client: httpx.Client, urls: list[str]) -> list[dict[str, str]]:
    """Fetch all articles sequentially with throttling to avoid rate limits."""
    articles: list[dict[str, str]] = []
    for i, url in enumerate(tqdm(urls, desc="Fetching articles"), 1):
        result = fetch_article(client, url)
        if result is not None:
            articles.append(result)
        if i < len(urls):
            delay = DELAY_EVERY_NTH_PAGE if i % NTH_PAGE == 0 else DELAY_BETWEEN_PAGES
            time.sleep(delay)
    return articles


def discover_article_urls(client: httpx.Client) -> list[str]:
    """Discover all article URLs from the sitemap."""
    logger.info(f"Fetching sitemap index: {SITEMAP_INDEX_URL}")
    resp = client.get(SITEMAP_INDEX_URL, timeout=30)
    resp.raise_for_status()

    sitemap_urls = parse_sitemap_index(resp.text)
    logger.info(f"Found {len(sitemap_urls)} sitemaps")

    all_urls: list[str] = []
    for sitemap_url in tqdm(sitemap_urls, desc="Fetching sitemaps"):
        logger.info(f"Fetching sitemap: {sitemap_url}")
        resp = client.get(sitemap_url, timeout=30)
        resp.raise_for_status()
        urls = parse_sitemap(resp.text)
        all_urls.extend(urls)

    # Filter to docs pages only (exclude homepage, category pages, etc.)
    doc_urls = [u for u in all_urls if "/docs/" in u]
    logger.info(f"Found {len(doc_urls)} article URLs (from {len(all_urls)} total)")
    return doc_urls


def upload_to_s3(local_path: str, s3_path: str) -> None:
    """Upload a file to S3 using AWS CLI."""
    cmd = ["aws", "s3", "cp", local_path, s3_path, "--content-type", "application/json"]
    logger.info(f"Uploading to {s3_path}")
    subprocess.run(cmd, check=True)
    logger.info(f"Uploaded successfully to {s3_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Scrape Rossum Knowledge Base articles")
    parser.add_argument("--output", required=True, help="Output path (local file or s3://bucket/key)")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose logging")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    with httpx.Client() as client:
        doc_urls = discover_article_urls(client)

        if not doc_urls:
            logger.error("No article URLs found")
            sys.exit(1)

        logger.info(f"Fetching {len(doc_urls)} articles via Jina Reader")
        articles = fetch_all_articles(client, doc_urls)
    logger.info(f"Successfully fetched {len(articles)} articles")

    data = {
        "scraped_at": datetime.now(UTC).isoformat(),
        "articles": sorted(articles, key=lambda a: a["slug"]),
    }

    output_json = json.dumps(data, indent=2, ensure_ascii=False)

    if args.output.startswith("s3://"):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write(output_json)
            tmp_path = f.name
        try:
            upload_to_s3(tmp_path, args.output)
        finally:
            Path(tmp_path).unlink()
    else:
        with open(args.output, "w") as f:
            f.write(output_json)
        logger.info(f"Written to {args.output} ({len(output_json)} bytes, {len(articles)} articles)")


if __name__ == "__main__":
    main()
