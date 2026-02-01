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
#
# Extra dev feature:
# - If the environment variable MEDIAWALKER_TEST_ERRORS=1 is set, the script
#   will also send a few deliberately bad paths through the ingest spine to
#   exercise error logging and show [INGEST-ERR] output.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

INPUT_FILE="${SCRIPT_DIR}/media_walker_input"

# Simple ANSI colors for readability
COLOR_RESET="\033[0m"
COLOR_BOLD="\033[1m"
COLOR_DIM="\033[2m"
COLOR_GREEN="\033[32m"
COLOR_DARK_GREEN="\033[32;2m"
COLOR_YELLOW="\033[33m"
COLOR_CYAN="\033[36m"
COLOR_BLUE1="\033[94m"  # lighter blue for [HOST]
COLOR_BLUE2="\033[34m"  # slightly darker blue for [INGEST-LOG]
COLOR_RED="\033[31m"
COLOR_ORANGE1="\033[38;5;208m"  # bright orange
COLOR_ORANGE2="\033[38;5;214m"  # lighter orange

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

    # Split rel_path into dir and filename for nicer coloring
    local dir_part file_part colored_path
    if [[ "$rel_path" == */* ]]; then
        dir_part="${rel_path%/*}/"
        file_part="${rel_path##*/}"
        colored_path="$(color "$dir_part" "$COLOR_GREEN")$(color "$file_part" "$COLOR_DARK_GREEN")"
    else
        colored_path="$(color "$rel_path" "$COLOR_DARK_GREEN")"
    fi

    printf "\n%s %s\n" \
        "$(color '[INGEST]' "$COLOR_GREEN")" \
        "$colored_path"

    local exit_code
    (
        cd "${PROJECT_ROOT}"
        # Suppress raw stdout/stderr from the Python call; we rely on log files instead.
        uv run python -m dev.path_ingest "${rel_path}" >/dev/null 2>&1
    )
    exit_code=$?

    # After ingest, show the latest host and ingest log lines for context
    show_last_host_dispatch
    show_last_ingest_intent

    # On non-zero exit (usage/validation errors, unexpected failures),
    # also show the last ERROR event from logs/ingest.log in orange.
    if [[ "$exit_code" -ne 0 ]]; then
        show_last_ingest_error
    fi
}

# Show the last DISPATCH line from dev/host.log (producer) in blue
show_last_host_dispatch() {
    local log_file="${PROJECT_ROOT}/dev/host.log"
    if [[ ! -f "$log_file" ]]; then
        return
    fi
    local line
    line="$(grep 'EVENT=DISPATCH' "$log_file" | tail -n 1 || true)"
    if [[ -n "$line" ]]; then
        printf "%s %s\n" \
            "$(color '[HOST]' "$COLOR_BLUE1")" \
            "$(color "$line" "$COLOR_BLUE1")"
    fi
}

# Show the last INGEST_INTENT_RECORDED line from logs/ingest.log (consumer) in another blue
# and color exists=true/false differently.
show_last_ingest_intent() {
    local log_file="${PROJECT_ROOT}/logs/ingest.log"
    if [[ ! -f "$log_file" ]]; then
        return
    fi
    local line
    line="$(grep 'EVENT=INGEST_INTENT_RECORDED' "$log_file" | tail -n 1 || true)"
    if [[ -z "$line" ]]; then
        return
    fi

    # Color exists=true/false inside the line, and make the whole line blue
    local colored_line
    colored_line="$(color "$line" "$COLOR_BLUE2")"
    colored_line="${colored_line//exists=true/$(color 'exists=true' "$COLOR_RED")}"
    colored_line="${colored_line//exists=false/$(color 'exists=false' "$COLOR_GREEN")}"

    printf "%s %s\n" \
        "$(color '[INGEST-LOG]' "$COLOR_BLUE2")" \
        "$colored_line"
}

# Show the last ERROR event from logs/ingest.log (consumer) in orange shades.
show_last_ingest_error() {
    local log_file="${PROJECT_ROOT}/logs/ingest.log"
    if [[ ! -f "$log_file" ]]; then
        return
    fi

    # Look for the last ERROR-level line
    local line
    line="$(grep 'LEVEL=ERROR' "$log_file" | tail -n 1 || true)"
    if [[ -z "$line" ]]; then
        return
    fi

    # Color the whole line in a lighter orange, and highlight EVENT=... in a brighter orange
    local colored_line
    colored_line="$(color "$line" "$COLOR_ORANGE2")"
    colored_line="${colored_line//EVENT=/$(color 'EVENT=' "$COLOR_ORANGE1")}"

    printf "%s %s\n" \
        "$(color '[INGEST-ERR]' "$COLOR_ORANGE1")" \
        "$colored_line"
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

# Deliberately exercise error paths in the ingest spine so that
# [INGEST-ERR] output is visible during development.
run_error_scenarios() {
    printf "\n%s\n" "$(color '=== mediawalker_test.sh error scenarios (dev-only) ===' "$COLOR_BOLD")"

    # 1) Directory path: should trigger VALIDATION_ERROR reason=not-a-regular-file
    local dir_path="${PROJECT_ROOT}/data/inbox"
    if [[ -d "$dir_path" ]]; then
        printf "\n%s %s\n" \
            "$(color '[ERR-TEST]' "$COLOR_ORANGE1")" \
            "$(color "ingesting directory path (expected validation error): $dir_path" "$COLOR_ORANGE2")"
        ingest_file "$dir_path"
    else
        printf "\n%s %s\n" \
            "$(color '[ERR-TEST]' "$COLOR_DIM")" \
            "$(color "skip directory error test, directory not found: $dir_path" "$COLOR_DIM")"
    fi

    # 2) Clearly bogus path: should be treated as missing file (no error, exists=false)
    #    This is included to contrast with the directory case.
    local missing_path="${PROJECT_ROOT}/data/inbox/this_file_does_not_exist_for_error_test.mp4"
    printf "\n%s %s\n" \
        "$(color '[ERR-TEST]' "$COLOR_ORANGE1")" \
        "$(color "ingesting missing file (expected exists=false, no error): $missing_path" "$COLOR_ORANGE2")"
    ingest_file "$missing_path"

    printf "\n%s\n" "$(color '=== mediawalker_test.sh error scenarios done ===' "$COLOR_BOLD")"
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

# Optional dev-only error scenarios to exercise [INGEST-ERR]
if [[ "${MEDIAWALKER_TEST_ERRORS:-0}" == "1" ]]; then
    run_error_scenarios
fi

printf "\n%s\n" "$(color '=== mediawalker_test.sh done ===' "$COLOR_BOLD")"
