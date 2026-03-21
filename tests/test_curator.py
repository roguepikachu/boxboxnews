import json
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone

from src.rumor_curator import curate, _format_candidates


def test_format_candidates():
    candidates = [
        {
            "title": "Hamilton to Ferrari",
            "summary": "Lewis Hamilton reportedly signing with Ferrari",
            "source": "autosport",
            "url": "https://autosport.com/1",
            "score": 0.0,
        },
    ]
    result = _format_candidates(candidates)
    assert "AUTOSPORT" in result
    assert "Hamilton to Ferrari" in result


def test_curate_success():
    candidates = [
        {
            "title": "Test rumor",
            "summary": "Test summary",
            "source": "reddit",
            "url": "https://reddit.com/test",
            "score": 100.0,
        },
    ]

    mock_response = MagicMock()
    mock_response.text = json.dumps({
        "selected_url": "https://reddit.com/test",
        "tagline": "TEST RUMOR HERE",
        "caption": "Test caption #F1",
        "image_prompt": "F1 car on track",
        "entities": {"drivers": [], "teams": [], "objects": []},
        "source": "reddit",
    })

    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = mock_response

    with patch("src.rumor_curator.genai.Client", return_value=mock_client):
        result = curate(candidates)

    assert result is not None
    assert result["tagline"] == "TEST RUMOR HERE"


def test_curate_empty_candidates():
    result = curate([])
    assert result is None
