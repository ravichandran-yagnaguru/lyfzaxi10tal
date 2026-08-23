#!/usr/bin/env bash
# Manually trigger a real post right now, outside the scheduled times.
# Requires: gcloud CLI installed and logged into an account with invoke
# access on the concept-bot Cloud Run service (the project owner has this
# by default).
set -euo pipefail

SERVICE_URL="https://concept-bot-1034344960712.us-central1.run.app"

# Usage:
#   ./trigger_now.sh                  real everyday post
#   ./trigger_now.sh idiom            real idiom post
#   ./trigger_now.sh "" dry           preview everyday post (no posting)
#   ./trigger_now.sh idiom dry        preview idiom post (no posting)
QUERY=""
[ "${1:-}" = "idiom" ] && QUERY="format=idiom"
[ "${2:-}" = "dry" ] && QUERY="${QUERY:+${QUERY}&}dry_run=true"

TOKEN=$(gcloud auth print-identity-token)
curl -s -X POST "${SERVICE_URL}/post${QUERY:+?${QUERY}}" -H "Authorization: Bearer ${TOKEN}" | python3 -m json.tool
