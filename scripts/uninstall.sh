#!/usr/bin/env bash
set -euo pipefail

if ! command -v uv >/dev/null 2>&1; then
  echo "uv is required. Install from https://astral.sh/uv/" >&2
  exit 1
fi

if [[ "${1:-}" == "--system" ]]; then
  sudo uv tool uninstall pytodo-tui
  echo "Uninstalled system-wide 'todo' command."
  exit 0
fi

uv tool uninstall pytodo-tui
echo "Uninstalled 'todo' command."
