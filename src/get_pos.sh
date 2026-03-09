# File responsible to generate the diff files for mutdafny

POS_MUT="../datasets/dafnybench_original_can_run"

KILLED_DIR="$POS_MUT/killed"
for mutant_file in "$KILLED_DIR"/*.dfy; do
    filename=$(basename "$mutant_file")
    original_name="${filename%__*}"
    original_file="$POS_MUT/original/${original_name}.dfy"
    if [[ ! -f "$original_file" ]]; then
        echo "Original file not found for $filename orignial $original_file"
        continue
    fi
    diff_file="$KILLED_DIR/${filename%.dfy}.txt"
    diff "$original_file" "$mutant_file" > "$diff_file"
done

echo "Diffs generated for all killed mutants."
