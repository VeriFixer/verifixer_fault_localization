#!/usr/bin/env bash
# Generate contract-based tests for each mutant using DafnyTestGen.
# Keeps only mutants for which tests compile and run without errors.
#
# Usage:
#   bash dataset/scripts/get_dataset_where_dafnyTestGen_can_be_generated.sh [INPUT_DIR] [OUTPUT_DIR]
#
# Arguments:
#   INPUT_DIR   Path to sampled dataset (with original/ and killed/).
#               Default: <repo_root>/dataset/data/sampled_4
#   OUTPUT_DIR  Where to write the filtered dataset with generated tests.
#               Default: <repo_root>/dataset/data/dafnytestgen_tests_can_run_samp4

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/find_repo_root.sh"
BASE_PATH="$(find_repo_root)" || exit 1

FULL_DATASET_DIR="${1:-${BASE_PATH}/dataset/data/sampled_4}"
OUT_DIR="${2:-${BASE_PATH}/dataset/data/dafnytestgen_tests_can_run_samp4}"

mkdir -p "$OUT_DIR/killed"
mkdir -p "$OUT_DIR/original"
mkdir -p "$OUT_DIR/not_supported"
mkdir -p "$OUT_DIR/has_errors"

ORIG_DIR="$FULL_DATASET_DIR/original"
KILLED_DIR="$FULL_DATASET_DIR/killed"
MAX_JOBS=${MAX_JOBS:-$(( $(nproc) ))}

PROGRESS_LOCK="${BASE_PATH}/tmp/dataset_scripts_progress.lock"
PROGRESS_TMP="${BASE_PATH}/tmp/dataset_scripts_progress.tmp"
mkdir -p "${BASE_PATH}/tmp"

echo "Input dataset : ${FULL_DATASET_DIR}"
echo "Output dataset: ${OUT_DIR}"

process_file() {
    killed_file="$1"
    filename=$(basename "$killed_file")
    filename_without_extension="${filename%.dfy}"

    out_file="$OUT_DIR/killed/${filename_without_extension}.test.dfy"
    command="dotnet ${BASE_PATH}/build_output/DafnyTestGen/DafnyCBT.dll \"$killed_file\" -o \"$out_file\" --grouping by-status --skip-on-exception --comment-uncompilable -n 20"
    output=$(eval "$command" 2>&1)
    status=$?

    if [ ! -f "$out_file" ] || [ ! -s "$out_file" ]; then
        status=1
    fi

    if [ $status -eq 0 ]; then
        sed -i '1,5d' "$out_file"

        has_errors=false
        command="dafny verify \"$out_file\""
        dafny_output=$(eval "$command" 2>&1)
        verified=$(echo $dafny_output | grep "Dafny program verifier finished")
        if [[ $verified ]]; then
            command="timeout 60 dafny run \"$out_file\" --no-verify"
            dafny_output=$(eval "$command" 2>&1)
            runs=$(echo $dafny_output | grep -i "exception")
            if [[ ! -z $runs ]]; then
                echo $dafny_output > logs.txt
                has_errors=true
            fi
        else
            has_errors=true
        fi

        if [[ $has_errors == false ]]; then
            cp "$killed_file" "$OUT_DIR/killed/"
            killed_txt="${killed_file%.dfy}.txt"
            if [ -f "$killed_txt" ]; then
                cp "$killed_txt" "$OUT_DIR/killed/"
            else
                echo "Warning: killed text file missing for $killed_file (tried $killed_txt)"
            fi
        else
            mv "$out_file" "$OUT_DIR/has_errors/"
            cp "$killed_file" "$OUT_DIR/has_errors/"
            killed_txt="${killed_file%.dfy}.txt"
            if [ -f "$killed_txt" ]; then
                cp "$killed_txt" "$OUT_DIR/has_errors/"
            else
                echo "Warning: killed text file missing for $killed_file (tried $killed_txt)"
            fi
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

        cp "$killed_file" "$OUT_DIR/not_supported/"
        echo "Command: $command" >> "$OUT_DIR/not_supported/${filename_without_extension}.debug.log"
        echo "Output: $output" >> "$OUT_DIR/not_supported/${filename_without_extension}.debug.log"
    fi

    (
        flock 200
        count=$(<${PROGRESS_TMP})
        count=$((count + 1))
        echo "$count" > ${PROGRESS_TMP}
        printf "\r|- Generating tests: %d/%d" "$count" "$TOTAL"
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
