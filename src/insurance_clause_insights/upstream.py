from __future__ import annotations

import hashlib
import logging
import os
import subprocess
import sys
from pathlib import Path
from typing import Optional

from .config import DEFAULT_UPSTREAM_VENV_DIR, UPSTREAM_REPO_URL

logger = logging.getLogger(__name__)


def run_command(args: list[str], cwd: Optional[Path] = None) -> None:
    subprocess.run(args, cwd=cwd, check=True)


def ensure_upstream_repo(upstream_dir: Path) -> Path:
    upstream_dir.parent.mkdir(parents=True, exist_ok=True)
    if not upstream_dir.exists():
        logger.info("克隆上游仓库: %s", UPSTREAM_REPO_URL)
        run_command(["git", "clone", "--depth=1", UPSTREAM_REPO_URL, str(upstream_dir)])
        return upstream_dir

    if not (upstream_dir / ".git").exists():
        raise RuntimeError(f"上游目录存在但不是 Git 仓库: {upstream_dir}")

    logger.info("更新上游仓库: %s", upstream_dir)
    run_command(["git", "-C", str(upstream_dir), "pull", "--ff-only"])
    return upstream_dir


def _iter_python_candidates() -> list[str]:
    candidates: list[str] = []
    explicit = os.environ.get("INSURANCE_UPSTREAM_PYTHON")
    if explicit:
        candidates.append(explicit)

    current_python = Path(sys.executable).name
    for candidate in (current_python, "python3.12", "python3.11", "python3.10", "python3"):
        if candidate not in candidates:
            candidates.append(candidate)
    return candidates


def find_compatible_python() -> str:
    for candidate in _iter_python_candidates():
        try:
            result = subprocess.run(
                [candidate, "-c", "import sys; print(f'{sys.version_info[0]}.{sys.version_info[1]}')"],
                check=True,
                capture_output=True,
                text=True,
            )
        except (subprocess.CalledProcessError, FileNotFoundError):
            continue

        major, minor = (int(part) for part in result.stdout.strip().split("."))
        if (major, minor) >= (3, 10):
            return candidate

    raise RuntimeError(
        "未找到可用于运行上游爬虫的 Python 3.10+ 解释器。"
        "请安装 python3.10+，或设置 INSURANCE_UPSTREAM_PYTHON 指向可用解释器。"
    )


def _venv_python(venv_dir: Path) -> Path:
    if os.name == "nt":
        return venv_dir / "Scripts" / "python.exe"
    return venv_dir / "bin" / "python"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def ensure_upstream_runtime(upstream_dir: Path, runtime_dir: Path = DEFAULT_UPSTREAM_VENV_DIR) -> Path:
    runtime_dir.parent.mkdir(parents=True, exist_ok=True)
    runtime_python = _venv_python(runtime_dir)
    requirements_path = upstream_dir / "requirements.txt"
    marker_path = runtime_dir / ".requirements.sha256"

    if not runtime_python.exists():
        compatible_python = find_compatible_python()
        logger.info("创建上游运行环境: %s", runtime_dir)
        run_command([compatible_python, "-m", "venv", str(runtime_dir)])

    current_hash = _sha256(requirements_path)
    installed_hash = marker_path.read_text(encoding="utf-8").strip() if marker_path.exists() else ""
    if installed_hash != current_hash:
        logger.info("安装上游依赖: %s", requirements_path)
        run_command([str(runtime_python), "-m", "pip", "install", "--upgrade", "pip"])
        run_command([str(runtime_python), "-m", "pip", "install", "-r", str(requirements_path)])
        marker_path.write_text(current_hash, encoding="utf-8")

    return runtime_python


def run_upstream_crawler(
    upstream_dir: Path,
    output_dir: Path,
    companies: Optional[list[str]] = None,
    headless: bool = True,
    workers: int = 1,
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    runtime_python = ensure_upstream_runtime(upstream_dir)
    runner_path = Path(__file__).with_name("upstream_bridge.py")

    command = [
        str(runtime_python),
        str(runner_path),
        "--upstream-dir",
        str(upstream_dir),
        "--output-dir",
        str(output_dir),
        "--workers",
        str(workers),
    ]
    if headless:
        command.append("--headless")
    if companies:
        command.extend(["--companies", *companies])

    run_command(command)
    return find_latest_crawl_json(output_dir)


def find_latest_crawl_json(output_dir: Path) -> Path:
    candidates = sorted((output_dir / "data").glob("insurance_data_*.json"))
    if not candidates:
        raise FileNotFoundError(f"未在 {output_dir / 'data'} 找到 insurance_data_*.json")
    return candidates[-1]
