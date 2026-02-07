"""Tests for scripts/scrape_knowledge_base.py module."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import httpx

# Add scripts directory to path so we can import the module
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

from scrape_knowledge_base import (
    discover_article_urls,
    extract_title_from_markdown,
    fetch_all_articles,
    fetch_article,
    parse_sitemap,
    parse_sitemap_index,
    url_to_slug,
)

_SITEMAP_INDEX_XML = """<?xml version="1.0" encoding="UTF-8"?>
<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <sitemap>
    <loc>https://knowledge-base.rossum.ai/sitemap-0.xml</loc>
  </sitemap>
  <sitemap>
    <loc>https://knowledge-base.rossum.ai/sitemap-1.xml</loc>
  </sitemap>
</sitemapindex>"""

_SITEMAP_XML = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url>
    <loc>https://knowledge-base.rossum.ai/docs/document-splitting-extension</loc>
  </url>
  <url>
    <loc>https://knowledge-base.rossum.ai/docs/webhook-configuration</loc>
  </url>
  <url>
    <loc>https://knowledge-base.rossum.ai/</loc>
  </url>
</urlset>"""


class TestParseSitemapIndex:
    """Test parse_sitemap_index function."""

    def test_extracts_sitemap_urls(self):
        """Test that sitemap URLs are extracted."""
        urls = parse_sitemap_index(_SITEMAP_INDEX_XML)

        assert len(urls) == 2
        assert "https://knowledge-base.rossum.ai/sitemap-0.xml" in urls
        assert "https://knowledge-base.rossum.ai/sitemap-1.xml" in urls

    def test_empty_sitemap_index(self):
        """Test empty sitemap index."""
        xml = '<?xml version="1.0"?><sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"></sitemapindex>'
        urls = parse_sitemap_index(xml)

        assert urls == []


class TestParseSitemap:
    """Test parse_sitemap function."""

    def test_extracts_page_urls(self):
        """Test that page URLs are extracted."""
        urls = parse_sitemap(_SITEMAP_XML)

        assert urls == [
            "https://knowledge-base.rossum.ai/docs/document-splitting-extension",
            "https://knowledge-base.rossum.ai/docs/webhook-configuration",
            "https://knowledge-base.rossum.ai/",
        ]

    def test_empty_sitemap(self):
        """Test empty sitemap."""
        xml = '<?xml version="1.0"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"></urlset>'
        urls = parse_sitemap(xml)

        assert urls == []


class TestUrlToSlug:
    """Test url_to_slug function."""

    def test_extracts_slug_from_docs_url(self):
        """Test slug extraction from docs URL."""
        slug = url_to_slug("https://knowledge-base.rossum.ai/docs/document-splitting-extension")
        assert slug == "document-splitting-extension"

    def test_handles_trailing_slash(self):
        """Test slug extraction with trailing slash."""
        slug = url_to_slug("https://knowledge-base.rossum.ai/docs/webhook-configuration/")
        assert slug == "webhook-configuration"


class TestExtractTitleFromMarkdown:
    """Test extract_title_from_markdown function."""

    def test_extracts_h1_heading(self):
        """Test extracting H1 heading."""
        content = "# Document Splitting\n\nSome content here."
        assert extract_title_from_markdown(content) == "Document Splitting"

    def test_returns_empty_when_no_heading(self):
        """Test returns empty string when no H1 heading."""
        content = "No heading here.\n\nJust paragraphs."
        assert extract_title_from_markdown(content) == ""

    def test_uses_first_h1_only(self):
        """Test that only the first H1 is used."""
        content = "# First Heading\n\n# Second Heading\n"
        assert extract_title_from_markdown(content) == "First Heading"


class TestFetchArticle:
    """Test fetch_article function."""

    def test_successful_fetch(self):
        mock_response = MagicMock()
        mock_response.text = "# Test Article\n\nContent here."
        mock_response.raise_for_status = MagicMock()

        mock_client = MagicMock(spec=httpx.Client)
        mock_client.get.return_value = mock_response

        result = fetch_article(mock_client, "https://knowledge-base.rossum.ai/docs/test-article")

        assert result is not None
        assert result["slug"] == "test-article"
        assert result["title"] == "Test Article"
        assert "Content here" in result["content"]

    def test_failed_fetch_returns_none(self):
        mock_client = MagicMock(spec=httpx.Client)
        mock_client.get.side_effect = httpx.HTTPError("Connection failed")

        result = fetch_article(mock_client, "https://knowledge-base.rossum.ai/docs/failing")

        assert result is None

    @patch("scrape_knowledge_base.time.sleep")
    def test_retries_on_429(self, mock_sleep):
        mock_429_response = MagicMock()
        mock_429_response.status_code = 429
        error_429 = httpx.HTTPStatusError("Rate limited", request=MagicMock(), response=mock_429_response)

        mock_ok_response = MagicMock()
        mock_ok_response.text = "# Retried Article\n\nContent."
        mock_ok_response.raise_for_status = MagicMock()

        mock_client = MagicMock(spec=httpx.Client)
        mock_client.get.side_effect = [error_429, mock_ok_response]

        result = fetch_article(mock_client, "https://knowledge-base.rossum.ai/docs/retry-article")

        assert result is not None
        assert result["slug"] == "retry-article"
        assert mock_client.get.call_count == 2
        mock_sleep.assert_called_once_with(2.0)

    @patch("scrape_knowledge_base.time.sleep")
    def test_gives_up_after_max_retries(self, mock_sleep):
        mock_429_response = MagicMock()
        mock_429_response.status_code = 429
        error_429 = httpx.HTTPStatusError("Rate limited", request=MagicMock(), response=mock_429_response)

        mock_client = MagicMock(spec=httpx.Client)
        mock_client.get.side_effect = [error_429, error_429, error_429, error_429]

        result = fetch_article(mock_client, "https://knowledge-base.rossum.ai/docs/fail-article")

        assert result is None
        assert mock_client.get.call_count == 4  # 1 initial + 3 retries


class TestFetchAllArticles:
    """Test fetch_all_articles throttling."""

    @patch("scrape_knowledge_base.time.sleep")
    @patch("scrape_knowledge_base.fetch_article")
    def test_throttling_delays(self, mock_fetch, mock_sleep):
        """2s delay after each page, 5s after every 10th."""
        mock_fetch.return_value = {"slug": "x", "url": "x", "title": "x", "content": "x"}
        mock_client = MagicMock(spec=httpx.Client)
        urls = [f"https://example.com/docs/page-{i}" for i in range(12)]

        fetch_all_articles(mock_client, urls)

        delays = [call.args[0] for call in mock_sleep.call_args_list]
        # Pages 1-9: 2s each, page 10: 5s, page 11: 2s, page 12 (last): no delay
        assert delays == [2.0, 2.0, 2.0, 2.0, 2.0, 2.0, 2.0, 2.0, 2.0, 5.0, 2.0]

    @patch("scrape_knowledge_base.time.sleep")
    @patch("scrape_knowledge_base.fetch_article")
    def test_no_delay_after_last_page(self, mock_fetch, mock_sleep):
        mock_fetch.return_value = {"slug": "x", "url": "x", "title": "x", "content": "x"}
        mock_client = MagicMock(spec=httpx.Client)

        fetch_all_articles(mock_client, ["https://example.com/docs/only-one"])

        mock_sleep.assert_not_called()


class TestDiscoverArticleUrls:
    """Test discover_article_urls function."""

    def test_discovers_doc_urls_only(self):
        """Test that only /docs/ URLs are returned."""
        mock_client = MagicMock(spec=httpx.Client)

        # First call: sitemap index
        sitemap_index_response = MagicMock()
        sitemap_index_response.text = _SITEMAP_INDEX_XML

        # Second and third calls: individual sitemaps
        sitemap_response = MagicMock()
        sitemap_response.text = _SITEMAP_XML

        mock_client.get.side_effect = [sitemap_index_response, sitemap_response, sitemap_response]

        urls = discover_article_urls(mock_client)

        # Should exclude the homepage (no /docs/ in path)
        assert all("/docs/" in u for u in urls)
        assert len(urls) == 4  # 2 doc URLs per sitemap * 2 sitemaps
