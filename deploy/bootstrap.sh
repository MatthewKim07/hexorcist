#!/usr/bin/env bash
# First-time setup on a fresh Ubuntu 24.04 VM: Docker, firewall, repo. Safe to run again.
# Usage, as root: bash bootstrap.sh [repo-url] [branch]
set -euo pipefail

REPO_URL="${1:-https://github.com/MatthewKim07/hexorcist.git}"
BRANCH="${2:-hexorcist-mvp}"
APP_DIR="/opt/hexorcist"

[ "$(id -u)" = 0 ] || { echo "Run as root." >&2; exit 1; }
. /etc/os-release
[ "${ID:-}" = ubuntu ] && [ "${VERSION_ID:-}" = "24.04" ] || echo "Warning: written for Ubuntu 24.04, this is ${PRETTY_NAME:-unknown}." >&2

export DEBIAN_FRONTEND=noninteractive

echo "== Firewall: allow 22, 80 and 443 only"
apt-get update -qq
apt-get install -y -qq ufw git curl ca-certificates openssl python3 iproute2 nano >/dev/null
# Allow SSH before enabling, so this cannot lock you out of the session running it.
ufw allow 22/tcp >/dev/null
ufw allow 80/tcp >/dev/null
ufw allow 443/tcp >/dev/null
ufw default deny incoming >/dev/null
ufw default allow outgoing >/dev/null
ufw --force enable >/dev/null
ufw status | sed -n '1,12p'

echo "== Docker, from Docker's own apt repository"
if ! command -v docker >/dev/null; then
    install -m 0755 -d /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
    chmod a+r /etc/apt/keyrings/docker.asc
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu ${VERSION_CODENAME} stable" \
        > /etc/apt/sources.list.d/docker.list
    apt-get update -qq
    apt-get install -y -qq docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin >/dev/null
fi
systemctl enable --now docker >/dev/null
docker --version
docker compose version

echo "== Repository at $APP_DIR, branch $BRANCH"
if [ -d "$APP_DIR/.git" ]; then
    git -C "$APP_DIR" fetch --quiet origin
    git -C "$APP_DIR" checkout --quiet "$BRANCH"
    git -C "$APP_DIR" pull --quiet --ff-only origin "$BRANCH"
else
    git clone --quiet --branch "$BRANCH" "$REPO_URL" "$APP_DIR"
fi
git -C "$APP_DIR" log --oneline -1

echo
echo "Next: create $APP_DIR/.env by following deploy/README.md, then run deploy/up.sh"
