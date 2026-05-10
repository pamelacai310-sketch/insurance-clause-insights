from __future__ import annotations

import argparse
import importlib.util
from pathlib import Path


def load_module(module_path: Path, module_name: str):
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"无法加载模块: {module_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> int:
    parser = argparse.ArgumentParser(description="Bridge runner for insurance-crawler-push")
    parser.add_argument("--upstream-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--companies", nargs="*")
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--headless", action="store_true")
    args = parser.parse_args()

    crawler_module = load_module(args.upstream_dir / "crawler.py", "insurance_crawler_upstream")
    crawler_module.OUTPUT_DIR = args.output_dir
    crawler_module.PDF_DIR = args.output_dir / "pdfs"
    crawler_module.DATA_DIR = args.output_dir / "data"

    crawler = crawler_module.InsuranceCrawler(
        headless=args.headless,
        max_workers=args.workers,
    )
    crawler.run(companies=args.companies)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
