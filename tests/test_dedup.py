import json
import tempfile
import os
from datetime import date, timedelta
from unittest.mock import patch, MagicMock

from src.dedup import filter_duplicates, record_post, _hash_story, _extract_keywords, _jaccard


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
        {"title": "Hamilton joins Ferrari", "summary": "", "source": "reddit", "url": "https://example.com/1"},
        {"title": "Verstappen contract update", "summary": "", "source": "autosport", "url": "https://example.com/2"},
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
        {"title": "Different headline about same article", "summary": "", "source": "autosport", "url": "https://example.com/same"},
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
    today = date.today().isoformat()
    candidates = [
        {"title": "Audi facing crisis after Wheatley departure confirmed", "summary": "", "source": "planetf1", "url": "https://example.com/new"},
    ]

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump({"posts": [{"hash": "x", "url_hash": "y", "tagline": "AUDI BOSS QUITS", "title": "Audi team boss Wheatley exits", "source": "the-race", "date": today, "url": "https://example.com/old", "keywords": ["audi", "wheatley"]}]}, f)
        tmp_path = f.name

    try:
        with patch("src.dedup.POSTED_HISTORY_PATH", tmp_path):
            result = filter_duplicates(candidates)
        assert len(result) == 0
    finally:
        os.unlink(tmp_path)


def test_filter_duplicates_keeps_different_story():
    today = date.today().isoformat()
    candidates = [
        {"title": "Hamilton signs new Mercedes deal", "summary": "", "source": "autosport", "url": "https://example.com/new"},
    ]

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump({"posts": [{"hash": "x", "url_hash": "y", "tagline": "AUDI BOSS QUITS", "title": "Audi boss exits", "source": "the-race", "date": today, "url": "https://example.com/old", "keywords": ["audi", "wheatley"]}]}, f)
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


def test_jaccard():
    assert _jaccard({"a", "b"}, {"a", "b"}) == 1.0
    assert _jaccard({"a"}, {"b"}) == 0.0
    assert _jaccard({"a", "b"}, {"a", "c"}) == 1 / 3  # intersection=1, union=3
    assert _jaccard(set(), {"a"}) == 0.0


def test_single_keyword_overlap_triggers_dedup():
    """A single shared keyword with high Jaccard should be caught."""
    today = date.today().isoformat()
    candidates = [
        {"title": "Wheatley confirms new role", "summary": "", "source": "planetf1", "url": "https://example.com/new"},
    ]
    # Posted story also only has "wheatley" — Jaccard = 1/1 = 1.0, overlap = 1
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump({"posts": [{"hash": "x", "url_hash": "y", "tagline": "WHEATLEY OUT", "title": "Wheatley exits", "source": "the-race", "date": today, "url": "https://example.com/old", "keywords": ["wheatley"]}]}, f)
        tmp_path = f.name

    try:
        with patch("src.dedup.POSTED_HISTORY_PATH", tmp_path):
            result = filter_duplicates(candidates)
        assert len(result) == 0
    finally:
        os.unlink(tmp_path)


def test_summary_keywords_extracted():
    """Keywords in summary (not title) should still trigger dedup."""
    today = date.today().isoformat()
    # Title doesn't mention Audi, but summary does
    candidates = [
        {"title": "New team boss confirmed for 2027", "summary": "Audi has confirmed its new team principal", "source": "autosport", "url": "https://example.com/new"},
    ]
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump({"posts": [{"hash": "x", "url_hash": "y", "tagline": "AUDI SHAKEUP", "title": "Audi restructure", "source": "the-race", "date": today, "url": "https://example.com/old", "keywords": ["audi"]}]}, f)
        tmp_path = f.name

    try:
        with patch("src.dedup.POSTED_HISTORY_PATH", tmp_path):
            result = filter_duplicates(candidates)
        assert len(result) == 0
    finally:
        os.unlink(tmp_path)


def test_recency_window_ignores_old_posts():
    """Keyword matching should NOT flag stories older than 7 days."""
    old_date = (date.today() - timedelta(days=10)).isoformat()
    candidates = [
        {"title": "Audi facing crisis after Wheatley departure", "summary": "", "source": "planetf1", "url": "https://example.com/new"},
    ]
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump({"posts": [{"hash": "x", "url_hash": "y", "tagline": "AUDI BOSS QUITS", "title": "Audi team boss Wheatley exits", "source": "the-race", "date": old_date, "url": "https://example.com/old", "keywords": ["audi", "wheatley"]}]}, f)
        tmp_path = f.name

    try:
        with patch("src.dedup.POSTED_HISTORY_PATH", tmp_path):
            result = filter_duplicates(candidates)
        # Old post should NOT block — keyword match is outside recency window
        assert len(result) == 1
    finally:
        os.unlink(tmp_path)


def test_record_post_with_summary():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump({"posts": []}, f)
        tmp_path = f.name

    try:
        with patch("src.dedup.POSTED_HISTORY_PATH", tmp_path):
            record_post(
                "HAMILTON TO FERRARI", "autosport", "https://example.com",
                title="Hamilton reportedly joining Ferrari",
                summary="Mercedes driver Hamilton to join Verstappen rival team",
            )

        with open(tmp_path) as f:
            data = json.load(f)
        post = data["posts"][0]
        assert post["summary"] == "Mercedes driver Hamilton to join Verstappen rival team"
        # Summary keywords should be extracted
        assert "mercedes" in post["keywords"]
        assert "verstappen" in post["keywords"]
    finally:
        os.unlink(tmp_path)


def test_validate_not_duplicate_passes():
    """When Gemini says fresh and not a duplicate, return curated unchanged."""
    from src.rumor_curator import validate_not_duplicate

    curated = {"tagline": "NEW STORY", "selected_url": "https://example.com/1", "source": "autosport"}
    candidates = [{"title": "New story", "summary": "", "url": "https://example.com/1", "source": "autosport", "score": 5}]

    fresh_response = MagicMock()
    fresh_response.text = '{"is_fresh": true, "reason": "breaking news"}'
    not_dup_response = MagicMock()
    not_dup_response.text = '{"is_duplicate": false, "reason": "different topic"}'

    with patch("src.dedup.POSTED_HISTORY_PATH", "/dev/null"), \
         patch("src.dedup._load_history", return_value={"posts": [{"tagline": "OLD", "title": "Old story", "keywords": ["hamilton"], "date": "2026-01-01"}]}), \
         patch("src.rumor_curator.genai") as mock_genai:
        mock_genai.Client.return_value.models.generate_content.side_effect = [fresh_response, not_dup_response]
        result = validate_not_duplicate(curated, candidates)

    assert result == curated


def test_validate_freshness_rejects_stale_and_recurates():
    """When Gemini flags story as stale, should remove and re-curate."""
    from src.rumor_curator import validate_not_duplicate

    curated1 = {"tagline": "OLD NEWS", "selected_url": "https://example.com/1", "source": "autosport"}
    curated2 = {"tagline": "FRESH STORY", "selected_url": "https://example.com/2", "source": "planetf1"}
    candidates = [
        {"title": "Old news", "summary": "", "url": "https://example.com/1", "source": "autosport", "score": 5},
        {"title": "Fresh", "summary": "", "url": "https://example.com/2", "source": "planetf1", "score": 4},
    ]

    stale_response = MagicMock()
    stale_response.text = '{"is_fresh": false, "reason": "already known transfer"}'
    fresh_response = MagicMock()
    fresh_response.text = '{"is_fresh": true, "reason": "new development"}'
    not_dup_response = MagicMock()
    not_dup_response.text = '{"is_duplicate": false, "reason": "new topic"}'

    with patch("src.dedup._load_history", return_value={"posts": [{"tagline": "OLD", "title": "Old", "keywords": ["hamilton"], "date": "2026-01-01"}]}), \
         patch("src.rumor_curator.genai") as mock_genai, \
         patch("src.rumor_curator.curate", return_value=curated2) as mock_curate:
        mock_client = mock_genai.Client.return_value
        # Call 1: freshness check on curated1 → stale
        # Call 2: freshness check on curated2 → fresh
        # Call 3: duplicate check on curated2 → not duplicate
        mock_client.models.generate_content.side_effect = [stale_response, fresh_response, not_dup_response]
        result = validate_not_duplicate(curated1, candidates)

    assert result == curated2
    mock_curate.assert_called_once()


def test_validate_not_duplicate_flags_and_recurates():
    """When Gemini flags duplicate, should remove candidate and re-curate."""
    from src.rumor_curator import validate_not_duplicate

    curated1 = {"tagline": "DUPLICATE STORY", "selected_url": "https://example.com/1", "source": "autosport"}
    curated2 = {"tagline": "FRESH STORY", "selected_url": "https://example.com/2", "source": "planetf1"}
    candidates = [
        {"title": "Duplicate", "summary": "", "url": "https://example.com/1", "source": "autosport", "score": 5},
        {"title": "Fresh", "summary": "", "url": "https://example.com/2", "source": "planetf1", "score": 4},
    ]

    fresh_response = MagicMock()
    fresh_response.text = '{"is_fresh": true, "reason": "new development"}'
    dup_response = MagicMock()
    dup_response.text = '{"is_duplicate": true, "reason": "same event"}'
    fresh_response2 = MagicMock()
    fresh_response2.text = '{"is_fresh": true, "reason": "new development"}'
    ok_response = MagicMock()
    ok_response.text = '{"is_duplicate": false, "reason": "new topic"}'

    with patch("src.dedup._load_history", return_value={"posts": [{"tagline": "OLD", "title": "Old", "keywords": ["hamilton"], "date": "2026-01-01"}]}), \
         patch("src.rumor_curator.genai") as mock_genai, \
         patch("src.rumor_curator.curate", return_value=curated2) as mock_curate:
        mock_client = mock_genai.Client.return_value
        # Call 1: freshness on curated1 → fresh
        # Call 2: duplicate on curated1 → duplicate
        # Call 3: freshness on curated2 → fresh
        # Call 4: duplicate on curated2 → not duplicate
        mock_client.models.generate_content.side_effect = [fresh_response, dup_response, fresh_response2, ok_response]
        result = validate_not_duplicate(curated1, candidates)

    assert result == curated2
    mock_curate.assert_called_once()
    recurated_candidates = mock_curate.call_args[0][0]
    assert len(recurated_candidates) == 1
    assert recurated_candidates[0]["url"] == "https://example.com/2"
