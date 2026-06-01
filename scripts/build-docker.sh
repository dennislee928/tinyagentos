#!/usr/bin/env bash
# Build the Docker image locally
# Usage: ./scripts/build-docker.sh [--platform linux/amd64,linux/arm64]
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_DIR"

PLATFORM="${1:-linux/amd64}"

echo "[build-docker] building for $PLATFORM"
docker buildx build --platform "$PLATFORM" --load -t tinyagentos:latest .
echo "[build-docker] done: tinyagentos:latest"
