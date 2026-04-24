#!/usr/bin/env bash
# Generate mutants from DafnyBench using MutDafny.
#
# Usage:
#   bash dataset/scripts/generate_mutdafny_datset.sh [INPUT_DIR]
#
# Arguments:
#   INPUT_DIR  Path to DafnyBench ground_truth directory.
#              Default: <repo_root>/external/bench/dafnybench/DafnyBench/dataset/ground_truth

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/find_repo_root.sh"
SCRIPT_BASE_DIR="$(find_repo_root)" || exit 1

DATASET_DIR="${1:-${SCRIPT_BASE_DIR}/external/bench/dafnybench/DafnyBench/dataset/ground_truth}"
DATASET_DIR="$(cd "$DATASET_DIR" && pwd)" # resolve to absolute

RELATIVE_TARGET_SCRIPT="external/mutation/mutdafny/run.sh"
RELATIVE_TARGET_SCRIPT_DIR="external/mutation/mutdafny"

TARGET_SCRIPT="${SCRIPT_BASE_DIR}/${RELATIVE_TARGET_SCRIPT}"
TARGET_SCRIPT_DIR="${SCRIPT_BASE_DIR}/${RELATIVE_TARGET_SCRIPT_DIR}"

echo "Starting dataset processing..."
echo "Input directory : ${DATASET_DIR}"
echo "MutDafny script : ${TARGET_SCRIPT}"

if [ ! -d "$DATASET_DIR" ] || [ ! -x "$TARGET_SCRIPT" ]; then
    echo "Error: Directory or script check failed."
    echo "  Dataset dir exists? $([ -d "$DATASET_DIR" ] && echo yes || echo NO)"
    echo "  Script executable?  $([ -x "$TARGET_SCRIPT" ] && echo yes || echo NO)"
    exit 1
fi

TOTAL=$(find "$DATASET_DIR" -mindepth 1 -maxdepth 1 | wc -l)
DONE=0
START_TIME=$(date +%s)

for item in "$DATASET_DIR"/*; do
    (
        cd "$TARGET_SCRIPT_DIR" || exit 1
        "$TARGET_SCRIPT" "$item" --quiet
    )

    if [ $? -ne 0 ]; then
        echo "Warning: ${TARGET_SCRIPT} failed for item $item (Exit Code: $?)"
    fi

    DONE=$((DONE + 1))
    NOW=$(date +%s)
    ELAPSED=$((NOW - START_TIME))
    AVG=$((ELAPSED / DONE))
    REMAINING=$((AVG * (TOTAL - DONE)))
    printf "\rProgress: %d/%d | Avg: %ds | ETA: %ds" "$DONE" "$TOTAL" "$AVG" "$REMAINING"
done

echo
echo "Processing complete."
