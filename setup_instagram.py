"""
Instagram Graph API setup helper.

Exchanges a short-lived token for a long-lived token and fetches
your Instagram Business Account ID.

Required .env vars:
    FB_APP_ID          - Facebook App ID
    FB_APP_SECRET      - Facebook App Secret
    FB_SHORT_TOKEN     - Short-lived token from Graph API Explorer

Outputs:
    INSTAGRAM_ACCESS_TOKEN  - Long-lived token (60 days)
    INSTAGRAM_ACCOUNT_ID    - Your IG Business Account ID

Run:
    python setup_instagram.py
"""

import os
import sys

import requests
from dotenv import load_dotenv

load_dotenv()

FB_APP_ID = os.environ.get("FB_APP_ID", "")
FB_APP_SECRET = os.environ.get("FB_APP_SECRET", "")
FB_SHORT_TOKEN = os.environ.get("FB_SHORT_TOKEN", "")

GRAPH_API = "https://graph.facebook.com/v21.0"


def exchange_token() -> str:
    """Exchange short-lived token for a long-lived one."""
    print("1. Exchanging for long-lived token...")
    resp = requests.get(
        f"{GRAPH_API}/oauth/access_token",
        params={
            "grant_type": "fb_exchange_token",
            "client_id": FB_APP_ID,
            "client_secret": FB_APP_SECRET,
            "fb_exchange_token": FB_SHORT_TOKEN,
        },
        timeout=30,
    )
    data = resp.json()
    if "error" in data:
        print(f"   ERROR: {data['error']['message']}")
        sys.exit(1)

    token = data["access_token"]
    expires = data.get("expires_in", "unknown")
    print(f"   Got long-lived token (expires in {expires}s / ~{int(expires)//86400} days)")
    return token


def get_ig_account_id(token: str) -> str:
    """Fetch Instagram Business Account ID via linked Facebook Pages."""
    print("2. Fetching Facebook Pages...")
    resp = requests.get(
        f"{GRAPH_API}/me/accounts",
        params={"access_token": token},
        timeout=30,
    )
    data = resp.json()
    if "error" in data:
        print(f"   ERROR: {data['error']['message']}")
        sys.exit(1)

    pages = data.get("data", [])
    if not pages:
        print("   ERROR: No Facebook Pages found. Link a Page to your IG account first.")
        sys.exit(1)

    for page in pages:
        print(f"   Found page: {page['name']} (ID: {page['id']})")
        resp2 = requests.get(
            f"{GRAPH_API}/{page['id']}",
            params={
                "fields": "instagram_business_account",
                "access_token": token,
            },
            timeout=30,
        )
        page_data = resp2.json()
        ig_account = page_data.get("instagram_business_account", {})
        if ig_account:
            ig_id = ig_account["id"]
            print(f"   Instagram Business Account ID: {ig_id}")
            return ig_id

    print("   ERROR: No Instagram Business Account linked to any Page.")
    sys.exit(1)


def main():
    missing = []
    if not FB_APP_ID:
        missing.append("FB_APP_ID")
    if not FB_APP_SECRET:
        missing.append("FB_APP_SECRET")
    if not FB_SHORT_TOKEN:
        missing.append("FB_SHORT_TOKEN")
    if missing:
        print(f"Missing .env vars: {', '.join(missing)}")
        sys.exit(1)

    token = exchange_token()
    ig_id = get_ig_account_id(token)

    print("\n" + "=" * 50)
    print("Add these to your .env file:\n")
    print(f"INSTAGRAM_ACCESS_TOKEN={token}")
    print(f"INSTAGRAM_ACCOUNT_ID={ig_id}")
    print("=" * 50)
    print("\nNote: Token expires in ~60 days. Re-run this script to refresh.")


if __name__ == "__main__":
    main()
