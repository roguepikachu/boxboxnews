import json
import logging

from google import genai

from src.config import GEMINI_API_KEY

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are the editorial brain behind @BoxBoxNews, a viral F1 rumors Instagram page
with a sports broadcast aesthetic.

You will receive a pool of F1 news items from multiple sources (Reddit, PlanetF1,
RacingNews365, Autosport, Motorsport.com). Pick the ONE most scroll-stopping
rumor that would make the best Instagram post.

Selection criteria (ranked):
1. Drama level — transfers, conflicts, surprise retirements, regulation drama
2. Specificity — concrete claims beat vague speculation
3. Source credibility — Autosport/Motorsport.com > PlanetF1 > Reddit
4. Recency — prefer last 12 hours
5. Visual potential — stories involving specific teams/cars generate better images

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
        lines.append(
            f"{i}. [{c['source'].upper()}] {c['title']}\n"
            f"   Summary: {c['summary'][:200]}\n"
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

    client = genai.Client(api_key=GEMINI_API_KEY)
    avoid_topics = _get_recent_topics()
    user_prompt = (
        f"Here are {len(candidates)} F1 news candidates from today:\n\n"
        f"{_format_candidates(candidates)}\n\n"
        f"{avoid_topics}\n\n"
        "Pick the ONE best rumor and return the JSON."
    )

    for attempt in range(max_retries + 1):
        try:
            response = client.models.generate_content(
                model="gemini-flash-latest",
                contents=[
                    {"role": "user", "parts": [{"text": SYSTEM_PROMPT + "\n\n" + user_prompt}]},
                ],
            )
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
