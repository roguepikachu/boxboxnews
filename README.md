# BoxBoxNews

An automated Formula 1 rumors Instagram bot. It scrapes F1 news from 8 RSS feeds, uses Google Gemini to pick the most scroll-stopping rumor, generates a cinematic image using AI with real reference photos, composites a text overlay, and posts to Instagram — all on autopilot via GitHub Actions.

Follow the page: **[@boxbox_news](https://instagram.com/boxbox_news)**

## How It Works

Every 4 days the pipeline runs automatically:

1. **Scrape** — Pulls the latest articles from 8 F1 RSS feeds (Autosport, Motorsport.com, The Race, PlanetF1, RacingNews365, RaceFans, GPblog, Formula1.com). Only articles from the last 24 hours are kept.

2. **Deduplicate** — Filters out stories that have already been posted. Uses three layers: exact title hash, exact URL hash, and fuzzy keyword matching (Jaccard similarity >= 0.33 within a 7-day window). Keywords are extracted from titles and summaries against a list of ~40 F1 entities (drivers, teams, key personnel).

3. **Curate** — Sends all remaining candidates to Gemini Flash, which picks the single best rumor based on drama level, specificity, source credibility, recency, and visual potential. Returns a tagline, caption, image prompt, and entity list.

4. **Validate** — A separate Gemini call cross-checks the selected story against the last 10 posts to catch duplicates the keyword filter might miss. If flagged, the candidate is removed and Gemini re-curates from the remaining pool (up to 3 attempts).

5. **Record** — The story is written to the dedup history file *before* posting to Instagram, closing the race condition where a crash after posting would leave no record.

6. **Reference Images** — Searches Bing Images for photos of the drivers, teams, and objects mentioned in the story. Downloads up to 5 candidates per search query, then sends them all to Gemini Flash which picks the best one based on subject accuracy, resolution, cinematic quality, and clean composition (no watermarks or collages).

7. **Generate Image** — Passes the reference photos + image prompt to the Gemini image model (Nano Banana Pro) for contextually accurate generation. Falls back through Imagen 4 if needed. Last resort is a gradient background.

8. **Text Overlay** — Composites the tagline onto the image at a random position (avoiding the watermark zone) with a bottom gradient, drop shadow, and `@boxbox_news` watermark using Pillow.

9. **Upload** — Pushes the final image to Cloudinary CDN.

10. **Post** — Publishes to Instagram via the Graph API with the AI-generated caption and hashtags.

## Prerequisites

- **Python 3.12+**
- **Google Cloud account** with Gemini API access (for text curation, image ranking, and image generation)
- **Instagram Business Account** connected to a Facebook Page
- **Facebook Developer App** (for Graph API token exchange)
- **Cloudinary account** (free tier works fine)

## Setup

### 1. Clone and install

```bash
git clone https://github.com/roguepikachu/boxboxnews.git
cd boxboxnews
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure environment variables

Copy the example and fill in your credentials:

```bash
cp .env.example .env
```

| Variable | Description |
|----------|-------------|
| `GEMINI_API_KEY` | Google AI Studio API key |
| `INSTAGRAM_ACCESS_TOKEN` | Long-lived Instagram Graph API token (60-day expiry) |
| `INSTAGRAM_ACCOUNT_ID` | Instagram Business Account ID |
| `CLOUDINARY_URL` | Cloudinary URL in the format `cloudinary://api_key:api_secret@cloud_name` |

### 3. Get Instagram credentials

If you don't have a long-lived token yet:

```bash
# Fill in FB_APP_ID, FB_APP_SECRET, FB_SHORT_TOKEN in .env first
python setup_instagram.py
```

This exchanges a short-lived Facebook token for a 60-day Instagram Graph API token and prints your Account ID.

### 4. Run locally

```bash
python -m src.main
```

### 5. Run tests

```bash
python -m pytest tests/ -v
```

## GitHub Actions

The pipeline is configured to run automatically via two workflows:

**Daily Post** (`daily-post.yml`) — Runs every 4 days at 9 AM UTC. Can also be triggered manually from the Actions tab or via:

```bash
./post_now.sh
```

**Token Refresh** (`refresh-token.yml`) — Runs every 50 days to refresh the Instagram access token before it expires (60-day lifetime).

### Required Secrets

Set these in your GitHub repo under Settings > Secrets and variables > Actions > Secrets:

- `GEMINI_API_KEY`
- `INSTAGRAM_ACCESS_TOKEN`
- `INSTAGRAM_ACCOUNT_ID`
- `CLOUDINARY_URL`

### Optional Variables

Set these under Settings > Secrets and variables > Actions > Variables to switch AI models without code changes:

| Variable | Default | Description |
|----------|---------|-------------|
| `GEMINI_TEXT_MODEL` | `gemini-2.5-flash` | Model for curation, validation, and image ranking |
| `GEMINI_IMAGE_MODEL` | `gemini-3-pro-image-generation` | Primary image generation model (Nano Banana Pro) |
| `IMAGEN_MODEL` | `imagen-4.0-generate-001` | Fallback image generation model |

## Token Management

Instagram tokens expire every 60 days. Two options to refresh:

**Automated** — The `refresh-token.yml` workflow runs every 50 days and prints the new token. You'll need to manually update the GitHub secret.

**Manual** — Run the rotate script locally:

```bash
./rotate_token.sh
```

This refreshes the token, updates the GitHub secret, and patches your local `.env`.

## External Services

| Service | Purpose | Cost |
|---------|---------|------|
| Google Gemini API | Story curation, duplicate validation, reference image ranking, image generation | Free tier available |
| Cloudinary | Image CDN hosting | Free tier (25 credits/month) |
| Instagram Graph API | Post publishing | Free |
| Bing Images | Reference photo search | Free (web scraping) |
| RSS Feeds | F1 news aggregation | Free (public feeds) |
