import io
import logging
from urllib.parse import urlparse

import cloudinary
import cloudinary.uploader

from src.config import CLOUDINARY_URL

logger = logging.getLogger(__name__)


def _configure():
    """Parse CLOUDINARY_URL and configure the client."""
    parsed = urlparse(CLOUDINARY_URL)
    cloudinary.config(
        cloud_name=parsed.hostname,
        api_key=parsed.username,
        api_secret=parsed.password,
    )


def upload_image(image_bytes: bytes) -> str | None:
    """Upload image to Cloudinary and return the public URL."""
    _configure()

    for attempt in range(2):
        try:
            result = cloudinary.uploader.upload(
                io.BytesIO(image_bytes),
                folder="boxboxnews",
                resource_type="image",
            )
            url = result["secure_url"]
            logger.info("Uploaded to Cloudinary: %s", url)
            return url
        except Exception:
            logger.exception("Cloudinary upload failed (attempt %d)", attempt + 1)

    return None
