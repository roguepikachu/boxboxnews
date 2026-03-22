"""Fetch reference images from Bing Images, ranked by Gemini Flash."""

import json
import logging
import re

import requests
from google import genai
from google.genai import types

from src.config import GEMINI_API_KEY, GEMINI_TEXT_MODEL

logger = logging.getLogger(__name__)

_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


def _build_queries(entities: dict) -> list[str]:
    """Build targeted search queries from curated entities."""
    queries = []
    for driver in entities.get("drivers", []):
        queries.append(f"{driver} F1 2025 portrait")
    for team in entities.get("teams", []):
        queries.append(f"{team} F1 2025 car")
    for obj in entities.get("objects", []):
        queries.append(f"F1 {obj} 2025")
    return queries[:3]


def _search_image_urls(query: str, num_results: int = 8) -> list[str]:
    """Extract full-resolution image URLs from Bing Images search."""
    url = "https://www.bing.com/images/search"
    try:
        resp = requests.get(
            url,
            params={"q": query, "form": "HDRSC2", "first": "1"},
            headers={"User-Agent": _USER_AGENT},
            timeout=10,
        )
        resp.raise_for_status()
        urls = re.findall(r'murl&quot;:&quot;(https?://[^&]+?)&quot;', resp.text)
        return urls[:num_results]
    except Exception:
        logger.warning("Image search failed for: %s", query)
        return []


def _download_image(url: str) -> bytes | None:
    """Download an image, returning bytes or None on failure."""
    try:
        resp = requests.get(
            url, headers={"User-Agent": _USER_AGENT}, timeout=10,
        )
        resp.raise_for_status()
        content_type = resp.headers.get("content-type", "")
        if "image" not in content_type:
            return None
        data = resp.content
        if len(data) < 5_000:
            return None
        return data
    except Exception:
        return None


def _detect_mime(data: bytes) -> str:
    if data[:4] == b"\x89PNG":
        return "image/png"
    if data[:4] == b"RIFF":
        return "image/webp"
    return "image/jpeg"


def _pick_best_with_gemini(
    candidates: list[bytes], query: str, entities: dict,
) -> list[bytes]:
    """Use Gemini Flash to pick the best reference image(s) from candidates.

    Sends all candidate images to Gemini and asks it to rank them by
    relevance, quality, and suitability as a reference for image generation.
    """
    if len(candidates) <= 1:
        return candidates

    entity_desc = []
    for driver in entities.get("drivers", []):
        entity_desc.append(f"Driver: {driver}")
    for team in entities.get("teams", []):
        entity_desc.append(f"Team: {team}")
    for obj in entities.get("objects", []):
        entity_desc.append(f"Object: {obj}")

    parts = [types.Part.from_text(text=
        f"I searched for \"{query}\" and got {len(candidates)} images.\n"
        f"Context — this is for an F1 news Instagram post about: {', '.join(entity_desc)}\n\n"
        "Look at each image and pick the ONE best image to use as a reference "
        "for generating a cinematic F1 Instagram post. Criteria:\n"
        "1. Correctly shows the right person/car/team (not a different driver or team)\n"
        "2. High resolution and sharp (not blurry, not a thumbnail)\n"
        "3. Dramatic or cinematic angle (action shots > posed headshots)\n"
        "4. Clean composition (no heavy text overlays, watermarks, or collages)\n\n"
        "Return ONLY valid JSON: {\"best_index\": <0-based index of the best image>,"
        " \"reason\": \"brief explanation\"}"
    )]

    for i, img in enumerate(candidates):
        parts.append(types.Part.from_text(text=f"Image {i}:"))
        parts.append(types.Part.from_bytes(data=img, mime_type=_detect_mime(img)))

    try:
        client = genai.Client(api_key=GEMINI_API_KEY)
        response = client.models.generate_content(
            model=GEMINI_TEXT_MODEL,
            contents=[types.Content(parts=parts, role="user")],
        )
        text = response.text.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1]
            if text.endswith("```"):
                text = text[:-3]
            text = text.strip()

        result = json.loads(text)
        idx = result.get("best_index", 0)
        reason = result.get("reason", "")

        if 0 <= idx < len(candidates):
            logger.info("Gemini picked image %d/%d: %s", idx + 1, len(candidates), reason)
            return [candidates[idx]]
        else:
            logger.warning("Gemini returned invalid index %d, using first image", idx)
            return [candidates[0]]

    except Exception:
        logger.exception("Gemini image ranking failed, using first image")
        return [candidates[0]]


def fetch_reference_images(entities: dict, max_images: int = 2) -> list[bytes]:
    """Fetch reference images for the story's entities.

    For each search query, downloads multiple candidates from Bing and uses
    Gemini Flash to pick the best one. Returns up to ``max_images`` images.
    """
    queries = _build_queries(entities)
    if not queries:
        return []

    images: list[bytes] = []
    for query in queries:
        if len(images) >= max_images:
            break

        # Download multiple candidates per query
        urls = _search_image_urls(query)
        candidates: list[bytes] = []
        for url in urls:
            if len(candidates) >= 5:  # cap downloads per query
                break
            img_bytes = _download_image(url)
            if img_bytes:
                candidates.append(img_bytes)

        if not candidates:
            logger.warning("No images downloaded for: %s", query)
            continue

        logger.info("Downloaded %d candidate images for: %s", len(candidates), query)

        # Let Gemini pick the best one
        best = _pick_best_with_gemini(candidates, query, entities)
        images.extend(best)

    logger.info("Fetched %d reference image(s)", len(images))
    return images
