#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(git rev-parse --show-toplevel)"
cd "$REPO_ROOT"

git config --local core.hooksPath .githooks
echo "Configured local Git hooks path to .githooks"
