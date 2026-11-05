#!/usr/bin/env bash
# docker compose with the production override. Usage: deploy/compose.sh up -d --build
# `deploy/compose.sh host` prints the hostname.
#
# The hostname comes from the VM's public IP: 203.0.113.5 becomes 203-0-113-5.sslip.io.
# Set SITE_HOST yourself to use a real domain, or if sslip.io certificates are unavailable.
set -euo pipefail
cd "$(dirname "$0")/.."

public_ip() {
    # Vultr's metadata service first, then an outside opinion.
    curl -fsS -m 3 http://169.254.169.254/v1/interfaces/0/ipv4/address 2>/dev/null \
        || curl -fsS -4 -m 5 https://api.ipify.org 2>/dev/null
}

if [ -z "${SITE_HOST:-}" ]; then
    ip="$(public_ip)" || { echo "Could not work out the public IP. Set SITE_HOST." >&2; exit 1; }
    SITE_HOST="${ip//./-}.sslip.io"
fi
export SITE_HOST

if [ "${1:-}" = host ]; then
    echo "$SITE_HOST"
    exit 0
fi

exec docker compose -f docker-compose.yml -f deploy/docker-compose.prod.yml "$@"
