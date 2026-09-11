# taskctl：本 fork 独有的命令与参数

[cli.md](cli.md) 是上游原文，保持不动以便对照上游 diff。我们自己加的命令和参数写在这里；
**本 fork 改过、与 cli.md 写的不一致的行为也写在这里，冲突时以本文为准**。

## 全局参数

```
--agent codex|claude
```

写入方标识，决定看板画哪个图标、「查看对话」用哪种深链打开。不传时自动判：有
`CODEX_THREAD_ID` 记 codex，有 `CLAUDE_CODE_SESSION_ID` 记 claude，都没有默认 codex。
所以 Cursor 这类两个变量都取不到的环境必须显式带 `--agent claude`，否则会被记成 Codex。

## 关系写不改会话归属（与 cli.md 不同）

`issue relation add` / `issue relation remove` **不会**把卡的 `threadId` 顶成执行这条命令的会话
——和评论同一条豁免。挂关系照常 bump `version` 与 `updatedAt`、照常把本会话追加进这张卡的关联
对话列表，只是「这张卡归谁做」不变。

所以**给别人正在开发的卡挂 blockedBy / related 是安全的**：不抢它的会话绑定，看板「查看对话」
仍开原会话，Claude 心跳也仍按原会话的 transcript 算。cli.md「Update issues」一节那句
`Its singular threadId is the Codex conversation that most recently created or changed the issue
itself` 按字面读会让人不敢挂链，本 fork 已经不是这样了。

写关系仍要带会话归属（`--thread-id` / 自动读环境变量）——归属用于追加关联对话，只是不再改写
`threadId`。

## 评论正文走文件（与 cli.md 不同）

```
taskctl comment add    <卡号>   [--body-file PATH | --body TEXT]
taskctl comment update <评论 id> [--body-file PATH | --body TEXT] --if-version N
```

cli.md 只写了 `--body TEXT`，本 fork 两条命令都收 `--body-file`（UTF-8 文件，与
`issue create --description-file`、`dispatch reply --body-file` 同一条语义）。**交付评论这类
多行长正文一律用 `--body-file`**：经 shell 传参会被静默改写（Bash 工具吃反斜杠，Windows
PowerShell 5.1 吃双引号并在引号内空格处裂参），两者都不报错。两个选项同时给报 usage error。

服务端对评论正文一律 trim 首尾空白（`--body` 也一样），所以文件末尾的换行不会落到卡上。

## 推进方式

```
taskctl issue create ... --mode deliver|discuss
taskctl issue update ID --mode deliver|discuss
```

设卡片字段 `advanceMode`，不传 = `deliver`。语义见 SKILL.md「推进方式」。

## 目的地

```
taskctl issue create ... --destination production|dev
```

设卡片字段 `destination`，不传 = `production`（项目级默认可配）。**只在建卡时可设**——
`issue update` 改这个字段的 agent 来源写入会被服务端拒绝，觉得该改就评论提议。语义见 SKILL.md
「目的地」。

## 自动派发

```
taskctl dispatch status [--json]
taskctl dispatch enable  <项目 id> [--agent claude|codex] [--merge dev|main]
                                   [--post-merge <命令>] [--deploy <命令>]
taskctl dispatch disable <项目 id>
taskctl dispatch tick
taskctl dispatch stop <运行 id>
```

按项目开关。配置与护栏落在生产数据目录的 `dispatch.json`，改了即生效。`status` 里的
`integration` 说明晋升为什么暂停，`pendingDeploys` 是排队中或正在跑的部署。

todo_hub 自己的偏好：

```
--post-merge "npm --prefix dashi-taskboard run build:web"
--deploy "powershell -NoProfile -ExecutionPolicy Bypass -File scripts/board.ps1 deploy"
```

## 收尾确认（ACK）

```
taskctl dispatch closeout ack <卡号> --delivery-id <delivery id>
```

开发卡进 `done` 后，看板把这条命令连同一个精确的 delivery id 投回原会话。**只在本对话实际收到
系统指令后原样执行**，不猜、不复用、不从别处抄——服务端会校验卡、原会话的 agent 与 session、
候选树／分支，以及当前 HEAD 是否干净且为冻结 HEAD 的后代，对不上直接拒。

ACK 本身不改卡状态、不 merge、不 push。ACK 之后由派发器负责落位、push、部署和收树。

## 冲突重解（resolve）

```
taskctl dispatch closeout resolve <卡号> --delivery-id <delivery id>
                                         [--absorbed | --merged | --give-up --reason-file FILE]
```

同一条命令服务**三种轮**，指令正文会写明本轮是哪一种：**候选轮**（这张卡的候选成果要上线时叠到
最新 main 撞了真冲突）、**归并轮**（本机 main 与 `origin/main` 归并撞了冲突）与**修正轮**（候选叠到
main 零冲突，但落位测试闸跑出了 main 基线上没有的红）。三轮的现场、动作和出口都不一样，**走错出口一律
409 并点名正确的那条命令**——先看清本轮是哪一种，别混用现场、delivery id、rebase 与 merge。

系统都不替你解，而是把冲突现场投回**原会话**，因为最懂这个 diff 的是当初写它的那段对话（原会话
永久回不来时才起 fresh 会话兜底，指令里会标明本轮非原 worker）。和另外三条同一条纪律：**只在本对话
实际收到系统的重解指令后原样执行**，delivery id 用系统这次给的，不猜、不复用、不从别处抄。

### 候选轮：候选叠到最新 main

现场是这张卡登记的候选工作树，动作是 rebase。三个互斥出口，指令正文连着现场一起给：

- **普通重解**：在指令点名的候选树里 rebase、逐个解冲突、commit，然后不带旗标 ACK。解的标准是
  两边的意图都保住，不是「取我这边／取它那边」。
- `--absorbed`：rebase 后你的提交全被判为已应用（patch-equal 丢弃），HEAD 落在点名的 main 上、
  相对它零内容差异——说明 main 上已经有等价改动。这时**必须显式声明**，普通 ACK 撞到空内容一律
  被拒。
- `--give-up --reason-file FILE`：两边意图真的互斥、需要产品决策时，写一个 UTF-8 文件说明卡在
  哪、试过什么、要谁拍什么板，把球交回 Sarah。**宁可交回也不要瞎解**——解错会静默上线错误内容。

纪律：只用指令点名的那个 main 提交，**不要自己去取最新 main**（那个 SHA 投出后不可变，正是为了
不让解冲突期间又动的 main 拒掉诚实干活的你）；动手前先 `git rebase --abort`、
`git cherry-pick --abort` 清掉残留中间态；确认分支头正是指令里的「重解前候选提交」，**对不上就
停手回报**，别在别人的中间态上接着解。

边界：不改卡状态、不 merge、不 push、不部署、不收树，也不改写重解前那个候选提交之前的历史。ACK
通过后由服务端把候选身份受控重冻到你的新提交，继续走落位、测试闸、push、部署、收树。

### 修正轮：落位测试闸拦下候选（普通交回 / `--give-up`）

候选叠到最新 main **没有冲突**，但在落位现场跑仓库自己声明的快层测试时，出了 main 基线上没有的红。
指令里给的是：候选工作树、修正前的候选提交、闸门对照的那个 main 提交、新增红的用例名（套件 :: 用例）、
要跑的套件命令与目录、闸门原文。现场是这张卡登记的候选工作树，动作是**追加修正提交**——不是 rebase。

- 先在候选树里复现（可以只跑红的那个文件）。红可能是候选自己的错，也可能是**合起来才红**：别的卡改了你
  依赖的东西。看 main 那边改了什么用 `git diff <修正前候选>...<点名的 main>`；要在合成品上复现可以
  `git merge <点名的 main>`——那也是追加一笔提交，不改写历史。**不要 rebase。**
- 修正，把红的套件整套跑绿，commit。**只能追加**：不 amend、不 rebase、不 reset，不改写修正前那个
  候选提交之前的任何历史——服务端只认「新 HEAD 是修正前候选的后代且不等于它」，改写了交回会被拒
  （`CONFLICT_HISTORY_REWRITTEN`），什么都没追加也会被拒（`CONFLICT_NO_FIX`）。
- 树干净后在候选工作树根目录不带旗标交回。通过后候选身份不变，只把要上线的提交推进到你的新 HEAD，
  闸门重跑；绿了照常 ff main、push、部署、收树。
- 红不是候选造成的（基线环境、闸门误判）或确实修不了 → `--give-up --reason-file FILE`，写清红在哪、
  试过什么、要谁拍什么板。**这一轮没有 `--absorbed` / `--merged`，也没有 `--resume`**：交回之后被动门
  一直开着（任何人在候选树追加一笔修正，下一轮落位就自动采纳），不需要恢复窗口。

纪律与候选轮相同：只在本对话实际收到系统的修正指令后原样执行，delivery id 用系统这次给的；不改卡状态、
不 merge 进 main、不 push、不部署、不收树、不动主检出。修正窗口开着时**不要**重新 `closeout ack`——
会被 409 拒（`CLOSEOUT_RESOLVE_PENDING`），追加的提交只能经 `resolve` 交回。

### 归并轮：本机 main 并 origin/main（`--merged`）

本机 main 与 GitHub 上的 main 各有对方没有的提交、自动归并撞冲突时开这一轮。冲突属于**仓库**、不属于
某张卡，投给「本机未推提交里最新那张带卡号 trailer 的卡」的原 worker（它最懂本机这半边的 diff）。
**窗口开着 = 本机所有卡的落位与推送都停着**，所以值得优先做完。

- **现场是 saga 新开的短命工作树**（已经停在冻结的本机 main 上），不是候选树，也不许在主检出里做。
  动手前先确认那棵树的 `git rev-parse HEAD` 正是指令里冻结的本机 main 提交，**对不上就停手**并在卡上
  评论，别在别人的中间态上接着解。
- **动作是 `git merge <指令点名的那个 origin/main 提交>`，不是 rebase**：远端那几笔已经发布，一个
  字节都不许改写，归并只能新造一笔合并提交。同样只用点名的那个 SHA，**不要自己去 fetch 最新的**。
  解的标准仍是两边意图都保住。
- 解完 `git commit`（保留 git 生成的 merge 信息即可），确认工作树完全干净（含未跟踪文件），在这棵短命
  树里执行 `... resolve <卡号> --delivery-id <id> --merged`。
- 校验：新提交必须**同时是**冻结的本机 main 与点名的 `origin/main` 的后代，且树干净。通过后系统把本机
  main **只快进**（`merge --ff-only`）到你这笔归并提交、当场回收短命树，被暂停的卡自己接着落位、过
  测试闸、push、部署；候选身份一列都不动——这一轮换的是 main。
- 解不动只有 `--give-up --reason-file FILE` 一个出口（写法同候选轮；`--absorbed` 是候选轮的，用了会被
  拒）。用本轮指令给的那条完整命令，**不能猜 delivery id**。

边界：不改卡状态、不 push、不部署、不收树，不动主检出和任何候选工作树，**也不要 rebase 本机 main**
——那会改写已落位提交的 SHA，让在途 saga 判定自己没落位。

轮次上限、护栏计数与重冻规格不在这里，事实源是 todo_hub 的
`dashi-taskboard/server/closeout-conflict.mjs`（候选轮 `conflictResolveInstruction`、归并轮
`mainMergeResolveInstruction`、修正轮 `landingGateFixInstruction`）与该仓 `CLAUDE.md`「候选撞冲突投回原
worker 重解」及「落位测试闸拦下候选投回原 worker 追加修正」两段。

## 评论回应落卡（reply）

```
taskctl dispatch reply <卡号> --delivery-id <delivery id> [--body-file PATH | --body TEXT]
```

Sarah 在看板上把评论标记「需要回应」后，系统会把回应指令投进这张卡的原会话；指令里带着
精确的 delivery id 和这条命令的完整形态。**只在本对话实际收到系统的回应指令后原样执行**，
delivery id 不猜、不复用。正文优先 `--body-file`（UTF-8 文件，防 shell 改写多行长文）；
受限环境写不了文件时，把回复正文作为本轮唯一的最终输出，系统会代为落卡（仅后台会话有效）。
服务端校验卡、原会话与 delivery id，落卡的同时把被标记评论翻成「已回应」。回应轮的行为边界
（能否顺便干活）由指令按卡状态写明，照做即可；任何状态都不改卡状态、不 merge / push / deploy。

## 家族复查与收口（family）

```
taskctl dispatch family review <卡号> [--reason TEXT | --reason-file FILE]
taskctl dispatch family ack    <父卡号> --delivery-id <delivery id> [--body-file PATH | --body TEXT]
```

家族（父卡 + 子卡）的拆分和顺序会随子卡的结论过时，而更新不经 Sarah 的手。系统有三个触发器把
一条指令投回**父卡的会话**：子卡进 `blocked`（自动）、家族全清即子卡全部 done/canceled/归档
（自动，转收口）、以及子卡会话自己请求（`family review`，任何时候都受理）。前两个跟随项目的
自动派发开关。

### review：子卡会话主动发

交付前若发现本卡结论影响兄弟卡的拆分或顺序（某张兄弟卡白做了、顺序反了、该拆的没拆），跑一次
它：卡号写**自己这张子卡**，服务端顺 parent 关系自己找到家族父卡，排一轮复查并在父卡留一条
评论。判断归你，改图归复查轮——**你自己不要去动兄弟卡的关系**。

- 卡既无父卡也无子卡 → 409 `FAMILY_NOT_FOUND`；父卡已 done / canceled / 归档 → 409 `FAMILY_CLOSED`。
- 理由含引号或换行改用 `--reason-file`（UTF-8 文件），别让 shell 改写正文。理由可省，省了父卡
  会话只能自己猜。
- **自动派发的家族子卡** prompt 里会带这条命令，手工 GUI 会话不带——手工做家族子卡时要自己记得。

### ack：父卡会话收件后落卡

和 `closeout ack` / `reply` 同一条纪律：**只在本对话实际收到系统投来的复查／收口指令后原样
执行**，delivery id 用系统这次给的，不猜、不复用。服务端校验卡、意图是否真的投出去了、以及
ACK 的会话是不是这次投递冻结的那个目标会话（agent 与 session 都要对上），对不上直接拒。正文
优先 `--body-file`，它会以该会话的身份落成**父卡**评论；headless 腿没自己 ACK 时由服务端拿最终
输出代发。

两轮的边界：复查轮只读——改图靠 taskctl，不写仓库文件；收口轮按现行分层（父卡有候选树才全权）。
`destination` / `bundleRelease` 这类受限字段照旧 403，只能评论提议。都不 merge / push / deploy，
也都不改卡状态——唯一的例外是收口轮负责把父卡挪 `in_review` 交付。
