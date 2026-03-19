#!/bin/zsh
set -euo pipefail

RESOURCE_DIR="$(cd "$(dirname "$0")" && pwd)"

export NUMBA_CACHE_DIR="${TMPDIR:-/tmp}/numba-cache"
export NUMBA_CACHE_LOCATOR_CLASSES="UserProvidedCacheLocator"
mkdir -p "$NUMBA_CACHE_DIR"

exec /usr/bin/env python3 "$RESOURCE_DIR/Convert_to_instrumental.py"
