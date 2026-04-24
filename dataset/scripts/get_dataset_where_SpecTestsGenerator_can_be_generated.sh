#!/usr/bin/env bash
# Generate spec-based tests for each mutant using SpecTestGenerator.
# Keeps only mutants for which tests are successfully generated.
#
# Usage:
#   bash dataset/scripts/get_dataset_where_SpecTestsGenerator_can_be_generated.sh [INPUT_DIR] [OUTPUT_DIR]
#
# Arguments:
#   INPUT_DIR   Path to dataset (with original/ and killed/).
#               Default: <repo_root>/dataset/data/sample_original_can_run
#   OUTPUT_DIR  Where to write the filtered dataset with generated tests.
#               Default: <repo_root>/dataset/data/spec_tests_can_run

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/find_repo_root.sh"
BASE_PATH="$(find_repo_root)" || exit 1

FULL_DATASET_DIR="${1:-${BASE_PATH}/dataset/data/sample_original_can_run}"
OUT_DIR="${2:-${BASE_PATH}/dataset/data/spec_tests_can_run}"

mkdir -p "$OUT_DIR/killed"
mkdir -p "$OUT_DIR/original"

ORIG_DIR="$FULL_DATASET_DIR/original"
KILLED_DIR="$FULL_DATASET_DIR/killed"
MAX_JOBS=${MAX_JOBS:-1}

PROGRESS_LOCK="${BASE_PATH}/tmp/dataset_scripts_progress.lock"
PROGRESS_TMP="${BASE_PATH}/tmp/dataset_scripts_progress.tmp"
mkdir -p "${BASE_PATH}/tmp"

echo "Input dataset : ${FULL_DATASET_DIR}"
echo "Output dataset: ${OUT_DIR}"

process_file() {
    killed_file="$1"
    filename=$(basename "$killed_file")

    killed_output="${killed_file%.dfy}_test.dfy"

    command="${BASE_PATH}/external/tests_gen/spec-test-generator/Binaries/Dafny generate-tests Spec \"$killed_file\" --test-count 1 > \"$killed_output\""
    output=$(eval "$command" 2>&1)
    status=$?

    if [ $status -eq 0 ]; then
        filename_without_extension="${filename%.dfy}"

        cp "$killed_file" "$OUT_DIR/killed/"

        if [ -f "$killed_output" ]; then
            cp "$killed_output" "$OUT_DIR/killed/"
        else
            echo "Warning: killed .dfy file missing for $killed_file (tried $killed_output)"
        fi

        base_name_raw="${filename_without_extension%__*}"
        original_file="$ORIG_DIR/${base_name_raw}.dfy"
        if [ -f "$original_file" ]; then
            cp "$original_file" "$OUT_DIR/original/"
        else
            echo "Warning: original .dfy not found for $killed_file (expected $original_file)"
        fi
    else
        echo "|-------------------------------------|"
        echo "Error processing $killed_file"
        echo "Command: $command"
        echo "Exit Status: $status"
        echo "$output"

        rm -f "$killed_output"
    fi

    (
        flock 200
        count=$(<${PROGRESS_TMP})
        count=$((count + 1))
        echo "$count" > ${PROGRESS_TMP}
        printf "\r|- Generating spec tests: %d/%d" "$count" "$TOTAL"
    ) 200>${PROGRESS_LOCK}
}

export -f process_file
export OUT_DIR BASE_PATH ORIG_DIR PROGRESS_TMP PROGRESS_LOCK

mapfile -t files < <(find "$KILLED_DIR" -name "*.dfy")
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
