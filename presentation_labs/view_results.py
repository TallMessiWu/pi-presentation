"""Project just the evidence from the live runs. The caller keeps the complete trace."""
from html import escape
import json
from pathlib import Path
import shutil
import subprocess

from IPython.display import HTML, display


def show_pi(trace):
    def first_line(text):
        return text.splitlines()[0]

    rows = [
        ("上次 read 的回执", first_line(trace["first_read"])),
        ("edit 执行前的磁盘", first_line(trace["disk_before_edit"])),
        ("edit 的实际回执", first_line(trace["edit_result"])),
    ]
    if trace["reread_result"] is not None:
        rows.append(("失败后再读的回执", first_line(trace["reread_result"])))
    rows.append(("结束时的磁盘", first_line(trace["file_at_end"])))
    table = "".join(f"<tr><th>{label}</th><td><code>{escape(value)}</code></td></tr>" for label, value in rows)
    display(HTML(f'<table class="live-results"><tbody>{table}</tbody></table>'))


def run_dsh_compare(extra_info=50):
    """Run the two dsh executors, returning the actual outgoing requests and file observations."""
    if type(extra_info) is not int or not 0 <= extra_info <= 200:
        raise ValueError("extra_info 是 0 到 200 的整数。")
    node = shutil.which("node")
    if not node:
        raise RuntimeError("请按 README 安装 Node.js 并准备现场实验。")
    runner = Path(__file__).resolve().with_name("dsh-runner.mjs")
    call = subprocess.run([node, str(runner), str(extra_info)], capture_output=True,
                          encoding="utf-8", errors="replace", timeout=240)
    if call.returncode:
        raise RuntimeError("dsh 实验运行失败。依赖准备命令见 README。\n" + call.stderr[-4000:])
    return json.loads(call.stdout)


def show_dsh(comparison):
    headers = ("执行器", "首包工具声明", "实际读取", "模型请求", "末次回执正文", "含启动日志")
    rows = []
    for name in ("native", "ptc"):
        run = comparison[name]
        schemas = ", ".join(tool["name"] for tool in run["requests"][0]["tools"])
        values = (name, schemas, len(run["reads"]), len(run["requests"]),
                  f'{run["result_chars"]} 字符', "有" if run["log_marker_visible"] else "无")
        rows.append("<tr>" + "".join(f"<td>{escape(str(value))}</td>" for value in values) + "</tr>")
    header = "".join(f"<th>{label}</th>" for label in headers)
    answers = [comparison[k]["answer"] for k in ("native", "ptc")]
    log_lines = comparison["native"]["last_tool_result"].splitlines()
    snippets = [next(line for line in log_lines if "INFO worker started" in line),
                next(line for line in log_lines if "FAIL " in line)]
    excerpt = "\n…\n".join(snippets)
    evidence = ('<details class="live-evidence"><summary>看最后一轮实际工具回执</summary>'
                f'<pre>native（节选）\n{escape(excerpt)}\n\nPTC（全文）\n'
                f'{escape(comparison["ptc"]["last_tool_result"])}</pre></details>')
    display(HTML(f'<table class="live-results"><thead><tr>{header}</tr></thead>'
                 f'<tbody>{"".join(rows)}</tbody></table>'
                 f'<p class="live-foot">模型回答　native <code>{escape(answers[0])}</code>'
                 f'　·　PTC <code>{escape(answers[1])}</code></p>' + evidence))
