#!/bin/bash
#
# Rotate the Instagram access token.
#
# This refreshes your long-lived token (valid for 60 days)
# and updates the GitHub repository secret automatically.
#
# Run this every ~50 days BEFORE the token expires.
#
# Usage:
#   ./rotate_token.sh
#
# Prerequisites:
#   - gh CLI authenticated (gh auth login)
#   - .env file with FB_APP_ID, FB_APP_SECRET, INSTAGRAM_ACCESS_TOKEN

set -e

REPO="roguepikachu/boxboxnews"

# Load .env
if [ -f .env ]; then
    export $(grep -v '^#' .env | xargs)
fi

if [ -z "$FB_APP_ID" ] || [ -z "$FB_APP_SECRET" ] || [ -z "$INSTAGRAM_ACCESS_TOKEN" ]; then
    echo "ERROR: Missing FB_APP_ID, FB_APP_SECRET, or INSTAGRAM_ACCESS_TOKEN in .env"
    exit 1
fi

echo "Refreshing token..."
RESPONSE=$(curl -s -X GET \
    "https://graph.facebook.com/v21.0/oauth/access_token?grant_type=fb_exchange_token&client_id=${FB_APP_ID}&client_secret=${FB_APP_SECRET}&fb_exchange_token=${INSTAGRAM_ACCESS_TOKEN}")

# Check for error
if echo "$RESPONSE" | python3 -c "import sys,json; d=json.load(sys.stdin); sys.exit(0 if 'access_token' in d else 1)" 2>/dev/null; then
    NEW_TOKEN=$(echo "$RESPONSE" | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")
    EXPIRES=$(echo "$RESPONSE" | python3 -c "import sys,json; print(json.load(sys.stdin).get('expires_in','unknown'))")
    DAYS=$((EXPIRES / 86400))

    echo "New token obtained (expires in ~${DAYS} days)"

    # Get page token from user token
    PAGE_TOKEN=$(curl -s "https://graph.facebook.com/v21.0/1103024646221350?fields=access_token&access_token=${NEW_TOKEN}" | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

    echo "Page token obtained"

    # Update GitHub secret
    echo "Updating GitHub secret..."
    gh secret set INSTAGRAM_ACCESS_TOKEN --repo "$REPO" --body "$PAGE_TOKEN"
    echo "GitHub secret updated."

    # Update local .env
    if [[ "$OSTYPE" == "darwin"* ]]; then
        sed -i '' "s|^INSTAGRAM_ACCESS_TOKEN=.*|INSTAGRAM_ACCESS_TOKEN=${PAGE_TOKEN}|" .env
    else
        sed -i "s|^INSTAGRAM_ACCESS_TOKEN=.*|INSTAGRAM_ACCESS_TOKEN=${PAGE_TOKEN}|" .env
    fi
    echo "Local .env updated."

    echo ""
    echo "Done! Token rotated successfully. Next rotation needed in ~50 days."
else
    ERROR=$(echo "$RESPONSE" | python3 -c "import sys,json; print(json.load(sys.stdin).get('error',{}).get('message','Unknown error'))")
    echo "ERROR: $ERROR"
    echo ""
    echo "Token may have expired. You need to generate a new one manually:"
    echo "  1. Go to developers.facebook.com/tools/explorer"
    echo "  2. Select app: BoxBoxNews"
    echo "  3. Get User Access Token with permissions:"
    echo "     - instagram_basic"
    echo "     - instagram_content_publish"
    echo "     - pages_read_engagement"
    echo "  4. Copy the token and run:"
    echo "     python setup_instagram.py"
    echo "  5. Update .env with the new INSTAGRAM_ACCESS_TOKEN"
    echo "  6. Run this script again to push to GitHub"
    exit 1
fi
