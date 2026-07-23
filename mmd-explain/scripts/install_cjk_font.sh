#!/usr/bin/env bash
# 安装 / 互链 Noto Sans CJK SC（无需 root；不强制 CDN，CJK 包很大）。
# 用法:
#   install_cjk_font.sh
#   install_cjk_font.sh /path/to/NotoSansCJKsc-VF.ttf
#   install_cjk_font.sh --check-only
set -euo pipefail

FONT_NAME="NotoSansCJKsc-VF.ttf"
FONT_FAMILY="Noto Sans CJK SC"
USER_FONT_DIR="${HOME}/.local/share/fonts"
CONDA_MMD_FONT_DIR="${HOME}/.conda/envs/mermaid/fonts"
CONDA_FC="${HOME}/.conda/envs/mermaid/etc/fonts/fonts.conf"

check_only=false
local_font=""

for arg in "$@"; do
  case "$arg" in
    --check-only) check_only=true ;;
    -h|--help) sed -n '2,7p' "$0"; exit 0 ;;
    *) [[ -f "$arg" ]] && local_font="$arg" ;;
  esac
done

is_installed() {
  local fc_file="${1:-}"
  if [[ -n "$fc_file" && -f "$fc_file" ]]; then
    FONTCONFIG_FILE="$fc_file" fc-list 2>/dev/null | grep -qi "$FONT_FAMILY"
  else
    fc-list 2>/dev/null | grep -qi "$FONT_FAMILY"
  fi
}

if $check_only; then
  is_installed && is_installed "$CONDA_FC" && exit 0
  exit 1
fi

mkdir -p "$USER_FONT_DIR"
mkdir -p "$CONDA_MMD_FONT_DIR" 2>/dev/null || true

if [[ -n "$local_font" ]]; then
  cp "$local_font" "$USER_FONT_DIR/$FONT_NAME"
elif [[ -f "$CONDA_MMD_FONT_DIR/$FONT_NAME" && ! -e "$USER_FONT_DIR/$FONT_NAME" ]]; then
  ln -sf "$CONDA_MMD_FONT_DIR/$FONT_NAME" "$USER_FONT_DIR/$FONT_NAME"
elif [[ -f "$USER_FONT_DIR/$FONT_NAME" && -d "$CONDA_MMD_FONT_DIR" && ! -e "$CONDA_MMD_FONT_DIR/$FONT_NAME" ]]; then
  ln -sf "$USER_FONT_DIR/$FONT_NAME" "$CONDA_MMD_FONT_DIR/$FONT_NAME"
elif [[ ! -e "$USER_FONT_DIR/$FONT_NAME" && ! -e "$CONDA_MMD_FONT_DIR/$FONT_NAME" ]]; then
  cat >&2 <<EOF
未找到 $FONT_NAME。请手动放入其一后重跑:
  $USER_FONT_DIR/
  $CONDA_MMD_FONT_DIR/
或: $0 /path/to/$FONT_NAME
EOF
  exit 1
fi

# 双向确保
if [[ -f "$USER_FONT_DIR/$FONT_NAME" && -d "$CONDA_MMD_FONT_DIR" && ! -e "$CONDA_MMD_FONT_DIR/$FONT_NAME" ]]; then
  ln -sf "$USER_FONT_DIR/$FONT_NAME" "$CONDA_MMD_FONT_DIR/$FONT_NAME"
fi
if [[ -f "$CONDA_MMD_FONT_DIR/$FONT_NAME" && ! -e "$USER_FONT_DIR/$FONT_NAME" ]]; then
  ln -sf "$CONDA_MMD_FONT_DIR/$FONT_NAME" "$USER_FONT_DIR/$FONT_NAME"
fi

fc-cache -f "$USER_FONT_DIR" >/dev/null 2>&1 || true
[[ -d "$CONDA_MMD_FONT_DIR" ]] && fc-cache -f "$CONDA_MMD_FONT_DIR" >/dev/null 2>&1 || true

ok=true
is_installed || ok=false
is_installed "$CONDA_FC" || ok=false
if $ok; then
  echo "✓ $FONT_FAMILY 可用（系统 + conda fontconfig）"
else
  echo "字体文件已就位，但 fontconfig 未完全识别。试: fc-cache -fv" >&2
  exit 1
fi
