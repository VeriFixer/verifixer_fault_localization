#!/usr/bin/env bash
# setup_data.sh — Extract compressed datasets and cached results.
# Run this ONCE after entering the Docker container (or after cloning).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "=== Extracting dataset/data/pos_test ==="
if [ ! -d "dataset/data/pos_test/killed" ]; then
    tar xzf dataset/data/pos_test.tar.gz -C dataset/data/
    echo "    done."
else
    echo "    already exists, skipping."
fi

echo "=== Extracting dataset/data/sample_original_can_run ==="
if [ ! -d "dataset/data/sample_original_can_run/killed" ]; then
    tar xzf dataset/data/sample_original_can_run.tar.gz -C dataset/data/
    echo "    done."
else
    echo "    already exists, skipping."
fi

echo "=== Extracting tmp/run_artifacts (cached_results, images, models_log) ==="
if [ ! -d "tmp/run_artifacts/cached_results" ]; then
    tar xzf tmp_run_artifacts.tar.gz
    echo "    done."
else
    echo "    already exists, skipping."
fi

echo ""
echo "Setup complete. You can now run the pipeline, e.g.:"
echo "  python src/runners/run_1_model.py RAND dataset/data/pos_test"
