#!/usr/bin/env bash
# Commits whatever is on disk (rewrite succeeded, partially succeeded, or
# failed outright) and force-pushes it to main. No PR, no review, no gate.
# Requires PUSH_TOKEN: a PAT/App token with contents:write and, if main is
# branch-protected, explicit bypass for that token's identity. This script
# does not attempt to modify branch protection itself.
set -euo pipefail

if [[ -z "${PUSH_TOKEN:-}" ]]; then
  echo "PUSH_TOKEN is required to push to main." >&2
  exit 1
fi

REPO_URL=$(git config --get remote.origin.url)
# Rewrite the remote URL to embed the token for this push only.
AUTH_URL=$(echo "$REPO_URL" | sed -E "s#https://#https://x-access-token:${PUSH_TOKEN}@#")

git config user.name "rusticide-bot"
git config user.email "rusticide-bot@users.noreply.github.com"

git add -A
if git diff --cached --quiet; then
  echo "Nothing to commit after rewrite attempt; marker may already be the only change."
fi
git commit -m "rusticide: one-shot rewrite (irreversible, unreviewed)" --allow-empty

git push --force "$AUTH_URL" HEAD:main
