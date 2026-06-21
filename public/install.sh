#!/usr/bin/env bash
set -e

# ── nexus-dev-toolkit Installer ───────────────────────────────────────────────
#
# Usage:
#   curl -fsSL https://nexus.coderstudio.co/install.sh | bash
#
# Options (env vars):
#   NEXUS_VERSION   PyPI version to install     (default: latest)
#   NEXUS_DIR       Install prefix              (default: ~/.local)
# ─────────────────────────────────────────────────────────────────────────────

VERSION="${NEXUS_VERSION:-}"
INSTALL_DIR="${NEXUS_DIR:-$HOME/.local}"
BIN_DIR="$INSTALL_DIR/bin"

BOLD="\033[1m"
CYAN="\033[36m"
GREEN="\033[32m"
RED="\033[31m"
DIM="\033[2m"
RESET="\033[0m"

print_logo() {
  printf "\n"
  printf "${CYAN}  ███╗   ██╗███████╗██╗  ██╗██╗   ██╗███████╗${RESET}\n"
  printf "${CYAN}  ████╗  ██║██╔════╝╚██╗██╔╝██║   ██║██╔════╝${RESET}\n"
  printf "${CYAN}  ██╔██╗ ██║█████╗   ╚███╔╝ ██║   ██║███████╗${RESET}\n"
  printf "${CYAN}  ██║╚██╗██║██╔══╝   ██╔██╗ ██║   ██║╚════██║${RESET}\n"
  printf "${CYAN}  ██║ ╚████║███████╗██╔╝ ██╗╚██████╔╝███████║${RESET}\n"
  printf "${CYAN}  ╚═╝  ╚═══╝╚══════╝╚═╝  ╚═╝ ╚═════╝ ╚══════╝${RESET}\n"
  printf "  ${DIM}dev toolkit${RESET}\n\n"
}

step() { printf "  ${CYAN}▶${RESET}  $1\n"; }
ok()   { printf "  ${GREEN}✓${RESET}  $1\n"; }
err()  { printf "  ${RED}✗${RESET}  $1\n" >&2; exit 1; }

need() {
  command -v "$1" >/dev/null 2>&1 || err "'$1' is required but not installed. $2"
}

print_logo

DISPLAY_VERSION="${VERSION:-latest}"
printf "  ${BOLD}Installing nexus CLI${RESET}  ${DIM}(version: $DISPLAY_VERSION)${RESET}\n\n"

# ── Check requirements ────────────────────────────────────────────────────────
step "Checking requirements…"
need curl "Install via: brew install curl"

if command -v uv >/dev/null 2>&1; then
  INSTALLER="uv"
elif command -v pip3 >/dev/null 2>&1; then
  INSTALLER="pip"
elif command -v pip >/dev/null 2>&1; then
  INSTALLER="pip"
else
  err "Neither 'uv' nor 'pip' found. Install uv: curl -LsSf https://astral.sh/uv/install.sh | sh"
fi
ok "Requirements satisfied  (installer: $INSTALLER)"

# ── Install ───────────────────────────────────────────────────────────────────
if [ -n "$VERSION" ]; then
  PYPI_PKG="nexus-dev-toolkit==$VERSION"
  step "Installing nexus-dev-toolkit==$VERSION from PyPI…"
else
  PYPI_PKG="nexus-dev-toolkit"
  step "Installing nexus-dev-toolkit from PyPI…"
fi

if [ "$INSTALLER" = "uv" ]; then
  uv tool install --reinstall --force "$PYPI_PKG" --quiet
  NEXUS_BIN="$(uv tool dir)/../bin/nexus"
  [ ! -f "$NEXUS_BIN" ] && NEXUS_BIN="$(uv tool dir)/nexus-dev-toolkit/bin/nexus"
else
  pip3 install --quiet --upgrade "$PYPI_PKG"
  NEXUS_BIN="$(python3 -m site --user-base)/bin/nexus"
fi

if [ ! -f "$NEXUS_BIN" ]; then
  NEXUS_BIN="$(find "${HOME}/.local" -name "nexus" -type f 2>/dev/null | head -1)"
fi

ok "Installed successfully"

hash -r 2>/dev/null || true

# ── Verify ────────────────────────────────────────────────────────────────────
step "Verifying installation…"

if command -v nexus >/dev/null 2>&1; then
  ok "nexus is in PATH"
else
  export PATH="$BIN_DIR:$(python3 -m site --user-base)/bin:$HOME/.local/share/uv/tools/nexus-dev-toolkit/bin:$PATH"
  if command -v nexus >/dev/null 2>&1; then
    ok "nexus found (PATH update needed — see below)"
  fi
fi

# ── Symlink ───────────────────────────────────────────────────────────────────
SYMLINK_DIR="/usr/local/bin"

if [ -f "$NEXUS_BIN" ] && ! command -v nexus >/dev/null 2>&1; then
  step "Creating symlink in $SYMLINK_DIR…"
  if [ -w "$SYMLINK_DIR" ]; then
    ln -sf "$NEXUS_BIN" "$SYMLINK_DIR/nexus"
    ok "Symlinked: $SYMLINK_DIR/nexus → $NEXUS_BIN"
  else
    if sudo ln -sf "$NEXUS_BIN" "$SYMLINK_DIR/nexus" 2>/dev/null; then
      ok "Symlinked (sudo): $SYMLINK_DIR/nexus → $NEXUS_BIN"
    else
      mkdir -p "$HOME/.local/bin"
      ln -sf "$NEXUS_BIN" "$HOME/.local/bin/nexus"
      ok "Symlinked: ~/.local/bin/nexus → $NEXUS_BIN"

      SHELL_RC=""
      case "$SHELL" in
        */zsh)  SHELL_RC="$HOME/.zshrc" ;;
        */bash) SHELL_RC="$HOME/.bashrc" ;;
        */fish) SHELL_RC="$HOME/.config/fish/config.fish" ;;
      esac
      if [ -n "$SHELL_RC" ] && ! echo "$PATH" | grep -q "$HOME/.local/bin"; then
        echo "\nexport PATH=\"\$HOME/.local/bin:\$PATH\"" >> "$SHELL_RC"
        export PATH="$HOME/.local/bin:$PATH"
        ok "PATH updated — restart your terminal or run: source $SHELL_RC"
      fi
    fi
  fi
fi

# ── Done ──────────────────────────────────────────────────────────────────────
printf "\n  ${GREEN}${BOLD}Installation complete!${RESET}\n\n"
printf "  ${DIM}Get started:${RESET}\n"
printf "  ${CYAN}nexus setup${RESET}                ${DIM}# init project + write MCP config + sync skills${RESET}\n"
printf "  ${CYAN}nexus skill add${RESET} ${DIM}my-review${RESET}  ${DIM}# create a custom skill${RESET}\n"
printf "  ${CYAN}nexus sync${RESET}                 ${DIM}# push .nexus/ to your LLM tool${RESET}\n\n"
