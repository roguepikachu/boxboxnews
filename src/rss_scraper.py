import hashlib
import logging
from datetime import datetime, timezone, timedelta
from time import mktime

import feedparser

from src.config import RSS_FEEDS

logger = logging.getLogger(__name__)


def _parse_entry_date(entry) -> datetime | None:
    for attr in ("published_parsed", "updated_parsed"):
        parsed = getattr(entry, attr, None)
        if parsed:
            return datetime.fromtimestamp(mktime(parsed), tz=timezone.utc)
    return None


def scrape_rss(max_age_hours: int = 168) -> list[dict]:
    """Fetch recent F1 articles from RSS feeds."""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=max_age_hours)
    candidates = []

    for key, feed_info in RSS_FEEDS.items():
        logger.info("Fetching RSS: %s (%s)", feed_info["name"], feed_info["url"])
        try:
            feed = feedparser.parse(feed_info["url"])
        except Exception:
            logger.exception("Failed to parse feed: %s", key)
            continue

        for entry in feed.entries:
            pub_date = _parse_entry_date(entry)
            if pub_date is None or pub_date < cutoff:
                continue

            title = entry.get("title", "")
            summary = entry.get("summary", entry.get("description", title))
            # Strip HTML tags from summary
            if "<" in summary:
                import re
                summary = re.sub(r"<[^>]+>", "", summary)
            summary = summary[:500]

            link = entry.get("link", "")
            raw_id = hashlib.sha256(link.encode()).hexdigest()[:16]

            candidates.append({
                "title": title,
                "summary": summary,
                "source": key,
                "url": link,
                "timestamp": pub_date,
                "score": 0.0,
                "raw_id": raw_id,
            })

    logger.info("Found %d RSS candidates", len(candidates))
    return candidates
