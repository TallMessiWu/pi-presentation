"""Prepare the generated model catalog used by the pinned pi source checkout."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
from tempfile import TemporaryDirectory
from urllib.request import urlopen


def prepare_pi_catalog(pi_source):
    """After npm ci in pi_source, hydrate the exact catalog pinned by pi itself."""
    repo = Path(pi_source).resolve()
    ai = repo / "packages" / "ai"
    revision = json.loads((repo / "nix" / "model-catalog.json").read_text(encoding="utf-8"))["revision"]
    digest = revision.removeprefix("sha256-")
    if len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
        raise ValueError(f"Unexpected pi catalog revision: {revision}")
    node = shutil.which("node")
    if not node:
        raise RuntimeError("pi 的目录生成工具需要 Node.js。")
    data = ai / "src" / "providers" / "data"
    stamp = data / ".presentation-catalog"
    checker = [node, "--experimental-strip-types", str(ai / "scripts" / "check-model-data.ts")]
    if stamp.exists() and stamp.read_text(encoding="ascii").strip() == revision:
        if subprocess.run(checker, cwd=repo, capture_output=True).returncode == 0:
            return
    url = f"https://pi.dev/api/models/revisions/{revision}?types=chat,image,classifier"
    with urlopen(url, timeout=60) as response:
        catalog = response.read()
    if hashlib.sha256(catalog).hexdigest() != digest:
        raise ValueError("pi 官方模型目录的内容与源码锁定的 SHA-256 不符。")
    with TemporaryDirectory(prefix="pi-model-catalog-") as temporary:
        path = Path(temporary) / "models.all.json"
        path.write_bytes(catalog)
        subprocess.run([node, "--experimental-strip-types", str(ai / "scripts" / "hydrate-model-catalog.ts"),
                        str(path)], cwd=repo, check=True)
    stamp.write_text(revision + "\n", encoding="ascii")
