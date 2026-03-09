#!/usr/bin/env bash

OUT_DIR="../datasets/dafnybench_original_can_run"
mkdir -p "$OUT_DIR/killed"
mkdir -p "$OUT_DIR/original"

FULL_DATASET_DIR="../datasets/dafnybench_all_mutants"
ORIG_DIR="$FULL_DATASET_DIR/original"
KILLED_DIR="$FULL_DATASET_DIR/killed"   # define killed directory
MAX_JOBS=${MAX_JOBS:-$(( $(nproc) ))}

process_file() {
    original_file="$1"
    filename=$(basename "$original_file")

    # Capture Dafny output
    output=$(dafny verify --allow-warnings "$original_file" 2>&1)
    status=$?

    if [ $status -eq 0 ]; then
        # Only copy function/mutation that ended well
        filename_without_extension="${filename%.dfy}"

        cp "$original_file" "$OUT_DIR/original/"

        # copy killed variants if they exist
        if compgen -G "$KILLED_DIR/${filename_without_extension}__*" > /dev/null; then
            cp "$KILLED_DIR/${filename_without_extension}__"* "$OUT_DIR/killed/"
        fi
    fi

    # thread-safe progress update
    (
        flock 200
        count=$(<progress.tmp)
        count=$((count + 1))
        echo "$count" > progress.tmp
        printf "\r|- Copying Origs that verify to dafnybench_original_can_run: %d/%d" "$count" "$TOTAL"
    ) 200>progress.lock
}

export -f process_file

mapfile -t files < <(find "$ORIG_DIR" -name "*.dfy")
TOTAL=${#files[@]}
echo 0 > progress.tmp
touch progress.lock

for file in "${files[@]}"; do
  ( process_file "$file") &

   while [[ $(jobs -r -p | wc -l) -ge $MAX_JOBS ]]; do
     wait -n
   done
done

wait

echo
rm -f progress.tmp progress.lock
