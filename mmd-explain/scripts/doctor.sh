#!/usr/bin/env bash
# Read-only Linux dependency check for mmd-explain.
set -euo pipefail

[[ "$(uname -s)" == "Linux" ]] || {
  echo "ERROR: doctor.sh is for Linux only" >&2
  exit 1
}

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
skill_dir="$(cd -- "$script_dir/.." && pwd -P)"
conda_env_name="${MMD_EXPLAIN_CONDA_ENV:-mermaid}"
status=0
conda_prefix=""

ok() {
  printf 'OK   %s\n' "$1"
}

warn() {
  printf 'WARN %s\n' "$1" >&2
}

fail() {
  printf 'FAIL %s\n' "$1" >&2
  status=1
}

for required in "$skill_dir/references/fonts.css" "$skill_dir/references/mmd-config.json"; do
  if [[ -f "$required" ]]; then
    ok "$required"
  else
    fail "missing file: $required"
  fi
done

renderer=""
if [[ -n "${MMD_EXPLAIN_MMDC:-}" ]]; then
  if [[ -x "$MMD_EXPLAIN_MMDC" ]]; then
    renderer="$MMD_EXPLAIN_MMDC"
  elif command -v "$MMD_EXPLAIN_MMDC" >/dev/null 2>&1; then
    renderer="$(command -v "$MMD_EXPLAIN_MMDC")"
  else
    fail "MMD_EXPLAIN_MMDC is not executable or on PATH: $MMD_EXPLAIN_MMDC"
  fi
elif command -v conda >/dev/null 2>&1 &&
    conda env list 2>/dev/null | awk '{print $1}' | grep -Fxq "$conda_env_name"; then
  conda_prefix="$(conda run -n "$conda_env_name" bash -c 'echo "$CONDA_PREFIX"')"
  [[ -x "$conda_prefix/bin/mmdc" ]] && renderer="$conda_prefix/bin/mmdc"
elif command -v mmdc >/dev/null 2>&1; then
  renderer="$(command -v mmdc)"
elif command -v npx >/dev/null 2>&1; then
  renderer="$(command -v npx) -y @mermaid-js/mermaid-cli"
elif command -v pnpm >/dev/null 2>&1; then
  renderer="$(command -v pnpm) dlx @mermaid-js/mermaid-cli"
fi

if [[ -n "$renderer" ]]; then
  ok "renderer: $renderer"
else
  fail "no renderer found (MMD_EXPLAIN_MMDC, conda, mmdc, npx, or pnpm)"
fi

if [[ -n "${PUPPETEER_EXECUTABLE_PATH:-}" ]]; then
  if [[ -x "$PUPPETEER_EXECUTABLE_PATH" ]]; then
    ok "browser override: $PUPPETEER_EXECUTABLE_PATH"
  else
    fail "PUPPETEER_EXECUTABLE_PATH is not executable: $PUPPETEER_EXECUTABLE_PATH"
  fi
else
  for browser in google-chrome google-chrome-stable chromium chromium-browser; do
    if command -v "$browser" >/dev/null 2>&1; then
      ok "system browser: $(command -v "$browser")"
      break
    fi
  done
fi

if ! command -v fc-list >/dev/null 2>&1; then
  fail "fc-list is required for font validation"
else
  font_env=()
  if [[ -n "$conda_prefix" && -f "$conda_prefix/etc/fonts/fonts.conf" ]]; then
    font_env=(env FONTCONFIG_FILE="$conda_prefix/etc/fonts/fonts.conf")
  fi
  if "${font_env[@]}" fc-list 2>/dev/null | grep -qi 'Noto Sans CJK SC'; then
    ok "font: Noto Sans CJK SC"
  else
    fail "font missing: Noto Sans CJK SC; run install_cjk_font.sh"
  fi
  if "${font_env[@]}" fc-list 2>/dev/null | grep -qi 'Noto Color Emoji'; then
    ok "font: Noto Color Emoji"
  else
    fail "font missing: Noto Color Emoji; run install_emoji_font.sh"
  fi
fi

if ((status == 0)); then
  ok "mmd-explain Linux environment is ready"
else
  warn "fix the failed checks before trusting rendered PNG files"
fi
exit "$status"
