import json
import tempfile
import os
from unittest.mock import patch

from src.dedup import filter_duplicates, record_post, _hash_story, _extract_keywords


def test_hash_story_normalization():
    assert _hash_story("HAMILTON JOINS FERRARI!") == _hash_story("hamilton joins ferrari")
    assert _hash_story("  Hello  World  ") == _hash_story("hello world")


def test_hash_story_different():
    assert _hash_story("Hamilton joins Ferrari") != _hash_story("Verstappen leaves Red Bull")


def test_extract_keywords():
    kw = _extract_keywords("Hamilton reportedly joining Ferrari next season")
    assert "hamilton" in kw
    assert "ferrari" in kw


def test_filter_duplicates_empty_history():
    candidates = [
        {"title": "Hamilton joins Ferrari", "source": "reddit", "url": "https://example.com/1"},
        {"title": "Verstappen contract update", "source": "autosport", "url": "https://example.com/2"},
    ]
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump({"posts": []}, f)
        tmp_path = f.name

    try:
        with patch("src.dedup.POSTED_HISTORY_PATH", tmp_path):
            result = filter_duplicates(candidates)
        assert len(result) == 2
    finally:
        os.unlink(tmp_path)


def test_filter_duplicates_removes_by_url():
    candidates = [
        {"title": "Different headline about same article", "source": "autosport", "url": "https://example.com/same"},
    ]
    from src.dedup import _hash_url
    url_hash = _hash_url("https://example.com/same")

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump({"posts": [{"hash": "x", "url_hash": url_hash, "tagline": "OLD POST", "source": "test", "date": "2026-01-01", "url": "https://example.com/same", "keywords": []}]}, f)
        tmp_path = f.name

    try:
        with patch("src.dedup.POSTED_HISTORY_PATH", tmp_path):
            result = filter_duplicates(candidates)
        assert len(result) == 0
    finally:
        os.unlink(tmp_path)


def test_filter_duplicates_removes_similar_keywords():
    candidates = [
        {"title": "Audi facing crisis after Wheatley departure confirmed", "source": "planetf1", "url": "https://example.com/new"},
    ]

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump({"posts": [{"hash": "x", "url_hash": "y", "tagline": "AUDI BOSS QUITS", "title": "Audi team boss Wheatley exits", "source": "the-race", "date": "2026-01-01", "url": "https://example.com/old", "keywords": ["audi", "wheatley"]}]}, f)
        tmp_path = f.name

    try:
        with patch("src.dedup.POSTED_HISTORY_PATH", tmp_path):
            result = filter_duplicates(candidates)
        assert len(result) == 0
    finally:
        os.unlink(tmp_path)


def test_filter_duplicates_keeps_different_story():
    candidates = [
        {"title": "Hamilton signs new Mercedes deal", "source": "autosport", "url": "https://example.com/new"},
    ]

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump({"posts": [{"hash": "x", "url_hash": "y", "tagline": "AUDI BOSS QUITS", "title": "Audi boss exits", "source": "the-race", "date": "2026-01-01", "url": "https://example.com/old", "keywords": ["audi", "wheatley"]}]}, f)
        tmp_path = f.name

    try:
        with patch("src.dedup.POSTED_HISTORY_PATH", tmp_path):
            result = filter_duplicates(candidates)
        assert len(result) == 1
    finally:
        os.unlink(tmp_path)


def test_record_post():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump({"posts": []}, f)
        tmp_path = f.name

    try:
        with patch("src.dedup.POSTED_HISTORY_PATH", tmp_path):
            record_post("HAMILTON TO FERRARI", "autosport", "https://example.com", title="Hamilton reportedly joining Ferrari")

        with open(tmp_path) as f:
            data = json.load(f)
        assert len(data["posts"]) == 1
        assert data["posts"][0]["tagline"] == "HAMILTON TO FERRARI"
        assert "hamilton" in data["posts"][0]["keywords"]
        assert "ferrari" in data["posts"][0]["keywords"]
        assert data["posts"][0]["url_hash"] != ""
    finally:
        os.unlink(tmp_path)
