#!/usr/bin/env bash
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/find_repo_root.sh"
BASE_PATH="$(find_repo_root)" || exit 1 

OUT_DIR="${BASE_PATH}/datasets/dafnybench_tests_can_run"
mkdir -p "$OUT_DIR/killed"
mkdir -p "$OUT_DIR/original"

#FULL_DATASET_DIR="${BASE_PATH}/datasets/dafnybench_original_can_run"
FULL_DATASET_DIR="${BASE_PATH}/src/pos_test"

ORIG_DIR="$FULL_DATASET_DIR/original"
KILLED_DIR="$FULL_DATASET_DIR/killed"   # define killed directory
#MAX_JOBS=${MAX_JOBS:-$(( $(nproc) ))}
MAX_JOBS=1

PROGRESS_LOCK="${BASE_PATH}/src/progress.lock"
PROGRESS_TMP="${BASE_PATH}/src/progress.tmp"

process_file() {
    original_file="$1"
    filename=$(basename "$original_file")

    # Capture Dafny output
    output=$(${BASE_PATH}/SpecTestGenerator/Binaries/Dafny generate-tests Spec "$original_file" --test-count 5 )
    status=$?

    if [ $status -eq 0 ]; then
        # Only copy function/mutation that ended well
        filename_without_extension="${filename%.dfy}"

        cp "$original_file" "$OUT_DIR/original/"

        # copy killed variants if they exist
        if compgen -G "$KILLED_DIR/${filename_without_extension}__*" > /dev/null; then
            cp "$KILLED_DIR/${filename_without_extension}__"* "$OUT_DIR/killed/"
        fi

    else
        echo "Error processing $original_file"
        echo "$output"
    fi

    # thread-safe progress update
    (
        flock 200
        count=$(<${PROGRESS_TMP})
        count=$((count + 1))
        echo "$count" > ${PROGRESS_TMP}
        printf "\r|- Copying files that test generated to dafnybench_tests_can_run: %d/%d" "$count" "$TOTAL"
    ) 200>${PROGRESS_LOCK}
}

export -f process_file

mapfile -t files < <(find "$ORIG_DIR" -name "*.dfy")
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
