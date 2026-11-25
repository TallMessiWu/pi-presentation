"""A scripted model and two file-backed CI tools for the ReAct exercise."""
from contextlib import contextmanager
from pathlib import Path
from tempfile import TemporaryDirectory
import json


TASK = "帮我看看，第 128 次 CI 为什么挂了？"


def schema(name, description, parameter):
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {
                "type": "object",
                "properties": {parameter: {"type": "integer"}},
                "required": [parameter],
            },
        },
    }


TOOLS = [
    schema("list_jobs", "List jobs for a CI run.", "run_id"),
    schema("read_log", "Read the log for one CI job.", "job_id"),
]


class CIFiles:
    def __init__(self, folder):
        self.folder = folder

    def list_jobs(self, run_id):
        return json.loads((self.folder / f"run-{int(run_id)}.json").read_text(encoding="utf-8"))

    def read_log(self, job_id):
        return (self.folder / f"job-{int(job_id)}.log").read_text(encoding="utf-8")


@contextmanager
def local_tools(*, tests_pass):
    """Create a new offline CI run on every execution; clean up on exit."""
    with TemporaryDirectory(prefix="react-ci-") as tmp:
        folder = Path(tmp)
        jobs = [
            {"id": 41, "name": "build", "status": "passed"},
            {"id": 42, "name": "unit-tests", "status": "passed" if tests_pass else "failed"},
        ]
        (folder / "run-128.json").write_text(json.dumps(jobs), encoding="utf-8")
        (folder / "job-41.log").write_text("Build passed.", encoding="utf-8")
        log = "All tests passed." if tests_pass else "FAIL test_invoice_total: expected 100, got 90"
        (folder / "job-42.log").write_text(log, encoding="utf-8")
        files = CIFiles(folder)
        yield {"list_jobs": files.list_jobs, "read_log": files.read_log}


def mock_llm(messages, tools):
    """Choose from scripted replies using only the latest incoming message."""
    latest = messages[-1]
    if latest["role"] == "user":
        name, args = "list_jobs", {"run_id": 128}
    elif latest["name"] == "list_jobs":
        failed = next((job for job in latest["content"] if job["status"] == "failed"), None)
        if failed is None:
            return {"role": "assistant", "content": "这次 CI 全部通过。"}
        name, args = "read_log", {"job_id": failed["id"]}
    else:
        return {"role": "assistant", "content": "测试日志显示：" + latest["content"]}
    if name not in {item["function"]["name"] for item in tools}:
        raise ValueError(f"Tool {name} was not declared.")
    return {"role": "assistant", "tool": name, "args": args, "id": f"call-{len(messages)}"}


def run_tool(executors, call):
    value = executors[call["tool"]](**call["args"])
    return {"role": "tool", "name": call["tool"], "tool_call_id": call["id"], "content": value}


def signatures(tools):
    entries = []
    for item in tools:
        func = item["function"]
        fields = [f"{key}: {spec['type']}" for key, spec in func["parameters"]["properties"].items()]
        entries.append(f"{func['name']}({', '.join(fields)})")
    return "   ".join(entries)


def short(value):
    if isinstance(value, list):
        return "，".join(f"{job['name']} {job['status']} (#{job['id']})" for job in value)
    return value


def describe(message):
    if "tool" in message:
        args = ", ".join(f"{key}={value}" for key, value in message["args"].items())
        return f"{message['tool']}({args})"
    return short(message["content"])


def show_turn(turn, previous, reply, result=None):
    print(f"第 {turn} 轮  输入 ({previous['role']})  {describe(previous)}")
    line = "       模型 → " + describe(reply)
    if result is not None:
        line += "    本地返回 → " + describe(result)
    print(line)
