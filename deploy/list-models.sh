#!/usr/bin/env bash
# List the models this API key can use, reading the key from .env. Never prints the key.
set -euo pipefail
cd "$(dirname "$0")/.."
exec python3 deploy/list_models.py
