#!/usr/bin/env bash
# Build every image on this machine and start the production stack.
set -euo pipefail
cd "$(dirname "$0")/.."

[ -f .env ] || { echo "No .env yet. Follow deploy/README.md." >&2; exit 1; }
chmod 600 .env

deploy/compose.sh build
deploy/compose.sh up -d
deploy/compose.sh ps

echo
echo "Starting at https://$(deploy/compose.sh host)"
echo "The first certificate can take a minute. Then run deploy/smoke-test.sh"
