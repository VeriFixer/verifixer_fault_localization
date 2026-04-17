#!/usr/bin/env bash
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/find_repo_root.sh"
BASE_PATH="$(find_repo_root)" || exit 1 

OUT_DIR="${BASE_PATH}/dataset/data/dafnybench_tests_can_run"
mkdir -p "$OUT_DIR/killed"
mkdir -p "$OUT_DIR/original"

#FULL_DATASET_DIR="${BASE_PATH}/dataset/data/dafnybench_original_can_run"
FULL_DATASET_DIR="${BASE_PATH}/dataset/data/pos_test"

ORIG_DIR="$FULL_DATASET_DIR/original"
KILLED_DIR="$FULL_DATASET_DIR/killed"   # define killed directory
#MAX_JOBS=${MAX_JOBS:-$(( $(nproc) ))}
MAX_JOBS=1

PROGRESS_LOCK="${BASE_PATH}/tmp/dataset_scripts_progress.lock"
PROGRESS_TMP="${BASE_PATH}/tmp/dataset_scripts_progress.tmp"

mkdir -p "${BASE_PATH}/tmp"

process_file() {
    killed_file="$1"
    filename=$(basename "$killed_file")

    # Capture Dafny output
    command="${BASE_PATH}/SpecTestGenerator/Binaries/Dafny generate-tests Spec \"$killed_file\" --test-count 5"
    output=$(eval "$command" 2>&1)
    status=$?

    # real success condition
    if [ $status -eq 0 ]; then
        filename_without_extension="${filename%.dfy}"

        cp "$killed_file" "$OUT_DIR/killed/"

        killed_txt="${killed_file%.dfy}.txt"
        if [ -f "$killed_txt" ]; then
            cp "$killed_txt" "$OUT_DIR/killed/"
        else
            echo "Warning: killed text file missing for $killed_file (tried $killed_txt)"
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
    fi

    # thread-safe progress update
    (
        flock 200
        count=$(<${PROGRESS_TMP})
        count=$((count + 1))
        echo "$count" > ${PROGRESS_TMP}
        printf "\r|- Copying files that generated tests to dafnybench_tests_can_run: %d/%d" "$count" "$TOTAL"
    ) 200>${PROGRESS_LOCK}
}

export -f process_file

mapfile -t files < <(find "$KILLED_DIR" -name "*.dfy")
TOTAL=${#files[@]}
echo 0 > ${PROGRESS_TMP}
touch ${PROGRESS_LOCK}

for file in "${files[@]}"; do
  ( process_file "$file") &

   while [[ $(jobs -r -p | wc -l) -ge $MAX_JOBS ]]; do
     wait -n
   done
done

wait

echo
rm -f ${PROGRESS_TMP} ${PROGRESS_LOCK}
