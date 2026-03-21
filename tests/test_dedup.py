import json
import tempfile
import os
from unittest.mock import patch
from datetime import datetime, timezone

from src.dedup import filter_duplicates, record_post, _hash_story


def test_hash_story_normalization():
    assert _hash_story("HAMILTON JOINS FERRARI!") == _hash_story("hamilton joins ferrari")
    assert _hash_story("  Hello  World  ") == _hash_story("hello world")


def test_hash_story_different():
    assert _hash_story("Hamilton joins Ferrari") != _hash_story("Verstappen leaves Red Bull")


def test_filter_duplicates_empty_history():
    candidates = [
        {"title": "Hamilton joins Ferrari", "source": "reddit"},
        {"title": "Verstappen contract update", "source": "autosport"},
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


def test_filter_duplicates_removes_posted():
    candidates = [
        {"title": "Hamilton joins Ferrari", "source": "reddit"},
        {"title": "Verstappen contract update", "source": "autosport"},
    ]
    existing_hash = _hash_story("Hamilton joins Ferrari")

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump({"posts": [{"hash": existing_hash, "tagline": "test", "source": "test", "date": "2026-01-01", "url": ""}]}, f)
        tmp_path = f.name

    try:
        with patch("src.dedup.POSTED_HISTORY_PATH", tmp_path):
            result = filter_duplicates(candidates)
        assert len(result) == 1
        assert result[0]["title"] == "Verstappen contract update"
    finally:
        os.unlink(tmp_path)


def test_record_post():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump({"posts": []}, f)
        tmp_path = f.name

    try:
        with patch("src.dedup.POSTED_HISTORY_PATH", tmp_path):
            record_post("HAMILTON TO FERRARI", "autosport", "https://example.com")

        with open(tmp_path) as f:
            data = json.load(f)
        assert len(data["posts"]) == 1
        assert data["posts"][0]["tagline"] == "HAMILTON TO FERRARI"
    finally:
        os.unlink(tmp_path)
