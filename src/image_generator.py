import logging
import os

from google import genai
from google.genai import types

from src.config import GEMINI_API_KEY, OUTPUT_DIR, GEMINI_IMAGE_MODEL, IMAGEN_MODEL

logger = logging.getLogger(__name__)

GENERIC_FALLBACK_PROMPT = (
    "Cinematic close-up of a Formula 1 car on track at twilight. "
    "Dramatic lighting, motion blur background, sparks flying from the floor. "
    "Editorial photography style. 1:1 square composition. "
    "Bottom 40% should be dark shadowed empty space. "
    "The image must contain absolutely no text, no words, no letters, "
    "no numbers, no logos, no watermarks, no labels. Pure photograph only."
)

# Appended to every prompt to reinforce no-text rule
NO_TEXT_SUFFIX = (
    " IMPORTANT: Generate a purely photographic image with absolutely no text, "
    "no words, no letters, no numbers, no logos, no watermarks, no labels, "
    "no overlays anywhere in the image. The image must be completely clean."
)



def _detect_mime(data: bytes) -> str:
    """Detect image MIME type from magic bytes."""
    if data[:4] == b"\x89PNG":
        return "image/png"
    if data[:4] == b"RIFF":
        return "image/webp"
    return "image/jpeg"


def _generate_with_gemini(
    client: genai.Client, prompt: str, reference_images: list[bytes] | None = None,
) -> bytes | None:
    """Generate an image using Gemini image model (Nano Banana Pro).

    Works with or without reference images.
    """
    parts = []

    if reference_images:
        parts.append(types.Part.from_text(
            "Use the following reference photos to understand what the people, "
            "cars, and teams look like. Generate a NEW cinematic image (not a copy) "
            "inspired by these references that matches the prompt below. "
            "The output must be a single 1:1 square image."
        ))
        for i, ref in enumerate(reference_images):
            parts.append(types.Part.from_bytes(data=ref, mime_type=_detect_mime(ref)))
            logger.info("Attached reference image %d (%d bytes)", i + 1, len(ref))

    parts.append(types.Part.from_text(prompt))

    response = client.models.generate_content(
        model=GEMINI_IMAGE_MODEL,
        contents=[types.Content(parts=parts, role="user")],
        config=types.GenerateContentConfig(
            response_modalities=["IMAGE", "TEXT"],
        ),
    )

    # Extract the generated image from the response parts
    for part in response.candidates[0].content.parts:
        if part.inline_data and part.inline_data.mime_type.startswith("image/"):
            return part.inline_data.data

    logger.warning("Gemini returned no image in response")
    return None


def _generate_with_imagen(client: genai.Client, prompt: str) -> bytes | None:
    """Generate an image using Imagen 4 (prompt-only fallback)."""
    response = client.models.generate_images(
        model=IMAGEN_MODEL,
        prompt=prompt,
        config=types.GenerateImagesConfig(
            number_of_images=1,
            aspect_ratio="1:1",
        ),
    )
    return response.generated_images[0].image.image_bytes


def generate_image(
    image_prompt: str, reference_images: list[bytes] | None = None,
) -> bytes | None:
    """Generate a 1:1 image using Nano Banana Pro (primary) with Imagen fallback.

    Strategy:
    1. Gemini image model with reference images (if available)
    2. Gemini image model prompt-only (no references)
    3. Imagen 4 with the original prompt
    4. Imagen 4 with a generic F1 prompt
    """
    client = genai.Client(api_key=GEMINI_API_KEY)
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    prompt_with_suffix = image_prompt + NO_TEXT_SUFFIX

    attempts: list[tuple[str, callable]] = []
    if reference_images:
        attempts.append((
            f"{GEMINI_IMAGE_MODEL} with references",
            lambda: _generate_with_gemini(client, prompt_with_suffix, reference_images),
        ))
    attempts.append((
        f"{GEMINI_IMAGE_MODEL} prompt-only",
        lambda: _generate_with_gemini(client, prompt_with_suffix),
    ))
    attempts.append((
        f"{IMAGEN_MODEL}",
        lambda: _generate_with_imagen(client, prompt_with_suffix),
    ))
    attempts.append((
        f"{IMAGEN_MODEL} fallback",
        lambda: _generate_with_imagen(client, GENERIC_FALLBACK_PROMPT),
    ))

    for i, (label, gen_fn) in enumerate(attempts):
        try:
            logger.info("Generating image via %s (attempt %d/%d)...", label, i + 1, len(attempts))
            image_bytes = gen_fn()
            if image_bytes:
                debug_path = os.path.join(OUTPUT_DIR, "generated_image.png")
                with open(debug_path, "wb") as f:
                    f.write(image_bytes)
                logger.info("Image generated via %s (%d bytes)", label, len(image_bytes))
                return image_bytes
        except Exception:
            logger.exception("Image generation failed via %s (attempt %d/%d)", label, i + 1, len(attempts))

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
