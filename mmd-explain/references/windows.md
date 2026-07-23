# Windows 渲染

只在 Windows 上读取本文件。

## 检查

首次使用或渲染失败时运行：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File `
  "$HOME\.claude\skills\mmd-explain\scripts\doctor.ps1"
```

doctor 依次检查公共 CSS/配置、renderer、浏览器和字体。renderer 按以下顺序探测：

1. 环境变量 `MMD_EXPLAIN_MMDC`
2. PATH 中的 `mmdc`
3. PATH 中的 `npx`
4. PATH 中的 `pnpm`

Codex Desktop 的 bundled `pnpm` 与 Node 未必同时位于 PATH。脚本会从 `pnpm.cmd` 的相对位置
找到配套 `node.exe`，并只为本次渲染进程临时补入 PATH，不修改系统环境变量。

浏览器优先使用 `PUPPETEER_EXECUTABLE_PATH`；未设置时自动探测 Chrome、Edge 和 Brave。
Puppeteer 自带浏览器时，doctor 即使没有找到系统浏览器也只会警告。

Windows 中文优先使用 Microsoft YaHei，emoji 优先使用 Segoe UI Emoji；若本机另外安装了
Noto 字体，公共 `fonts.css` 也会优先使用。

## 渲染

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File `
  "$HOME\.claude\skills\mmd-explain\scripts\render.ps1" `
  -InputPath "{in}.mmd" -OutputPath "{out}.png"
```

可用 `-Width`、`-Height` 和 `-Scale` 覆盖默认 2400×2400@2。脚本自动创建输出目录。
不要在 Windows 上运行 `.sh` 字体安装脚本。

渲染后查看 PNG；缺字时先运行 doctor，再修本机字体或浏览器环境。
