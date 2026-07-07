#!/usr/bin/env bash
# 将 ~/.claude/skills 同步到 ~/.cursor/skills（符号链接，单一事实源在 claude_skills repo）。
# Cursor 只扫描 ~/.cursor/skills/，不会自动读 ~/.claude/skills/。
set -euo pipefail

CLAUDE_SKILLS="${HOME}/.claude/skills"
CURSOR_SKILLS="${HOME}/.cursor/skills"

usage() {
  cat <<'EOF'
用法: sync_cursor_skills.sh [--dry-run]

为每个 ~/.claude/skills/<name>/ 在 ~/.cursor/skills/ 创建符号链接（已存在且指向别处则跳过）。
Cursor 专属 skill（如 factorhub-handadd）保持原目录不动。
EOF
}

dry_run=false
[[ "${1:-}" == "--dry-run" ]] && dry_run=true

if [[ ! -d "$CLAUDE_SKILLS" ]]; then
  echo "未找到 $CLAUDE_SKILLS" >&2
  exit 1
fi

mkdir -p "$CURSOR_SKILLS"

linked=0
skipped=0

for entry in "$CLAUDE_SKILLS"/*; do
  [[ -d "$entry" ]] || continue
  name="$(basename "$entry")"

  # 仓库元数据 / 非 skill 目录
  case "$name" in
    global|.git|scripts) continue ;;
  esac

  # 只同步含 SKILL.md 的目录
  [[ -f "$entry/SKILL.md" ]] || continue

  # 已有同名真实目录（Cursor 专属 skill）不覆盖
  target="$CURSOR_SKILLS/$name"
  if [[ -e "$target" && ! -L "$target" ]]; then
    echo "跳过（Cursor 专属目录）: $name"
    skipped=$((skipped + 1))
    continue
  fi

  # 已指向正确位置
  if [[ -L "$target" ]]; then
    current="$(readlink -f "$target" 2>/dev/null || readlink "$target")"
    expected="$(readlink -f "$entry")"
    if [[ "$current" == "$expected" ]]; then
      echo "已同步: $name"
      skipped=$((skipped + 1))
      continue
    fi
    if $dry_run; then
      echo "将更新链接: $name ($current -> $expected)"
    else
      rm "$target"
      ln -s "$entry" "$target"
      echo "已更新链接: $name"
    fi
    linked=$((linked + 1))
    continue
  fi

  if $dry_run; then
    echo "将创建链接: $name -> $entry"
  else
    ln -s "$entry" "$target"
    echo "已创建链接: $name"
  fi
  linked=$((linked + 1))
done

# 兼容旧名：mmdexplain（无连字符）若仅有 mmd-explain 则补一条
if [[ -d "$CLAUDE_SKILLS/mmd-explain" && ! -e "$CURSOR_SKILLS/mmdexplain" ]]; then
  if $dry_run; then
    echo "将创建链接: mmdexplain -> $CLAUDE_SKILLS/mmd-explain"
  else
    ln -s "$CLAUDE_SKILLS/mmd-explain" "$CURSOR_SKILLS/mmdexplain"
    echo "已创建链接: mmdexplain"
  fi
  linked=$((linked + 1))
fi

echo "---"
echo "新建/更新: $linked, 跳过: $skipped"
echo "Cursor skills 目录: $CURSOR_SKILLS"
ls -la "$CURSOR_SKILLS"
