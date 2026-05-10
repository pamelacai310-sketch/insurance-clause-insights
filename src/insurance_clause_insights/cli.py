from __future__ import annotations

import argparse
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

from .analysis import compare_contracts
from .config import DEFAULT_OUTPUT_ROOT, DEFAULT_UPSTREAM_DIR
from .parsing import load_contract_records
from .reporting import write_excel_report, write_json_report, write_markdown_report
from .upstream import ensure_upstream_repo, run_upstream_crawler


def configure_logging(verbose: bool) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )


def timestamp_slug() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="保险条款横向比较工具")
    parser.add_argument("--verbose", action="store_true", help="输出更详细日志")

    subparsers = parser.add_subparsers(dest="command", required=True)

    sync_parser = subparsers.add_parser("sync-upstream", help="同步上游 insurance-crawler-push")
    sync_parser.add_argument("--upstream-dir", type=Path, default=DEFAULT_UPSTREAM_DIR)

    crawl_parser = subparsers.add_parser("crawl", help="运行上游爬虫")
    crawl_parser.add_argument("--upstream-dir", type=Path, default=DEFAULT_UPSTREAM_DIR)
    crawl_parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_ROOT / f"run_{timestamp_slug()}" / "raw")
    crawl_parser.add_argument("--companies", nargs="*", help="指定公司名称，默认全部")
    crawl_parser.add_argument("--workers", type=int, default=1)
    crawl_parser.add_argument("--show-browser", action="store_true", help="显示浏览器窗口")

    analyze_parser = subparsers.add_parser("analyze", help="分析既有抓取结果")
    analyze_parser.add_argument("--crawl-json", type=Path, required=True, help="上游生成的 insurance_data_*.json")
    analyze_parser.add_argument("--report-dir", type=Path, default=DEFAULT_OUTPUT_ROOT / f"analysis_{timestamp_slug()}")
    analyze_parser.add_argument("--category", type=str, help="只分析指定类别")
    analyze_parser.add_argument("--min-products", type=int, default=20)
    analyze_parser.add_argument("--top-features", type=int, default=3)

    run_parser = subparsers.add_parser("run", help="同步上游 + 抓取 + 分析")
    run_parser.add_argument("--upstream-dir", type=Path, default=DEFAULT_UPSTREAM_DIR)
    run_parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    run_parser.add_argument("--companies", nargs="*", help="指定公司名称，默认全部")
    run_parser.add_argument("--workers", type=int, default=1)
    run_parser.add_argument("--show-browser", action="store_true", help="显示浏览器窗口")
    run_parser.add_argument("--category", type=str, help="只分析指定类别")
    run_parser.add_argument("--min-products", type=int, default=20)
    run_parser.add_argument("--top-features", type=int, default=3)

    return parser


def handle_sync(upstream_dir: Path) -> int:
    ensure_upstream_repo(upstream_dir)
    print(f"上游仓库已就绪: {upstream_dir}")
    return 0


def handle_crawl(
    upstream_dir: Path,
    output_dir: Path,
    companies: Optional[list[str]],
    workers: int,
    show_browser: bool,
) -> int:
    ensure_upstream_repo(upstream_dir)
    latest_json = run_upstream_crawler(
        upstream_dir=upstream_dir,
        output_dir=output_dir,
        companies=companies,
        headless=not show_browser,
        workers=workers,
    )
    print(f"抓取完成: {latest_json}")
    return 0


def handle_analyze(
    crawl_json: Path,
    report_dir: Path,
    category: Optional[str],
    min_products: int,
    top_features: int,
) -> int:
    report_dir.mkdir(parents=True, exist_ok=True)
    contracts, category_counts = load_contract_records(crawl_json)
    groups, counts = compare_contracts(
        contracts=contracts,
        min_products=min_products,
        preferred_category=category,
        top_n=top_features,
    )

    write_json_report(groups, counts or category_counts, report_dir / "comparison_report.json")
    write_markdown_report(groups, counts or category_counts, report_dir / "comparison_report.md")
    write_excel_report(groups, counts or category_counts, report_dir / "comparison_report.xlsx")

    print(f"分析完成: {report_dir}")
    return 0


def handle_run(args: argparse.Namespace) -> int:
    run_dir = args.output_root / f"run_{timestamp_slug()}"
    raw_dir = run_dir / "raw"
    report_dir = run_dir / "reports"

    ensure_upstream_repo(args.upstream_dir)
    latest_json = run_upstream_crawler(
        upstream_dir=args.upstream_dir,
        output_dir=raw_dir,
        companies=args.companies,
        headless=not args.show_browser,
        workers=args.workers,
    )
    contracts, _ = load_contract_records(latest_json)
    groups, counts = compare_contracts(
        contracts=contracts,
        min_products=args.min_products,
        preferred_category=args.category,
        top_n=args.top_features,
    )

    report_dir.mkdir(parents=True, exist_ok=True)
    write_json_report(groups, counts, report_dir / "comparison_report.json")
    write_markdown_report(groups, counts, report_dir / "comparison_report.md")
    write_excel_report(groups, counts, report_dir / "comparison_report.xlsx")

    print(f"完整流程完成: {run_dir}")
    print(f"原始抓取数据: {latest_json}")
    print(f"分析报告目录: {report_dir}")
    return 0


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    configure_logging(verbose=args.verbose)

    if args.command == "sync-upstream":
        return handle_sync(args.upstream_dir)
    if args.command == "crawl":
        return handle_crawl(
            upstream_dir=args.upstream_dir,
            output_dir=args.output_dir,
            companies=args.companies,
            workers=args.workers,
            show_browser=args.show_browser,
        )
    if args.command == "analyze":
        return handle_analyze(
            crawl_json=args.crawl_json,
            report_dir=args.report_dir,
            category=args.category,
            min_products=args.min_products,
            top_features=args.top_features,
        )
    if args.command == "run":
        return handle_run(args)

    raise ValueError(f"未知命令: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
