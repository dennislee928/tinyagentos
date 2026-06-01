#!/usr/bin/env bash
# Build the Electron desktop wrapper locally
# Usage: ./scripts/build-electron.sh [--mac|--win|--linux]
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_DIR"

TARGET="${1:---mac}"
echo "[build-electron] target: $TARGET"

echo "[build-electron] (1/3) installing Python deps..."
pip install -e ".[dev]" --quiet

echo "[build-electron] (2/3) building SPA frontend..."
cd desktop
npm ci --silent
npm run build
cd ..

echo "[build-electron] (3/3) building Electron app..."
cd electron
npm ci --silent
npx electron-builder "$TARGET"
cd ..

echo "[build-electron] done. artifacts in electron/dist/"
