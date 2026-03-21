#!/bin/bash
#
# Manually trigger a post right now via GitHub Actions.
#
# Usage:
#   ./post_now.sh
#

set -e

REPO="roguepikachu/boxboxnews"

echo "Triggering daily post workflow..."
gh workflow run daily-post.yml --repo "$REPO"
echo "Triggered! Watch progress at:"
echo "  https://github.com/$REPO/actions"
echo ""
echo "Or run: gh run watch --repo $REPO"
