#!/usr/bin/env bash
# Experimental: mediawalker_test.sh
#
# This script is a development-only helper to populate ingest_log by walking
# files and folders and firing the existing ingestion spine.
#
# Scope:
# - Runs locally (pre-project) on the host.
# - Calls the Python producer stub: dev.path_ingest
# - Filters files by extension: .mp4, .jpg, .nfo
# - Does NOT implement any library_items or media-unit logic.
#
# Input priority:
# 1. If one or more PATH arguments are provided, they are treated as files or
#    folders to walk. The media_walker_input file is ignored.
# 2. If no arguments are provided, the script reads dev/mediawalker_test/media_walker_input
#    and treats each non-comment, non-empty line as a file or folder to walk.
#
# This script is experimental and NOT part of the ingestion contract.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

INPUT_FILE="${SCRIPT_DIR}/media_walker_input"

# Simple ANSI colors for readability
COLOR_RESET="\033[0m"
COLOR_BOLD="\033[1m"
COLOR_DIM="\033[2m"
COLOR_GREEN="\033[32m"
COLOR_YELLOW="\033[33m"
COLOR_CYAN="\033[36m"

color() {
    # usage: color "TEXT" "$COLOR_CODE"
    printf "%b%s%b" "$2" "$1" "$COLOR_RESET"
}

# File extensions to include (lowercase, without dot)
INCLUDE_EXTENSIONS=("mp4" "jpg" "nfo")

# Helper: check if a filename has an included extension
has_included_extension() {
    local path="$1"
    local filename ext
    filename="$(basename -- "$path")"
    ext="${filename##*.}"
    ext="${ext,,}"  # to lowercase (bash 4+)
    for inc in "${INCLUDE_EXTENSIONS[@]}"; do
        if [[ "$ext" == "$inc" ]]; then
            return 0
        fi
    done
    return 1
}

# Helper: call the Python producer stub for a single file path
ingest_file() {
    local abs_path="$1"

    # Compute path relative to project root, to match existing dev usage
    local rel_path
    rel_path="$(realpath --relative-to="${PROJECT_ROOT}" "$abs_path")"

    printf "\n%s %s\n" \
        "$(color '[INGEST]' "$COLOR_GREEN")" \
        "$(color "$rel_path" "$COLOR_CYAN")"

    # Local dev: call the producer stub directly via uv
    # NOTE: In final Unraid deployment, this will be replaced by a docker exec
    # into the container, not a direct uv call on the host.
    (
        cd "${PROJECT_ROOT}"
        uv run python -m dev.path_ingest "${rel_path}"
    )
}

# Walk a single path (file or directory)
walk_path() {
    local path="$1"

    if [[ -d "$path" ]]; then
        printf "\n%s %s\n" \
            "$(color '[DIR]' "$COLOR_BOLD")" \
            "$(color "$path" "$COLOR_CYAN")"

        # Directory: recurse and ingest matching files
        while IFS= read -r -d '' file; do
            if has_included_extension "$file"; then
                ingest_file "$file"
            else
                printf "\n%s %s\n" \
                    "$(color '[SKIP]' "$COLOR_DIM")" \
                    "$(color "$file (extension not included)" "$COLOR_DIM")"
            fi
        done < <(find "$path" -type f -print0)
    elif [[ -f "$path" ]]; then
        # Single file
        if has_included_extension "$path"; then
            ingest_file "$path"
        else
            printf "\n%s %s\n" \
                "$(color '[SKIP]' "$COLOR_DIM")" \
                "$(color "$path (extension not included)" "$COLOR_DIM")"
        fi
    else
        printf "\n%s %s\n" \
            "$(color '[WARN]' "$COLOR_YELLOW")" \
            "$(color "path does not exist or is not a regular file/directory: $path" "$COLOR_YELLOW")" >&2
    fi
}

# Determine input paths
declare -a PATHS=()

if [[ "$#" -gt 0 ]]; then
    # Use CLI arguments as paths
    for arg in "$@"; do
        PATHS+=("$arg")
    done
else
    # No args: fall back to media_walker_input
    if [[ ! -f "$INPUT_FILE" ]]; then
        printf "%s\n" \
            "$(color "Error: no arguments provided and input file not found: $INPUT_FILE" "$COLOR_YELLOW")" >&2
        exit 1
    fi

    while IFS= read -r line; do
        # Skip empty lines and comments
        [[ -z "$line" ]] && continue
        [[ "$line" =~ ^# ]] && continue
        PATHS+=("$line")
    done < "$INPUT_FILE"
fi

# Process all paths
printf "%s\n" "$(color '=== mediawalker_test.sh starting ===' "$COLOR_BOLD")"

for p in "${PATHS[@]}"; do
    # Interpret paths relative to project root if they are not absolute
    if [[ "$p" = /* ]]; then
        walk_path "$p"
    else
        walk_path "${PROJECT_ROOT}/${p}"
    fi
done

printf "\n%s\n" "$(color '=== mediawalker_test.sh done ===' "$COLOR_BOLD")"
