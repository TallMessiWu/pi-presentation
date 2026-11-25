"""Run the pinned pi CLI with real file tools and a fully local model transport."""
import json
import os
from pathlib import Path
import shutil
import subprocess
from tempfile import TemporaryDirectory
from time import monotonic, sleep


def run_pi_edit(after_read=None, *, pi_source=None):
    """Run a fresh trial. after_read(path) runs while pi is paused after reading.

    The result includes original wire requests in rounds[i]["request"], the
    simulated replies in rounds[i]["model_reply"], and the actual file/receipts.
    """
    lab_dir = Path(__file__).resolve().parent
    repo = Path(pi_source).resolve() if pi_source else lab_dir.parent / "pi"
    source = repo / "packages" / "coding-agent" / "src"
    node = shutil.which("node")
    required = (source / "cli.ts", repo / "node_modules",
                repo / "packages" / "ai" / "src" / "providers" / "data" / "deepseek.json")
    if not node or not all(path.exists() for path in required):
        raise RuntimeError("pi 运行环境未准备好。请先按仓库 README 安装现场实验依赖。")

    with TemporaryDirectory(prefix="pi-edit-lab-") as temporary:
        root = Path(temporary)
        cwd, trace, settings = (root / n for n in ("project", "trace", "agent"))
        for directory in (cwd, trace, settings):
            directory.mkdir()
        path = cwd / "config.txt"
        path.write_bytes(b"mode=DEBUG\nlevel=info\n")
        (cwd / "AGENTS.md").write_text("Keep unrelated configuration values unchanged.\n", encoding="utf-8")
        allowed_env = {"PATH", "SYSTEMROOT", "WINDIR", "PATHEXT", "TEMP", "TMP", "TMPDIR", "LANG", "LC_ALL",
                       "COMSPEC", "USERPROFILE", "APPDATA", "LOCALAPPDATA", "HOME"}
        env = {key: value for key, value in os.environ.items() if key.upper() in allowed_env}
        env.update(PI_CODING_AGENT_DIR=str(settings), PI_PACKAGE_DIR=str(source.parent),
                   PI_LAB_TRACE_DIR=str(trace), PI_OFFLINE="1", DEEPSEEK_API_KEY="offline-placeholder")
        command = [node, "--experimental-strip-types"]
        for preload in (source / "experimental" / "source-resolver.ts",
                        source / "core" / "http-dispatcher.ts", lab_dir / "pi-model.mjs"):
            command.extend(["--import", preload.as_uri()])
        command.extend([str(source / "cli.ts"), "--offline", "--no-session", "--no-extensions",
                        "--no-skills", "--no-prompt-templates", "--tools", "read,edit",
                        "--provider", "deepseek", "--model", "deepseek-flash", "--thinking", "off", "-p",
                        "Read config.txt, then use edit to replace DEBUG with RELEASE. If the edit fails, "
                        "read the file again and leave it unchanged. On success, answer DONE."])
        log_path = root / "cli.log"
        answer_path = root / "answer.txt"
        with log_path.open("wb") as log, answer_path.open("wb") as output:
            process = subprocess.Popen(command, cwd=cwd, env=env, stdin=subprocess.DEVNULL,
                                       stdout=output, stderr=log)
            try:
                deadline = monotonic() + 60
                while not (trace / "paused").exists():
                    if process.poll() is not None:
                        raise RuntimeError("pi 在第一次 read 之前退出。\n" + log_path.read_text("utf-8", errors="replace")[-2400:])
                    if monotonic() > deadline:
                        raise TimeoutError("pi 在 60 秒内没有完成第一次读取。")
                    sleep(0.025)
                disk_at_pause = path.read_text(encoding="utf-8")
                if after_read is not None:
                    after_read(path)
                disk_before_edit = path.read_text(encoding="utf-8")
                (trace / "continue").touch()
                if process.wait(timeout=60) != 0:
                    raise RuntimeError("pi 运行失败。\n" + log_path.read_text("utf-8", errors="replace")[-2400:])
            finally:
                if process.poll() is None:
                    process.kill()
                    process.wait()
        rounds = [json.loads(p.read_text(encoding="utf-8")) for p in sorted(trace.glob("round-*.json"))]
        receipts = {}
        for round_data in rounds:
            message = round_data["request"]["messages"][-1]
            if message["role"] == "tool":
                receipts[message["tool_call_id"]] = message["content"]
        return {
            "rounds": rounds, "first_read": receipts["lab-read"], "disk_at_pause": disk_at_pause,
            "disk_before_edit": disk_before_edit, "edit_result": receipts["lab-edit"],
            "reread_result": receipts.get("lab-reread"), "file_at_end": path.read_text(encoding="utf-8"),
            "final_answer": answer_path.read_text(encoding="utf-8").strip(),
        }
