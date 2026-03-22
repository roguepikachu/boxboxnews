import os
from dotenv import load_dotenv

load_dotenv()

# Gemini
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")

# Instagram Graph API
INSTAGRAM_ACCESS_TOKEN = os.environ.get("INSTAGRAM_ACCESS_TOKEN", "")
INSTAGRAM_ACCOUNT_ID = os.environ.get("INSTAGRAM_ACCOUNT_ID", "")

# Cloudinary
CLOUDINARY_URL = os.environ.get("CLOUDINARY_URL", "")

# RSS Feeds — breaking F1 news sources, no general sports sites
RSS_FEEDS = {
    "autosport": {
        "url": "https://www.autosport.com/rss/feed/f1",
        "name": "Autosport",
    },
    "motorsport": {
        "url": "https://www.motorsport.com/rss/f1/news/",
        "name": "Motorsport.com",
    },
    "therace": {
        "url": "https://www.the-race.com/feed/",
        "name": "The Race",
    },
    "bbc_f1": {
        "url": "https://feeds.bbci.co.uk/sport/formula1/rss.xml",
        "name": "BBC F1",
    },
    "crash_f1": {
        "url": "https://www.crash.net/rss/f1",
        "name": "Crash.net F1",
    },
    "gpfans": {
        "url": "https://www.gpfans.com/en/rss.xml",
        "name": "GPFans",
    },
    "formula1_official": {
        "url": "https://www.formula1.com/content/fom-website/en/latest/all.xml",
        "name": "Formula1.com",
    },
    "racefans": {
        "url": "https://www.racefans.net/feed/",
        "name": "RaceFans",
    },
}

# Paths
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSETS_DIR = os.path.join(PROJECT_ROOT, "assets")
FONTS_DIR = os.path.join(ASSETS_DIR, "fonts")
DATA_DIR = os.path.join(PROJECT_ROOT, "data")
OUTPUT_DIR = os.path.join(PROJECT_ROOT, "output")
POSTED_HISTORY_PATH = os.path.join(DATA_DIR, "posted_history.json")

# Image
IMAGE_SIZE = (1080, 1080)
F1_RED = "#E10600"

# Models — override via GitHub repo variables or env vars
GEMINI_TEXT_MODEL = os.environ.get("GEMINI_TEXT_MODEL", "gemini-2.5-flash")
GEMINI_IMAGE_MODEL = os.environ.get("GEMINI_IMAGE_MODEL", "gemini-3-pro-image-preview")
IMAGEN_MODEL = os.environ.get("IMAGEN_MODEL", "imagen-4.0-generate-001")
