#!/usr/bin/env bash
# Randomly sample N mutants (with their originals and diff files) from a
# filtered dataset into a new dataset directory.
#
# NOTE: sampling is random and uses no fixed seed, so re-running this script
# against the same input will pick a *different* subset of mutants each time.
# The pre-shipped dataset/data/sample_original_can_run/ cannot be regenerated
# byte-for-byte with this script; it is provided as a tarball precisely so
# reviewers can reproduce results on the exact same sample. Use this script
# to understand the sampling process, not to recreate that exact dataset.
#
# Usage:
#   bash dataset/scripts/sample_dataset.sh N [INPUT_DIR] [OUTPUT_DIR]
#
# Arguments:
#   N           Number of mutants to sample (required).
#   INPUT_DIR   Path to filtered dataset (with original/ and killed/).
#               Default: <repo_root>/dataset/data/dafnybench_original_can_run
#   OUTPUT_DIR  Where to write the sampled dataset.
#               Default: <repo_root>/dataset/data/sampled_<N>

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/find_repo_root.sh"
BASE_PATH="$(find_repo_root)" || exit 1

if [[ -z "${1:-}" ]]; then
    echo "Usage: bash dataset/scripts/sample_dataset.sh N [INPUT_DIR] [OUTPUT_DIR]"
    exit 1
fi

N="$1"
INPUT_DIR="${2:-${BASE_PATH}/dataset/data/dafnybench_original_can_run}"
OUT_DIR="${3:-${BASE_PATH}/dataset/data/sampled_${N}}"

KILLED_DIR="$INPUT_DIR/killed"
ORIG_DIR="$INPUT_DIR/original"

mkdir -p "$OUT_DIR/killed"
mkdir -p "$OUT_DIR/original"

echo "Input dataset : ${INPUT_DIR}"
echo "Output dataset: ${OUT_DIR}"
echo "Sample size   : ${N}"

mapfile -t mutants < <(find "$KILLED_DIR" -name "*.dfy" ! -name "*.test.dfy" -printf "%f\n" | sort -R | head -n "$N")

if [[ ${#mutants[@]} -lt $N ]]; then
    echo "Warning: requested ${N} mutants but only found ${#mutants[@]} available."
fi

copied=0
for mutant_filename in "${mutants[@]}"; do
    mutant_stem="${mutant_filename%.dfy}"

    cp "$KILLED_DIR/$mutant_filename" "$OUT_DIR/killed/"

    diff_file="$KILLED_DIR/${mutant_stem}.txt"
    if [[ -f "$diff_file" ]]; then
        cp "$diff_file" "$OUT_DIR/killed/"
    else
        echo "Warning: diff file missing for $mutant_filename (expected $diff_file)"
    fi

    test_file="$KILLED_DIR/${mutant_stem}.test.dfy"
    if [[ -f "$test_file" ]]; then
        cp "$test_file" "$OUT_DIR/killed/"
    fi

    original_name="${mutant_stem%__*}"
    original_file="$ORIG_DIR/${original_name}.dfy"
    if [[ -f "$original_file" ]]; then
        cp "$original_file" "$OUT_DIR/original/"
    else
        echo "Warning: original .dfy not found for $mutant_filename (expected $original_file)"
    fi

    copied=$((copied + 1))
done

echo "Done. Sampled ${copied} mutants into: ${OUT_DIR}"
