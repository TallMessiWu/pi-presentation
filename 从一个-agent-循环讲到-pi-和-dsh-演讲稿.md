# 从一个 agent 循环讲到 pi 和 dsh

**40 分钟 · AI 工程师部门分享**

| 时间 | 现场要看的问题 |
|---|---|
| 00:00–04:00 | 交替运行两格代码，一轮一轮看完整请求、模拟模型的原始回答和文件工具的实际回执。 |
| 04:00–20:00 | pi 的一次工具调用，怎样从 `AgentSession` 走到本地文件，又进入下一次请求？ |
| 20:00–34:30 | 对照 pi 读 dsh 的架构和三次请求：启动时谁装配组件，运行时谁管历史，写文件时谁检查权限？ |
| 34:30–37:00 | 把插件放回架构图，先看规划和权限，再试加一道检查、换文件实现、换循环。 |
| 37:00–38:00 | 三种记忆插件把同一句约定存到哪里，新会话怎样取回，各有什么代价？ |
| 38:00–40:00 | 按团队需求、模型接入方式和同模型实测，决定先试 pi 还是 dsh。 |

> **讲者用**　等宽字体是投影时值得指的字段或函数。系统提示、工具参数和结果保留英文；旁边的中文是讲解。长代码藏在附录，正文的源码链接对应本地检出的版本，pi `8209929`，dsh `4b399c3`。图中节点和下文代码相对应。

随讲稿可以[打开六份模型请求和本地会话记录](./harness-requests.json)。正文会按消息出现的顺序把关键的 JSON 列出来。

## 00:00–04:00　用三轮请求手动跑一次 ReAct

### 00:00　第 1 页　改一行文件要问模型几次？

今天只改一行配置。这个例子来自 dsh 仓库的 `fs-edit` 测试，用户原话翻成中文就是“先用 read 读 config.txt，再用 edit 把 DEBUG 换成 RELEASE，最后只回 DONE”。仓库里留着改之前的文件、改之后的文件和中间的调用记录，等会儿跑 pi 和 dsh 时能一项一项对。咱们先自己当一下那个循环，发一轮就停一下。[测试文件和预期结果](https://github.com/deepseek-ai/deepseek-harness/tree/4b399c39a6d1479cd84ca591b4d7c88e24d38a96/snapshots/session/fs-edit) · [录制里的用户原话](https://github.com/deepseek-ai/deepseek-harness/blob/4b399c39a6d1479cd84ca591b4d7c88e24d38a96/snapshots/session/fs-edit/session.v4.jsonl#L10-L25)

### 00:30　第 2 页　先备好工具和一段空白会话

第一格里有两个真正干活的 Python 函数。`read` 读文件，`edit` 在文件里找到原文、改掉一处。发给模型的是另外一份工具声明，里面写名字、用途和参数。我们这边留着名字到函数的对照表，等模型报出工具名才知道去调谁。

第二格创建一份临时文件，初始值是 `mode=DEBUG` 和 `level=info`。对话从两条消息开始，一条是演示里写的简短英文系统说明，一条是用户的完整指令。请记住第二行 `level=info`，用户一句都没提过它。模型回复由本地函数模拟，读写用的就是刚创建的文件。

> **操作**　依次运行 Cell 1、2。若已执行过 Run All，上台前再运行一次 Cell 2，把历史和临时文件一起恢复到起点。

### 02:00　第 3 页　我们决定什么时候进入下一轮

这一页左边两格，右边共用一个结果区。点 Cell 3 看准备发出的完整请求，点 Cell 4 才揭晓回复、执行工具。每次选中代码按 **Ctrl + Enter**，我们自己控制这六次停顿。

1. **第一次运行 Cell 3。** 先问“现在模型能说出文件第二行吗？”往下看得到 `tools` 里的 `read`，但 `messages` 里只有系统说明和用户任务。运行 Cell 4，模型在原始 JSON 里选了 `read`，给出文件名。跟着 `function.arguments` 看，那还是一串 JSON 字符。程序解析参数、运行本地函数，工具回执里才有那两行配置。
2. **先猜第二份请求会多几条消息，再跑 Cell 3。** 右边停在新增的位置。一条是助手说“我要读”，一条是工具答“读到了这些”，相同的调用编号把它们对上。现在模型才看见 `level=info`。猜完它下一步要做什么，再跑 Cell 4，看 `edit` 拿到哪些参数、工具改完回了什么。
3. **第三次运行 Cell 3 前再猜一下。** 磁盘已经改成了 `RELEASE`，先前那条 read 回执会跟着变吗？翻回去还是 `mode=DEBUG`，末尾新加的是 edit 成功的回执。运行 Cell 4，助手这次只答 `DONE`，任务到这儿结束。

刚才模型提出一次工具调用，是一个 action。工具真正读到或改到什么，把结果记回对话，就是下一轮可以用的 observation。我们自己按键决定什么时候再发请求。把同一句任务交给 pi 以后，谁来准备第一包，谁把回执送进第二包？现在从用户按回车开始追。[ReAct 作者的论文与示例](https://react-lm.github.io/)

## 04:00–20:00　pi：用户打的一句话，怎么变成三份请求？

### 04:00　从用户按回车开始

把进度拨回开头。现在我坐在终端前，交给 pi 的是这样一句话。这是本地命令行收到的英文任务原文：

> First use the read tool to read config.txt in the current directory. Then use the edit tool (NOT bash) to replace the literal text DEBUG with RELEASE in that file. Then reply with exactly the single word DONE.

我敲到这里就按回车了。后面大家会在请求里看到很多别的英文，先记住哪一句是我写的。pi 给这段输入标上来源：`role` 表示是谁说的，用户自己输入的就叫 `user`；`content` 装正文。这次正文只有一个文本块。这是从本地会话里**单独抽出的用户这一项**，保留开头一句供大家认出来：

```json
{
  "role": "user",
  "content": [{"type": "text", "text": "First use the read tool to read config.txt in the current directory. …"}]
}
```

为了能逐项对照，我在本机跑这版 pi，保存它在发送前准备的会话消息和交给网络层的 JSON。模型的回答用预先准备的内容回放，读写文件由 pi 真正执行。

按回车以后，先接到这项任务的是本机的 pi。从源码图里的 `AgentSession` 沿着 `Agent` 和 `runLoop` 走到 `pi-ai`，才到第一次向模型发请求的位置。前面手动演示里，Cell 3 一行 `build_request(messages, tools)` 就备好了请求。换到 pi，咱们沿这条路看看准备工作具体落在哪几个模块。

图 1　pi CLI 的源码架构

![pi 源码架构：coding-agent 的启动、会话和工具，agent-core 的调度，以及 pi-ai 的模型协议层](./pi-architecture.svg)

[单独打开放大架构图](./pi-architecture.svg)

这里先分清两个名字。`AgentSession` 是管这段会话的本地对象，`agent.state.tools` 是它所管理的 `Agent` 当前启用的工具列表。拿 `read` 跟两次回到会话的箭头：

1. **选工具时，注册表 → AgentSession。** 这次命令行把 `read,edit,write,bash` 这四个**名字**交给会话。注册表就在 `AgentSession` 自己里面：会话按名调用 `_toolRegistry.get("read")`，拿回带有 `execute` 的 `read` 对象。四个名字逐个取完，**会话把选好的对象组成列表，写进 `agent.state.tools`**。图上的“返回：该名称的工具对象”就是这一趟的回程。[CLI 启用名单](https://github.com/earendil-works/pi/blob/8209929fb553e7a8c91dc0894569f9ec43dd201f/packages/coding-agent/src/core/sdk.ts#L280-L294) · [按名取对象](https://github.com/earendil-works/pi/blob/8209929fb553e7a8c91dc0894569f9ec43dd201f/packages/coding-agent/src/core/agent-session.ts#L1671-L1677) · [写入工具列表](https://github.com/earendil-works/pi/blob/8209929fb553e7a8c91dc0894569f9ec43dd201f/packages/coding-agent/src/core/agent-session.ts#L1710-L1717)
2. **每轮发包前，agent.state.tools → AgentSession → runLoop。** 循环调用 `prepareRequest`，由会话从当前分支取历史，再用 `this.agent.state.tools.slice()` 取一份当前工具列表。它把两样东西一起装进本轮上下文，交回循环。因此图上有两根相接的长虚线：“每轮读回工具列表副本”指向会话，“本轮消息和工具副本”从会话指向循环。[会话准备并返回上下文](https://github.com/earendil-works/pi/blob/8209929fb553e7a8c91dc0894569f9ec43dd201f/packages/coding-agent/src/core/agent-session.ts#L852-L879) · [循环取回上下文](https://github.com/earendil-works/pi/blob/8209929fb553e7a8c91dc0894569f9ec43dd201f/packages/agent/src/agent-loop.ts#L228-L251)

图里还有一条从 `agent.state.tools` 通向循环的线。启动循环时，`Agent` 会先取一份包含工具的快照，循环用它记录工具声明；上面第 2 步的回流线，画的是每轮发送前会话再取当前工具列表。两处读取的是同一份 Agent 状态。[启动循环时取快照](https://github.com/earendil-works/pi/blob/8209929fb553e7a8c91dc0894569f9ec43dd201f/packages/agent/src/agent.ts#L441-L473)

到了模型那一侧，用第一份请求里的 `tools[0].function` 对照：名字是 `read`，带有用途说明和路径参数 `path`。`pi-ai` 把消息中记录的声明放进出站的 `tools`。模型回了 `read` 这个名字后，分派层再到本轮的工具集合里查找并执行。`execute` 一直留在本机。[声明如何记录](https://github.com/earendil-works/pi/blob/8209929fb553e7a8c91dc0894569f9ec43dd201f/packages/agent/src/agent-loop.ts#L333-L369) · [发送工具声明](https://github.com/earendil-works/pi/blob/8209929fb553e7a8c91dc0894569f9ec43dd201f/packages/ai/src/api/openai-completions.ts#L847-L849) · [模型点名后执行](https://github.com/earendil-works/pi/blob/8209929fb553e7a8c91dc0894569f9ec43dd201f/packages/agent/src/agent-loop.ts#L721-L738)

先找 `runLoop`。沿实线看谁调用谁，沿标有返回内容的长虚线逆向读。短点线 `message_end` 表示会话订阅的事件。Notebook 的「突出回流」会保留结果与记历史的路径，淡化普通调用。

- **模型回了什么？** 从模型端点往回走：SSE 增量进入 `pi-ai` 的适配器，转成助手消息事件流交给循环。循环收齐后，第一轮拿到 `read` 调用，最后一轮拿到文本 `DONE`。[适配器返回事件流](https://github.com/earendil-works/pi/blob/8209929fb553e7a8c91dc0894569f9ec43dd201f/packages/ai/src/models.ts#L958-L969) · [循环消费响应](https://github.com/earendil-works/pi/blob/8209929fb553e7a8c91dc0894569f9ec43dd201f/packages/agent/src/agent-loop.ts#L412-L465)
- **两行文件内容去了哪？** `read` 从文件系统读回内容，把正文交给工具分派。工具批次将结果整理成 `toolResult`；`message_end` 经 `Agent` 通知 `AgentSession` 追加到会话历史。下一轮再从 `SessionManager` 取出当前分支的消息，`level=info` 这才进入发给模型的输入。[工具返回和结果消息](https://github.com/earendil-works/pi/blob/8209929fb553e7a8c91dc0894569f9ec43dd201f/packages/agent/src/agent-loop.ts#L824-L853) · [会话接收消息](https://github.com/earendil-works/pi/blob/8209929fb553e7a8c91dc0894569f9ec43dd201f/packages/coding-agent/src/core/agent-session.ts#L1215-L1235)
- **终端怎么拿到 `DONE`？** `runPrintMode` 等待任务完成，再读取 `session.state.messages` 的最后一条助手文本，写到标准输出。[print 模式读取最终结果](https://github.com/earendil-works/pi/blob/8209929fb553e7a8c91dc0894569f9ec43dd201f/packages/coding-agent/src/modes/print-mode.ts#L137-L158)

<details>
<summary>展开原版 Mermaid 架构图及源码入口</summary>

```mermaid
---
config:
  theme: base
  themeVariables:
    background: "#ffffff"
    primaryColor: "#ffffff"
    primaryTextColor: "#303030"
    primaryBorderColor: "#757575"
    secondaryColor: "#ffffff"
    secondaryTextColor: "#303030"
    secondaryBorderColor: "#999999"
    tertiaryColor: "#ffffff"
    tertiaryTextColor: "#303030"
    tertiaryBorderColor: "#c4c4c4"
    mainBkg: "#ffffff"
    clusterBkg: "#ffffff"
    clusterBorder: "#c4c4c4"
    edgeLabelBackground: "#ffffff"
    nodeBorder: "#757575"
    lineColor: "#505050"
    textColor: "#303030"
    titleColor: "#303030"
  flowchart:
    nodeSpacing: 34
    rankSpacing: 32
    padding: 11
---
flowchart TB
  subgraph CLI["coding-agent · 启动与输入"]
    boot["cli.ts → main.ts"]
    sdk["sdk.ts · createAgentSession"]
    mode["runPrintMode / InteractiveMode"]
    boot <-->|创建并取得会话| sdk
    boot --> mode
  end
  subgraph Session["coding-agent · 会话、提示词与本地工具"]
    sess["AgentSession · prompt / _prepareRun"]
    load["DefaultResourceLoader<br/>项目指令、扩展与 skills"]
    prompt["system-prompt.ts<br/>buildSystemPromptSections"]
    hist["SessionManager<br/>会话树、消息与上下文投影"]
    defs["工具注册表 · _toolRegistry<br/>内置 read / edit / write 等 + 扩展工具"]
    load -->|提供 prompt 输入| sess
    sess <-->|构建 / 返回系统指令段| prompt
    sess -->|记消息 / 读取当前分支| hist
    sess -->|① 登记 / ② 按名查找| defs
  end
  subgraph Core["agent-core · 调度"]
    toolset["本轮可用工具 · agent.state.tools<br/>本例 read / edit / write / bash"]
    agent["Agent · runPromptMessages"]
    loopNode["agent-loop.ts · runLoop"]
    dispatch["prepareToolCall / executePreparedToolCall"]
    agent --> loopNode
    loopNode -->|模型点名 read + 参数| dispatch
  end
  subgraph Network["pi-ai · 模型协议"]
    route["ModelRuntime.streamSimple"]
    api["openai-completions.ts<br/>buildParams / 流式解码"]
    route -->|按模型协议转换| api
  end
  sdk -->|构造| agent
  sdk -->|传入 Agent 与启用名单| sess
  mode -->|提交任务 / 结束后读状态| sess
  sess -->|agent.prompt| agent
  loopNode -->|③ 消息带工具声明| route
  loopNode -.->|事件：message_end| agent
  agent -.->|事件：通知会话写历史| sess
  dispatch -->|④ 调用选中实现的 execute| defs
  defs -->|本地文件操作| fs["文件系统"]
  api -->|③ tools 数组：名称、说明、参数| model["模型端点"]
  model -.->|返回：SSE 增量| api
  api -.->|返回：助手事件流| route
  route -.->|返回：工具调用或文本流| loopNode
  fs -.->|返回：文件字节 / 写入完成| defs
  defs -.->|返回：正文 / 修改回执| dispatch
  dispatch -.->|回流：批次整理为 toolResult| loopNode
  hist -.->|返回：当前分支消息| sess
  loopNode -->|每轮 prepareRequest| sess
  sess -.->|返回：本轮消息和工具副本| loopNode
  sess -.->|读得最终助手文本 DONE| mode
  defs -.->|② 返回：该名称的工具对象| sess
  sess -->|② 写入已选工具列表| toolset
  toolset -.->|③ 每轮读回工具列表副本| sess
  toolset -->|③ 由循环提取声明| loopNode
  toolset -->|④ 供分派按名查找| dispatch
  click sdk href "https://github.com/earendil-works/pi/blob/8209929fb553e7a8c91dc0894569f9ec43dd201f/packages/coding-agent/src/core/sdk.ts#L403" "打开固定版本源码"
  click sess href "https://github.com/earendil-works/pi/blob/8209929fb553e7a8c91dc0894569f9ec43dd201f/packages/coding-agent/src/core/agent-session.ts#L2011" "打开固定版本源码"
  click loopNode href "https://github.com/earendil-works/pi/blob/8209929fb553e7a8c91dc0894569f9ec43dd201f/packages/agent/src/agent-loop.ts#L189" "打开固定版本源码"
  click dispatch href "https://github.com/earendil-works/pi/blob/8209929fb553e7a8c91dc0894569f9ec43dd201f/packages/agent/src/agent-loop.ts#L725" "打开固定版本源码"
  click api href "https://github.com/earendil-works/pi/blob/8209929fb553e7a8c91dc0894569f9ec43dd201f/packages/ai/src/api/openai-completions.ts#L787" "打开固定版本源码"
  click defs href "https://github.com/earendil-works/pi/blob/8209929fb553e7a8c91dc0894569f9ec43dd201f/packages/coding-agent/src/core/tools/edit.ts#L180" "打开固定版本源码"
  click toolset href "https://github.com/earendil-works/pi/blob/8209929fb553e7a8c91dc0894569f9ec43dd201f/packages/coding-agent/src/core/agent-session.ts#L1669" "启用本轮工具"
  linkStyle 19,20,21,22,23,24,25,27,28,29,31 stroke:#444444,stroke-width:1.65px,stroke-dasharray:7 4;
```

</details>

### 06:00　先看谁加了系统提示，再打开第一次请求

还是刚才那句话。假设我只把用户原文交给一个模型，它看得到“用 `read`”，却不知道我们这儿的 `read` 怎么叫、允许给什么参数。pi 手上还有两份材料可以补进去。

一份是**给助手的工作说明**。为了看清项目约定怎么进模型，我在临时演示目录里放了一个 `AGENTS.md`，里面只写了一行：`Keep unrelated configuration values unchanged.`，意思是“只改这次要求改的配置项，其他项保持原样”。落到我们的文件，就是改 `mode`，保留 `level=info`。pi 准备首包时把这句约定和它自带的工作说明一起放进 `system`，用户在终端打的任务仍放在 `user`。这时模型已经知道要保留其他配置；具体还有哪几行，得等 `read` 把文件正文带回来。

另一份是**工具清单**。这次启动时给 pi 启用了 `read`、`edit`、`write` 和 `bash`。本地注册的工具各有名字、用法和执行函数。pi 需要把可调用的名字和用法告诉模型，真正打开文件的函数留在本机。

先停在**本地会话刚准备好、还没交给模型适配器**的地方。下面是从同一次回放取出的两条内部消息。第一条把工作说明按段保存：`preamble` 是开场指令，`project_context` 里包含项目约定。`toolsAdded` 记录首次声明的工具，例子里每项只展开名字。第二条还是刚才的用户输入。长字符串中的 `…` 表示投影时折叠的原文，完整数据在附件的 `pi.local_before_send[0]`。[pi 组装系统提示的源码](https://github.com/earendil-works/pi/blob/8209929fb553e7a8c91dc0894569f9ec43dd201f/packages/coding-agent/src/core/system-prompt.ts#L128-L189)

```json
[
  {
    "role": "system",
    "sections": {
      "preamble": "You are a coding assistant running inside pi, a coding agent harness. Help users inspect files, run commands, and modify code.",
      "project_context": "…\nKeep unrelated configuration values unchanged.\n…"
    },
    "toolsAdded": [{"name": "read"}, {"name": "edit"}, {"name": "write"}, {"name": "bash"}]
  },
  {
    "role": "user",
    "content": [{"type": "text", "text": "First use the read tool to read config.txt in the current directory. …"}]
  }
]
```

现在才走到**发给 DeepSeek 的请求体**。适配器把工作说明的各段连成一段文字，放进 `messages` 里的第一条；用户任务是第二条。可调用的工具另列在外层 `tools`；`model` 指定这次用哪个模型。看下面就能对上：左边如果停在刚才的本地列表，右边的 `system` 和 `user` 都找得到来源。示例保留实际字段名、外层形状和消息顺序，只摘长文本与工具名字；每轮未经节选的 JSON 都在[请求附件](./harness-requests.json)。[本轮会话怎样交给适配器](https://github.com/earendil-works/pi/blob/8209929fb553e7a8c91dc0894569f9ec43dd201f/packages/coding-agent/src/core/agent-session.ts#L852-L879)

**发出 ① · pi 请求体节选。** `messages` 的两项都在，四个工具各保留名称，长文本以 `…` 折叠。

```json
{
  "model": "deepseek-flash",
  "messages": [
    {
      "role": "system",
      "content": "You are a coding assistant running inside pi, a coding agent harness. Help users inspect files, run commands, and modify code.\n…\nKeep unrelated configuration values unchanged.\n…"
    },
    {
      "role": "user",
      "content": [
        {
          "type": "text",
          "text": "First use the read tool to read config.txt in the current directory. …"
        }
      ]
    }
  ],
  "tools": [
    {"type": "function", "function": {"name": "read"}},
    {"type": "function", "function": {"name": "edit"}},
    {"type": "function", "function": {"name": "write"}},
    {"type": "function", "function": {"name": "bash"}}
  ]
}
```

> **台上操作**　在同一份请求里找两处文字。`Keep unrelated` 能找到，因为项目约定已经被 pi 读入；`level=info` 找不到，因为要求操作的 `config.txt` 还没人读过。工具出现在清单里，只能说明它可用。

### 10:00　第二次请求：模型说要读，谁把读出的内容送回去？

先看这张完整时序图。第一条箭头是人按回车，最后一条箭头是人看到 `DONE`。此刻我们刚走完“第一次请求”，顺着模型的返回箭头往下看。

从第一条箭头往下读：用户按回车后，pi 准备请求。模型先要求 `read`，再要求 `edit`，最后一条 `DONE` 回到终端。

![pi 从用户输入到三次模型请求、两次本地工具执行，最终把 DONE 返回给用户](./pi-request-sequence.svg)

[单独打开放大这张时序图](./pi-request-sequence.svg)

模型回的是一个动作：“请用 `read` 读取 `config.txt`。”这种回复在会话里的作者叫 `assistant`。它带一个调用编号 `fs-edit-read`，相当于给这次读取贴了一张回执号。等本地工具读完文件，pi 拿着同一个号，把两行正文记为工具结果。本地会话把这种结果叫 `toolResult`。先看新增的这两项，文件内容出现在哪一项？

```json
[
  {
    "role": "assistant",
    "content": [
      {
        "type": "toolCall",
        "name": "read",
        "id": "fs-edit-read",
        "arguments": {"path": "config.txt", "offset": null, "limit": null}
      }
    ]
  },
  {
    "role": "toolResult",
    "toolCallId": "fs-edit-read",
    "content": [{"type": "text", "text": "mode=DEBUG\nlevel=info\n"}]
  }
]
```

这两项下一轮都要带回去。下面直接看**第二次请求的 `messages`**：前两条还是第一轮那份工作说明和用户任务；新增的一对里，`tool_calls` 表示模型上轮具体选中的动作，`role: "tool"` 表示这次调用的返回。调用号把它们配成一对。注意第一包的 `tools` 是四种可选工具，这儿的 `tool_calls` 只有已经选中的 `read`。[工具结果写进请求的位置](https://github.com/earendil-works/pi/blob/8209929fb553e7a8c91dc0894569f9ec43dd201f/packages/ai/src/api/openai-completions.ts#L1401-L1427)

**发出 ② · 完整消息顺序，共 4 项。** 前 2 项与上一轮相同，末尾两项是本轮新增。下面按原顺序显示每一项，长指令和部分字段折叠；`…` 由讲稿添加。本轮模型和工具清单沿用第一份。

```json
[
  {
    "role": "system",
    "content": "You are a coding assistant running inside pi, a coding agent harness. Help users inspect files, run commands, and modify code.\n…\nKeep unrelated configuration values unchanged.\n…"
  },
  {
    "role": "user",
    "content": [{"type": "text", "text": "First use the read tool to read config.txt in the current directory. …"}]
  },
  {
    "role": "assistant",
    "tool_calls": [
      {
        "id": "fs-edit-read",
        "type": "function",
        "function": {"name": "read", "arguments": "{\"path\":\"config.txt\",\"offset\":null,\"limit\":null}"}
      }
    ]
  },
  {"role": "tool", "tool_call_id": "fs-edit-read", "content": "mode=DEBUG\nlevel=info\n"}
]
```

这次 `level=info` 出现了。用户没有再打字，消息数却由 2 变成 4，因为中间有一项来自模型，一项来自工具。pi 每次发包会取当前会话分支走到这里的历史。同一分支的这个短任务里，我们实际看到第一轮的两条消息在第二轮原样保留。

### 15:00　第三次请求：带进去的是新文件，还是工具的回执？

模型看过原文，第二次回复选了 `edit`。它给了文件名、旧文本 `DEBUG` 和新文本 `RELEASE`。本地工具照这次调用去改文件，在会话里又添了一对：助手提出的 `edit`，以及写入成功的结果。这次的编号是 `fs-edit-replace`。如果用 `write`，模型就得给出整份要写入的内容；这里实际选的是 `edit`，只给一处替换。[本地 edit 及其返回值](https://github.com/earendil-works/pi/blob/8209929fb553e7a8c91dc0894569f9ec43dd201f/packages/coding-agent/src/core/tools/edit.ts#L181-L213)

**第三次请求的 `messages` 有六条。** 前四条沿用，最后两条刚加入。这次专门看最后一条的正文：

**发出 ③ · 完整消息顺序，共 6 项。** 前 4 项与上一轮相同，末尾两项是本轮新增。下面按原顺序显示每一项，长指令和部分字段折叠；`…` 由讲稿添加。本轮模型和工具清单沿用第一份。

```json
[
  {
    "role": "system",
    "content": "You are a coding assistant running inside pi, a coding agent harness. Help users inspect files, run commands, and modify code.\n…\nKeep unrelated configuration values unchanged.\n…"
  },
  {
    "role": "user",
    "content": [{"type": "text", "text": "First use the read tool to read config.txt in the current directory. …"}]
  },
  {
    "role": "assistant",
    "tool_calls": [
      {
        "id": "fs-edit-read",
        "type": "function",
        "function": {"name": "read", "arguments": "{\"path\":\"config.txt\",\"offset\":null,\"limit\":null}"}
      }
    ]
  },
  {"role": "tool", "tool_call_id": "fs-edit-read", "content": "mode=DEBUG\nlevel=info\n"},
  {
    "role": "assistant",
    "tool_calls": [
      {
        "id": "fs-edit-replace",
        "type": "function",
        "function": {
          "name": "edit",
          "arguments": "{\"path\":\"config.txt\",\"edits\":[{\"oldText\":\"DEBUG\",\"newText\":\"RELEASE\"}]}"
        }
      }
    ]
  },
  {
    "role": "tool",
    "tool_call_id": "fs-edit-replace",
    "content": "Successfully replaced 1 block(s) in config.txt."
  }
]
```

它说“成功替换了一个文本块”。如果这时把鼠标往上移，前一轮 `read` 的结果居然还写着 `mode=DEBUG`。这两条可以同时成立：一条是更改前读到的旧内容，一条是之后写入的回执。如果用户还想看改完的完整文件，得再读一次；这条任务只要求改完回 `DONE`。

### 18:00　把请求和响应接回用户

现在第三份请求已发出，模型才给出最后一句回答。pi 收到纯文本 `DONE`，本轮没有工具要执行，终端把它显示给用户。图上最后那条回到“用户”的箭头，就是这个时刻。

> **台上操作**　看附件里三份 `pi.requests` 的最后一条消息：第一次是用户任务，第二次是读到的文件，第三次是写入成功的回执。再问：“哪一份里有助手已经回答的 `DONE`？”用户任务里一开始就有这个词，可真正的答案属于第三次**响应**。它在最后一份请求发出时还没发生。

停在表格最后一行。edit 说文件已经改好了，用户这时还没看到 DONE。中间还隔着一次模型请求。刚才是哪段程序把这条成功回执送回模型的？

## 20:00–34:30　对照 pi，看 dsh 的架构与工作流

### 20:00　同一个任务交给 dsh，谁来跑这个循环？

答案就是我们前面看到的 pi 循环。模型选了 edit，pi 调本地工具，把成功回执接到历史里，再问一次模型。等这次模型答了 DONE，这个任务才结束。在 pi 的源码里，Agent 直接调用内置的 runAgentLoop。假如团队想在改 config.txt 前多检查一下路径，就在工具执行前接一个扩展。连 edit 的实现也可以换；要自己决定整个循环怎么跑，就得另外搭主程序，或者改核心代码。[Agent 怎样进入 runAgentLoop](https://github.com/earendil-works/pi/blob/8209929fb553e7a8c91dc0894569f9ec43dd201f/packages/agent/src/agent.ts#L441-L453) · [同名工具覆盖内置实现](https://github.com/earendil-works/pi/blob/8209929fb553e7a8c91dc0894569f9ec43dd201f/packages/coding-agent/docs/extensions.md#L2358-L2364)

现在把完全相同的任务交给 dsh。用户还是要它先读、再改、最后回 DONE，所以还是得有一段程序负责这几轮。换个问题：dsh 启动时，怎么知道该用谁来跑？打开配置，能找到 dsh-agent-loop。它是默认的循环插件。我们也可以按 AgentFactory 接口写自己的插件，再让配置选用它。接下来看架构图，先找命令行入口把这句任务交给了谁。[默认配置列出工具、循环和文件服务](https://github.com/deepseek-ai/deepseek-harness/blob/4b399c39a6d1479cd84ca591b4d7c88e24d38a96/packages/bundle/base/cordis.patch.yml#L524-L561) · [循环插件登记 Agent 工厂](https://github.com/deepseek-ai/deepseek-harness/blob/4b399c39a6d1479cd84ca591b4d7c88e24d38a96/packages/core/agent-loop/src/index.ts#L328-L338) · [AgentFactory 的创建与恢复约定](https://github.com/deepseek-ai/deepseek-harness/blob/4b399c39a6d1479cd84ca591b4d7c88e24d38a96/packages/core/agent/src/index.ts#L176-L220)

图 2　dsh headless 的源码架构

![dsh 源码架构：headless 入口、agent-loop、工具与上下文、会话日志、模型适配器及文件执行路径](./dsh-architecture.svg)

[并排看 pi 的架构图](./pi-architecture.svg) · [放大 dsh 的架构图](./dsh-architecture.svg)

> **台上操作**　选「循环由谁提供」，从 headless 的 `agents.create` 沿线找到默认的 `ReactLoopAgent`。现在回到任务开头：用户让它先读 config.txt，模型第一轮怎么知道有 `read` 可选？切到「可用工具」。

跟 pi 一样，模型在本次请求的 `tools` 中看见工具；dsh 的区别在于，**每一步从当前配置装载的插件中确定可用工具集**。

1. **登记、选用。** 这个 headless profile 装入了文件工具插件。插件启用 `read` 时向工具服务登记名字、说明、参数和执行函数；进入一个模型步骤时，循环调用 `tools.resolve`，得到这一步的 `toolSet`。[文件插件注册 read](https://github.com/deepseek-ai/deepseek-harness/blob/4b399c39a6d1479cd84ca591b4d7c88e24d38a96/packages/fs/tool-fs/src/read.ts#L67-L84) · [本步选择工具集](https://github.com/deepseek-ai/deepseek-harness/blob/4b399c39a6d1479cd84ca591b4d7c88e24d38a96/packages/core/agent-loop/src/agent.ts#L286-L303)
2. **发给模型。** 请求组装沿用这份集合，把工具声明交给 `buildRequest`。归档的这次任务有 **24 项工具声明**；在 DeepSeek Messages 请求的顶层 `tools` 找 `name: "read"`，旁边就是 `description` 和 `input_schema`，路径参数在这里叫 `file_path`。24 是这次录制的数量，换配置可以得到另一份清单。[收集工具声明](https://github.com/deepseek-ai/deepseek-harness/blob/4b399c39a6d1479cd84ca591b4d7c88e24d38a96/packages/core/system-prompt/src/index.ts#L757-L769) · [出站工具字段](https://github.com/deepseek-ai/deepseek-harness/blob/4b399c39a6d1479cd84ca591b4d7c88e24d38a96/packages/llm/llm-deepseek/src/serialize.ts#L159-L167)
3. **在本机执行。** 模型回复 `tool_use`，名字为 `read`。循环把模型给的调用和**刚才选出的同一份 `toolSet`** 交给工具执行器，按名找到本地实现，再走本次调用的参数和策略检查。[把原工具集交给执行器](https://github.com/deepseek-ai/deepseek-harness/blob/4b399c39a6d1479cd84ca591b4d7c88e24d38a96/packages/core/agent-loop/src/agent.ts#L576-L583)

回到 `ReactLoopAgent`，沿长虚线读返回的数据；带「注册」的短点线是启动时的关系，`tool/result` 则是工具系统向会话追加的事件。准备阶段的双向箭头分别列出请求的动作和取回的材料。

- **模型响应怎样回到循环？** `llm-deepseek` 读到 SSE，翻译成统一的 `StreamChunk`。循环从模型服务层消费这些片段，组装助手消息，再写入 `Session`。[适配器传回流片段](https://github.com/deepseek-ai/deepseek-harness/blob/4b399c39a6d1479cd84ca591b4d7c88e24d38a96/packages/llm/llm-deepseek/src/adapter.ts#L150-L177) · [循环接收与记录](https://github.com/deepseek-ai/deepseek-harness/blob/4b399c39a6d1479cd84ca591b4d7c88e24d38a96/packages/core/agent-loop/src/agent.ts#L556-L577)
- **工具执行完，哪条线带正文？** 文件后端把读取结果交回 `tool-fs`，工具系统把正文和调用 ID 记成 `tool/result`。另一条线从 `ToolsService.execute` 回到循环，带回本批执行结果；循环查看其中的完成状态，决定是否再走一步。下一步 `deriveMessages` 把包含文件正文的消息交给 `buildRequest`，组好的请求再交回循环发送。[工具结果写进会话](https://github.com/deepseek-ai/deepseek-harness/blob/4b399c39a6d1479cd84ca591b4d7c88e24d38a96/packages/core/tools/src/batch.ts#L243-L268) · [循环使用批次状态](https://github.com/deepseek-ai/deepseek-harness/blob/4b399c39a6d1479cd84ca591b4d7c88e24d38a96/packages/core/agent-loop/src/agent.ts#L576-L587) · [本轮请求的返回值](https://github.com/deepseek-ai/deepseek-harness/blob/4b399c39a6d1479cd84ca591b4d7c88e24d38a96/packages/core/agent-loop/src/agent.ts#L717-L733)
- **终端怎么拿到 `DONE`？** headless 等会话空闲、刷新日志，再从本轮记录里取出最后的助手文本并打印。[headless 读取最终结果](https://github.com/deepseek-ai/deepseek-harness/blob/4b399c39a6d1479cd84ca591b4d7c88e24d38a96/packages/bundle/headless/src/index.ts#L418-L437)

<details>
<summary>展开原版 Mermaid 架构图及源码入口</summary>

```mermaid
---
config:
  theme: base
  themeVariables:
    background: "#ffffff"
    primaryColor: "#ffffff"
    primaryTextColor: "#303030"
    primaryBorderColor: "#757575"
    secondaryColor: "#ffffff"
    secondaryTextColor: "#303030"
    secondaryBorderColor: "#999999"
    tertiaryColor: "#ffffff"
    tertiaryTextColor: "#303030"
    tertiaryBorderColor: "#c4c4c4"
    mainBkg: "#ffffff"
    clusterBkg: "#ffffff"
    clusterBorder: "#c4c4c4"
    edgeLabelBackground: "#ffffff"
    nodeBorder: "#757575"
    lineColor: "#505050"
    textColor: "#303030"
    titleColor: "#303030"
  flowchart:
    nodeSpacing: 34
    rankSpacing: 32
    padding: 11
---
flowchart TB
  CLI["apps/cli · headless profile"] --> RUN["headless.run · agents.create / agent.followup"]
  subgraph Agent["core/agent-loop"]
    DRIVER["ReactLoopAgent · turn / preStep / step"]
    BUILD["buildRequest · 产生 GenerateOptions"]
  end
  RUN --> DRIVER
  subgraph Input["选择本步能力与上下文"]
    TOOLS["工具注册表 · core/tools<br/>resolve → 本步 ResolvedToolSet"]
    PROMPT["core/system-prompt · assemble / systemUpdates"]
    CTX["RuntimeContextProjection · project"]
  end
  DRIVER <-->|② resolve 选出本步工具集| TOOLS
  DRIVER <-->|组装 / 本步提示| PROMPT
  DRIVER <-->|读取 / 环境更新| CTX
  DRIVER --> BUILD
  subgraph State["core/session"]
    LOG["Session.append · 有序事件"]
    VIEW["Session.deriveMessages · 当前消息历史"]
  end
  DRIVER -->|追加指令、用户与助手消息| LOG
  LOG --> VIEW
  BUILD -->|取本步对话历史| VIEW
  subgraph Provider["模型服务路径"]
    LLM["LlmRuntime.prepareCall / stream"]
    WIRE["llm-deepseek · serialize / fetch / translate"]
    NET["DeepSeek Messages API"]
  end
  DRIVER -->|带工具声明的请求| LLM --> WIRE -->|③ tools 数组：name、description、input_schema| NET
  subgraph Local["文件操作路径"]
    EXEC["ToolsService.execute · 工具策略 / native executor"]
    FS["tool-fs · read / edit"]
    GUARD["fs-sandbox · editText / checkedTarget"]
    DISK["fs-local · readText / editText"]
  end
  DRIVER -->|④ 模型返回的名字 + 本步工具集| EXEC -->|④ 按名执行 read 或 edit| FS
  FS -->|"只读"| DISK
  FS -->|"修改"| GUARD -->|授权后委托写入| DISK
  FS -.->|"① register：声明和执行函数"| TOOLS
  FS -.->|"注册工具使用说明"| PROMPT
  EXEC -->|"写入事件：tool/result"| LOG
  NET -.->|返回：SSE 事件| WIRE
  WIRE -.->|返回：StreamChunk 流| LLM
  LLM -.->|返回：流片段由循环组装| DRIVER
  DISK -.->|返回：读取的正文| FS
  DISK -.->|返回：修改结果| GUARD
  GUARD -.->|返回：修改结果| FS
  FS -.->|返回：文件工具执行值| EXEC
  EXEC -.->|返回：批次状态 / 附加上下文| DRIVER
  VIEW -.->|返回：本步消息列表| BUILD
  BUILD -.->|返回：组好的模型请求| DRIVER
  LOG -.->|读日志得到 DONE| RUN
  CLI -.->|① profile 装载 tool-fs| FS
  TOOLS -->|② 经 preStep 提供本步工具集| PROMPT
  PROMPT -->|③ 经 step 传入 assembly.tools| BUILD
  click RUN href "https://github.com/deepseek-ai/deepseek-harness/blob/4b399c39a6d1479cd84ca591b4d7c88e24d38a96/packages/bundle/headless/src/index.ts#L385" "打开固定版本源码"
  click DRIVER href "https://github.com/deepseek-ai/deepseek-harness/blob/4b399c39a6d1479cd84ca591b4d7c88e24d38a96/packages/core/agent-loop/src/agent.ts#L286" "打开固定版本源码"
  click BUILD href "https://github.com/deepseek-ai/deepseek-harness/blob/4b399c39a6d1479cd84ca591b4d7c88e24d38a96/packages/core/agent-loop/src/agent.ts#L714" "打开固定版本源码"
  click VIEW href "https://github.com/deepseek-ai/deepseek-harness/blob/4b399c39a6d1479cd84ca591b4d7c88e24d38a96/packages/core/session/src/index.ts#L760" "打开固定版本源码"
  click WIRE href "https://github.com/deepseek-ai/deepseek-harness/blob/4b399c39a6d1479cd84ca591b4d7c88e24d38a96/packages/llm/llm-deepseek/src/serialize.ts#L118" "打开固定版本源码"
  click FS href "https://github.com/deepseek-ai/deepseek-harness/blob/4b399c39a6d1479cd84ca591b4d7c88e24d38a96/packages/fs/tool-fs/src/edit.ts#L120" "打开固定版本源码"
  click GUARD href "https://github.com/deepseek-ai/deepseek-harness/blob/4b399c39a6d1479cd84ca591b4d7c88e24d38a96/packages/fs/fs-sandbox/src/index.ts#L153" "打开固定版本源码"
  click TOOLS href "https://github.com/deepseek-ai/deepseek-harness/blob/4b399c39a6d1479cd84ca591b4d7c88e24d38a96/packages/core/tools/src/index.ts#L110" "本地工具和模型可见声明"
  click PROMPT href "https://github.com/deepseek-ai/deepseek-harness/blob/4b399c39a6d1479cd84ca591b4d7c88e24d38a96/packages/core/system-prompt/src/index.ts#L757" "生成本轮工具声明"
  linkStyle 20,21,22,23,24,25,26,27,28,29,30 stroke:#444444,stroke-width:1.65px,stroke-dasharray:7 4;
```

</details>

现在打开 dsh 仓库里这次改 config.txt 的录制。刚才是沿图走，这次顺着记录找：第 5 行，用户的任务进入队列；第 10 行，准备第一步时，同一句话被记成一条用户消息。[原始会话记录，第 5–12 行](https://github.com/deepseek-ai/deepseek-harness/blob/4b399c39a6d1479cd84ca591b4d7c88e24d38a96/snapshots/session/fs-edit/session.v4.jsonl#L5-L12)

先停在 `ReactLoopAgent` 准备第一步的位置。此时用户的输入已经有了。dsh 还要给这次请求补三样东西。**谁在工作、工具怎么用**，由框架和启用的工具提供说明；稍后你会在系统指令 `system` 里看见它们。**当前在哪里工作、有什么权限**，由 dsh 从这次会话取出来，写成一段环境提醒。**模型能选哪些工具**，由本地登记好的工具清单提供。它们跟用户输入拼在一起，才够模型开始工作。

先看第 9–12 行的**本地记录**。下方把四条日志按原顺序列成一个 JSON 数组，每条只摘相关字段。`data` 装事件数据；只要关注里面是谁提供了哪段文字就够了。其中 `type` 告诉我们 dsh 记下了什么事，`source.kind` 说明对应消息来自哪里。归档用 `{{system}}` 和 `{{tools}}` 代指另外保存的指令全文和工具清单，用 `{{cwd}}` 代指当时的工作目录。拿用户的那句话当参照，看看它前后各多出了什么。

```json
[
  {
    "type": "system/message",
    "data": {
      "message": {
        "role": "system",
        "content": [{"type": "text", "text": "{{system}}"}],
        "source": {"kind": "system-prompt"}
      }
    }
  },
  {
    "type": "user/message",
    "data": {
      "role": "user",
      "source": {"kind": "user"},
      "content": [
        {
          "type": "text",
          "text": "First use the read tool to read config.txt in the current directory. …"
        }
      ]
    }
  },
  {
    "type": "user/message",
    "data": {
      "role": "user",
      "source": {"kind": "runtime-context"},
      "content": [
        {
          "type": "text",
          "text": "<system-reminder>\nThe following information describes your current session:\n\nCurrent working directory: \"{{cwd}}\".\n…"
        }
      ]
    }
  },
  {
    "type": "request/header",
    "data": {
      "header": {"config": {"provider": "deepseek-official", "model": "deepseek-v4-flash"}, "tools": "{{tools}}"}
    }
  }
]
```

第 9 行放系统指令。每段都有来源，比如框架身份、运行模式、`edit` 的用法；归档把长文本收到了配套文件，这里以 `{{system}}` 占位。第 10 行是用户自己打的原话。第 11 行同样记作 `user/message`，但来源写的是 `runtime-context`，也就是 dsh 补进去的运行环境。第 12 行登记这次用的模型和工具清单。到这一步，本地既知道一句话要带给模型，也知道这句话是谁加的。[归档的英文系统指令](https://github.com/deepseek-ai/deepseek-harness/blob/4b399c39a6d1479cd84ca591b4d7c88e24d38a96/snapshots/session/text-turn/system-prompt.expected.md) · [归档的工具清单](https://github.com/deepseek-ai/deepseek-harness/blob/4b399c39a6d1479cd84ca591b4d7c88e24d38a96/snapshots/session/text-turn/tool-schemas.expected.json)

### 24:00　首包对照：同一个工作目录，两边从哪里带给模型？

现在把模型接口需要的 JSON 展开：`model` 指定模型，`system` 放工作说明，`messages` 放会话内容，`tools` 列它能调用的工具。下面三份 dsh 请求都用当时的消息和归档原文，交给当前源码的适配器在本机生成；原录制保留的是会话事件。我们主要对照消息角色和内容。[三份完整请求体](./harness-requests.json)

**发出 ① · dsh 请求体节选。** 保留同一条 user 消息里的两个文本块，24 项工具只展开 `read` 的名称和说明。`…` 表示省去一段原文。

```json
{
  "model": "deepseek-v4-flash",
  "system": "You are an AI agent powered by DeepSeek Harness.\n…\nRead a file before editing it unless you just created or edited it in this session.\n…",
  "messages": [
    {
      "role": "user",
      "content": [
        {
          "type": "text",
          "text": "First use the read tool to read config.txt in the current directory. …"
        },
        {
          "type": "text",
          "text": "<system-reminder>\nThe following information describes your current session:\n\nCurrent working directory: \"{{cwd}}\".\n…"
        }
      ]
    }
  ],
  "tools": [{"name": "read", "description": "Read a UTF-8 text file and return line-numbered content."}]
}
```

我们用手指走三下就能对上。先看顶层的 `system`，里面有一句 `Read a file before editing it unless you just created or edited it in this session.`，意思是编辑前先读文件。这句话来自前面第 9 行那组工具使用说明。再看 `messages`，里面只有一条 `user`。点开这条的 `content` 却有两块：第一块是第 10 行的英文用户任务，第二块以 `<system-reminder>` 开头，来自第 11 行的运行环境。dsh 适配器把这两条相邻消息装进了同一个列表项，里面仍然保留两个文本块。最后看顶层 `tools`，它对应第 12 行的工具清单，模型从中能找到 `read` 和它的参数。[相邻消息如何进入请求](https://github.com/deepseek-ai/deepseek-harness/blob/4b399c39a6d1479cd84ca591b4d7c88e24d38a96/packages/llm/llm-deepseek/src/serialize.ts#L107-L129)

> **投影**　先只看用户那块文本，再展开旁边的环境提醒。问大家：“用户有没有告诉模型当前目录？模型收到第一份请求时，有没有这条信息？”这两个问题可以有不同的答案。归档里的 `{{cwd}}` 代表录制时的目录。

把两份首包并排，找同一个事实：**工作目录是谁告诉模型的？**

| 找这件事 | pi 的第一次请求 | dsh 的第一次请求 |
|---|---|---|
| 在本地由谁提供 | pi 把当前目录放进系统提示的 `cwd` 段。 | 会话把目录和权限提供给运行环境插件，日志另记一条来源为 `runtime-context` 的消息。 |
| 在发出的包里去哪找 | 展开 `messages[0]`。它的角色是 `system`，正文里能搜到 `<cwd>`。 | 展开 `messages[0].content[1]`。它和用户任务同属一条 `user` 消息，以 `<system-reminder>` 开头；工作指令另放在顶层 `system`。 |

这个对照里有两个原因。**目录最初记到哪里**，由 harness 决定。**系统指令在 JSON 里用哪个字段**，还取决于选的模型接口：这里 pi 走 Chat Completions，dsh 走 DeepSeek Messages。两边的用户都没在任务里写出当前目录，两边也都能在第一轮把目录带给模型。[两份首包及发送前的记录](./harness-requests.json)

### 27:00　同一次 read，pi 从当前分支取，dsh 从日志重建

同样从用户按回车读起。留意文件工具读完后的那条返回线：结果先记进 dsh 的会话日志，下一次向模型发请求时才带上它。

![dsh 从用户输入到三次模型请求、两次本地工具执行，最终把 DONE 返回给用户](./dsh-request-sequence.svg)

[并排看 pi 的时序图](./pi-request-sequence.svg) · [放大 dsh 的时序图](./dsh-request-sequence.svg)

先把模型的回答和工具的回答分开看。第一轮模型发出的要求翻成口语就是“用 `read` 读 `config.txt`”。这次工具调用带着编号 `fs-edit-read`。dsh 把这句话登记成助手回复，再让本地文件工具去打开文件。工具读完，才出现第 17 行的 `tool/result`。它给出的正文里有路径和行号，可以找到下面这两行。[模型要求、工具执行和返回，第 15–18 行](https://github.com/deepseek-ai/deepseek-harness/blob/4b399c39a6d1479cd84ca591b4d7c88e24d38a96/snapshots/session/fs-edit/session.v4.jsonl#L15-L18)

```text
1: mode=DEBUG
2: level=info
```

再问模型，就得让它知道“刚才是你让我读的”和“这是我读到的内容”。循环去本地会话取出到这一步的对话历史，第一份请求里的那条用户消息还在，后面跟上了下面这一对。看 JSON 前先认两个词：`tool_use` 是模型想调用工具，`tool_result` 是本地执行后的结果。[请求怎样拿到当前历史](https://github.com/deepseek-ai/deepseek-harness/blob/4b399c39a6d1479cd84ca591b4d7c88e24d38a96/packages/core/agent-loop/src/agent.ts#L714-L733)

我们把第二轮送进适配器之前的本地历史先投成一行，只读各条消息的来源角色：`["system", "user", "user", "assistant", "tool"]`。前面两条 `user` 就是人说的话和框架的提醒。最后一条 `tool` 是本地工具回执。下面看同一次提交给模型时，这五项怎么装进一份请求。完整的本地输入也在附件 `dsh.local_before_send[1]` 里。

**发出 ② · 完整消息顺序，共 3 项。** 前 1 项与上一轮相同，末尾两项是本轮新增。下面按原顺序显示每一项，长指令和部分字段折叠；`…` 由讲稿添加。本轮模型和工具清单沿用第一份。

```json
[
  {
    "role": "user",
    "content": [
      {"type": "text", "text": "First use the read tool to read config.txt in the current directory. …"},
      {
        "type": "text",
        "text": "<system-reminder>\nThe following information describes your current session:\n\nCurrent working directory: \"{{cwd}}\".\n…"
      }
    ]
  },
  {
    "role": "assistant",
    "content": [{"type": "tool_use", "id": "fs-edit-read", "name": "read", "input": {"file_path": "config.txt"}}]
  },
  {
    "role": "user",
    "content": [
      {
        "type": "tool_result",
        "tool_use_id": "fs-edit-read",
        "content": [
          {
            "type": "text",
            "text": "<path>{{cwd}}/config.txt</path>\n<type>file</type>\n<content>\n1: mode=DEBUG\n2: level=info\n\n(End of file - total 2 lines)\n</content>"
          }
        ],
        "is_error": false
      }
    ]
  }
]
```

在两份第二轮请求里搜同一个编号 `fs-edit-read`。两边都能定位到“谁要求读”和“文件工具回了什么”，只看 `role` 则很容易读错：

| 跟着 `fs-edit-read` 走 | pi | dsh |
|---|---|---|
| 本地怎样记 | 助手调用和 `toolResult` 接到当前会话分支上。下轮从该分支取历史。 | 助手回复、工具结果和 `step/end` 都是有顺序的事件。下轮从日志取出模型可见的对话。 |
| 模型第二次怎样看到两行正文 | 在 `role: "tool"` 的消息里，经 `tool_call_id` 与上一次调用相连。 | 在 `role: "user"` 里面的 `tool_result` 块里，经 `tool_use_id` 与上一次调用相连。 |

这会改变我的调试习惯。在 pi 里，我先问“当时走的是哪条会话分支，发出前扩展又加了什么？”在 dsh 里，我先问“哪个事件引入了这段文字，它有没有被选进请求？”dsh 把“模型可见的输入要能从记录重建”写进了架构约定，所以写插件时，新增模型可见的信息也得交代它怎样留在日志里。pi 则允许扩展在发出前调整本次请求的消息；要查调整后的实际内容，我们这次就直接记录了发包时的 JSON。[pi 如何选当前会话历史](https://github.com/earendil-works/pi/blob/8209929fb553e7a8c91dc0894569f9ec43dd201f/packages/coding-agent/src/core/agent-session.ts#L852-L879) · [pi 的逐次请求钩子](https://github.com/earendil-works/pi/blob/8209929fb553e7a8c91dc0894569f9ec43dd201f/packages/coding-agent/docs/extensions.md#L815-L831) · [dsh 的记录约定](https://github.com/deepseek-ai/deepseek-harness/blob/4b399c39a6d1479cd84ca591b4d7c88e24d38a96/docs/architecture.md#L136-L140)

> **投影**　沿日志第 17 行的 `level=info` 一路指到第二份请求最后一条消息，再把第 18 行的 `step/end` 也找一遍。`step/end` 留在本地帮助 dsh 记录进度。这样就能亲眼确认，会话记录里的内容是经过挑选才进入模型输入的。



### 31:30　同一次 edit，谁有权写，谁知道已经写好？

两个模型回复都要求在 `config.txt` 里把 `DEBUG` 换成 `RELEASE`，编号同为 `fs-edit-replace`。磁盘由本地工具改，这一步两边相同。把目标从当前目录换到另一个项目，就会碰到一个真正影响部署的差别。

pi 默认沿用启动进程的系统权限。dsh 在文件工具和磁盘之间接了一层沙箱，由它判断这个路径能不能改。这段录制放开了 dsh 的路径限制，所以这里会看到修改成功的回执。等到第 20 页，我们切到新会话的默认配置，把同样的修改指向隔壁项目，看看调用停在哪。[pi 的默认权限](https://github.com/earendil-works/pi/blob/8209929fb553e7a8c91dc0894569f9ec43dd201f/README.md#L88-L98) · [dsh 的默认权限](https://github.com/deepseek-ai/deepseek-harness/blob/4b399c39a6d1479cd84ca591b4d7c88e24d38a96/packages/bundle/base/cordis.patch.yml#L243-L282) · [录制采用的权限](https://github.com/deepseek-ai/deepseek-harness/blob/4b399c39a6d1479cd84ca591b4d7c88e24d38a96/snapshots/session/fs-edit/session.v4.jsonl#L1-L4)

**发出 ③ · 完整消息顺序，共 5 项。** 前 3 项与上一轮相同，末尾两项是本轮新增。下面按原顺序显示每一项，长指令和部分字段折叠；`…` 由讲稿添加。本轮模型和工具清单沿用第一份。

```json
[
  {
    "role": "user",
    "content": [
      {"type": "text", "text": "First use the read tool to read config.txt in the current directory. …"},
      {
        "type": "text",
        "text": "<system-reminder>\nThe following information describes your current session:\n\nCurrent working directory: \"{{cwd}}\".\n…"
      }
    ]
  },
  {
    "role": "assistant",
    "content": [{"type": "tool_use", "id": "fs-edit-read", "name": "read", "input": {"file_path": "config.txt"}}]
  },
  {
    "role": "user",
    "content": [
      {
        "type": "tool_result",
        "tool_use_id": "fs-edit-read",
        "content": [
          {
            "type": "text",
            "text": "<path>{{cwd}}/config.txt</path>\n<type>file</type>\n<content>\n1: mode=DEBUG\n2: level=info\n\n(End of file - total 2 lines)\n</content>"
          }
        ],
        "is_error": false
      }
    ]
  },
  {
    "role": "assistant",
    "content": [
      {
        "type": "tool_use",
        "id": "fs-edit-replace",
        "name": "edit",
        "input": {"file_path": "config.txt", "old_string": "DEBUG", "new_string": "RELEASE"}
      }
    ]
  },
  {
    "role": "user",
    "content": [
      {
        "type": "tool_result",
        "tool_use_id": "fs-edit-replace",
        "content": [{"type": "text", "text": "The file {{cwd}}/config.txt has been updated successfully."}],
        "is_error": false
      }
    ]
  }
]
```

沿列表从头看一遍，第一项仍然是任务和环境提醒，接着是上一轮 `read` 的要求及返回，最后才是刚刚新增的 `edit` 要求及返回。此时文件已经改好，可是历史里那条旧的读取结果仍然写着 `mode=DEBUG`。它记录的是**读取当时**看到的内容。模型判断已经改好，靠的是末尾这句 `The file {{cwd}}/config.txt has been updated successfully.`。如果用户还想让它再打开核对，就要再走一轮 `read`。

第三份请求发出以后，模型才回复 `DONE`。可以在会话记录第 25 行看到这条助手回复。它属于这次请求的返回值，下一行是步骤结束，再下一行是整轮结束。这样我们能在记录里把三个时刻分清：文件在第二轮工具执行时改变，模型在第三次请求里看见成功回执，用户随后看见 `DONE`。[最终回复和任务结束，第 25–27 行](https://github.com/deepseek-ai/deepseek-harness/blob/4b399c39a6d1479cd84ca591b4d7c88e24d38a96/snapshots/session/fs-edit/session.v4.jsonl#L25-L27)

> **投影**　并排放三份请求，只读 `messages` 的最后一项，依次是“任务和提醒”“读取回执”“修改回执”。三份的 `system` 和工具清单相同，消息列表是 **1 → 3 → 5**。两个框架都在第二次请求才见到 `level=info`。

### 33:00　为什么第一轮 pi 有两条消息，dsh 只有一条？

看第 19 页。刚才我们只敲了一次回车，让它读 config.txt，再把 DEBUG 改成 RELEASE。框架自己也有话要交代。比如 pi 写了 `Use edit for targeted changes.`，意思是只改文件的一小处就用 edit。dsh 的说明里有一句以 `Read a file before editing it` 开头，讲的是编辑前先读文件。这些用工具的说明都写在系统提示词里。

现在只数 `messages` 那对方括号里的条目。左边 pi 有两条，第一条标着 `system`，装的是框架的说明；第二条标着 `user`，才轮到我们那句话。右边 dsh 把说明放到了方括号外面，和 `messages` 并排。两个字段随同一份请求发给模型。这样，列表里就只有一条 `user`，把它展开能看到用户的原话和框架补的环境提醒。

接下来的两轮很好数。每轮把刚才的工具调用和结果加进去，各多两条。所以 pi 是 2、4、6，dsh 是 1、3、5。接下来看 Plan Mode 时，可以继续盯着这份请求，看看开关一拨，框架又交代了什么。

## 34:30–37:00　两边怎样用插件改变同一个循环？

还是改 config.txt。先看 pi 的官方 Plan 扩展示例。打开规划，盯着从 AgentSession 发给模型的工具列表，`read` 还在，`edit` 和 `write` 消失了。如果模型选了 `bash`，pi 在运行命令前触发本地事件 `tool_call`。Plan 扩展监听这个事件，检查命令：`ls` 放行，`touch note.txt` 就拦住，把原因交回循环。[pi 怎样切换工具清单](https://github.com/earendil-works/pi/blob/8209929fb553e7a8c91dc0894569f9ec43dd201f/packages/coding-agent/examples/extensions/plan-mode/index.ts#L94-L118) · [Plan 扩展监听 tool_call](https://github.com/earendil-works/pi/blob/8209929fb553e7a8c91dc0894569f9ec43dd201f/packages/coding-agent/examples/extensions/plan-mode/index.ts#L167-L178)

切到 dsh 的「发请求前选工具」。每轮 core/tools.resolve 都会按启用条件选出工具集。第一次开规划，exit_plan_mode 满足条件，和 edit、write 一起列在清单里。循环把这份清单发给模型，执行时也按同一份清单找工具。规划插件另外加了系统提示，让模型用 exit_plan_mode 交计划。仓库的测试里，模拟模型在规划中调用 write，工具照样执行成功。[dsh 规划规则插入点](https://github.com/deepseek-ai/deepseek-harness/blob/4b399c39a6d1479cd84ca591b4d7c88e24d38a96/packages/plan/plan-mode/src/index.ts#L193-L222) · [规划工具的启用时机](https://github.com/deepseek-ai/deepseek-harness/blob/4b399c39a6d1479cd84ca591b4d7c88e24d38a96/packages/plan/plan-mode/src/index.ts#L15-L18)

再点「调用后在哪拦」，顺着同一次 edit 看。第一站是 tools/pre-execute。如果额外装了拒绝 edit 的策略，这里就能把原因交回循环，文件工具还没动。再切到「另一个未授权项目」：这回执行前的策略放行，tool-fs 把路径交给 fs-sandbox，沙箱发现越界，在写盘前拦住。这次拒绝的原因会回到模型。它可以重新调用 edit 并说明理由，Web 用户批准后只放行这一次。[执行前策略](https://github.com/deepseek-ai/deepseek-harness/blob/4b399c39a6d1479cd84ca591b4d7c88e24d38a96/packages/core/tools/src/events.ts#L7-L18) · [文件路径检查](https://github.com/deepseek-ai/deepseek-harness/blob/4b399c39a6d1479cd84ca591b4d7c88e24d38a96/packages/fs/fs-sandbox/src/index.ts#L156-L177) · [批准单次操作](https://github.com/deepseek-ai/deepseek-harness/blob/4b399c39a6d1479cd84ca591b4d7c88e24d38a96/packages/fs/tool-fs/src/sandbox.ts#L94-L114)

> **讲者备查**　第 20 页的路径演示采用 dsh 默认配置 `workspace-write + ask`，授权目录内可写，扩大范围可申请。前面回放用的是 `danger-full-access + never`，dsh 不限制文件路径，也不向人申请额外权限。两种配置下都受操作系统权限约束。 [新会话的默认权限](https://github.com/deepseek-ai/deepseek-harness/blob/4b399c39a6d1479cd84ca591b4d7c88e24d38a96/packages/bundle/base/cordis.patch.yml#L243-L282) · [回放采用的权限](https://github.com/deepseek-ai/deepseek-harness/blob/4b399c39a6d1479cd84ca591b4d7c88e24d38a96/snapshots/session/fs-edit/session.v4.jsonl#L1-L4)

### 35:30　同样的功能，两边要改哪一层？

先看「换文件后端」。假设 config.txt 在本机和 SSH 远端各有一份。两边的 edit 都已经改了远端那份。现在请模型调用附录里的另一个工具 `read_config` 来核对。大家猜，它读回来的是哪一份？

顺着 pi 的两条线看。SSH 示例换了名叫 edit 的工具，`read_config` 却是我们自己写的，里面直接调 Node 的 `readFile`，所以读回本机那份。再看 dsh，两条线都汇到 `ctx.fs`：edit 通过它改文件，`read_config` 通过它读文件。把这个服务换成 `fs-ssh`，两条线就都通到远端。这里看出来了：换一个工具，影响点名这个工具的调用。换一个共用服务，影响所有经过它的调用。[pi 的 SSH 示例替换具名工具](https://github.com/earendil-works/pi/blob/8209929fb553e7a8c91dc0894569f9ec43dd201f/packages/coding-agent/examples/extensions/ssh.ts#L128-L169) · [dsh 的远端 readText](https://github.com/deepseek-ai/deepseek-harness/blob/4b399c39a6d1479cd84ca591b4d7c88e24d38a96/packages/ssh/fs-ssh/src/index.ts#L40-L49) · [dsh 的远端 editText](https://github.com/deepseek-ai/deepseek-harness/blob/4b399c39a6d1479cd84ca591b4d7c88e24d38a96/packages/ssh/fs-ssh/src/index.ts#L85-L91)

再点「加门禁」。就拿同一条规则：不准用 edit 改 .env。pi 可以监听 `tool_call` 并拦住调用。dsh 也可以写个策略插件，在 `tools/pre-execute` 返回拒绝。这件小事两边做起来很像。[pi 官方路径检查示例](https://github.com/earendil-works/pi/blob/8209929fb553e7a8c91dc0894569f9ec43dd201f/packages/coding-agent/examples/extensions/protected-paths.ts#L10-L28) · [dsh 执行前策略接口](https://github.com/deepseek-ai/deepseek-harness/blob/4b399c39a6d1479cd84ca591b4d7c88e24d38a96/packages/core/tools/src/events.ts#L7-L18)

最后点「换循环」。pi 把现成循环交给你扩展。真要整个换掉，就要自己搭主程序，或改核心。dsh 连默认循环都是启动配置选的插件。你可以换成自己写的，但得实现创建和恢复 agent 的接口，并让新工厂接替旧工厂。[pi 的 Agent 直接调用循环](https://github.com/earendil-works/pi/blob/8209929fb553e7a8c91dc0894569f9ec43dd201f/packages/agent/src/agent.ts#L439-L453) · [dsh 循环插件登记工厂](https://github.com/deepseek-ai/deepseek-harness/blob/4b399c39a6d1479cd84ca591b4d7c88e24d38a96/packages/core/agent-loop/src/index.ts#L328-L338) · [同一注册表内的工厂约束](https://github.com/deepseek-ai/deepseek-harness/blob/4b399c39a6d1479cd84ca591b4d7c88e24d38a96/packages/core/agent/src/index.ts#L377-L397)

## 37:00–38:00　昨天的约定，今天怎么找回来？

昨天我们告诉助手：“记住，A 项目的发布说明用中文写。”今天开新会话，只让它写发布说明。这句“用中文”怎么回来？

**pi-memory** 有两本笔记：这条长期约定写 MEMORY.md；今天做了什么，写进 daily/2026-11-24.md。新会话默认带上限长快照，里面有长期笔记和今天、昨天的日志。好处是笔记能自己改；代价是暂时用不到的内容也占上下文。

**Hermes** 按项目保存，一条约定写在这个项目的 MEMORY.md 里，同步到本地数据库 sessions.db。开场先告诉模型什么时候该查。模型想到要查，就用 memory_search 搜关键词，搜到的约定随工具结果进下一轮。这样省上下文，也有漏查的可能。

**Remnic** 把明确要记的事实交给独立服务。它会建 facts/2026-11-24/ 这样的日期目录，每条事实一个 Markdown 文件。今天这句“帮我写发布说明”本身就触发检索，命中片段随第一份请求给模型。它省了模型主动查的一步，但要运行服务，而且开场的话题会影响这次会话找回什么。

> **讲者备查**　这是同一条项目约定的源码走读。三种插件分别使用默认取回策略，演示中的普通会话没有加载它们。下面三项可按提问展开。

**pi-memory v0.4.2**　模型调用 memory_write 必须选目标：long_term 写长期约定，daily 按本地日期追加到当天的 .md 文件。

```text
~/.pi/agent/memory/
├─ MEMORY.md
├─ SCRATCHPAD.md
└─ daily/
   └─ 2026-11-24.md
```

会话启动时，插件读取长期笔记、未完成待办和今天、昨天已有的日记，按长度上限拼成快照。默认模式直接取这份快照。快照在任务开始前加进系统提示词。上周的日记仍在磁盘上，需要另读；今天的快照里只会取今天和昨天已有的日志。

稳定约定少时最省事，打开 Markdown 就能核对和修改。常驻笔记占上下文，超出快照的条目要另读。安装搜索组件 qmd 后，也可以单独查旧笔记。 [默认目录](https://github.com/jayzeng/pi-memory/blob/v0.4.2/index.ts#L50-L64) · [日期文件名](https://github.com/jayzeng/pi-memory/blob/v0.4.2/index.ts#L137-L142) · [两种写入目标](https://github.com/jayzeng/pi-memory/blob/v0.4.2/index.ts#L1635-L1744) · [取今天和昨天](https://github.com/jayzeng/pi-memory/blob/v0.4.2/index.ts#L780-L852)

**Hermes Memory v0.11.0**　memory_add 选 project 时按项目名找 MEMORY.md。日期记在条目里；本机的 sessions.db 是默认查询用的数据库。

```text
~/.pi/agent/
├─ projects-memory/
│  └─ A/MEMORY.md
└─ pi-hermes-memory/
   └─ sessions.db
```

默认先给模型一段“什么时候该查”的说明。模型如果决定查，就调用 memory_search，可限定当前项目，用关键词找匹配条目。命中的约定作为工具结果进入下一次请求。模型这次没查，就可能用不上昨天的约定。

适合积累了很多项目决定、每次只用几条的团队。只把查到的内容带入上下文。要等模型主动查，关键词也可能没匹配上。命中后通常多一次模型调用。 [项目目录](https://github.com/chandra447/pi-hermes-memory/blob/v0.11.0/src/project.ts#L84-L122) · [写入与同步](https://github.com/chandra447/pi-hermes-memory/blob/v0.11.0/src/tools/memory-tool.ts#L319-L368) · [数据库文件](https://github.com/chandra447/pi-hermes-memory/blob/v0.11.0/src/store/db.ts#L179-L188) · [按词检索](https://github.com/chandra447/pi-hermes-memory/blob/v0.11.0/src/store/sqlite-memory-store.ts#L849-L892)

**Remnic v9.69.56**　/remnic-remember 明确保存一条事实。服务按 UTC 日期建目录，每条事实写一份 Markdown。图中省略文件的唯一编号。

```text
当前命名空间的存储根目录/
└─ facts/
   └─ 2026-11-24/
      └─ fact-….md
```

开启自动检索、凭据和服务可用时，插件拿新会话的首条非空输入尝试查询，按相关性找片段。服务也能从上报的对话里提取事实。查到“用中文写”后，插件在问模型之前把它放进系统提示词。这个会话会复用开场查到的片段。

历史多、又希望开场就补上相关背景时，模型可以省去主动搜索这一步。要运行并配置独立服务。中途转去聊别的话题，开场找回的内容可能不合用。 [命令指定 fact](https://github.com/joshuaswarren/remnic/blob/v9.69.56/packages/plugin-pi/src/client.ts#L282-L289) · [日期目录](https://github.com/joshuaswarren/remnic/blob/v9.69.56/packages/remnic-core/src/storage.ts#L3668-L3684) · [生成文件编号](https://github.com/joshuaswarren/remnic/blob/v9.69.56/packages/remnic-core/src/storage.ts#L3712-L3725) · [检索与注入](https://github.com/joshuaswarren/remnic/blob/v9.69.56/packages/plugin-pi/src/index.ts#L168-L214)

> **本地核对**　复核方式：在隔离的临时目录里，用 pi-memory v0.4.2 的实际 memory_write 写入两种目标，再运行 session_start 和 before_agent_start。快照带上了长期约定、今天和昨天的日志，没有带上较早的测试日志。测试替代了 pi 的注册接口，未调用在线模型。Hermes 与 Remnic 的路径按各自固定版本的写入、检索源码核对。

pi-memory 的正常退出流程若成功生成非空摘要，也会追加到当天的 daily 文件；默认切换会话时跳过这一步。[退出摘要写入](https://github.com/jayzeng/pi-memory/blob/v0.4.2/index.ts#L1465-L1517)　Hermes 表中是普通项目记忆。用户显式置顶的 STANDING.md 可以直接注入；普通项目条目的创建日期保存在条目元数据中。[默认提示策略](https://github.com/chandra447/pi-hermes-memory/blob/v0.11.0/src/prompt-context.ts#L36-L65) · [日期元数据](https://github.com/chandra447/pi-hermes-memory/blob/v0.11.0/src/store/memory-store.ts#L658-L675)　Remnic 图中是 /remnic-remember 指定的 fact 写入路径。服务观察到的原始对话转录另有按日的 JSONL 文件。[显式保存命令](https://github.com/joshuaswarren/remnic/blob/v9.69.56/packages/plugin-pi/src/index.ts#L350-L360) · [转录路径](https://github.com/joshuaswarren/remnic/blob/v9.69.56/packages/remnic-core/src/transcript.ts#L101-L132)

## 38:00–40:00　给团队做助手，怎么选 pi 和 dsh？

> **台上操作 · 38:00–40:00**　默认页挑“个人开发者”和“平台工程师”各举一例，随后点「同模型实测」。其余行和「按模型选」可在提问时展开。

前面两个 SSH 例子都能改远端文件。真要给组里选，我会问一句：未来半年，我们改得最勤的是什么？我自己在终端里用，只想在 edit 前加一道检查，我会先上 pi，写一个扩展就够了。如果组里有 Web 和命令行两套入口，我得保证两个入口的文件工具都去同一台远端，那我会先上 dsh，让它们用同一个文件服务。新工具只要也接 ctx.fs，这次更换就覆盖得到；直接读本机的工具仍得另外改。 [pi 工具扩展点](https://github.com/earendil-works/pi/blob/8209929fb553e7a8c91dc0894569f9ec43dd201f/packages/coding-agent/docs/extensions.md#L350-L371) · [dsh SSH 文件后端](https://github.com/deepseek-ai/deepseek-harness/blob/4b399c39a6d1479cd84ca591b4d7c88e24d38a96/packages/ssh/fs-ssh/src/index.ts#L85-L91)

| 谁在用 | 需求 | 先试 | 优势与代价 |
|---|---|---|---|
| 个人开发者 | 经常给终端助手加规则、小工具 | pi | 沿已有循环接一个扩展。规则只管经过它的调用。 |
| 模型评测同学 | 用同套工具轮换多家模型 | pi | 配置好模型后可切换；先验证各家的工具调用格式。 |
| 团队平台工程师 | Web、命令行一起切 SSH 文件后端 | dsh | 共用 ctx.fs 的工具一起切换；要配好 SSH 和沙箱策略。 |
| 运维或排障同学 | 事后还原模型当时看到了什么 | dsh | 能沿会话事件追来源；接入新信息时也要记录它。 |
| 想自建调度的团队 | 自己决定下一步问模型还是跑工具 | dsh | 可替换默认循环插件；新工厂要实现创建、恢复等接口。 |

[dsh 会话历史的可还原约定](https://github.com/deepseek-ai/deepseek-harness/blob/4b399c39a6d1479cd84ca591b4d7c88e24d38a96/docs/architecture.md#L133-L140) · [dsh 的工厂接口](https://github.com/deepseek-ai/deepseek-harness/blob/4b399c39a6d1479cd84ca591b4d7c88e24d38a96/packages/core/agent/src/index.ts#L376-L397) · [pi 的 SSH 工具示例](https://github.com/earendil-works/pi/blob/8209929fb553e7a8c91dc0894569f9ec43dd201f/packages/coding-agent/examples/extensions/ssh.ts#L128-L169)

再看模型。用 DeepSeek，两边都能接。想保留 dsh 的会话、权限，又想换 GPT、Claude 或 Gemini，可以给 dsh 的 pi-ai 适配器配置对应路由。如果主要是个人在几家模型之间来回试，pi 已有的模型目录和切换命令用起来更直接。自建服务要先核对协议和工具调用能不能配上。 [pi 模型配置](https://github.com/earendil-works/pi/blob/8209929fb553e7a8c91dc0894569f9ec43dd201f/packages/coding-agent/docs/models.md#L3-L13) · [dsh 配置模型](https://github.com/deepseek-ai/deepseek-harness/blob/4b399c39a6d1479cd84ca591b4d7c88e24d38a96/docs/user/guide/providers.md#L7-L29) · [基础配置已声明 pi-ai 部件](https://github.com/deepseek-ai/deepseek-harness/blob/4b399c39a6d1479cd84ca591b4d7c88e24d38a96/packages/bundle/base/cordis.patch.yml#L130-L141)

能接通以后，哪个做题好？点「同模型实测」。先看独立研究的 63 道终端题。GPT-6 Astra 配 pi 过了 38 题，配 dsh 过了 33 题；换 Claude Opus 5，变成 pi 19 题、dsh 22 题。再点「DeepSeek V4.1 Flash」，看另一组实验。DeepSWE 是修软件问题，pi 是 66.2%，dsh Standard 是 70.5%，差 4.3 个百分点。换到终端任务，两个数变成 86.1% 和 85.8%，这次只差 0.3 个百分点。再看最后一列，dsh 自己换成 Minimal，成绩也变了。我会拿自己的模型、自己的题和准备上线的配置再跑一遍。

**独立研究 · Terminal-Bench 4 的 63 道无需 H100 的题，通过题数。**

| 固定模型 | pi 0.84.4 | dsh 0.1.1-rc.2 | OpenHands SDK 1.44.1 |
|---|---|---|---|
| GPT-6 Astra | 38 / 63 | 33 / 63 | 31 / 63 |
| Claude Opus 5 | 19 / 63 | 22 / 63 | 36 / 63 |
| GLM-5.3 | 20 / 63 | 27 / 63 | 26 / 63 |
| Kimi K3 | 7 / 63 | 11 / 63 | 7 / 63 |

该研究于 2026 年 10 月 1 日提交。每行使用 OpenRouter 连接同一第一方模型服务，都请求 high 推理，工具、上下文管理和轮数上限按论文附录 A 的配置，同名推理档不保证相同实际预算。这次 GPT 配 pi 多过 5 题，Claude 配 dsh 多过 3 题；研究中的其他模型也要逐行看。 [Finding the Right Fit §4.1](https://arxiv.org/html/2610.00917v1#S4.T1) · [实验配置、版本与任务划分](https://github.com/liyix/finding-the-right-fit#harnesses-and-models)

**DeepSeek 官方 · 固定 V4.1-Flash，换题集和 harness 配置。**

| 题集 | 指标 | pi | dsh Standard | dsh Minimal |
|---|---|---|---|---|
| DeepSWE v1.1 | 软件问题解决率 | 66.2% | 70.5% | 72.6% |
| Terminal-Bench 2.1 | 终端任务 Pass@1 | 86.1% | 85.8% | 90.6% |

这份表来自 DeepSeek 在 2026 年 9 月 17 日提交的 V4.1-Flash 技术报告。作者固定模型权重、题目和解码配置，比较各套 harness 自带的提示词、工具和循环。推理强度为 100（Max），Linux 容器、温度 1.0、top-p 0.95、1M 上下文，每个 agent 最多 500 次模型生成。DeepSWE 每题采样 8 次，Terminal-Bench 每题 3 次，终端评测断网。pi 用 v0.84.2 的 RPC 模式，加文件、shell 和搜索工具。dsh Standard 用 v0.1.1+custom.202609011522 的完整 SDK 配置，起初 26 个函数工具；Minimal 只有 bash。要判断某个钩子或工具具体贡献了多少，需要单独做消融。其他模型也要按实际配置另测。 [技术报告 §5.3.4 表 4](https://arxiv.org/html/2609.19969v1#S5.SS3.SSS4) · [附录 B.1 的评测配置](https://arxiv.org/html/2609.19969v1#A2.SS1) · [官方模型卡](https://huggingface.co/deepseek-ai/DeepSeek-V4.1-Flash/blob/314113f8a7dadb388215396ba5fbee2c610a04d6/README.md)

## 附录 A　ReAct 现场运行顺序

打开《从一个 agent 循环讲到 pi 和 dsh》的 Notebook，第 2 页先运行 Cell 1 定义工具、模拟模型和回复解析函数，再运行 Cell 2 准备会话与临时文件。想重新讲一遍，只要重跑 Cell 2。[可执行 Notebook](./从一个-agent-循环讲到-pi-和-dsh.ipynb)

想和后面的 pi、dsh 录制对照，可以在第一份请求的 `user` 消息里找到完整原话。

> First use the read tool to read config.txt in the current directory. Then use the edit tool (NOT bash) to replace the literal text DEBUG with RELEASE in that file. Then reply with exactly the single word DONE.

第 3 页的 Cell 3 只做两件事。把当前的消息历史与工具声明组装成请求，在右边显示它的完整正文。同一轮可以多看几次。

```python
request = build_request(messages, tools)
show_request(request)
```

等大家猜完，再执行下面的 Cell 4。模拟服务返回的原始 JSON 留在 `raw`，解析出来的助手消息留在 `reply`。程序把助手的调用和工具回执两条消息追加到历史。下一次再跑 Cell 3，这两条就会一起出现。模型答 `DONE` 这一轮没有工具需要执行。

```python
raw = mock_llm(request)
reply = parse_assistant_message(raw)
results = execute_tool_calls(reply, executors)
record_and_show_turn(messages, reply, results, raw=raw)
```

两格依次各跑三次。可以用下表检查当前停在了哪一轮。

| 运行 Cell 3 时的历史条数 | 请求发出前，最后一条消息来自谁 | 运行 Cell 4 后看到的模拟模型回复 |
| --- | --- | --- |
| 2 | 用户交代读文件、改配置、回 DONE | 要求 `read` |
| 4 | 文件工具读出 `mode=DEBUG` 和 `level=info` | 要求 `edit` |
| 6 | 文件工具确认成功替换 | 最终文字 `DONE` |

## 附录 B　同一个 `read_config` 的两个注册入口（供会后查阅）

这是额外注册新工具的示例。前面六份包的工具清单都没有 `read_config`。下面两份工具都读当前会话目录下的 `config.txt`，无参数，返回文本。可按需对照如何登记工具和返回结果。两段 TypeScript 按给定提交的接口编写，作为源码对照。

### pi 侧

将代码放在可信项目的 `.pi/extensions/read-config.ts`，启动交互式 pi，或对已经打开的会话执行 `/reload`。模型下次拿到工具定义时，能看到 `read_config` 的名字、用途和空参数表。[官方工具示例](https://github.com/earendil-works/pi/blob/8209929fb553e7a8c91dc0894569f9ec43dd201f/packages/coding-agent/examples/extensions/hello.ts) · [扩展发现路径](https://github.com/earendil-works/pi/blob/8209929fb553e7a8c91dc0894569f9ec43dd201f/packages/coding-agent/docs/extensions.md#L125-L141)

```ts
import { readFile } from "node:fs/promises";
import { join } from "node:path";
import { Type } from "@earendil-works/pi-ai";
import { defineTool, type ExtensionAPI } from "@earendil-works/pi-coding-agent";

export default function (pi: ExtensionAPI) {
  pi.registerTool(defineTool({
    name: "read_config",
    label: "读取项目配置",
    description: "Read config.txt from the current session directory.",
    parameters: Type.Object({}),
    async execute(_id, _args, signal, _update, ctx) {
      const path = join(ctx.cwd, "config.txt");
      const text = await readFile(path, { encoding: "utf8", signal });
      return { content: [{ type: "text", text }], details: undefined };
    },
  }));
}
```

### dsh 侧



示例面向已按仓库文档构建并安装依赖的源码检出。工具读取当前会话的小型演示文件。如果由非 Agent 调用，则沿用文件服务的默认目录。这里展示注册、读取、渲染三个接口。

```ts
import type { Context } from '@deepseek-ai/cordis'
import type {} from '@deepseek-ai/dsh-fs'
import type {} from '@deepseek-ai/dsh-working-directory'
import { defineTool } from '@deepseek-ai/dsh-tools'

export const name = 'demo-read-config'
export const inject = ['tools', 'fs', 'workingDirectory']

export function apply(ctx: Context) {
  ctx.tools.register(defineTool({
    name: 'read_config',
    description: 'Read config.txt from the current session directory.',
    parameters: {},
    output: {
      schema: { type: 'string' },
      render: (_args, text) => [{ type: 'text', text }],
    },
    async execute(_args, { agent, signal }) {
      const options = agent
        ? { cwd: await ctx.workingDirectory.ensure(agent, signal), signal }
        : { signal }
      const target = await ctx.fs.resolve('config.txt', options)
      return ctx.fs.readText(target, signal)
    },
  }))
}
```

以源码检出的本地开发方式为例，将上面模块放在 `scratch-plugin/src/read-config.ts`。在 `scratch-plugin/cordis.yml` 中写一个 overlay，`name` 使用模块文件在这台电脑上的绝对路径。下面的 `/absolute/path/to/deepseek-harness` 需换成实际路径。

```yaml
- insert:
    - id: demo-read-config
      name: '/absolute/path/to/deepseek-harness/scratch-plugin/src/read-config.ts'
```

官方教程的启动方式是从已构建的仓库根目录执行 `pnpm dsh web --patch ./scratch-plugin/cordis.yml`。在 Web 里选用含有演示 `config.txt` 的会话工作目录，然后输入“请调用 read_config，告诉我 mode 现在等于什么”。常驻 profile 也能把同一项放进对应的 `$DSH_HOME/profiles/<name>/cordis.patch.yml`。

> **源码**　[工具编写教程](https://github.com/deepseek-ai/deepseek-harness/blob/4b399c39a6d1479cd84ca591b4d7c88e24d38a96/docs/user/develop/basic/tool.zh.md#L9-L45) · [本地源码插件的 overlay 与启动](https://github.com/deepseek-ai/deepseek-harness/blob/4b399c39a6d1479cd84ca591b4d7c88e24d38a96/docs/user/develop/basic/index.zh.md#L46-L64) · [内置工具解析会话目录的实现](https://github.com/deepseek-ai/deepseek-harness/blob/4b399c39a6d1479cd84ca591b4d7c88e24d38a96/packages/fs/tool-fs/src/session-cwd.ts#L16-L24)

## 附录 C　从项目环境启动 JupyterLab

```bash
cd pi-presentation
uv sync --locked
uv run --locked jupyter lab
```

项目用 `uv.lock` 固定依赖，Python 3.11 内核可以运行附录 A 对应的四个 Notebook 单元格，无需模型密钥。Notebook 放映使用 JupyterLab RISE，进入放映后仍可执行当前单元格。交互图可以嵌入可信单元格的 HTML 输出。放映时按图里的“上一步 / 下一步”切换高亮箭头和解释，幻灯片导航用于翻页。[RISE 用法](https://jupyterlab-contrib.github.io/rise.html)
