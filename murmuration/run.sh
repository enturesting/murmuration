#!/usr/bin/env bash
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
cd "$HERE"
if [[ ! -d .venv ]]; then
  echo "venv missing — run setup first"; exit 1
fi
# load any keys (EIA, NREL, ANTHROPIC) from .env if present
if [[ -f .env ]]; then
  set -a
  source .env
  set +a
fi
exec .venv/bin/python -m murmuration.api.server
