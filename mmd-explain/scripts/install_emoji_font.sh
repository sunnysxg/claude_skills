#!/usr/bin/env bash
# 安装 Noto Color Emoji 到用户字体目录（无需 root）。
# 用法:
#   install_emoji_font.sh              # 自动从 CDN 下载（集群可访问时）
#   install_emoji_font.sh /path/to/NotoColorEmoji.ttf  # 使用本地字体文件
#   install_emoji_font.sh --check-only # 仅检查是否已安装
set -euo pipefail

FONT_NAME="NotoColorEmoji.ttf"
FONT_FAMILY="Noto Color Emoji"
USER_FONT_DIR="${HOME}/.local/share/fonts"
CONDA_MMD_FONT_DIR="${HOME}/.conda/envs/mermaid/fonts"
CDN_URL="https://cdn.jsdelivr.net/gh/googlefonts/noto-emoji@main/fonts/NotoColorEmoji.ttf"

check_only=false
local_font=""

for arg in "$@"; do
  case "$arg" in
    --check-only) check_only=true ;;
    -h|--help)
      sed -n '2,6p' "$0"
      exit 0
      ;;
    *)
      if [[ -f "$arg" ]]; then
        local_font="$arg"
      fi
      ;;
  esac
done

is_installed() {
  fc-list | grep -qi "$FONT_FAMILY"
}

if $check_only; then
  if is_installed; then
    exit 0
  fi
  exit 1
fi

mkdir -p "$USER_FONT_DIR"

if [[ -n "$local_font" ]]; then
  cp "$local_font" "$USER_FONT_DIR/$FONT_NAME"
  echo "已安装本地字体: $local_font -> $USER_FONT_DIR/$FONT_NAME"
elif [[ -f "$USER_FONT_DIR/$FONT_NAME" ]]; then
  echo "字体已存在: $USER_FONT_DIR/$FONT_NAME"
else
  echo "从 CDN 下载 $FONT_FAMILY ..."
  if ! curl -fsSL --connect-timeout 10 --max-time 120 \
      -o "$USER_FONT_DIR/$FONT_NAME" "$CDN_URL"; then
    cat >&2 <<EOF
下载失败。请手动获取 NotoColorEmoji.ttf 后执行:
  $0 /path/to/NotoColorEmoji.ttf

下载地址（任选其一）:
  $CDN_URL
  https://github.com/googlefonts/noto-emoji/raw/main/fonts/NotoColorEmoji.ttf
EOF
    exit 1
  fi
  echo "已下载到 $USER_FONT_DIR/$FONT_NAME"
fi

# 与 mermaid conda 环境共用（CJK 字体同目录，方便 headless 渲染）
if [[ -d "$CONDA_MMD_FONT_DIR" ]]; then
  ln -sf "$USER_FONT_DIR/$FONT_NAME" "$CONDA_MMD_FONT_DIR/$FONT_NAME"
  fc-cache -f "$CONDA_MMD_FONT_DIR" >/dev/null 2>&1 || true
fi

fc-cache -f "$USER_FONT_DIR" >/dev/null 2>&1 || true

CONDA_FC="${HOME}/.conda/envs/mermaid/etc/fonts/fonts.conf"
is_installed_fc() {
  local fc_file="${1:-}"
  if [[ -n "$fc_file" && -f "$fc_file" ]]; then
    FONTCONFIG_FILE="$fc_file" fc-list 2>/dev/null | grep -qi "$FONT_FAMILY"
  else
    fc-list 2>/dev/null | grep -qi "$FONT_FAMILY"
  fi
}

if is_installed_fc && { [[ ! -f "$CONDA_FC" ]] || is_installed_fc "$CONDA_FC"; }; then
  echo "✓ $FONT_FAMILY 已可用"
  fc-list | grep -i "$FONT_FAMILY" | head -1
else
  echo "字体文件已复制，但 fontconfig 尚未识别（检查系统与 conda FONTCONFIG）。可尝试: fc-cache -fv ~/.local/share/fonts" >&2
  exit 1
fi
