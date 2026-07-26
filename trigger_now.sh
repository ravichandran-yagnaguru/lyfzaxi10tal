#!/usr/bin/env bash
# Manually trigger a real post right now, outside the scheduled times.
# Requires: gcloud CLI installed and logged into an account with invoke
# access on the concept-bot Cloud Run service (the project owner has this
# by default).
set -euo pipefail

SERVICE_URL="https://concept-bot-du3idxkh7a-uc.a.run.app"

TOKEN=$(gcloud auth print-identity-token)
curl -s -X POST "${SERVICE_URL}/post" -H "Authorization: Bearer ${TOKEN}" | python3 -m json.tool
