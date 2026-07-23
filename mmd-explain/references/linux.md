# Linux 渲染

只在 Linux 上读取本文件。

## 检查

首次使用、环境变化或渲染失败时运行：

```bash
~/.claude/skills/mmd-explain/scripts/doctor.sh
```

renderer 按以下顺序探测：

1. 环境变量 `MMD_EXPLAIN_MMDC`
2. conda 环境 `mermaid`；可用 `MMD_EXPLAIN_CONDA_ENV` 改名
3. PATH 中的 `mmdc`
4. PATH 中的 `npx`
5. PATH 中的 `pnpm`

如果设置了 `PUPPETEER_EXECUTABLE_PATH`，doctor 会校验目标浏览器是否存在。

## 字体

Linux headless Chromium 需要 fontconfig 能看到中文与 emoji 字体。cpfs/conda 环境使用：

| 字体 | 用途 | 安装脚本 |
|---|---|---|
| Noto Sans CJK SC | 中文 | `scripts/install_cjk_font.sh` |
| Noto Color Emoji | emoji | `scripts/install_emoji_font.sh` |

```bash
~/.claude/skills/mmd-explain/scripts/install_cjk_font.sh
~/.claude/skills/mmd-explain/scripts/install_emoji_font.sh
~/.claude/skills/mmd-explain/scripts/doctor.sh
```

脚本把字体放在用户 fontconfig 目录，并在存在 conda `mermaid` 字体目录时建立共享链接。
CJK 字体包较大，安装脚本不自动从 CDN 下载；传入已有字体路径即可。

## 渲染

```bash
~/.claude/skills/mmd-explain/scripts/render.sh -i "{in}.mmd" -o "{out}.png"
```

可用 `-w`、`-H` 与 `-s` 覆盖默认 2400×2400@2。渲染后查看 PNG；doctor 或 renderer 的字体
告警不能忽略。
