import logging
import os

from google import genai
from google.genai import types

from src.config import GEMINI_API_KEY, OUTPUT_DIR

logger = logging.getLogger(__name__)

GENERIC_FALLBACK_PROMPT = (
    "Cinematic close-up of a Formula 1 car on track at twilight. "
    "Dramatic lighting, motion blur background, sparks flying from the floor. "
    "Editorial photography style. 1:1 square composition. "
    "Bottom 30% darker/shadowed area for text overlay. "
    "Do NOT include any text or words in the image."
)


def generate_image(image_prompt: str) -> bytes | None:
    """Generate a 1:1 image using Imagen 4 Generate. Returns PNG bytes or None."""
    client = genai.Client(api_key=GEMINI_API_KEY)
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    prompts = [image_prompt, GENERIC_FALLBACK_PROMPT]

    for attempt, prompt in enumerate(prompts):
        try:
            logger.info("Generating image (attempt %d)...", attempt + 1)
            response = client.models.generate_images(
                model="imagen-4.0-generate-001",
                prompt=prompt,
                config=types.GenerateImagesConfig(
                    number_of_images=1,
                    aspect_ratio="1:1",
                ),
            )
            image_bytes = response.generated_images[0].image.image_bytes
            # Save debug copy
            debug_path = os.path.join(OUTPUT_DIR, "generated_image.png")
            with open(debug_path, "wb") as f:
                f.write(image_bytes)
            logger.info("Image generated successfully (%d bytes)", len(image_bytes))
            return image_bytes

        except Exception:
            logger.exception("Image generation failed (attempt %d)", attempt + 1)

    logger.error("All image generation attempts failed")
    return None


def create_gradient_fallback() -> bytes:
    """Create a simple gradient background as last-resort fallback."""
    from PIL import Image, ImageDraw

    img = Image.new("RGB", (1080, 1080), (20, 20, 30))
    draw = ImageDraw.Draw(img)

    # Dark gradient at bottom
    for y in range(700, 1080):
        alpha = int((y - 700) / 380 * 200)
        draw.rectangle([(0, y), (1080, y + 1)], fill=(10, 10, 15))

    import io
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()
