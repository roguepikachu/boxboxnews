import io
import json
import logging
import os
import random
import textwrap

from PIL import Image, ImageDraw, ImageFont
from google import genai
from google.genai import types

from src.config import FONTS_DIR, OUTPUT_DIR, IMAGE_SIZE, F1_RED, GEMINI_API_KEY, GEMINI_TEXT_MODEL

logger = logging.getLogger(__name__)


def _load_font(name: str, size: int) -> ImageFont.FreeTypeFont:
    path = os.path.join(FONTS_DIR, name)
    if os.path.exists(path):
        return ImageFont.truetype(path, size)
    logger.warning("Font %s not found, using default", name)
    return ImageFont.load_default()


def _ask_gemini_placement(image_bytes: bytes, tagline: str, text_w: int, text_h: int) -> dict | None:
    """Ask Gemini to analyze the image and recommend text placement.

    Returns {"x": int, "y": int, "alignment": "left"|"center"|"right"} or None.
    """
    try:
        client = genai.Client(api_key=GEMINI_API_KEY)

        # Detect mime
        mime = "image/jpeg"
        if image_bytes[:4] == b"\x89PNG":
            mime = "image/png"
        elif image_bytes[:4] == b"RIFF":
            mime = "image/webp"

        prompt = (
            f"This is a {IMAGE_SIZE[0]}x{IMAGE_SIZE[1]} image for an F1 Instagram post. "
            f"I need to place the tagline \"{tagline}\" on it.\n"
            f"The text block is approximately {text_w}px wide and {text_h}px tall.\n"
            f"The @boxbox_news watermark occupies the bottom-right corner "
            f"(roughly x>830, y>1045).\n\n"
            "Analyze the image and find the BEST position for the tagline where:\n"
            "1. Text will be readable (place over darker, less busy areas)\n"
            "2. Text does NOT cover the main subject (face, car, key action)\n"
            "3. Text does NOT overlap the bottom-right watermark zone\n"
            "4. Prefer areas with natural contrast (shadows, sky, dark backgrounds)\n\n"
            f"The x,y coordinates are for the top-left corner of the text block. "
            f"Valid ranges: x: 30-{IMAGE_SIZE[0] - text_w - 30}, "
            f"y: 30-{IMAGE_SIZE[1] - text_h - 50}.\n\n"
            "Return ONLY valid JSON:\n"
            "{\"x\": <int>, \"y\": <int>, \"alignment\": \"left\" or \"center\" or \"right\", "
            "\"reason\": \"brief explanation\"}"
        )

        response = client.models.generate_content(
            model=GEMINI_TEXT_MODEL,
            contents=[types.Content(parts=[
                types.Part.from_bytes(data=image_bytes, mime_type=mime),
                types.Part.from_text(text=prompt),
            ], role="user")],
        )

        text = response.text.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1]
            if text.endswith("```"):
                text = text[:-3]
            text = text.strip()

        result = json.loads(text)
        x = int(result["x"])
        y = int(result["y"])
        alignment = result.get("alignment", "left")
        reason = result.get("reason", "")

        # Clamp to valid bounds
        x = max(30, min(x, IMAGE_SIZE[0] - text_w - 30))
        y = max(30, min(y, IMAGE_SIZE[1] - text_h - 50))

        logger.info("Gemini text placement: (%d, %d) align=%s — %s", x, y, alignment, reason)
        return {"x": x, "y": y, "alignment": alignment}

    except Exception:
        logger.exception("Gemini text placement failed, using random fallback")
        return None


def _random_placement(text_w: int, text_h: int) -> dict:
    """Fallback random placement avoiding the watermark zone."""
    pad = 40
    wm_zone_x = IMAGE_SIZE[0] - 250
    wm_zone_y = IMAGE_SIZE[1] - 50

    max_x = max(pad, IMAGE_SIZE[0] - text_w - pad)
    max_y = max(pad, IMAGE_SIZE[1] - text_h - pad)
    x = random.randint(pad, max_x)
    y = random.randint(pad, max_y)

    # Nudge if overlapping watermark
    if y + text_h > wm_zone_y and x + text_w > wm_zone_x:
        y = max(pad, wm_zone_y - text_h - pad)

    return {"x": x, "y": y, "alignment": "left"}


def composite(image_bytes: bytes, tagline: str) -> bytes:
    """Add text overlay to the generated image."""
    img = Image.open(io.BytesIO(image_bytes)).convert("RGBA")
    img = img.resize(IMAGE_SIZE, Image.LANCZOS)

    overlay = Image.new("RGBA", IMAGE_SIZE, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    # Tagline setup
    tagline_font = _load_font("BebasNeue-Regular.ttf", 80)
    tagline_upper = tagline.upper()

    wrapped = textwrap.fill(tagline_upper, width=20)
    lines = wrapped.split("\n")[:3]

    line_height = 85
    total_text_height = len(lines) * line_height
    max_line_w = max(
        draw.textbbox((0, 0), line, font=tagline_font)[2] - draw.textbbox((0, 0), line, font=tagline_font)[0]
        for line in lines
    )

    # Ask Gemini where to place the text
    placement = _ask_gemini_placement(image_bytes, tagline_upper, max_line_w, total_text_height)
    if placement is None:
        placement = _random_placement(max_line_w, total_text_height)

    x_base = placement["x"]
    y_start = placement["y"]
    alignment = placement.get("alignment", "left")

    # Draw a subtle local gradient behind the text for readability
    grad_pad = 20
    grad_x1 = max(0, x_base - grad_pad)
    grad_y1 = max(0, y_start - grad_pad)
    grad_x2 = min(IMAGE_SIZE[0], x_base + max_line_w + grad_pad)
    grad_y2 = min(IMAGE_SIZE[1], y_start + total_text_height + grad_pad)
    for y in range(grad_y1, grad_y2):
        # Fade in from edges, max alpha 140 at center
        vert_progress = 1.0 - abs(y - (grad_y1 + grad_y2) / 2) / ((grad_y2 - grad_y1) / 2)
        alpha = int(vert_progress * 140)
        draw.rectangle([(grad_x1, y), (grad_x2, y + 1)], fill=(0, 0, 0, alpha))

    # Render tagline lines
    for line in lines:
        line_bbox = draw.textbbox((0, 0), line, font=tagline_font)
        line_w = line_bbox[2] - line_bbox[0]

        if alignment == "center":
            x_pos = x_base + (max_line_w - line_w) // 2
        elif alignment == "right":
            x_pos = x_base + max_line_w - line_w
        else:
            x_pos = x_base

        # Shadow
        draw.text((x_pos + 3, y_start + 3), line, fill=(0, 0, 0, 200), font=tagline_font)
        # Main text
        draw.text((x_pos, y_start), line, fill="white", font=tagline_font)
        y_start += line_height

    # @boxbox_news watermark — bottom right
    watermark_font = _load_font("Oswald-Bold.ttf", 20)
    wm_text = "@boxbox_news"
    wm_bbox = draw.textbbox((0, 0), wm_text, font=watermark_font)
    wm_w = wm_bbox[2] - wm_bbox[0]
    draw.text(
        (IMAGE_SIZE[0] - wm_w - 30, IMAGE_SIZE[1] - 35),
        wm_text,
        fill=(255, 255, 255, 140),
        font=watermark_font,
    )

    # Composite
    result = Image.alpha_composite(img, overlay).convert("RGB")

    # Save debug copy
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    debug_path = os.path.join(OUTPUT_DIR, "final_post.png")
    result.save(debug_path)
    logger.info("Composite saved to %s", debug_path)

    buf = io.BytesIO()
    result.save(buf, format="PNG")
    return buf.getvalue()
