from __future__ import annotations

import importlib.util
import logging
import subprocess
from pathlib import Path
from typing import Optional

from .config import UPSTREAM_REPO_URL

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


def _load_module(module_path: Path, module_name: str):
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"无法加载模块: {module_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run_upstream_crawler(
    upstream_dir: Path,
    output_dir: Path,
    companies: Optional[list[str]] = None,
    headless: bool = True,
    workers: int = 1,
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    crawler_module = _load_module(upstream_dir / "crawler.py", "insurance_crawler_upstream")

    crawler_module.OUTPUT_DIR = output_dir
    crawler_module.PDF_DIR = output_dir / "pdfs"
    crawler_module.DATA_DIR = output_dir / "data"

    crawler = crawler_module.InsuranceCrawler(headless=headless, max_workers=workers)
    crawler.run(companies=companies)
    return find_latest_crawl_json(output_dir)


def find_latest_crawl_json(output_dir: Path) -> Path:
    candidates = sorted((output_dir / "data").glob("insurance_data_*.json"))
    if not candidates:
        raise FileNotFoundError(f"未在 {output_dir / 'data'} 找到 insurance_data_*.json")
    return candidates[-1]
