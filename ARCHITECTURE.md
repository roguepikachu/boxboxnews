# Architecture

## Overview

BoxBoxNews is a pipeline-based system. Each run executes a linear sequence of stages, where each stage transforms or enriches data before passing it to the next. The pipeline is orchestrated by `src/main.py` and runs as a single Python process — no queues, workers, or databases.

## Pipeline Flow

```
RSS Feeds (8 sources)
    │
    ▼
┌──────────────┐
│  RSS Scraper │  Fetches articles, filters by recency (24h), extracts metadata
└──────┬───────┘
       │  candidates: list[dict]
       ▼
┌──────────────┐
│    Dedup     │  Removes exact matches (title hash, URL hash) and fuzzy matches
│   Filter     │  (keyword Jaccard >= 0.33 within 7-day window)
└──────┬───────┘
       │  filtered candidates
       ▼
┌──────────────┐
│   Gemini     │  Picks the single best rumor. Returns tagline, caption,
│   Curator    │  image prompt, entities, source attribution
└──────┬───────┘
       │  curated: dict
       ▼
┌──────────────┐
│   Gemini     │  Cross-checks against last 10 posts. If duplicate detected,
│  Validator   │  removes candidate and re-curates (up to 3 attempts)
└──────┬───────┘
       │  validated curated: dict
       ▼
┌──────────────┐
│   Record     │  Writes to posted_history.json BEFORE posting (closes race condition)
│    Post      │
└──────┬───────┘
       │
       ▼
┌──────────────┐
│   Reference  │  Searches Bing Images for entities (drivers, teams, objects).
│    Images    │  Downloads candidates, Gemini Flash picks the best per query.
└──────┬───────┘
       │  reference_images: list[bytes]
       ▼
┌──────────────┐
│    Image     │  Gemini image model (with references) → Gemini (prompt-only)
│  Generator   │  → Imagen 4 → Imagen 4 (generic fallback) → gradient
└──────┬───────┘
       │  image_bytes
       ▼
┌──────────────┐
│    Text      │  Bottom gradient, tagline at random position,
│   Overlay    │  @boxbox_news watermark bottom-right
└──────┬───────┘
       │  final_image: bytes
       ▼
┌──────────────┐
│  Cloudinary  │  Uploads PNG, returns CDN URL
│   Upload     │
└──────┬───────┘
       │  image_url: str
       ▼
┌──────────────┐
│  Instagram   │  Two-step Graph API: create container → publish
│   Poster     │
└──────────────┘
```

## Modules

### `src/main.py` — Orchestrator

Coordinates the pipeline. Contains no business logic itself — just calls each stage in sequence and handles exit conditions (no candidates, curation failure, upload failure, etc.).

### `src/config.py` — Configuration

Single source of truth for all environment variables, file paths, RSS feed URLs, image dimensions, and model names. All values are read from environment variables with sensible defaults. Model names (`GEMINI_TEXT_MODEL`, `GEMINI_IMAGE_MODEL`, `IMAGEN_MODEL`) can be swapped via GitHub repository variables without code changes.

### `src/rss_scraper.py` — RSS Ingestion

Fetches articles from 8 F1 news sources using `feedparser`. Filters articles to the last 24 hours, strips HTML from summaries, and returns a list of candidate dicts with title, summary, source, URL, timestamp, and a content hash.

### `src/dedup.py` — Duplicate Detection

Three-layer dedup system backed by a JSON history file (`data/posted_history.json`):

- **Layer 1: Exact title hash** — SHA256 of normalized title. Permanent, no expiry.
- **Layer 2: Exact URL hash** — SHA256 of source URL. Permanent, no expiry.
- **Layer 3: Keyword overlap** — Extracts F1 entity names (drivers, teams, personnel) from title + summary. Flags as duplicate if Jaccard similarity >= 0.33 with any post from the last 7 days.

The `record_post` function stores the story hash, URL hash, extracted keywords, tagline, title, summary, and date. Posts are recorded *before* Instagram publishing to prevent race conditions.

### `src/rumor_curator.py` — AI Curation

Two Gemini-powered functions:

**`curate()`** sends all candidates to Gemini Flash with a system prompt that prioritizes drama, specificity, source credibility, recency, and visual potential. Returns structured JSON: tagline, caption, image prompt, entities, and source. Retries up to 2 times on parse errors.

**`validate_not_duplicate()`** makes a separate Gemini call comparing the selected story against the last 10 posts. This catches semantic duplicates that keyword matching misses (e.g. "Wheatley leaves Audi" vs "Audi team boss departure confirmed"). If flagged, removes that candidate and re-curates from the remaining pool. Up to 3 attempts. Fails open on API errors.

### `src/reference_images.py` — Visual Reference Fetching

Builds search queries from the curated story's entities (e.g. "Lewis Hamilton F1 2025 portrait", "Ferrari F1 2025 car"). Scrapes Bing Images for full-resolution URLs, downloads up to 5 candidates per query, then sends all candidates to Gemini Flash for ranking.

Gemini evaluates each image for:
- Subject accuracy (correct driver/team)
- Resolution and sharpness
- Cinematic quality (action shots preferred)
- Clean composition (rejects watermarks, collages, text overlays)

Returns up to 2 best reference images.

### `src/image_generator.py` — AI Image Generation

Four-level fallback chain:

1. **Gemini image model + references** — Sends reference photos and prompt to Nano Banana Pro (or configured model). The model sees what the actual people and cars look like and generates a contextually accurate cinematic image.
2. **Gemini image model, prompt-only** — Same model without references.
3. **Imagen 4** — Google's dedicated image generation model, prompt-only.
4. **Imagen 4 with generic prompt** — Last-resort F1 image generation.

If all four fail, a gradient fallback is generated locally with Pillow.

### `src/text_overlay.py` — Image Compositing

Uses Pillow to composite the final Instagram post:
- Resizes image to 1080x1080
- Adds a bottom gradient overlay (60%–100% of image height, alpha 0→230)
- Renders the tagline in BebasNeue-Regular at size 80, randomly positioned to keep the layout fresh across posts — avoids overlapping the watermark zone
- Drop shadow effect (3px offset)
- `@boxbox_news` watermark in Oswald-Bold at bottom-right

### `src/image_uploader.py` — CDN Upload

Uploads the final PNG to Cloudinary. Parses the `CLOUDINARY_URL` environment variable for credentials. Returns a public HTTPS URL that Instagram can fetch.

### `src/instagram_poster.py` — Instagram Publishing

Two-step Graph API flow:
1. **Create media container** — POST image URL + caption to `/v21.0/{account_id}/media`
2. **Publish** — POST container ID to `/v21.0/{account_id}/media_publish`

Includes a 5-second wait between steps (Instagram requires processing time) and exponential backoff on rate limits.

## Data Flow

```
Input:   RSS XML feeds (8 sources, public internet)
                ↓
Process: Python pipeline (single process, ~30-60 seconds)
                ↓
State:   data/posted_history.json (committed to git after each run)
                ↓
Output:  Instagram post (image + caption)
```

### Candidate Dict Shape

```python
{
    "title": "Hamilton reportedly joining Ferrari next season",
    "summary": "According to sources close to the team...",
    "source": "autosport",
    "url": "https://autosport.com/...",
    "timestamp": "2026-03-22T08:30:00",
    "score": 3,
    "raw_id": "sha256hex..."
}
```

### Curated Dict Shape

```python
{
    "selected_url": "https://autosport.com/...",
    "tagline": "HAMILTON TO FERRARI CONFIRMED",
    "caption": "Instagram caption with hashtags...",
    "image_prompt": "Cinematic F1 scene description...",
    "entities": {
        "drivers": ["Lewis Hamilton"],
        "teams": ["Ferrari"],
        "objects": ["SF-26"]
    },
    "source": "autosport"
}
```

### Post History Entry Shape

```python
{
    "hash": "sha256hex...",
    "url_hash": "sha256hex...",
    "tagline": "HAMILTON TO FERRARI CONFIRMED",
    "title": "Hamilton reportedly joining Ferrari next season",
    "summary": "According to sources close to the team...",
    "source": "autosport",
    "date": "2026-03-22",
    "url": "https://autosport.com/...",
    "keywords": ["hamilton", "ferrari"]
}
```

## External Dependencies

| Service | Used By | Auth | Purpose |
|---------|---------|------|---------|
| Google Gemini API | rumor_curator, reference_images, image_generator | API key | Text curation, validation, image ranking, image generation |
| Bing Images | reference_images | None (User-Agent header) | Reference photo search |
| Cloudinary | image_uploader | URL-encoded credentials | Image CDN |
| Instagram Graph API | instagram_poster | Access token | Post publishing |
| 8 RSS feeds | rss_scraper | None (public) | News ingestion |

## Deployment

Runs on GitHub Actions (Ubuntu runner). No server, no database, no container.

- **Schedule**: `0 9 */4 * *` (every 4 days at 9 AM UTC)
- **State**: `data/posted_history.json` committed back to the repo after each run
- **Secrets**: Stored in GitHub repository secrets
- **Model config**: Stored in GitHub repository variables (swappable without code changes)
- **Token refresh**: Separate workflow runs every 50 days

## Error Handling Strategy

- **Gemini failures**: Retry with backoff (2-3 attempts). Curation failure = no post today.
- **Image generation failures**: Four-level fallback chain. Total failure = gradient background.
- **Reference image failures**: Returns empty list — pipeline continues without references.
- **Instagram failures**: Retry with exponential backoff (3 attempts). Failure = exit with error.
- **Duplicate validation failures**: Fails open — on API error, allows the story through.
- **Race conditions**: Post recorded to history before Instagram publish, not after.
