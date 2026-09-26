#!/usr/bin/env bash
# Almanac bootstrap — one-liner install:
#   curl -fsSL https://raw.githubusercontent.com/AndriGitDev/almanac/main/bootstrap.sh | bash
#
# Pass flags through:
#   curl -fsSL ... | bash -s -- --experimental --remote https://vault.example.com:8745
set -euo pipefail

REPO="https://github.com/AndriGitDev/almanac.git"
INSTALL_DIR="${ALMANAC_INSTALL_DIR:-${MEMENTO_INSTALL_DIR:-$HOME/.local/share/almanac}}"

# curl|bash leaves stdin attached to the script stream/EOF, so downstream
# prompts cannot be answered safely. Make that mode explicit and disable git's
# credential prompts rather than hanging in unattended bootstrap installs.
if [ ! -t 0 ]; then
    export MEMENTO_NONINTERACTIVE=1
    export GIT_TERMINAL_PROMPT=0
fi

# Colors
if [ -t 1 ]; then
    BOLD='\033[1m' GREEN='\033[0;32m' NC='\033[0m'
else
    BOLD='' GREEN='' NC=''
fi

echo -e "${BOLD}Almanac${NC} — bootstrap installer"
echo ""

if [ -d "$INSTALL_DIR/.git" ]; then
    REMOTE_URL="$(git -C "$INSTALL_DIR" remote get-url origin 2>/dev/null || true)"
    case "$REMOTE_URL" in
        *AndriGitDev/almanac.git|*AndriGitDev/almanac) ;;
        *) echo "Error: $INSTALL_DIR is not an Almanac checkout (origin: $REMOTE_URL)" >&2; exit 1 ;;
    esac
    echo -e "${GREEN}[+]${NC} Updating existing install at $INSTALL_DIR..."
    git -C "$INSTALL_DIR" pull --ff-only 2>/dev/null || git -C "$INSTALL_DIR" pull --rebase
else
    echo -e "${GREEN}[+]${NC} Cloning Almanac to $INSTALL_DIR..."
    git clone --depth 1 "$REPO" "$INSTALL_DIR"
fi

echo ""
exec "$INSTALL_DIR/install.sh" "$@"
