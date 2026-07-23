#!/usr/bin/env bash
# Backward-compatible Cursor-only entry point.
set -euo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
exec bash "$script_dir/sync_skills.sh" --client cursor "$@"
