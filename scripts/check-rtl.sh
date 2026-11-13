#!/usr/bin/env bash
# Fails if web/src uses physical direction utilities. Positional data-[side=...] variants of shadcn
# overlays (Sheet/Sidebar/Tooltip) are physical by design (side="left" means the end side in RTL) and are allowed.
set -uo pipefail
cd "$(dirname "$0")/../web"
hits=$(grep -rnE '\b(ml|mr|pl|pr|left|right)-[0-9a-z]|text-(left|right)\b' src | grep -v 'data-\[side=' || true)
if [ -n "$hits" ]; then
  echo "PHYSICAL DIRECTION CLASSES FOUND:"
  echo "$hits"
  exit 1
fi
echo "rtl ok"
