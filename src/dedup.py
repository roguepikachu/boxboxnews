import hashlib
import json
import logging
import re
from datetime import date

from src.config import POSTED_HISTORY_PATH

logger = logging.getLogger(__name__)


def _normalize_text(text: str) -> str:
    text = text.lower()
    text = re.sub(r"[^\w\s]", "", text)
    return " ".join(text.split())


def _hash_story(title: str) -> str:
    normalized = _normalize_text(title)
    return hashlib.sha256(normalized.encode()).hexdigest()


def _load_history() -> dict:
    try:
        with open(POSTED_HISTORY_PATH) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"posts": []}


def _save_history(history: dict) -> None:
    with open(POSTED_HISTORY_PATH, "w") as f:
        json.dump(history, f, indent=2)


def filter_duplicates(candidates: list[dict]) -> list[dict]:
    """Remove candidates that have already been posted."""
    history = _load_history()
    posted_hashes = {p["hash"] for p in history["posts"]}

    filtered = []
    for c in candidates:
        h = _hash_story(c["title"])
        if h not in posted_hashes:
            filtered.append(c)
        else:
            logger.debug("Skipping duplicate: %s", c["title"][:60])

    logger.info("Dedup: %d → %d candidates", len(candidates), len(filtered))
    return filtered


def record_post(tagline: str, source: str, url: str) -> None:
    """Record a posted story to prevent future duplicates."""
    history = _load_history()
    history["posts"].append({
        "hash": _hash_story(tagline),
        "tagline": tagline,
        "source": source,
        "date": date.today().isoformat(),
        "url": url,
    })
    _save_history(history)
    logger.info("Recorded post: %s", tagline)
