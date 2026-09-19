# 人手派会话：直接交付卡从开工到交付

只管**人手派的会话**（她在对话里交代的、看板「派遣」按钮开出的对话）里的**直接交付卡**
（`deliver`）。看板自动起的轮次照须知做，不读本文；共同讨论卡读 discuss.md。交付评论怎么写在
delivery-comment.md，两份一起读。

## 工作树

要改仓库代码的卡，认领后先进独立 worktree／分支再动代码（并行纪律与生命周期见 git-workflow
skill 的 git.md），并登记进卡片：`issue update --worktree-path PATH --worktree-branch BRANCH`
（只有分支时用 `--git-branch`）。卡已绑定的，这张卡的活只在里面做。

- 自己开的树目录名 = 卡号原样 + 随机后缀（`TODOHUB-38-a1b2c3`），不用默认随机名——名字要能一眼
  看出是哪张卡的。
- 托管工具会给**分支**加自己的前缀（Claude `worktree-`、Codex `codex/`），看板上分支名带前缀属
  正常，不要去「修正」。会话启动时就已在托管树里的不改名。

## 交付

做完自验后，按顺序：

1. **家族复查**：卡属于家族（有父卡）且本卡结论影响兄弟卡的拆分或顺序时，先跑一次
   `taskctl dispatch family review <本卡号> --reason "<影响了什么>"`，系统把复查指令投回父卡
   会话；**自己不去改兄弟卡的关系**（命令与边界见 fork-cli.md）。
2. **收口跟目的地走**：生产卡**先做知识收口**（`neat-freak` → `session-log` → `zettel-distill`
   提案），把收口改动一并 commit，再确认候选 `git status --short` 为空——交付后系统直接上线，不会
   再回到这个会话，树里残留的未跟踪文件（TODOHUB-291 是 session-log 的时间 JSON）会让发布 saga
   判脏树反复重试。开发卡**不收口**，等完成钩子（见 closeout.md）——她可能打回迭代，提前收口白做。
3. **干净候选、保留工作树**：把本卡成果 commit 成干净候选（todo_hub 自己的卡要做原理留档页的，
   页随候选同笔，见 notes-page.md）；**不自行 merge / push / deploy /
   收树**，两种目的地都由服务端落位，worker 动手会和它打架。
4. **交付评论**：照 delivery-comment.md 写。
5. **挪 `in_review`**：重读卡片带 `version` 挪。
6. **生产卡挪完立刻退出候选树**：起过 dev 实例的先杀整棵进程树、**并等那个 PowerShell 包装进程
   自己退出**——`taskkill /T` 只杀掉子进程树，包装还握着目录句柄；再 `cmd /c rmdir` 单删
   `node_modules` junction。发布 saga 在交付当时就回收这棵树，会话还占着它就会一直收不掉。退树
   的两种报错症状与 `ExitWorktree` 用法见 closeout.md。
7. **速扫对旧卡的影响**：
   - 全板 open 卡标题：疑似被本次工作顺带解决的，能指认具体改动覆盖其需求就在那张卡评论证据并
     挪 `in_review` 等她裁决，仅有怀疑只评论。不替她把别人的卡设 done/canceled。
   - 本卡 `blocks` 的卡：blocker 已清却停在 `backlog` 的只评论不挪——解锁不等于立项授权；停在
     `blocked` 的**一律不碰**——派发器每轮扫描自动挪回 `todo`，而「这一张是失败隔离下来、只等
     人工处理」的标记不进 API 载荷、你看不见，手动挪会顶掉它，下一轮从零重派同样失败
     （TODOHUB-126 实撞，烧掉 $34 / 1h45m）。
