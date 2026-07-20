#!/bin/zsh
set -euo pipefail

PROJECT_ROOT="/Users/robertograu/roxy_trading"
cd "$PROJECT_ROOT"

export PATH="/Users/robertograu/.local/share/fnm/node-versions/v24.5.0/installation/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"

NODE_BIN="$(command -v node || true)"
if [[ -z "$NODE_BIN" ]]; then
  echo "Roxy knowledge autopilot could not find node." >&2
  exit 127
fi

"$NODE_BIN" scripts/updateKnowledge.ts
