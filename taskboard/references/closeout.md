# 完成收尾与 ACK，以及退出候选树

prompt 含【看板完成钩子】时读本文；人手派会话交付生产卡后退树也看「退出候选树」一节。

## 完成收尾

只有开发卡会收到（目的地 `dev` 已停用，TODOHUB-493，只剩存量开发卡）：卡进 `done` 后看板把收尾指令自动投回**当初干活的对话**（生产卡已在交付前
收口，她点完成只是归档、不再投递——存量卡若仍收到，照常执行）。收口步骤、ACK 命令、ACK 被拒
怎么办、什么时候才用 `closeout report`，**以指令原文为准**，本文不复述。指令之外要守的：

- **delivery id 只能用系统这次给的**：不猜、不复用、不从别处抄——服务端会校验卡、原会话、候选
  树／分支和 HEAD，对不上直接拒。
- 不改卡状态、不 merge、不 push、不部署、不收树。送达不等于 ACK，ACK 也不等于已发布。

## 退出候选树

ACK 成功后（人手派的生产卡：挪 `in_review` 后）**立刻退出候选树**：会话还占着树，服务端就收
不掉。症状有两种，别只认第一种：

- `EnterWorktree` 建的托管树挂着 git 锁，报 `cannot remove a locked working tree, lock reason:
  claude session <树名> (pid N)`（点名了是谁）。
- 自己 `git worktree add` 建、再 `EnterWorktree` 传 `path` 进去的树**不加锁**，撞的是 Windows
  文件占用，报的是裸的 `error: failed to delete '...': Permission denied`（不说是谁占的）。

Claude 用 `ExitWorktree` 传 `action: "keep"`——`remove` 会连分支一起删，服务端校验反而对不上；
退出只是把工作目录还回主检出，会话照常继续。

**一个会话连做两张卡会撞到边界**：`EnterWorktree` 只允许持有一棵托管树（第二次传 `name` 直接
拒），而 `keep` 要还回去的那个目录可能已经随上一张卡被回收了。真要连做，第二棵树自己
`git worktree add` + `EnterWorktree {path}`，并在交付／ACK 后手动 `cd` 出去。

收不掉不会再把卡钉住（服务端 30 分钟宽限期后收敛并在评论里点名），但留下的树要人手工删。
