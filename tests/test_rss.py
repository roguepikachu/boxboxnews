from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock
from time import struct_time

from src.rss_scraper import scrape_rss, _parse_entry_date


def test_parse_entry_date_with_published():
    entry = MagicMock()
    entry.published_parsed = struct_time((2026, 3, 20, 12, 0, 0, 0, 0, 0))
    entry.updated_parsed = None
    result = _parse_entry_date(entry)
    assert result is not None
    assert result.year == 2026


def test_parse_entry_date_none():
    entry = MagicMock()
    entry.published_parsed = None
    entry.updated_parsed = None
    result = _parse_entry_date(entry)
    assert result is None


def test_scrape_rss_filters_old_articles():
    now = datetime.now(timezone.utc)
    old_time = (now - timedelta(hours=48)).timetuple()
    fresh_time = (now - timedelta(hours=6)).timetuple()

    old_entry = MagicMock()
    old_entry.published_parsed = old_time
    old_entry.title = "Old article"
    old_entry.get = lambda k, d="": {"title": "Old article", "summary": "Old summary", "link": "https://example.com/old"}.get(k, d)

    fresh_entry = MagicMock()
    fresh_entry.published_parsed = fresh_time
    fresh_entry.title = "Fresh article"
    fresh_entry.get = lambda k, d="": {"title": "Fresh article", "summary": "Fresh summary", "link": "https://example.com/fresh"}.get(k, d)

    mock_feed = MagicMock()
    mock_feed.entries = [old_entry, fresh_entry]

    with patch("src.rss_scraper.feedparser.parse", return_value=mock_feed):
        with patch("src.rss_scraper.RSS_FEEDS", {"test": {"url": "https://test.com/feed", "name": "Test"}}):
            results = scrape_rss()

    assert len(results) == 1
    assert results[0]["title"] == "Fresh article"
