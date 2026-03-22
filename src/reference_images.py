"""Fetch reference images from Google Images for contextual image generation."""

import logging
import re

import requests
from urllib.parse import quote_plus

logger = logging.getLogger(__name__)

_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


def _build_queries(entities: dict) -> list[str]:
    """Build targeted search queries from curated entities."""
    queries = []
    for driver in entities.get("drivers", []):
        queries.append(f"{driver} F1 2025 close up portrait helmet")
    for team in entities.get("teams", []):
        queries.append(f"{team} F1 2025 car on track")
    for obj in entities.get("objects", []):
        queries.append(f"F1 {obj} 2025 close up")
    return queries[:3]


def _search_image_urls(query: str, num_results: int = 5) -> list[str]:
    """Extract image URLs from a Google Images search page."""
    url = f"https://www.google.com/search?q={quote_plus(query)}&tbm=isch&safe=active"
    try:
        resp = requests.get(url, headers={"User-Agent": _USER_AGENT}, timeout=10)
        resp.raise_for_status()
        # Google embeds full-resolution URLs in JSON-like structures on the page
        urls = re.findall(
            r'\["(https?://[^"]+\.(?:jpg|jpeg|png|webp))[^"]*",[0-9]+,[0-9]+\]',
            resp.text,
        )
        # Filter out Google-owned domains and tracking URLs
        urls = [
            u for u in urls
            if "google.com" not in u
            and "gstatic.com" not in u
            and "googleapis.com" not in u
        ]
        return urls[:num_results]
    except Exception:
        logger.warning("Image search failed for: %s", query)
        return []


def _download_image(url: str) -> bytes | None:
    """Download an image, returning bytes or None on failure."""
    try:
        resp = requests.get(
            url, headers={"User-Agent": _USER_AGENT}, timeout=10, stream=True,
        )
        resp.raise_for_status()
        content_type = resp.headers.get("content-type", "")
        if "image" not in content_type:
            return None
        data = resp.content
        if len(data) < 5_000:  # skip tiny/broken images
            return None
        return data
    except Exception:
        return None


def fetch_reference_images(entities: dict, max_images: int = 2) -> list[bytes]:
    """Fetch reference images for the story's entities.

    Returns up to ``max_images`` image byte buffers. Returns an empty list
    (never raises) if nothing can be fetched.
    """
    queries = _build_queries(entities)
    if not queries:
        return []

    images: list[bytes] = []
    for query in queries:
        if len(images) >= max_images:
            break
        for url in _search_image_urls(query):
            if len(images) >= max_images:
                break
            img_bytes = _download_image(url)
            if img_bytes:
                logger.info("Downloaded reference image for: %s", query)
                images.append(img_bytes)
                break  # one good image per query

    logger.info("Fetched %d reference image(s)", len(images))
    return images
