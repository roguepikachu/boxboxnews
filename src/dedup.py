import hashlib
import json
import logging
import re
from datetime import date

from src.config import POSTED_HISTORY_PATH

logger = logging.getLogger(__name__)

# Key entities that indicate the same story across different headlines
ENTITY_KEYWORDS = [
    "hamilton", "verstappen", "norris", "leclerc", "sainz", "piastri",
    "russell", "alonso", "stroll", "gasly", "ocon", "tsunoda", "ricciardo",
    "hulkenberg", "bearman", "lawson", "albon", "colapinto", "bottas",
    "zhou", "antonelli", "doohan", "bortoleto", "hadjar",
    "mercedes", "red bull", "ferrari", "mclaren", "aston martin",
    "alpine", "williams", "haas", "rb", "sauber", "audi", "cadillac",
    "wheatley", "newey", "horner", "wolff", "vasseur", "brown",
]


def _normalize_text(text: str) -> str:
    text = text.lower()
    text = re.sub(r"[^\w\s]", "", text)
    return " ".join(text.split())


def _extract_keywords(text: str) -> set[str]:
    """Extract key F1 entities from text for fuzzy matching."""
    text_lower = text.lower()
    return {kw for kw in ENTITY_KEYWORDS if kw in text_lower}


def _hash_story(title: str) -> str:
    normalized = _normalize_text(title)
    return hashlib.sha256(normalized.encode()).hexdigest()


def _hash_url(url: str) -> str:
    return hashlib.sha256(url.strip().encode()).hexdigest()


def _load_history() -> dict:
    try:
        with open(POSTED_HISTORY_PATH) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"posts": []}


def _save_history(history: dict) -> None:
    with open(POSTED_HISTORY_PATH, "w") as f:
        json.dump(history, f, indent=2)


def already_posted_today() -> bool:
    """Check if we've already posted today."""
    history = _load_history()
    today = date.today().isoformat()
    return any(p.get("date") == today for p in history["posts"])


def filter_duplicates(candidates: list[dict]) -> list[dict]:
    """Remove candidates that match already-posted stories."""
    history = _load_history()

    # Build sets for matching
    posted_title_hashes = {p["hash"] for p in history["posts"]}
    posted_url_hashes = {p.get("url_hash", "") for p in history["posts"]}
    posted_keywords = [set(p.get("keywords", [])) for p in history["posts"]]

    filtered = []
    for c in candidates:
        title_hash = _hash_story(c["title"])
        url_hash = _hash_url(c["url"])
        candidate_kw = _extract_keywords(c["title"])

        # Skip if exact title or URL match
        if title_hash in posted_title_hashes or url_hash in posted_url_hashes:
            logger.debug("Skipping exact match: %s", c["title"][:60])
            continue

        # Skip if the same key entities overlap significantly (same story, different headline)
        if candidate_kw and any(
            len(candidate_kw & posted_kw) >= 2 and len(candidate_kw & posted_kw) / max(len(candidate_kw), 1) >= 0.5
            for posted_kw in posted_keywords if posted_kw
        ):
            logger.debug("Skipping similar story: %s", c["title"][:60])
            continue

        filtered.append(c)

    logger.info("Dedup: %d → %d candidates", len(candidates), len(filtered))
    return filtered


def record_post(tagline: str, source: str, url: str, title: str = "") -> None:
    """Record a posted story to prevent future duplicates."""
    keywords = list(_extract_keywords(tagline) | _extract_keywords(title))
    history = _load_history()
    history["posts"].append({
        "hash": _hash_story(title or tagline),
        "url_hash": _hash_url(url),
        "tagline": tagline,
        "title": title,
        "source": source,
        "date": date.today().isoformat(),
        "url": url,
        "keywords": keywords,
    })
    _save_history(history)
    logger.info("Recorded post: %s", tagline)
