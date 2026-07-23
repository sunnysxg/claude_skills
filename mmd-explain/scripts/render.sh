#!/usr/bin/env bash
# mmd-explain 统一渲染入口：自动探测 mmdc、注入字体 CSS、处理集群 lib 依赖。
set -euo pipefail

usage() {
  cat <<'EOF'
用法: render.sh -i INPUT.mmd [-o OUTPUT.png] [-w WIDTH] [-H HEIGHT] [-s SCALE]

默认输出与输入同名 .png。
默认：宽 2400、高 2400、scale 2（puppeteer 像素倍率；旧默认 1200x900@1x 图过小难读）。
EOF
}

INPUT=""
OUTPUT=""
WIDTH="2400"
HEIGHT="2400"
SCALE="2"

while getopts "i:o:w:H:s:h" opt; do
  case "$opt" in
    i) INPUT="$OPTARG" ;;
    o) OUTPUT="$OPTARG" ;;
    w) WIDTH="$OPTARG" ;;
    H) HEIGHT="$OPTARG" ;;
    s) SCALE="$OPTARG" ;;
    h) usage; exit 0 ;;
    *) usage; exit 1 ;;
  esac
done

if [[ -z "$INPUT" ]]; then
  usage
  exit 1
fi

if [[ ! -f "$INPUT" ]]; then
  echo "输入文件不存在: $INPUT" >&2
  exit 1
fi

if [[ -z "$OUTPUT" ]]; then
  OUTPUT="${INPUT%.mmd}.png"
  if [[ "$OUTPUT" == "$INPUT" ]]; then
    OUTPUT="${INPUT}.png"
  fi
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
CSS_FILE="$SKILL_DIR/references/fonts.css"
CONFIG_FILE="$SKILL_DIR/references/mmd-config.json"
CONDA_ENV_NAME="${MMD_EXPLAIN_CONDA_ENV:-mermaid}"

if [[ ! -f "$CSS_FILE" || ! -f "$CONFIG_FILE" ]]; then
  echo "缺少字体配置: $CSS_FILE 或 $CONFIG_FILE" >&2
  exit 1
fi

if [[ -n "${PUPPETEER_EXECUTABLE_PATH:-}" && ! -x "$PUPPETEER_EXECUTABLE_PATH" ]]; then
  echo "PUPPETEER_EXECUTABLE_PATH 不可执行: $PUPPETEER_EXECUTABLE_PATH" >&2
  exit 1
fi

# 字体预检：CJK（中文）+ emoji。缺则告警；conda mermaid 必须能扫到
# ~/.conda/envs/mermaid/fonts/（本机先前装好的 NotoSansCJKsc-VF）或 ~/.local/share/fonts/
_check_fonts() {
  local fc_env=()
  if [[ -n "${1:-}" && -f "${1}/etc/fonts/fonts.conf" ]]; then
    fc_env=(env FONTCONFIG_FILE="${1}/etc/fonts/fonts.conf")
  fi
  if ! "${fc_env[@]}" fc-list 2>/dev/null | grep -qi 'Noto Sans CJK SC'; then
    echo "[mmd-explain] WARN: 未找到 Noto Sans CJK SC。中文会方框/缺字。" >&2
    echo "  运行: $SCRIPT_DIR/install_cjk_font.sh" >&2
    echo "  （需同时在 ~/.local/share/fonts 与 ~/.conda/envs/mermaid/fonts，并 fc-cache）" >&2
  fi
  if ! "${fc_env[@]}" fc-list 2>/dev/null | grep -qi 'Noto Color Emoji'; then
    echo "[mmd-explain] WARN: 未找到 Noto Color Emoji。可运行:" >&2
    echo "  $SCRIPT_DIR/install_emoji_font.sh" >&2
  fi
}

render_with_mmdc() {
  local mmdc_bin="$1"
  local env_prefix="${2:-}"

  _check_fonts "${env_prefix:-}"

  if [[ -n "$env_prefix" ]]; then
    # shellcheck disable=SC2086
    LD_LIBRARY_PATH="${env_prefix}/lib:${LD_LIBRARY_PATH:-}" \
      FONTCONFIG_FILE="${env_prefix}/etc/fonts/fonts.conf" \
      "$mmdc_bin" \
        -i "$INPUT" \
        -o "$OUTPUT" \
        -w "$WIDTH" \
        -H "$HEIGHT" \
        -s "$SCALE" \
        -c "$CONFIG_FILE" \
        -C "$CSS_FILE" \
        -b white \
        -q
  else
    "$mmdc_bin" \
      -i "$INPUT" \
      -o "$OUTPUT" \
      -w "$WIDTH" \
      -H "$HEIGHT" \
      -s "$SCALE" \
      -c "$CONFIG_FILE" \
      -C "$CSS_FILE" \
      -b white \
      -q
  fi
}

# 显式本机覆盖优先，但不写入 Git。
if [[ -n "${MMD_EXPLAIN_MMDC:-}" ]]; then
  if [[ -x "$MMD_EXPLAIN_MMDC" ]]; then
    render_with_mmdc "$MMD_EXPLAIN_MMDC"
    echo "$OUTPUT"
    exit 0
  elif command -v "$MMD_EXPLAIN_MMDC" >/dev/null 2>&1; then
    render_with_mmdc "$(command -v "$MMD_EXPLAIN_MMDC")"
    echo "$OUTPUT"
    exit 0
  else
    echo "MMD_EXPLAIN_MMDC 不可执行或不在 PATH: $MMD_EXPLAIN_MMDC" >&2
    exit 1
  fi
fi

# 优先 conda renderer（集群上 PATH 的 mmdc 常缺 libatk）。
if command -v conda >/dev/null 2>&1 &&
    conda env list 2>/dev/null | awk '{print $1}' | grep -Fxq "$CONDA_ENV_NAME"; then
  CONDA_PREFIX="$(conda run -n "$CONDA_ENV_NAME" bash -c 'echo "$CONDA_PREFIX"')"
  MMDC_BIN="$CONDA_PREFIX/bin/mmdc"
  if [[ -x "$MMDC_BIN" ]]; then
    render_with_mmdc "$MMDC_BIN" "$CONDA_PREFIX"
    echo "$OUTPUT"
    exit 0
  fi
fi

if command -v mmdc >/dev/null 2>&1; then
  if render_with_mmdc "$(command -v mmdc)"; then
    echo "$OUTPUT"
    exit 0
  fi
fi

if command -v npx >/dev/null 2>&1; then
  _check_fonts
  npx -y @mermaid-js/mermaid-cli \
    -i "$INPUT" \
    -o "$OUTPUT" \
    -w "$WIDTH" \
    -H "$HEIGHT" \
    -s "$SCALE" \
    -c "$CONFIG_FILE" \
    -C "$CSS_FILE" \
    -b white \
    -q
  echo "$OUTPUT"
  exit 0
fi

if command -v pnpm >/dev/null 2>&1; then
  _check_fonts
  pnpm dlx @mermaid-js/mermaid-cli \
    -i "$INPUT" \
    -o "$OUTPUT" \
    -w "$WIDTH" \
    -H "$HEIGHT" \
    -s "$SCALE" \
    -c "$CONFIG_FILE" \
    -C "$CSS_FILE" \
    -b white \
    -q
  echo "$OUTPUT"
  exit 0
fi

echo "未找到 mmdc / conda mermaid / npx / pnpm，无法渲染 PNG" >&2
exit 1
