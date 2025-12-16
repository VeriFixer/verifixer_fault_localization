# --- Configuration ---

# 1. Determine the absolute path of the directory where the script is run
# This is the project root (e.g., /home/ricostynha/Desktop/verifixer_fault_localization)
SCRIPT_BASE_DIR="$(pwd)"

# The relative paths provided by the user:
RELATIVE_DATASET_DIR="dataset/base_dataset_for_mutdafny"
RELATIVE_TARGET_SCRIPT="mutdafny/run.sh"
RELATIVE_TARGET_SCRIPT_DIR="mutdafny"

# 2. Convert relative paths to absolute paths
DATASET_DIR="${SCRIPT_BASE_DIR}/${RELATIVE_DATASET_DIR}"
TARGET_SCRIPT="${SCRIPT_BASE_DIR}/${RELATIVE_TARGET_SCRIPT}"
TARGET_SCRIPT_DIR="${SCRIPT_BASE_DIR}/${RELATIVE_TARGET_SCRIPT_DIR}"

# --- Main Logic ---

echo "Starting dataset processing..."
echo "Absolute Target script: ${TARGET_SCRIPT}"
echo "Absolute Dataset directory: ${DATASET_DIR}"
echo "Execution directory for mutdafny: ${SCRIPT_BASE_DIR}"

# Check directories and permissions (Checks remain valid)
if [ ! -d "$DATASET_DIR" ] || [ ! -x "$TARGET_SCRIPT" ]; then
    echo "Error: Directory or script check failed."
    exit 1
fi

# Iterate over all files and directories inside the DATASET_DIR
for item in "$DATASET_DIR"/*; do
    # $item contains the absolute path to the data file.
    
    echo "--- Processing: $(basename "$item") (Absolute Path: $item) ---"
    
    # 4. CRUCIAL FIX: Run the command inside a subshell
    # The subshell:
    # a) Executes 'cd "$SCRIPT_BASE_DIR"' to move to the project root.
    # b) Executes the target script, passing the absolute data file path ($item).
    # c) Automatically exits the subshell, returning the main script to the original directory (though PWD is the same here).
    
    (
        cd "$TARGET_SCRIPT_DIR" || exit 1 # Move to project root where Dafny and mutdafny are found
        
        # Execute run.sh with the absolute path of the item
        "$TARGET_SCRIPT" "$item"
        
    ) # End of subshell

    # Check the exit status of the TARGET_SCRIPT (stored in the subshell's exit code $?)
    if [ $? -ne 0 ]; then
        echo "Warning: ${TARGET_SCRIPT} failed for item $item (Exit Code: $?)"
    fi
    
done

echo "Processing complete."