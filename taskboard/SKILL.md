---
name: taskboard
description: 操作中央看板（用户说 todo、看板、面板，或派遣 prompt 里的 e-taskboard）：读卡、认领、改状态、评论、建卡、关联，全部走 taskctl CLI。当输入含卡片编号（如 TODOHUB-3）、被派遣「处理任务面板任务」、要把工作结果回写看板、或发现了值得记录的新待办时使用本 skill。
---

# taskboard — 操作中央看板

待办的事实源是本机看板（todo_hub 仓 `dashi-taskboard/` 里的 dashi fork）。一切读写走 `taskctl`，
消费它的 JSON 输出。卡片编号以看板或 prompt 给出的为准，不猜、不派生、不改写前缀——编号错了
会把工作记到别人的卡上。

**判成功要看 `error` 字段或退出码，不能只看输出能否解析**：用法错误、版本冲突返回的同样是合法
JSON，`JSON.parse` 成功不代表写进去了。管道里包一层解析脚本时尤其容易把失败读成成功。

## 调用方式

```
taskctl <子命令>
```

`taskctl` 已在 PATH。找不到 = 该机没跑过 `board.ps1 install`，降级用显式路径，**写正斜杠**：

```
node C:/Users/sarah/.taskboard/app/dashi-taskboard/cli/taskctl.mjs <子命令>
```

exit code 3 = 看板服务没在跑。跑一次幂等拉起再重试，**不要自己 `npm start`**——那是拿开发代码
配空数据库冒充生产：

```
powershell -NoProfile -ExecutionPolicy Bypass -File C:/Users/sarah/Projects/todo_hub/scripts/board.ps1 ensure
```

- 命令语法用到哪节读哪节：[references/cli.md](references/cli.md)（上游原文）
- 本 fork 独有的命令与参数（`dispatch`、`--mode`、`--agent`…）：[references/fork-cli.md](references/fork-cli.md)
- 分区语义与交付纪律以本文为准，cli.md 只管语法

## 会话归属与写入方标识

每个写操作都要归属到一个会话，否则看板认不出这张卡是谁在做、「查看对话」也打不开。

- Codex 内自动读 `CODEX_THREAD_ID`。
- Claude Code 内：桌面 App 里跑时取 `CLAUDE_CODE_HOST_SESSION_ID`（侧栏那行编号去掉 `local_`
  前缀），终端裸跑才取 `CLAUDE_CODE_SESSION_ID`。两者都不用显式传。**顺序不能反**——
  `claude://resume?session=` 只认宿主 id，拿 CLI id 会导入成一条无标题的重复记录。
- 取不到的环境（Cursor 等）显式传 `--thread-id <当前会话 UUID>`；再取不到就用
  `claude-YYYYMMDDHHMM` 一次性 id，同一会话从一而终。
- 写入方标识 `--agent codex|claude` 决定看板画哪个图标、深链怎么开。有 `CODEX_THREAD_ID` 自动记
  codex，有 `CLAUDE_CODE_SESSION_ID` 自动记 claude，都没有默认 codex——所以 **Cursor 会话必须
  显式带 `--agent claude`**。

读操作不需要归属。

## 分区：每一列装什么

界面文案是上游的中文，字段值是英文，写命令用字段值。**判据一栏是归位的唯一依据**——只看判据
就能定位，不靠「这个她大概想看吧」的感觉。

| 字段值 | 界面 | 这一列装什么（判据） | 球在谁手上 |
|---|---|---|---|
| `backlog` | 待立项 | 还没获授权的想法，允许不完整，可以只是一句话种子 | Sarah |
| `todo` | 等待认领 | 已授权、描述里的 `## 验收标准` 自包含、现在就能开工 | 下一个会话 |
| `in_progress` | 处理中 | 已绑定某个具体会话，那个会话正在做 | 那个会话 |
| `in_review` | 等你确认 | 成果已交付：生产卡已上线等她过目，开发卡候选待她放行 | Sarah |
| `blocked` | 遇到阻碍 | 做不下去，要外部输入才能继续：等她拍板、等外部依赖、等 blocker 卡 | Sarah 或外部 |
| `done` | 完成 | 她点过「完成」；对开发卡这一下同时是放行上线 | 无 |
| `canceled` | 取消 | 不做了 | 无 |

流转规则：

- **`done` 只由 Sarah 点，agent 永远不点**。她要过一眼每张做完的卡；agent 自己点，她就得去完成
  列里考古哪些是新的。`deliver`（直接交付）说的是这张卡不需要边做边讨论，**不是授权 agent 替她
  确认**。
- **进 `todo` 的门槛是自包含的 `## 验收标准`**：只看这一节就能知道任务的对象与场景、外部结果、
  边界和逐项判定方式，不拿实现方案或「测试通过」冒充需求。各项默认 agent 验收，只有显式标
  `[Sarah]` 的交给她——`[Sarah]` 只表达「这项由她验」，不决定上不上线（那是目的地的事）。共识
  散在评论里的先归并回描述，评论留作历史。
- **`backlog` 可以只是种子**，门槛只在进 `todo` 或获得实施授权前生效。授权是她明确说的，
  assignee 是谁不算授权。
- **等她的卡必须停在她会看的列**：等确认 = `in_review`，要她拍板才能继续 = `blocked`。不要把等
  她的卡留在 `backlog` 指望被看到。共同讨论往来还在会话里时留 `in_progress` 属正常；但会话要
  结束而球在她手上时，挪 `blocked` 并评论——别指望那个对话她还开着。

## 目的地：成果去哪

每张卡有「目的地」字段（`destination`）：`production` 生产（默认）/ `dev` 开发，与推进方式正交。
项目级默认可配。它决定交付后成果落在哪、她点完成时发生什么：

- **生产**：交付时系统直接把候选合并进 main、push、部署，卡进「等你确认」时成果已在线上；她点
  完成 = 纯归档。
- **开发**：候选由系统合入 dev 集成分支，她在常驻 dev 实例上验；点完成 = 放行，触发合并上线。
- **agent 不改这个字段**：建卡时可设（不传 = 生产），之后觉得该改就评论提议，改不改她定。
- 收口时机跟目的地走，见核心纪律第 6、7 条。

## 推进方式

`advanceMode` 是卡片字段，和分区、目的地都正交：`deliver` 直接交付（默认）/ `discuss` 共同
讨论。建出来的卡默认 `deliver`；需要她参与才能成形的，建卡时用 `--mode discuss` 标成共同讨论
——自动派发只领 `deliver` 的 `todo`，`discuss` 卡永远等人手动派。

## 核心纪律

1. **已有卡先 `issue get` + `comment list`**，读完描述和最新评论再决定动不动——评论是现行需求，
   含打回重做。评论说等待／别执行时，停下汇报，不改状态。

2. **认领**：可开工的 `todo` 带当前 `version` 挪 `in_progress`，成功之前不继续。已是
   `in_progress` 的卡只有绑定当前会话才继续，**别的会话认领的卡永远不碰**——两个会话同时写同
   一张卡会互相覆盖。

3. **版本冲突**：重新 `issue get` + `comment list`，仅当它仍是可认领的 `todo`、未绑他会话、未
   归档、描述评论都没变时，用新 version 重试一次；否则停下汇报，不循环抢占。

4. **建卡**：先 `context current` + 搜现有卡，能更新就不新建重复卡；琐碎请求不上板；粒度按
   todo_convention.md（一个会话能做完为界）。建 `backlog` 可以只写待讨论的种子；直接建 `todo`
   要同时满足验收标准门槛。

5. **工作树**：要改仓库代码的卡，认领后先进独立 worktree／分支再动代码（并行纪律与生命周期见
   git-workflow skill 的 git.md），并登记进卡片：`issue update --worktree-path PATH
   --worktree-branch BRANCH`（只有分支时用 `--git-branch`）。卡已绑定的，这张卡的活只在里面做。
   自己开的树目录名 = 卡号原样 + 随机后缀（`TODOHUB-38-a1b2c3`），不用默认随机名——名字要能
   一眼看出是哪张卡的。托管工具会给**分支**加自己的前缀（Claude `worktree-`、Codex `codex/`），
   看板上分支名带前缀属正常，不要去「修正」。会话启动时就已在托管树里的不改名。

6. **交付**：做完自验后——
   - 生产卡**先做知识收口**（`neat-freak` → `session-log` → `zettel-distill` 提案），把收口改动
     一并 commit——交付后系统直接上线，不会再回到这个会话；开发卡**不收口**，等完成 hook——她
     可能打回迭代，提前收口白做。
   - 交付物的机制或原理不是一眼能懂、需要她理解才能验收（机制类、流程类、不可见的后端行为类）
     时，做一页**原理留档页**：静态单页进看板仓 `dashi-taskboard/web/public/notes/`，文件名
     snake_case 带卡号，视觉按帮助页 token、内联主题联动脚本（样板
     `todohub_92_decisions_merge.html`），随候选同笔 commit——生产卡交付即随部署上线，链接立即
     可用。交付评论给两条链接（本机 `http://127.0.0.1:47823/notes/…` + 手机
     `https://todo.54.153.185.138.sslip.io/notes/…`）和一两句结论摘要。留档页是单卡验收材料，
     不进正式帮助页；UI 效果类改动不做——效果本身可见。不用 Claude Artifact 或评论附件交
     验收材料（拍板见 todo_hub decisions.md）。
   - 把本卡成果 commit 成干净候选并**保留工作树**；**不自行 merge / push / deploy / 收树**，两种
     目的地都由服务端落位，worker 动手会和它打架。
   - 生产卡挪 `in_review` 之后**立刻退出候选树**（起过 dev 实例的先杀整棵进程树、`cmd /c rmdir` 单删
     `node_modules` junction）：发布 saga 在交付当时就回收这棵树，会话还占着它就会一直收不掉。
   - 顺带速扫全板 open 卡标题：疑似被本次工作顺带解决的，能指认具体改动覆盖其需求就在那张卡
     评论证据并挪 `in_review` 等她裁决，仅有怀疑只评论。不替她把别人的卡设 done/canceled。
   - 交付评论固定头两行，然后逐验收项写结果与证据：

     ```
     做了啥：<一句话>
     要你干啥：纯归档（已上线）／点完成上线／先按下面步骤验：…
     ```

     有 `[Sarah]` 项的，逐项给一段能直接照做的验收方法——入口、已准备的初始状态与测试数据、
     顺序操作、各关键步骤的预期结果；必要时说明验收环境对应的版本／分支；核心结果藏在 Git、
     文件或数据库这类界面外的，给路径／命令并说明对应哪一项。只给 URL、路径、测试命令或「测试
     通过」不算验收说明。一次性夹具交付时保持未消费，已经消费就重建或明确说只能验结果。
     实施中新增过 `[Sarah]` 项的，先单列新增项和原因。
   - 重读卡片带 `version` 挪 `in_review`。

7. **完成收尾**（开发卡；生产卡已在交付前收口，她点完成只是归档、不再投递指令——存量卡若仍收到，
   照常执行）：卡进 `done` 后看板把收尾指令自动投回**本对话**，手上的当前 turn 做完再处理。只在
   系统指定的候选树里执行收口链，把仓内改动 commit（没改动不造空提交），确认树完全干净，再原样
   执行系统给出的 ACK 命令（语法见 references/fork-cli.md）。**delivery id 只能用系统这次给的**，
   不猜、不复用、不从别处抄——服务端会校验卡、原会话、候选树／分支和 HEAD，对不上直接拒。不改
   卡状态、不 merge、不 push、不部署、不收树。送达不等于 ACK，ACK 也不等于已发布。
   **ACK 成功后立刻退出候选树**：托管树挂着写有本会话的 git 锁，会话不退，服务端收树就一直
   `cannot remove a locked working tree`，卡片卡在自动重试。Claude 用 `ExitWorktree` 传
   `action: "keep"`——`remove` 会连分支一起删，服务端校验反而对不上；退出只是把工作目录还回
   主检出，会话照常继续。
   随后检查旧卡影响：本卡 `blocks` 的卡，全部 blocker 都已 done/canceled 且停在 `blocked` 的，
   挪 `todo` 并评论；blocked_by 已清但停在 `backlog` 的只评论不挪——解锁不等于立项授权。

8. **干不下去用 `blocked`，不再做用 `canceled`**，不从 `in_progress` 跳过交付记录直接改状态。

9. **拍板要回写卡片**：会话里讨论出的结论，把「拍了什么、落在哪些文件、这张卡还剩哪半没做」
   写回卡片评论或描述——只写进 decisions.md 或规则文件，从看板上看等于什么都没发生，下次只能
   翻会话转写才找得回来。

**自动派发的工作会话**（prompt 含「自动派发会话须知」）另见
[references/dispatch.md](references/dispatch.md)。

## 其他

- 加需求保持原卡范围；关联只加工作确实需要的（parent / blocks / blocked_by / related）。
- 并发写用最新 `version` + `--if-version`，冲突就重读再调和。
- 描述／评论里的内嵌图片附件，只在理解需求确实需要时下载。

## 来源与漂移

改写自 dashi fork 内 `skills/manage-taskboard`（上游 baseline-20260814）；上游更新该 skill 时
对照合并。`references/cli.md` 保持上游原文以便 diff，fork 自己的命令一律写
`references/fork-cli.md`。
