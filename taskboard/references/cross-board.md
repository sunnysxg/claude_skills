# SeraCC 与无影看板路由

## 建卡落点

按任务需要在哪边执行来选看板，由 agent 判断，与 Sarah 从哪台机器提出无关。

| 需要做的事 | 建在哪 |
| --- | --- |
| 依赖无影的工作仓库、cpu005、无影 Clash 或无影看板本机部署 | 无影的对应项目 |
| todo_hub 通用改动，或排查「某卡为什么又出问题」且没有无影本机依赖 | SeraCC 的 `todo-hub`，通用测试也在那里跑 |
| 私人项目 | SeraCC 的对应项目 |

先确认目标项目 id，再在该项目查同题旧卡，沿用 [建卡规则](../SKILL.md#建卡)。两边默认显式传
`--status todo`（等待认领），原有暂存例外照常，常规跨看板建卡无需再请 Sarah 授权。
已知的同板关系随建卡提交。正文首行如需引用另一看板的来源卡，写「来自无影 TODOHUBWYY-85 的会话」
这样的看板名和裸卡号。两边独立存储，跨板来源用正文追溯。建成就告诉 Sarah 看板和新卡号，无需在来源卡发回执或同步状态。

## 用哪个入口

目标是本机看板时照常用 `taskctl`。新建跨板卡的查重与写入都走目标看板的入口。

- **无影 → SeraCC**：用无影已部署的 PowerShell 包装命令。它给生产 `taskctl` 传 `--client-pem`
  客户端证书选项，经 HTTPS 向 SeraCC 证明身份，只作用于本次调用。下例在无影运行，正文文件使用 UTF-8。

  ```powershell
  $seracc = "$env:USERPROFILE\.taskboard\seracc\taskctl-seracc.cmd"
  & $seracc issue search --project todo-hub "<关键词>"
  & $seracc issue create --project todo-hub --title "<标题>" --description-file <正文文件> --status todo
  ```

- **SeraCC → 无影**：在 SeraCC 的 `~/Projects/todo_hub` 检出根运行 `node scripts/wuying_taskboard.mjs`。
  入口经 SSH（远程登录通道）在无影本机调用生产 `taskctl`，`create` 成功直接返回卡号。

  ```powershell
  node scripts/wuying_taskboard.mjs search --project "<无影项目 id>" "<关键词>"
  node scripts/wuying_taskboard.mjs create --project "<无影项目 id>" --title "<标题>" --description-file <正文文件> --status todo
  ```

无影 SSH 入口提供 `search`、`get`、`create`。查重已发现一张应该追加评论的无影旧卡时，保留该卡并使用无影本机的写入入口处理；本轮无法在无影追加时，说明卡号和未写入的原因。失败时先看退出码和错误；跨板建卡若回包前断线，先在目标项目查重确认是否已写入，再决定是否重试。入口维护及故障排查查 todo_hub 的 `docs/agent/access.md`。

## 查历史卡

Sarah 问「我做过某某卡吗」且没限定看板时，两边各查一次，范围都是全部项目，包含已完成和取消的卡。

| 当前机器 | 查本机 | 查另一边 |
| --- | --- | --- |
| SeraCC | `taskctl issue search --all-projects <词>` | `node scripts/wuying_taskboard.mjs search <词>`，默认查无影全部项目 |
| 无影 | `taskctl issue search --all-projects <词>` | `& $seracc issue search --all-projects <词>`，证书入口查 SeraCC 全部项目 |

结果带上所属看板；任一边查询失败，说明哪一边暂时查不到。无影 SSH 搜索在远端裁剪，只返回
`identifier`（卡号）、`title`（标题）、`status`（状态）、`projectId`（项目 id）。SeraCC 确需看无影正文时，
另跑 `node scripts/wuying_taskboard.mjs get <卡号>`；确需读评论才加 `--comments`。

## 数据边界

无影工作卡的标题和卡号可以引用。无影工作项目的正文、评论及其中的业务细节留在无影，写往 SeraCC 的卡或评论时只描述 SeraCC 执行任务所需的通用问题。
在 SeraCC 只按需读取无影查询结果，不将无影工作数据写入本地文件、会话归档或缓存。

取舍记录见 todo_hub 的 `docs/decisions/202611261110-cross-board-wyy-seracc.md`。
