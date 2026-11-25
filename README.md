# 从一个 agent 循环讲到 pi 和 dsh

一场 40 分钟的源码分享。先在 Python 里跑一个查 CI 失败原因的 ReAct 循环。然后让 pi 和 dsh 各走一次「读 config.txt、替换 DEBUG、回 DONE」，从架构图进入连续三轮请求，全程走完再看时序图。两个框架各有一个可以改参数重跑的实验。

- [Jupyter Notebook（23 页）](./从一个-agent-循环讲到-pi-和-dsh.ipynb) · [中文演讲稿](./从一个-agent-循环讲到-pi-和-dsh-演讲稿.md)
- pi：[源码架构图](./pi-architecture.svg) · [请求时序图](./pi-request-sequence.svg)
- dsh：[源码架构图](./dsh-architecture.svg) · [请求时序图](./dsh-request-sequence.svg)
- [六份请求与对应的本地会话记录（JSON）](./harness-requests.json)。pi 部分在本地 CLI 的发送边界采集，模型回复使用离线回放；dsh 部分由归档的会话记录通过固定版本的适配器还原。

## 新机器准备与放映

安装 Git、[uv](https://docs.astral.sh/uv/) 和带 npm 的 Node.js。现场跑两个框架需要 Node **24.x（≥ 24.22.3）或 ≥ 26.13.1**。第一次准备时需要联网下载依赖和 pi 锁定的模型目录，请提前完成。实验用本地模拟模型，无需 API 密钥。

```sh
git clone https://github.com/TallMessiWu/pi-presentation.git
cd pi-presentation
uv sync --python 3.11
uv run python -m presentation_labs.prepare
uv run jupyter trust "从一个-agent-循环讲到-pi-和-dsh.ipynb"
uv run jupyter lab "从一个-agent-循环讲到-pi-和-dsh.ipynb"
```

已有仓库可先运行 `git pull --ff-only`。准备命令会初始化 pi 源码子模块，在 `pi/` 与 `presentation_labs/` 安装各自锁定的 npm 依赖。Windows 可先在 JupyterLab 里 **Run All Cells**，确认图表和实验输出出现，再按 **Alt + R** 放映（macOS 用 **Option + R**）。方向键翻页，**S** 开演讲者窗口。预备好环境后，选中可编辑的代码格，改参数按 **Ctrl + Enter** 原地运行。只看已保存的演示可以跳过 Node 依赖准备。

## 台上可以改什么

| 页 | 操作 | 观察 |
| --- | --- | --- |
| 2–3 | 先分别运行模型和本地工具，再将 `tests_pass` 切为 `True` | 相同提问先查 CI 任务；全部通过时跳过 `read_log`。 |
| 6–8、14–16 | 连续翻原始三轮请求，切「本地组装 / 发给模型 / 模型回复」和「完整 JSON」 | 同一个调用编号怎样把模型的要求和磁盘回执对起来。 |
| 10 | 切换 `interfere`，在 pi 读完后从 Python 修改临时文件 | 成功替换和匹配失败都来自实际 pi CLI。失败后按预设再读一次，检查新的正文。 |
| 19 | 把 `extra_info` 从 0 改为 50 | 真正的 dsh headless 使用 native 和 PTC 两套执行器。两边读同一份清单、同一份日志，对照请求数和末次工具回执正文。 |

第 10 页的 `pi_trial["rounds"]` 保存本次 pi 请求与模拟回复。第 19 页的 `dsh_trial["native"]["requests"]` 和 `dsh_trial["ptc"]["requests"]` 保存本次运行实际发给回环模型端点的完整 JSON。表中字符数是末次工具回执正文的长度，和 token 计费是两件事。

## 对照源码

想顺着图读代码时，在仓库根目录运行 `git submodule update --init`。下面两个目录对应分享时实际使用的提交。

| 目录 | 上游源码 |
| --- | --- |
| `pi/` | [earendil-works/pi · 8209929](https://github.com/earendil-works/pi/tree/8209929fb553e7a8c91dc0894569f9ec43dd201f) |
| `deepseek-harness/` | [deepseek-ai/deepseek-harness · 4b399c3](https://github.com/deepseek-ai/deepseek-harness/tree/4b399c39a6d1479cd84ca591b4d7c88e24d38a96) |

[上游许可声明](./THIRD_PARTY_NOTICES.md)
