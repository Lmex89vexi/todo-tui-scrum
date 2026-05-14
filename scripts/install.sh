#!/usr/bin/env bash
set -euo pipefail

if ! command -v uv >/dev/null 2>&1; then
  echo "uv is required. Install from https://astral.sh/uv/" >&2
  exit 1
fi

if [[ "${1:-}" == "--system" ]]; then
  sudo uv tool install -e .
  echo "Installed system-wide 'todo' command."
  exit 0
fi

uv tool install -e .
echo "Installed 'todo' command. Ensure ~/.local/bin is in PATH."
