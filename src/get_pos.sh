POS_MUT="pos_mutation"

cp -r ../mutdafny/mutants $POS_MUT
cp -r ../mutdafny/original $POS_MUT/original

rm -rf $POS_MUT/alive
rm -rf $POS_MUT/timed-out

KILLED_DIR="$POS_MUT/killed"
for mutant_file in "$KILLED_DIR"/*.dfy; do
    filename=$(basename "$mutant_file")
    original_name="${filename%%__*}"
    original_file="$POS_MUT/original/${original_name}.dfy"
    if [[ ! -f "$original_file" ]]; then
        echo "Original file not found for $filename"
        continue
    fi
    diff_file="$KILLED_DIR/${filename%.dfy}.txt"
    diff "$original_file" "$mutant_file" > "$diff_file"
done

echo "Diffs generated for all killed mutants."
