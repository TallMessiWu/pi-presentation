# 从一个 agent 循环讲到 pi 和 dsh

一场 40 分钟的源码分享。用同一个任务走两遍：读 `config.txt`，把 `DEBUG` 改成 `RELEASE`，最后回复 `DONE`。跟着三轮请求，可以看到用户输入、系统提示词、工具声明和执行结果分别在哪一刻到达模型。

- [Jupyter Notebook（23 页）](./从一个-agent-循环讲到-pi-和-dsh.ipynb) · [中文演讲稿](./从一个-agent-循环讲到-pi-和-dsh-演讲稿.md)
- pi：[源码架构图](./pi-architecture.svg) · [请求时序图](./pi-request-sequence.svg)
- dsh：[源码架构图](./dsh-architecture.svg) · [请求时序图](./dsh-request-sequence.svg)
- [六份请求与对应的本地会话记录（JSON）](./harness-requests.json)。pi 部分在本地 CLI 的发送边界采集，模型回复使用离线回放；dsh 部分由归档的会话记录通过固定版本的适配器还原。

## 本地放映

使用 [uv](https://docs.astral.sh/uv/) 安装项目锁定的 JupyterLab 和 RISE 环境。第一次下载依赖需要联网，放映和运行文件读写示例无需模型密钥。

```sh
git clone https://github.com/TallMessiWu/pi-presentation.git
cd pi-presentation
uv sync --locked --python 3.11
uv run --locked jupyter trust '从一个-agent-循环讲到-pi-和-dsh.ipynb'
uv run --locked jupyter lab '从一个-agent-循环讲到-pi-和-dsh.ipynb'
```

在 JupyterLab 里按 **Option+R**（Windows / Linux 用 **Alt+R**）进入放映。左右方向键翻页，图内的“下一步”沿请求逐步高亮。第 3 页可以重新执行，会在临时目录里真正读写示例文件。

## 对照源码

想顺着图读代码时，在仓库根目录运行 `git submodule update --init`。下面两个目录对应分享时实际使用的提交。

| 目录 | 上游源码 |
| --- | --- |
| `pi/` | [earendil-works/pi · 8209929](https://github.com/earendil-works/pi/tree/8209929fb553e7a8c91dc0894569f9ec43dd201f) |
| `deepseek-harness/` | [deepseek-ai/deepseek-harness · 4b399c3](https://github.com/deepseek-ai/deepseek-harness/tree/4b399c39a6d1479cd84ca591b4d7c88e24d38a96) |

[上游许可声明](./THIRD_PARTY_NOTICES.md)
