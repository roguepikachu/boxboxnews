import logging
import time

import requests

from src.config import INSTAGRAM_ACCESS_TOKEN, INSTAGRAM_ACCOUNT_ID

logger = logging.getLogger(__name__)

GRAPH_API_BASE = "https://graph.facebook.com/v21.0"


def post_to_instagram(image_url: str, caption: str, max_retries: int = 3) -> str | None:
    """Post an image to Instagram via Graph API. Returns the media ID."""
    for attempt in range(max_retries):
        try:
            # Step 1: Create media container
            container_resp = requests.post(
                f"{GRAPH_API_BASE}/{INSTAGRAM_ACCOUNT_ID}/media",
                data={
                    "image_url": image_url,
                    "caption": caption,
                    "access_token": INSTAGRAM_ACCESS_TOKEN,
                },
                timeout=30,
            )
            container_resp.raise_for_status()
            container_id = container_resp.json()["id"]
            logger.info("Created container: %s", container_id)

            # Wait for processing
            time.sleep(5)

            # Step 2: Publish
            publish_resp = requests.post(
                f"{GRAPH_API_BASE}/{INSTAGRAM_ACCOUNT_ID}/media_publish",
                data={
                    "creation_id": container_id,
                    "access_token": INSTAGRAM_ACCESS_TOKEN,
                },
                timeout=30,
            )
            publish_resp.raise_for_status()
            media_id = publish_resp.json()["id"]
            logger.info("Published! Media ID: %s", media_id)
            return media_id

        except requests.exceptions.HTTPError as e:
            status = e.response.status_code if e.response is not None else 0
            body = e.response.text if e.response is not None else ""
            if status == 429:
                wait = 2 ** (attempt + 1) * 10
                logger.warning("Rate limited, waiting %ds (attempt %d)", wait, attempt + 1)
                time.sleep(wait)
            else:
                logger.error("Instagram API error (attempt %d): %s %s", attempt + 1, status, body)
                break
        except Exception:
            logger.exception("Instagram post failed (attempt %d)", attempt + 1)
            break

    logger.error("Failed to post to Instagram after %d attempts", max_retries)
    return None
