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

# RSS Feeds
RSS_FEEDS = {
    "planetf1": {
        "url": "https://www.planetf1.com/news/feed/",
        "name": "PlanetF1",
    },
    "racingnews365": {
        "url": "https://racingnews365.com/feed/news.xml",
        "name": "RacingNews365",
    },
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
    "racefans": {
        "url": "https://www.racefans.net/feed/",
        "name": "RaceFans",
    },
    "gpblog": {
        "url": "https://www.gpblog.com/en/rss/index.xml",
        "name": "GPblog",
    },
    "formulanews": {
        "url": "https://www.formula1.com/content/fom-website/en/latest/all.xml",
        "name": "Formula1.com",
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
