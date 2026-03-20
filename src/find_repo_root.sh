#!/usr/bin/env bash
find_repo_root() {
    local marker="${1:-.repo_verifixer_fault_localization_marker}"
    local dir

    dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"

    while [[ "$dir" != "/" ]]; do
        if [[ -e "$dir/$marker" ]]; then
            echo "$dir"
            return 0
        fi
        dir="$(dirname "$dir")"
    done

    echo "Error: Could not find repository root (marker: $marker)" >&2
    return 1
}