import logging
import sys

from src.rss_scraper import scrape_rss
from src.dedup import already_posted_today, filter_duplicates, record_post
from src.rumor_curator import curate, validate_not_duplicate
from src.image_generator import generate_image, create_gradient_fallback
from src.text_overlay import composite
from src.image_uploader import upload_image
from src.instagram_poster import post_to_instagram

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def run() -> None:
    # 0. Check if already posted today
    if already_posted_today():
        logger.info("Already posted today. Skipping.")
        sys.exit(0)

    # 1. Scrape RSS feeds
    try:
        candidates = scrape_rss()
    except Exception:
        logger.exception("RSS scraping failed. No post today.")
        sys.exit(1)

    if not candidates:
        logger.error("No articles found. No post today.")
        sys.exit(0)

    # 2. Deduplicate
    candidates = filter_duplicates(candidates)
    if not candidates:
        logger.info("No fresh content after dedup. Skipping post.")
        sys.exit(0)

    # 3. Curate
    curated = curate(candidates)
    if not curated:
        logger.error("Curation failed. No post today.")
        sys.exit(1)

    # 4. Validate not a duplicate via Gemini
    curated = validate_not_duplicate(curated, candidates)
    if not curated:
        logger.error("All candidates flagged as duplicates. No post today.")
        sys.exit(0)

    # 5. Record for dedup BEFORE posting — closes race condition
    original_title = ""
    original_summary = ""
    for c in candidates:
        if c["url"] == curated["selected_url"]:
            original_title = c["title"]
            original_summary = c.get("summary", "")
            break

    record_post(
        tagline=curated["tagline"],
        source=curated["source"],
        url=curated["selected_url"],
        title=original_title,
        summary=original_summary,
    )

    # 6. Generate image
    image_bytes = generate_image(curated["image_prompt"])
    if image_bytes is None:
        logger.warning("Using gradient fallback for image")
        image_bytes = create_gradient_fallback()

    # 7. Text overlay
    final_image = composite(image_bytes, curated["tagline"])

    # 8. Upload to Cloudinary
    image_url = upload_image(final_image)
    if not image_url:
        logger.error("Image upload failed. No post today.")
        sys.exit(1)

    # 9. Post to Instagram
    media_id = post_to_instagram(image_url, curated["caption"])
    if not media_id:
        logger.error("Instagram posting failed.")
        sys.exit(1)

    logger.info("Pipeline complete! Media ID: %s", media_id)


if __name__ == "__main__":
    run()
