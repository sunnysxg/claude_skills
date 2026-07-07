#!/usr/bin/env bash
# mmd-explain 统一渲染入口：自动探测 mmdc、注入字体 CSS、处理集群 lib 依赖。
set -euo pipefail

usage() {
  cat <<'EOF'
用法: render.sh -i INPUT.mmd [-o OUTPUT.png] [-w WIDTH] [-H HEIGHT]

默认输出与输入同名 .png；宽 1200、高 900。
EOF
}

INPUT=""
OUTPUT=""
WIDTH="1200"
HEIGHT="900"

while getopts "i:o:w:H:h" opt; do
  case "$opt" in
    i) INPUT="$OPTARG" ;;
    o) OUTPUT="$OPTARG" ;;
    w) WIDTH="$OPTARG" ;;
    H) HEIGHT="$OPTARG" ;;
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

if [[ ! -f "$CSS_FILE" || ! -f "$CONFIG_FILE" ]]; then
  echo "缺少字体配置: $CSS_FILE 或 $CONFIG_FILE" >&2
  exit 1
fi

# 确保用户级 emoji 字体已注册（幂等，不报错）
if [[ -x "$SCRIPT_DIR/install_emoji_font.sh" ]]; then
  "$SCRIPT_DIR/install_emoji_font.sh" --check-only 2>/dev/null || true
fi

render_with_mmdc() {
  local mmdc_bin="$1"
  local env_prefix="${2:-}"

  if [[ -n "$env_prefix" ]]; then
    # shellcheck disable=SC2086
    LD_LIBRARY_PATH="${env_prefix}/lib:${LD_LIBRARY_PATH:-}" \
      FONTCONFIG_FILE="${env_prefix}/etc/fonts/fonts.conf" \
      "$mmdc_bin" \
        -i "$INPUT" \
        -o "$OUTPUT" \
        -w "$WIDTH" \
        -H "$HEIGHT" \
        -c "$CONFIG_FILE" \
        -C "$CSS_FILE" \
        -q
  else
    "$mmdc_bin" \
      -i "$INPUT" \
      -o "$OUTPUT" \
      -w "$WIDTH" \
      -H "$HEIGHT" \
      -c "$CONFIG_FILE" \
      -C "$CSS_FILE" \
      -q
  fi
}

# 优先 conda mermaid（集群上 PATH 的 mmdc 常缺 libatk）
if command -v conda >/dev/null 2>&1 && conda env list 2>/dev/null | awk '{print $1}' | grep -qx mermaid; then
  CONDA_PREFIX="$(conda run -n mermaid bash -c 'echo "$CONDA_PREFIX"')"
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
  npx -y @mermaid-js/mermaid-cli \
    -i "$INPUT" \
    -o "$OUTPUT" \
    -w "$WIDTH" \
    -H "$HEIGHT" \
    -c "$CONFIG_FILE" \
    -C "$CSS_FILE" \
    -q
  echo "$OUTPUT"
  exit 0
fi

echo "未找到 mmdc / conda mermaid / npx，无法渲染 PNG" >&2
exit 1
