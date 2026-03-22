import io
import logging
import os
import random
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

    # Bottom gradient (bottom 40%)
    gradient_start = int(IMAGE_SIZE[1] * 0.60)
    for y in range(gradient_start, IMAGE_SIZE[1]):
        progress = (y - gradient_start) / (IMAGE_SIZE[1] - gradient_start)
        alpha = int(progress * 230)
        draw.rectangle([(0, y), (IMAGE_SIZE[0], y + 1)], fill=(0, 0, 0, alpha))

    # Tagline — random position, avoiding watermark zone
    tagline_font = _load_font("BebasNeue-Regular.ttf", 80)
    tagline_upper = tagline.upper()

    # Word-wrap to max 3 lines
    wrapped = textwrap.fill(tagline_upper, width=20)
    lines = wrapped.split("\n")[:3]

    # Measure text block dimensions
    line_height = 85
    total_text_height = len(lines) * line_height
    max_line_w = max(
        draw.textbbox((0, 0), line, font=tagline_font)[2] - draw.textbbox((0, 0), line, font=tagline_font)[0]
        for line in lines
    )

    # Watermark exclusion zone (bottom-right corner)
    wm_zone_x = IMAGE_SIZE[0] - 250  # watermark starts around here
    wm_zone_y = IMAGE_SIZE[1] - 50   # watermark vertical area

    # Random position with padding, ensuring text stays in bounds
    pad = 40
    max_x = max(pad, IMAGE_SIZE[0] - max_line_w - pad)
    max_y = max(pad, IMAGE_SIZE[1] - total_text_height - pad)
    x_base = random.randint(pad, max_x)
    y_start = random.randint(pad, max_y)

    # If tagline block overlaps watermark zone, nudge it up or left
    tagline_bottom = y_start + total_text_height
    if tagline_bottom > wm_zone_y and x_base + max_line_w > wm_zone_x:
        # Try moving up first
        y_start = max(pad, wm_zone_y - total_text_height - pad)

    for line in lines:
        line_bbox = draw.textbbox((0, 0), line, font=tagline_font)
        line_w = line_bbox[2] - line_bbox[0]
        # Center each line relative to the block's x_base
        x_pos = x_base + (max_line_w - line_w) // 2
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
