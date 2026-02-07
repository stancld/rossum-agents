"""Tests for rossum_agent.tools.knowledge_base_search module."""

from __future__ import annotations

import json
import os
import re
import time
from unittest.mock import patch

import httpx
import pytest

_DUMMY_REQUEST = httpx.Request("GET", "https://example.com")
_DUMMY_KB_URL = "https://example.com/kb.json"

from rossum_agent.tools.knowledge_base_search import (
    _ARTICLE_OUTPUT_LIMIT,
    _CACHE_TTL_SECONDS,
    _GREP_MATCH_LIMIT,
    KBCache,
    _make_snippet,
    kb_get_article,
    kb_grep,
    refresh_knowledge_base,
)


@pytest.fixture(autouse=True)
def _set_kb_url_env(monkeypatch):
    monkeypatch.setenv("ROSSUM_KB_DATA_URL", _DUMMY_KB_URL)


_SAMPLE_DATA = {
    "scraped_at": "2026-02-07T12:00:00Z",
    "articles": [
        {
            "slug": "document-splitting-extension",
            "url": "https://knowledge-base.rossum.ai/docs/document-splitting-extension",
            "title": "Document Splitting Extension",
            "content": "# Document Splitting Extension\n\nSplit documents into multiple pages based on rules.",
        },
        {
            "slug": "webhook-configuration",
            "url": "https://knowledge-base.rossum.ai/docs/webhook-configuration",
            "title": "Webhook Configuration",
            "content": "# Webhook Configuration\n\nConfigure webhooks for real-time event processing.",
        },
        {
            "slug": "email-import",
            "url": "https://knowledge-base.rossum.ai/docs/email-import",
            "title": "Email Import",
            "content": "# Email Import\n\nImport documents via email with attachment processing.",
        },
    ],
}


@pytest.fixture
def sample_data():
    return _SAMPLE_DATA


@pytest.fixture
def cache_path(tmp_path):
    return tmp_path / "test_kb.json"


@pytest.fixture
def populated_cache(cache_path, sample_data):
    """Create a KBCache with pre-populated data."""
    cache_path.write_text(json.dumps(sample_data))
    return KBCache(cache_path=cache_path)


class TestKBCache:
    """Test KBCache class."""

    def test_download_on_first_load(self, cache_path, sample_data):
        """Test that data is downloaded when no cache exists."""
        cache = KBCache(cache_path=cache_path)

        with patch("rossum_agent.tools.knowledge_base_search.httpx.get") as mock_get:
            mock_response = httpx.Response(200, text=json.dumps(sample_data), request=_DUMMY_REQUEST)
            mock_get.return_value = mock_response

            data = cache.load()

            mock_get.assert_called_once()
            assert data["articles"] == sample_data["articles"]
            assert cache_path.exists()

    def test_disk_cache_used_when_fresh(self, populated_cache, cache_path, sample_data):
        """Test that fresh disk cache is used without downloading."""
        with patch("rossum_agent.tools.knowledge_base_search.httpx.get") as mock_get:
            data = populated_cache.load()

            mock_get.assert_not_called()
            assert data["articles"] == sample_data["articles"]

    def test_memory_cache_used_on_second_load(self, populated_cache):
        """Test that in-memory cache is used on subsequent loads."""
        data1 = populated_cache.load()
        data2 = populated_cache.load()

        assert data1 is data2

    def test_memory_cache_invalidated_on_mtime_change(self, populated_cache, cache_path, sample_data):
        """Test that memory cache is refreshed when file mtime changes."""
        data1 = populated_cache.load()

        # Modify the file and explicitly bump mtime (1-second resolution on some systems)
        modified_data = {**sample_data, "scraped_at": "2026-02-08T00:00:00Z"}
        cache_path.write_text(json.dumps(modified_data))
        future_mtime = time.time() + 10
        os.utime(cache_path, (future_mtime, future_mtime))

        data2 = populated_cache.load()

        assert data1 is not data2
        assert data2["scraped_at"] == "2026-02-08T00:00:00Z"

    def test_stale_cache_triggers_redownload(self, cache_path, sample_data):
        """Test that expired cache triggers re-download."""
        cache_path.write_text(json.dumps(sample_data))
        # Make file look old
        old_mtime = time.time() - _CACHE_TTL_SECONDS - 100
        os.utime(cache_path, (old_mtime, old_mtime))

        cache = KBCache(cache_path=cache_path)

        updated_data = {**sample_data, "scraped_at": "2026-02-08T00:00:00Z"}
        with patch("rossum_agent.tools.knowledge_base_search.httpx.get") as mock_get:
            mock_response = httpx.Response(200, text=json.dumps(updated_data), request=_DUMMY_REQUEST)
            mock_get.return_value = mock_response

            data = cache.load()

            mock_get.assert_called_once()
            assert data["scraped_at"] == "2026-02-08T00:00:00Z"

    def test_invalidate_clears_memory_and_disk(self, populated_cache, cache_path):
        """Test that invalidate clears both caches."""
        populated_cache.load()
        populated_cache.invalidate()

        assert not cache_path.exists()
        assert populated_cache._data is None
        assert populated_cache._mtime == 0

    def test_atomic_write_on_download(self, cache_path, sample_data):
        """Test that download uses atomic write."""
        cache = KBCache(cache_path=cache_path)

        with patch("rossum_agent.tools.knowledge_base_search.httpx.get") as mock_get:
            mock_response = httpx.Response(200, text=json.dumps(sample_data), request=_DUMMY_REQUEST)
            mock_get.return_value = mock_response

            cache.load()

            # Verify file exists and is valid JSON
            assert cache_path.exists()
            loaded = json.loads(cache_path.read_text())
            assert loaded["articles"] == sample_data["articles"]

    def test_corrupt_cache_triggers_redownload(self, cache_path, sample_data):
        """Test that corrupt cache file triggers re-download."""
        cache_path.write_text("not valid json{{{")

        cache = KBCache(cache_path=cache_path)

        with patch("rossum_agent.tools.knowledge_base_search.httpx.get") as mock_get:
            mock_response = httpx.Response(200, text=json.dumps(sample_data), request=_DUMMY_REQUEST)
            mock_get.return_value = mock_response

            data = cache.load()

            mock_get.assert_called_once()
            assert data["articles"] == sample_data["articles"]

    def test_corrupt_local_path_not_deleted(self, tmp_path, sample_data, monkeypatch):
        """Test that corrupt local file (via env var) is not deleted during reload."""
        local_file = tmp_path / "local_kb.json"
        local_file.write_text("not valid json{{{")
        monkeypatch.setenv("ROSSUM_KB_DATA_PATH", str(local_file))

        cache = KBCache(cache_path=tmp_path / "cache_kb.json")

        with pytest.raises(json.JSONDecodeError):
            cache.load()

        # The local file must NOT have been deleted
        assert local_file.exists()

    def test_corrupt_cache_redownload_updates_mtime(self, cache_path, sample_data):
        """Test that re-download after corrupt cache correctly updates mtime."""
        cache_path.write_text("not valid json{{{")
        cache = KBCache(cache_path=cache_path)

        with patch("rossum_agent.tools.knowledge_base_search.httpx.get") as mock_get:
            mock_response = httpx.Response(200, text=json.dumps(sample_data), request=_DUMMY_REQUEST)
            mock_get.return_value = mock_response

            data1 = cache.load()
            # Second load should use memory cache (mtime was updated correctly)
            data2 = cache.load()

            assert data1 is data2
            mock_get.assert_called_once()

    def test_uses_env_var_for_url(self, cache_path, sample_data):
        """Test that ROSSUM_KB_DATA_URL env var is used."""
        cache = KBCache(cache_path=cache_path)

        with (
            patch.dict(os.environ, {"ROSSUM_KB_DATA_URL": "https://custom-url.example.com/kb.json"}),
            patch("rossum_agent.tools.knowledge_base_search.httpx.get") as mock_get,
        ):
            mock_response = httpx.Response(200, text=json.dumps(sample_data), request=_DUMMY_REQUEST)
            mock_get.return_value = mock_response

            cache.load()

            mock_get.assert_called_once_with("https://custom-url.example.com/kb.json", timeout=60)


class TestMakeSnippet:
    """Test _make_snippet helper."""

    def test_normalizes_whitespace(self):
        """Test that newlines and multiple spaces are collapsed to single spaces."""
        text = "Before context.\n\n  Multiple   spaces\nand\nnewlines  here.  After context."
        match = re.search("Multiple", text)
        snippet = _make_snippet(text, match)

        assert "\n" not in snippet
        assert "  " not in snippet
        assert "Multiple spaces and newlines here." in snippet


class TestKbGrep:
    """Test kb_grep tool."""

    def test_empty_pattern_returns_error(self, populated_cache):
        """Test that empty or whitespace-only patterns return an error."""
        with patch("rossum_agent.tools.knowledge_base_search._cache", populated_cache):
            for pattern in ["", "   ", "\t"]:
                result = kb_grep(pattern)
                parsed = json.loads(result)

                assert parsed["status"] == "error"
                assert parsed["message"] == "Empty pattern not allowed"

    def test_basic_search(self, populated_cache):
        """Test basic keyword search."""
        with patch("rossum_agent.tools.knowledge_base_search._cache", populated_cache):
            result = kb_grep("document splitting")
            parsed = json.loads(result)

            assert parsed["status"] == "success"
            assert parsed["matches"] == 1
            assert parsed["result"][0]["slug"] == "document-splitting-extension"

    def test_case_insensitive_search(self, populated_cache):
        """Test case-insensitive search (default)."""
        with patch("rossum_agent.tools.knowledge_base_search._cache", populated_cache):
            result = kb_grep("WEBHOOK")
            parsed = json.loads(result)

            assert parsed["status"] == "success"
            assert parsed["matches"] == 1
            assert parsed["result"][0]["slug"] == "webhook-configuration"

    def test_case_sensitive_search(self, populated_cache):
        """Test case-sensitive search."""
        with patch("rossum_agent.tools.knowledge_base_search._cache", populated_cache):
            result = kb_grep("WEBHOOK", case_insensitive=False)
            parsed = json.loads(result)

            assert parsed["status"] == "success"
            assert parsed["result"] == "No matches found"

    def test_regex_search(self, populated_cache):
        """Test regex pattern search."""
        with patch("rossum_agent.tools.knowledge_base_search._cache", populated_cache):
            result = kb_grep("email|webhook")
            parsed = json.loads(result)

            assert parsed["status"] == "success"
            assert parsed["matches"] == 2

    def test_no_matches(self, populated_cache):
        """Test search with no results."""
        with patch("rossum_agent.tools.knowledge_base_search._cache", populated_cache):
            result = kb_grep("nonexistent_topic_xyz")
            parsed = json.loads(result)

            assert parsed["status"] == "success"
            assert parsed["result"] == "No matches found"

    def test_invalid_regex(self, populated_cache):
        """Test invalid regex pattern returns error."""
        with patch("rossum_agent.tools.knowledge_base_search._cache", populated_cache):
            result = kb_grep("[invalid")
            parsed = json.loads(result)

            assert parsed["status"] == "error"
            assert "Invalid regex" in parsed["message"]

    def test_match_in_title_includes_title_marker(self, populated_cache):
        """Test that title matches are marked with [title]."""
        with patch("rossum_agent.tools.knowledge_base_search._cache", populated_cache):
            result = kb_grep("Email Import")
            parsed = json.loads(result)

            assert parsed["status"] == "success"
            assert "[title]" in parsed["result"][0]["snippet"]

    def test_match_limit(self, cache_path):
        """Test that results are limited to _GREP_MATCH_LIMIT."""
        # Create data with more articles than the limit
        articles = [
            {
                "slug": f"article-{i}",
                "url": f"https://kb.example.com/docs/article-{i}",
                "title": f"Article {i} about testing",
                "content": f"Content about testing article {i}",
            }
            for i in range(_GREP_MATCH_LIMIT + 50)
        ]
        data = {"scraped_at": "2026-01-01T00:00:00Z", "articles": articles}
        cache_path.write_text(json.dumps(data))
        cache = KBCache(cache_path=cache_path)

        with patch("rossum_agent.tools.knowledge_base_search._cache", cache):
            result = kb_grep("testing")
            parsed = json.loads(result)

            assert parsed["status"] == "success"
            assert parsed["matches"] == _GREP_MATCH_LIMIT + 50
            assert len(parsed["result"]) <= _GREP_MATCH_LIMIT

    def test_load_error(self):
        """Test error when KB data can't be loaded."""
        with patch(
            "rossum_agent.tools.knowledge_base_search._cache.load",
            side_effect=httpx.HTTPStatusError("Not found", request=None, response=None),
        ):
            result = kb_grep("test")
            parsed = json.loads(result)

            assert parsed["status"] == "error"
            assert "Error loading KB data" in parsed["message"]


class TestKbGetArticle:
    """Test kb_get_article tool."""

    def test_exact_slug_match(self, populated_cache):
        """Test fetching article by exact slug."""
        with patch("rossum_agent.tools.knowledge_base_search._cache", populated_cache):
            result = kb_get_article("document-splitting-extension")
            parsed = json.loads(result)

            assert parsed["status"] == "success"
            assert parsed["slug"] == "document-splitting-extension"
            assert parsed["title"] == "Document Splitting Extension"
            assert "Split documents" in parsed["content"]

    def test_partial_slug_match(self, populated_cache):
        """Test fetching article by partial slug."""
        with patch("rossum_agent.tools.knowledge_base_search._cache", populated_cache):
            result = kb_get_article("splitting")
            parsed = json.loads(result)

            assert parsed["status"] == "success"
            assert parsed["slug"] == "document-splitting-extension"

    def test_case_insensitive_partial_match(self, populated_cache):
        """Test partial match is case-insensitive."""
        with patch("rossum_agent.tools.knowledge_base_search._cache", populated_cache):
            result = kb_get_article("WEBHOOK")
            parsed = json.loads(result)

            assert parsed["status"] == "success"
            assert parsed["slug"] == "webhook-configuration"

    def test_not_found(self, populated_cache):
        """Test slug not found returns error."""
        with patch("rossum_agent.tools.knowledge_base_search._cache", populated_cache):
            result = kb_get_article("nonexistent-article")
            parsed = json.loads(result)

            assert parsed["status"] == "error"
            assert "No article found" in parsed["message"]

    def test_content_truncation(self, cache_path):
        """Test that very long content is truncated."""
        long_content = "x" * (_ARTICLE_OUTPUT_LIMIT + 1000)
        data = {
            "scraped_at": "2026-01-01T00:00:00Z",
            "articles": [
                {
                    "slug": "long-article",
                    "url": "https://kb.example.com/docs/long-article",
                    "title": "Long Article",
                    "content": long_content,
                }
            ],
        }
        cache_path.write_text(json.dumps(data))
        cache = KBCache(cache_path=cache_path)

        with patch("rossum_agent.tools.knowledge_base_search._cache", cache):
            result = kb_get_article("long-article")
            parsed = json.loads(result)

            assert parsed["status"] == "success"
            assert len(parsed["content"]) <= _ARTICLE_OUTPUT_LIMIT + 50  # +50 for "... (truncated)"
            assert parsed["content"].endswith("... (truncated)")

    def test_load_error(self):
        """Test error when KB data can't be loaded."""
        with patch(
            "rossum_agent.tools.knowledge_base_search._cache.load",
            side_effect=httpx.HTTPStatusError("Not found", request=None, response=None),
        ):
            result = kb_get_article("test-slug")
            parsed = json.loads(result)

            assert parsed["status"] == "error"
            assert "Error loading KB data" in parsed["message"]

    def test_ambiguous_partial_slug_returns_candidates(self, cache_path):
        """Test that multiple partial matches return an error with candidate slugs."""
        data = {
            "scraped_at": "2026-01-01T00:00:00Z",
            "articles": [
                {
                    "slug": "webhook-configuration",
                    "url": "https://kb.example.com/docs/webhook-configuration",
                    "title": "Webhook Configuration",
                    "content": "Configure webhooks.",
                },
                {
                    "slug": "webhook-events",
                    "url": "https://kb.example.com/docs/webhook-events",
                    "title": "Webhook Events",
                    "content": "Webhook event types.",
                },
            ],
        }
        cache_path.write_text(json.dumps(data))
        cache = KBCache(cache_path=cache_path)

        with patch("rossum_agent.tools.knowledge_base_search._cache", cache):
            result = kb_get_article("webhook")
            parsed = json.loads(result)

            assert parsed["status"] == "error"
            assert "Ambiguous slug" in parsed["message"]
            assert "webhook-configuration" in parsed["message"]
            assert "webhook-events" in parsed["message"]

    def test_exact_match_preferred_over_partial(self, cache_path):
        """Test that exact slug match is preferred over partial match."""
        data = {
            "scraped_at": "2026-01-01T00:00:00Z",
            "articles": [
                {
                    "slug": "webhook-configuration-advanced",
                    "url": "https://kb.example.com/docs/webhook-configuration-advanced",
                    "title": "Advanced Webhook",
                    "content": "Advanced content",
                },
                {
                    "slug": "webhook",
                    "url": "https://kb.example.com/docs/webhook",
                    "title": "Webhook",
                    "content": "Basic webhook content",
                },
            ],
        }
        cache_path.write_text(json.dumps(data))
        cache = KBCache(cache_path=cache_path)

        with patch("rossum_agent.tools.knowledge_base_search._cache", cache):
            result = kb_get_article("webhook")
            parsed = json.loads(result)

            assert parsed["status"] == "success"
            assert parsed["slug"] == "webhook"


class TestRefreshKnowledgeBase:
    """Test refresh_knowledge_base function."""

    def test_calls_invalidate(self):
        """Test that refresh_knowledge_base calls cache invalidate."""
        with patch("rossum_agent.tools.knowledge_base_search._cache") as mock_cache:
            refresh_knowledge_base()
            mock_cache.invalidate.assert_called_once()


class TestRealKBData:
    """Regression tests using the real scraped KB data file."""

    def test_grep_finds_document_splitting(self, real_kb_cache):
        """Test kb_grep finds document splitting articles in real data."""
        with patch("rossum_agent.tools.knowledge_base_search._cache", real_kb_cache):
            result = kb_grep("document splitting")
            parsed = json.loads(result)

            assert parsed["status"] == "success"
            assert parsed["matches"] >= 1
            slugs = [m["slug"] for m in parsed["result"]]
            assert any("splitting" in s for s in slugs)

    def test_grep_finds_webhook(self, real_kb_cache):
        """Test kb_grep finds webhook articles in real data."""
        with patch("rossum_agent.tools.knowledge_base_search._cache", real_kb_cache):
            result = kb_grep("webhook")
            parsed = json.loads(result)

            assert parsed["status"] == "success"
            assert parsed["matches"] >= 1

    def test_grep_finds_hooks(self, real_kb_cache):
        """Test kb_grep finds hook-related articles in real data."""
        with patch("rossum_agent.tools.knowledge_base_search._cache", real_kb_cache):
            result = kb_grep("serverless function")
            parsed = json.loads(result)

            assert parsed["status"] == "success"
            assert parsed["matches"] >= 1

    def test_get_article_by_exact_slug(self, real_kb_cache):
        """Test kb_get_article retrieves a real article by exact slug."""
        with patch("rossum_agent.tools.knowledge_base_search._cache", real_kb_cache):
            result = kb_get_article("document-splitting-extension")
            parsed = json.loads(result)

            assert parsed["status"] == "success"
            assert parsed["slug"] == "document-splitting-extension"
            assert len(parsed["content"]) > 100

    def test_get_article_by_partial_slug(self, real_kb_cache):
        """Test kb_get_article retrieves article by partial slug."""
        with patch("rossum_agent.tools.knowledge_base_search._cache", real_kb_cache):
            result = kb_get_article("formula-fields")
            parsed = json.loads(result)

            assert parsed["status"] == "success"
            assert "formula" in parsed["slug"]

    def test_get_nonexistent_article(self, real_kb_cache):
        """Test kb_get_article returns error for nonexistent slug."""
        with patch("rossum_agent.tools.knowledge_base_search._cache", real_kb_cache):
            result = kb_get_article("this-article-does-not-exist-xyz")
            parsed = json.loads(result)

            assert parsed["status"] == "error"
