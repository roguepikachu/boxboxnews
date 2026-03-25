import logging
import sys

from src.rss_scraper import scrape_rss
from src.dedup import filter_duplicates, record_post
from src.rumor_curator import curate, validate_not_duplicate
from src.image_generator import generate_image, create_gradient_fallback
from src.reference_images import fetch_reference_images
from src.text_overlay import composite
from src.image_uploader import upload_image
from src.instagram_poster import post_to_instagram, preflight_check
from src.cost_tracker import tracker

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def run() -> None:
    # 0. Preflight: verify Instagram credentials before spending API credits
    if not preflight_check():
        logger.error("Instagram preflight failed. Fix credentials before running pipeline.")
        sys.exit(1)

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

    # 6. Fetch reference images from Google for relevant visuals
    reference_images = fetch_reference_images(curated.get("entities", {}))

    # 7. Generate image using references for context
    image_bytes = generate_image(curated["image_prompt"], reference_images=reference_images)
    if image_bytes is None:
        logger.warning("Using gradient fallback for image")
        image_bytes = create_gradient_fallback()

    # 8. Text overlay
    final_image = composite(image_bytes, curated["tagline"])

    # 9. Upload to Cloudinary
    image_url = upload_image(final_image)
    if not image_url:
        logger.error("Image upload failed. No post today.")
        sys.exit(1)

    # 10. Post to Instagram
    media_id = post_to_instagram(image_url, curated["caption"])
    if not media_id:
        logger.error("Instagram posting failed.")
        sys.exit(1)

    logger.info("Pipeline complete! Media ID: %s", media_id)

    # Print cost summary
    print("\n" + tracker.summary())


if __name__ == "__main__":
    run()
