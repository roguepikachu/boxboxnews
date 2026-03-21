import io
import logging
import os
import textwrap

from PIL import Image, ImageDraw, ImageFont

from src.config import FONTS_DIR, OUTPUT_DIR, IMAGE_SIZE, F1_RED

logger = logging.getLogger(__name__)


def _load_font(name: str, size: int) -> ImageFont.FreeTypeFont:
    path = os.path.join(FONTS_DIR, name)
    if os.path.exists(path):
        return ImageFont.truetype(path, size)
    logger.warning("Font %s not found, using default", name)
    return ImageFont.load_default()


def composite(image_bytes: bytes, tagline: str) -> bytes:
    """Add text overlay to the generated image."""
    img = Image.open(io.BytesIO(image_bytes)).convert("RGBA")
    img = img.resize(IMAGE_SIZE, Image.LANCZOS)

    overlay = Image.new("RGBA", IMAGE_SIZE, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    # Bottom gradient (bottom 35%)
    gradient_start = int(IMAGE_SIZE[1] * 0.65)
    for y in range(gradient_start, IMAGE_SIZE[1]):
        progress = (y - gradient_start) / (IMAGE_SIZE[1] - gradient_start)
        alpha = int(progress * 220)
        draw.rectangle([(0, y), (IMAGE_SIZE[0], y + 1)], fill=(0, 0, 0, alpha))

    # "RUMOR" badge — top left
    badge_font = _load_font("BebasNeue-Regular.ttf", 28)
    badge_text = "\U0001f3c1 RUMOR"
    badge_bbox = draw.textbbox((0, 0), badge_text, font=badge_font)
    badge_w = badge_bbox[2] - badge_bbox[0] + 24
    badge_h = badge_bbox[3] - badge_bbox[1] + 12
    draw.rounded_rectangle(
        [(20, 20), (20 + badge_w, 20 + badge_h)],
        radius=6,
        fill=F1_RED,
    )
    draw.text((32, 22), badge_text, fill="white", font=badge_font)

    # Tagline — bottom area
    tagline_font = _load_font("BebasNeue-Regular.ttf", 76)
    tagline_upper = tagline.upper()

    # Word-wrap to max 2 lines
    wrapped = textwrap.fill(tagline_upper, width=18)
    lines = wrapped.split("\n")[:2]

    # Draw with drop shadow
    y_pos = IMAGE_SIZE[1] - 160
    for line in lines:
        # Shadow
        draw.text((42, y_pos + 2), line, fill=(0, 0, 0, 180), font=tagline_font)
        # Main text
        draw.text((40, y_pos), line, fill="white", font=tagline_font)
        y_pos += 80

    # @boxboxnews watermark — bottom right
    watermark_font = _load_font("Oswald-Bold.ttf", 22)
    wm_text = "@boxboxnews"
    wm_bbox = draw.textbbox((0, 0), wm_text, font=watermark_font)
    wm_w = wm_bbox[2] - wm_bbox[0]
    draw.text(
        (IMAGE_SIZE[0] - wm_w - 30, IMAGE_SIZE[1] - 40),
        wm_text,
        fill=(255, 255, 255, 160),
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
