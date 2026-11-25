"""Install the pinned runtimes for the two live framework demos before the talk."""
from pathlib import Path
import shutil
import subprocess

from .pi_setup import prepare_pi_catalog


def main():
    labs = Path(__file__).resolve().parent
    project = labs.parent
    node = shutil.which("node")
    npm = shutil.which("npm.cmd") or shutil.which("npm")
    git = shutil.which("git")
    if not all((node, npm, git)):
        raise SystemExit("请先安装 Git 和 Node.js（含 npm），重新打开终端后再运行本命令。")
    version = subprocess.check_output([node, "--version"], text=True).strip()
    major, minor, patch = map(int, version.removeprefix("v").split("-")[0].split("."))
    if not ((major == 24 and (minor, patch) >= (22, 3)) or (major, minor, patch) >= (26, 13, 1)):
        raise SystemExit(f"当前 Node.js {version}。dsh 需要 24.22.3+ 的 24.x 或 26.13.1 及以上。")

    subprocess.run([git, "submodule", "update", "--init", "--", "pi"], cwd=project, check=True)
    install = [npm, "ci", "--ignore-scripts", "--no-audit", "--no-fund"]
    subprocess.run([*install, "--omit=dev"], cwd=project / "pi", check=True)
    prepare_pi_catalog(project / "pi")
    subprocess.run(install, cwd=labs, check=True)
    print("pi 和 dsh 的现场实验已准备好。")


if __name__ == "__main__":
    main()
