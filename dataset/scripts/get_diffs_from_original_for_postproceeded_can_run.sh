#!/usr/bin/env bash
# Generate diff files (ground truth) for each mutant against its original.
#
# Usage:
#   bash dataset/scripts/get_diffs_from_original_for_postproceeded_can_run.sh [DATASET_DIR]
#
# Arguments:
#   DATASET_DIR  Path to dataset with original/ and killed/ subdirectories.
#                Default: <repo_root>/dataset/data/dafnybench_original_can_run

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/find_repo_root.sh"
BASE_PATH="$(find_repo_root)" || exit 1

POS_MUT="${1:-${BASE_PATH}/dataset/data/dafnybench_original_can_run}"

KILLED_DIR="$POS_MUT/killed"

echo "Generating diffs for dataset: ${POS_MUT}"

for mutant_file in "$KILLED_DIR"/*.dfy; do
    filename=$(basename "$mutant_file")
    original_name="${filename%__*}"
    original_file="$POS_MUT/original/${original_name}.dfy"
    if [[ ! -f "$original_file" ]]; then
        echo "Original file not found for $filename (expected $original_file)"
        continue
    fi
    diff_file="$KILLED_DIR/${filename%.dfy}.txt"
    diff "$original_file" "$mutant_file" > "$diff_file" || true
done

echo "Diffs generated for all killed mutants."
