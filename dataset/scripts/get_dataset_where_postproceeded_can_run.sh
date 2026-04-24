#!/usr/bin/env bash
# Filter dataset to only originals that Dafny can verify, plus their mutants.
#
# Usage:
#   bash dataset/scripts/get_dataset_where_postproceeded_can_run.sh [INPUT_DIR] [OUTPUT_DIR]
#
# Arguments:
#   INPUT_DIR   Path to full mutant dataset (with original/ and killed/).
#               Default: <repo_root>/dataset/data/dafnybench_all_mutants
#   OUTPUT_DIR  Where to write the filtered dataset.
#               Default: <repo_root>/dataset/data/dafnybench_original_can_run

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/find_repo_root.sh"
BASE_PATH="$(find_repo_root)" || exit 1

FULL_DATASET_DIR="${1:-${BASE_PATH}/dataset/data/dafnybench_all_mutants}"
OUT_DIR="${2:-${BASE_PATH}/dataset/data/dafnybench_original_can_run}"

mkdir -p "$OUT_DIR/killed"
mkdir -p "$OUT_DIR/original"

ORIG_DIR="$FULL_DATASET_DIR/original"
KILLED_DIR="$FULL_DATASET_DIR/killed"
MAX_JOBS=${MAX_JOBS:-$(( $(nproc) ))}

PROGRESS_LOCK="${BASE_PATH}/tmp/dataset_scripts_progress.lock"
PROGRESS_TMP="${BASE_PATH}/tmp/dataset_scripts_progress.tmp"
mkdir -p "${BASE_PATH}/tmp"

echo "Input dataset : ${FULL_DATASET_DIR}"
echo "Output dataset: ${OUT_DIR}"

process_file() {
    original_file="$1"
    filename=$(basename "$original_file")

    output=$(dafny verify --allow-warnings "$original_file" 2>&1)
    status=$?

    if [ $status -eq 0 ]; then
        filename_without_extension="${filename%.dfy}"
        cp "$original_file" "$OUT_DIR/original/"

        if compgen -G "$KILLED_DIR/${filename_without_extension}__*" > /dev/null; then
            cp "$KILLED_DIR/${filename_without_extension}__"* "$OUT_DIR/killed/"
        fi
    fi

    (
        flock 200
        count=$(<${PROGRESS_TMP})
        count=$((count + 1))
        echo "$count" > ${PROGRESS_TMP}
        printf "\r|- Filtering originals that verify: %d/%d" "$count" "$TOTAL"
    ) 200>${PROGRESS_LOCK}
}

export -f process_file
export OUT_DIR KILLED_DIR PROGRESS_TMP PROGRESS_LOCK

mapfile -t files < <(find "$ORIG_DIR" -name "*.dfy")
TOTAL=${#files[@]}
export TOTAL
echo 0 > ${PROGRESS_TMP}
touch ${PROGRESS_LOCK}

for file in "${files[@]}"; do
    ( process_file "$file" ) &
    while [[ $(jobs -r -p | wc -l) -ge $MAX_JOBS ]]; do
        wait -n
    done
done

wait
echo
rm -f ${PROGRESS_TMP} ${PROGRESS_LOCK}
echo "Done. Output at: ${OUT_DIR}"
