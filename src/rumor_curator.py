import json
import logging

from google import genai

from src.config import GEMINI_API_KEY, GEMINI_TEXT_MODEL
from src.cost_tracker import tracker

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are the editorial brain behind @BoxBoxNews, a viral F1 rumors Instagram page
with a sports broadcast aesthetic.

You will receive a pool of F1 news items from multiple sources (Reddit, PlanetF1,
RacingNews365, Autosport, Motorsport.com). Pick the ONE most scroll-stopping
rumor that would make the best Instagram post.

CRITICAL FRESHNESS RULE:
- Only pick stories about NEW developments from THIS WEEK.
- REJECT stories about transfers, moves, or deals that are already confirmed and
  publicly known (e.g. if a driver has already joined a team, that is old news).
- REJECT "reaction to" or "analysis of" old events unless there is a genuinely
  new development (new quote, new conflict, new FIA ruling, etc.).
- The story must contain something the average F1 fan would NOT already know.
  Ask yourself: "Would an F1 fan say 'I already knew that'?" If yes, skip it.

Selection criteria (ranked):
1. Freshness — MUST be a genuinely new development, not a rehash of known facts
2. Drama level — transfers, conflicts, surprise retirements, regulation drama
3. Specificity — concrete claims beat vague speculation
4. Source credibility — Autosport/Motorsport.com > PlanetF1 > Reddit
5. Recency — prefer last 12 hours
6. Visual potential — stories involving specific teams/cars generate better images

Return ONLY valid JSON:
{
    "selected_url": "original source URL",
    "tagline": "3-6 word ALL CAPS punchy headline for the image overlay",
    "caption": "2-3 paragraph Instagram caption. Hook on first line. Conversational but authoritative. Reference the source naturally. Include emojis sparingly. End with line break then hashtags: #F1 #Formula1 #BoxBoxNews + 5-8 relevant tags",
    "image_prompt": "Detailed Imagen prompt. Cinematic F1 scene matching the rumor. Team livery colors, helmet design, dramatic lighting. Motion blur background. Editorial photography style. 1:1 square. Bottom 40% should be dark/shadowed empty space. CRITICAL: The image must contain ZERO text, ZERO words, ZERO letters, ZERO numbers, ZERO logos, ZERO watermarks, ZERO labels, ZERO overlays. Pure photographic image only, completely clean of any writing or symbols.",
    "entities": {
        "drivers": ["Lewis Hamilton"],
        "teams": ["Ferrari"],
        "objects": ["SF-26", "front wing"]
    },
    "source": "autosport"
}"""


def _format_candidates(candidates: list[dict]) -> str:
    lines = []
    for i, c in enumerate(candidates, 1):
        pub = ""
        if c.get("timestamp"):
            pub = f"   Published: {c['timestamp'].isoformat()}\n"
        lines.append(
            f"{i}. [{c['source'].upper()}] {c['title']}\n"
            f"   Summary: {c['summary'][:200]}\n"
            f"{pub}"
            f"   URL: {c['url']}\n"
            f"   Score: {c['score']}"
        )
    return "\n\n".join(lines)


def _get_recent_topics() -> str:
    """Load recent post topics to tell Gemini what to avoid."""
    from src.dedup import _load_history
    history = _load_history()
    if not history["posts"]:
        return ""

    lines = []
    for p in history["posts"][-10:]:  # last 10 posts
        tagline = p.get("tagline", "")
        title = p.get("title", "")
        keywords = ", ".join(p.get("keywords", []))
        lines.append(f"- {tagline} ({title}) [keywords: {keywords}]")

    return (
        "\n\nIMPORTANT - DO NOT pick stories about these topics, "
        "we already posted about them:\n" + "\n".join(lines)
    )


def curate(candidates: list[dict], max_retries: int = 2) -> dict | None:
    """Use Gemini Flash to pick the best rumor and generate post content."""
    if not candidates:
        logger.warning("No candidates to curate")
        return None

    from datetime import date
    client = genai.Client(api_key=GEMINI_API_KEY)
    avoid_topics = _get_recent_topics()
    today = date.today().isoformat()
    user_prompt = (
        f"Today's date is {today}.\n\n"
        f"Here are {len(candidates)} F1 news candidates from today:\n\n"
        f"{_format_candidates(candidates)}\n\n"
        f"{avoid_topics}\n\n"
        "Pick the ONE best rumor and return the JSON. "
        "Remember: only pick something that is a GENUINELY NEW development this week, "
        "not old news being rehashed."
    )

    for attempt in range(max_retries + 1):
        try:
            response = client.models.generate_content(
                model=GEMINI_TEXT_MODEL,
                contents=[
                    {"role": "user", "parts": [{"text": SYSTEM_PROMPT + "\n\n" + user_prompt}]},
                ],
            )
            tracker.record_generate_content(GEMINI_TEXT_MODEL, response)
            text = response.text.strip()
            # Strip markdown code fences if present
            if text.startswith("```"):
                text = text.split("\n", 1)[1]
                if text.endswith("```"):
                    text = text[:-3]
                text = text.strip()

            result = json.loads(text)

            # Validate required fields
            required = {"selected_url", "tagline", "caption", "image_prompt", "entities", "source"}
            if not required.issubset(result.keys()):
                missing = required - result.keys()
                logger.warning("Missing fields %s, retrying (attempt %d)", missing, attempt + 1)
                continue

            logger.info("Curated: %s", result["tagline"])
            return result

        except (json.JSONDecodeError, KeyError) as e:
            logger.warning("Gemini response parse error: %s (attempt %d)", e, attempt + 1)
        except Exception:
            logger.exception("Gemini API error (attempt %d)", attempt + 1)

    logger.error("Failed to curate after %d attempts", max_retries + 1)
    return None


FRESHNESS_PROMPT = """You are a strict freshness judge for an F1 Instagram news page.

Your job is to determine whether a story is GENUINELY NEW or just a rehash of
old/already-known information.

A story is STALE if:
- It reports a transfer, signing, or deal that was already publicly confirmed
  weeks or months ago (e.g. "Driver X joins Team Y" when that happened last season)
- It is a reaction/analysis/opinion piece about an event everyone already knows about
- It reports on a driver already being at their current team as if it were news
- The headline could have been written a month ago and still be accurate

A story is FRESH if:
- It reports something that happened in the last 48 hours
- It contains a NEW quote, NEW development, NEW conflict, or NEW FIA decision
- It is a breaking story or a genuinely new rumor not yet widely known
- Even if it involves known people/teams, the specific event or claim is new

Return ONLY valid JSON:
{
    "is_fresh": true/false,
    "reason": "brief explanation of why this is fresh or stale"
}"""


VALIDATION_PROMPT = """You are a duplicate-detection judge for an F1 Instagram news page.

Given a SELECTED story and a list of RECENTLY POSTED stories, determine whether the
selected story covers the SAME underlying event as any recent post.

Same event means: same incident, same transfer rumor, same regulation change, etc.
Different angles or updates on the same event still count as duplicates.

Return ONLY valid JSON:
{
    "is_duplicate": true/false,
    "reason": "brief explanation"
}"""


def _check_freshness(client: genai.Client, curated: dict, today: str) -> bool:
    """Ask Gemini whether the curated story is genuinely fresh. Returns True if fresh."""
    selected_desc = (
        f"Today's date: {today}\n"
        f"Tagline: {curated['tagline']}\n"
        f"Caption: {curated.get('caption', '')[:300]}\n"
        f"Source: {curated['source']}\n"
        f"URL: {curated['selected_url']}"
    )
    user_prompt = (
        f"SELECTED STORY:\n{selected_desc}\n\n"
        "Is this story genuinely fresh and newsworthy as of today's date, "
        "or is it stale/old/already-known information?"
    )

    try:
        response = client.models.generate_content(
            model=GEMINI_TEXT_MODEL,
            contents=[
                {"role": "user", "parts": [{"text": FRESHNESS_PROMPT + "\n\n" + user_prompt}]},
            ],
        )
        tracker.record_generate_content(GEMINI_TEXT_MODEL, response)
        text = response.text.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1]
            if text.endswith("```"):
                text = text[:-3]
            text = text.strip()

        result = json.loads(text)
        is_fresh = result.get("is_fresh", True)
        reason = result.get("reason", "")

        if is_fresh:
            logger.info("Freshness check passed: %s", reason)
        else:
            logger.warning("Freshness check FAILED: %s", reason)
        return is_fresh

    except Exception:
        logger.exception("Freshness check error, allowing story through")
        return True  # fail open


def validate_not_duplicate(curated: dict, candidates: list[dict], max_attempts: int = 3) -> dict | None:
    """Validate curated story is genuinely fresh and not a duplicate.

    Runs two checks per attempt:
    1. Freshness — is this actually new news, not a rehash of old facts?
    2. Duplicate — does this overlap with recent posts?

    If either check fails, removes that candidate and re-curates.
    Returns the final validated curated result, or None.
    """
    from datetime import date
    from src.dedup import _load_history

    today = date.today().isoformat()
    client = genai.Client(api_key=GEMINI_API_KEY)
    remaining = list(candidates)

    # Build recent posts context for duplicate check
    history = _load_history()
    recent_posts = history["posts"][-10:]
    recent_block = ""
    if recent_posts:
        recent_lines = []
        for p in recent_posts:
            recent_lines.append(
                f"- {p.get('tagline', '')} | {p.get('title', '')} | keywords: {', '.join(p.get('keywords', []))}"
            )
        recent_block = "\n".join(recent_lines)

    for attempt in range(max_attempts):
        # --- Check 1: Freshness ---
        if not _check_freshness(client, curated, today):
            logger.warning("Story rejected as stale (attempt %d/%d)", attempt + 1, max_attempts)
            remaining = [c for c in remaining if c["url"] != curated["selected_url"]]
            if not remaining:
                logger.error("No candidates left after freshness filtering")
                return None
            curated = curate(remaining)
            if not curated:
                logger.error("Re-curation failed after freshness rejection")
                return None
            continue

        # --- Check 2: Duplicate (skip if no history) ---
        if not recent_posts:
            logger.info("No post history, skipping duplicate check")
            return curated

        selected_desc = (
            f"Tagline: {curated['tagline']}\n"
            f"Source URL: {curated['selected_url']}\n"
            f"Source: {curated['source']}"
        )
        user_prompt = (
            f"SELECTED STORY:\n{selected_desc}\n\n"
            f"RECENTLY POSTED:\n{recent_block}\n\n"
            "Is the selected story a duplicate of any recent post?"
        )

        try:
            response = client.models.generate_content(
                model=GEMINI_TEXT_MODEL,
                contents=[
                    {"role": "user", "parts": [{"text": VALIDATION_PROMPT + "\n\n" + user_prompt}]},
                ],
            )
            tracker.record_generate_content(GEMINI_TEXT_MODEL, response)
            text = response.text.strip()
            if text.startswith("```"):
                text = text.split("\n", 1)[1]
                if text.endswith("```"):
                    text = text[:-3]
                text = text.strip()

            result = json.loads(text)

            if not result.get("is_duplicate", False):
                logger.info("Duplicate check passed: not a duplicate")
                return curated

            logger.warning(
                "Duplicate check FAILED (attempt %d/%d): %s",
                attempt + 1, max_attempts, result.get("reason", ""),
            )

            remaining = [c for c in remaining if c["url"] != curated["selected_url"]]
            if not remaining:
                logger.error("No candidates left after removing duplicates")
                return None

            curated = curate(remaining)
            if not curated:
                logger.error("Re-curation failed after removing duplicate")
                return None

        except (json.JSONDecodeError, KeyError) as e:
            logger.warning("Duplicate check parse error: %s (attempt %d)", e, attempt + 1)
            return curated
        except Exception:
            logger.exception("Duplicate check API error (attempt %d)", attempt + 1)
            return curated

    logger.error("Could not find fresh, non-duplicate story after %d attempts", max_attempts)
    return None
