from __future__ import annotations

import json
import math
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import pdfplumber
import requests

ROOT = Path("/Users/caijiawen/Documents/New project/insurance-clause-insights")
PRODUCT_ANALYSIS_ROOT = Path("/Users/caijiawen/Documents/New project/insurance-product-analysis")
DISCOVERY_JSON = ROOT / "outputs/full_peer_discovery_20260603/full_peer_candidates.json"
OUTPUT_DIR = ROOT / "outputs/huiyingfengnian_20260603_analysis"
DOC_DIR = OUTPUT_DIR / "docs"
TEXT_DIR = OUTPUT_DIR / "text_cache"
CLAUSE_REPORT_DIR = ROOT / "reports"
ACTUARIAL_REPORT_DIR = PRODUCT_ANALYSIS_ROOT / "reports"

sys.path.insert(0, str(PRODUCT_ANALYSIS_ROOT))
from actuarial_calculator import calculate_irr, generate_rating  # noqa: E402

TARGET_NAME = "汇丰汇赢丰年2026年金保险（分红型）"


@dataclass
class ActuarialConfig:
    entry_age: int
    gender: str
    payment_period: int
    annual_premium: float | None
    base_amount: float | None
    regular_benefit: float | None
    start_year: int | None
    terminal_age: int | None
    maturity_benefit: float = 0.0
    regular_to_terminal: bool = False
    lumps: dict[int, float] = field(default_factory=dict)
    source_quality: str = "manual_example"
    benefit_summary: str = ""
    note: str = ""


ACTUARIAL_CONFIGS: dict[str, ActuarialConfig] = {
    TARGET_NAME: ActuarialConfig(
        40,
        "M",
        5,
        290363.50,
        35000,
        35000,
        5,
        105,
        35000,
        benefit_summary="40岁男性、5年交样例；第5个保单周年日起年领基本保险金额，105周岁满期给付基本保险金额。",
        note="按条款修正：满期金为基本保险金额，不按总保费返还；红利为非保证利益。",
    ),
    "汇丰尊享精彩年金保险（分红型）": ActuarialConfig(
        45,
        "F",
        3,
        1877720,
        100000,
        100000,
        5,
        105,
        1877720 * 3 + 100000,
        benefit_summary="第5个保单周年日起年领基本保险金额，满期给付已交保险费总额加基本保险金额。",
    ),
    "汇丰汇赢长鸿年金保险（分红型）": ActuarialConfig(
        40,
        "F",
        5,
        200000,
        51827.60,
        51827.60,
        5,
        105,
        200000 * 5,
        benefit_summary="第5个保单周年日起年领基本保险金额，满期给付已交保险费总额。",
    ),
    "汇丰精彩逸生年金保险（分红型）": ActuarialConfig(
        45,
        "F",
        3,
        1779800,
        100000,
        100000,
        5,
        105,
        1779800 * 3,
        benefit_summary="第5个保单周年日起年领基本保险金额，满期给付已交保险费总额。",
    ),
    "汇丰汇赢恒利年金保险（分红型）": ActuarialConfig(
        40,
        "M",
        6,
        50000,
        4541.90,
        4541.90,
        6,
        105,
        50000 * 6,
        benefit_summary="6年交样例；第6个保单周年日起年领基本保险金额，满期给付已交保险费总额。",
    ),
    "平安盛世金越养老年金保险（分红型）": ActuarialConfig(
        40,
        "M",
        6,
        50000,
        6535,
        6535,
        20,
        105,
        50000 * 6,
        benefit_summary="60周岁起年领基本保险金额，105周岁满期按计划系数给付已交保费。",
    ),
    "平安颐享天年养老年金保险（分红型）": ActuarialConfig(
        60,
        "M",
        3,
        100000,
        1070,
        3210,
        1,
        105,
        100000 * 3 + 1070 * 3,
        benefit_summary="首个保单周年日起领取，交费期满后年领基本保险金额乘以交费年度数。",
    ),
    "平安颐享延年（2026）养老年金保险（分红型）": ActuarialConfig(
        50,
        "F",
        6,
        486492,
        120000,
        120000,
        15,
        105,
        0,
        benefit_summary="65周岁起年领12万元，保证给付期限30年；身故时可给付剩余保证养老年金。",
    ),
}


RARE_RULES: list[tuple[str, str]] = [
    ("购买交清增额", "红利可购买交清增额保险"),
    ("交清增额保险金额", "交清增额保险金额参与后续给付或退保"),
    ("增额红利", "采用增额红利机制"),
    ("终了红利", "含满期/理赔/退保终了红利"),
    ("不提供其他红利实现方式", "红利实现方式锁定为交清增额"),
    ("保证给付期限", "养老年金保证给付期限"),
    ("保证给付", "含保证给付/保证领取责任"),
    ("祝寿金", "含祝寿金责任"),
    ("特别生存保险金", "含特别生存保险金"),
    ("月领", "支持月领"),
    ("按月", "支持按月给付"),
    ("一次性领取", "可选择一次性领取"),
    ("两名被保险人", "双被保险人设计"),
    ("第二投保人", "含第二投保人安排"),
    ("减额交清", "支持减额交清"),
    ("减少基本保险金额", "支持减保/减少基本保险金额"),
    ("保单贷款", "支持保单贷款"),
]


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "").replace("\u3000", " ")).strip()


def safe_filename(text: str) -> str:
    return re.sub(r'[\\/:*?"<>|\s]+', "_", text)[:140]


def doc_path(company: str, product_name: str, category: str, url: str) -> Path:
    suffix = Path(url.split("?", 1)[0]).suffix.lower() or ".pdf"
    if suffix != ".pdf":
        suffix = ".pdf"
    return DOC_DIR / f"{safe_filename(company)}_{safe_filename(product_name)}_{safe_filename(category)}{suffix}"


def download_pdf(company: str, product_name: str, category: str, url: str) -> str:
    if not url:
        return ""
    DOC_DIR.mkdir(parents=True, exist_ok=True)
    path = doc_path(company, product_name, category, url)
    if path.exists() and path.stat().st_size > 0:
        return str(path)
    resp = requests.get(
        url,
        headers={"User-Agent": "Mozilla/5.0", "Referer": url},
        timeout=90,
    )
    resp.raise_for_status()
    path.write_bytes(resp.content)
    return str(path)


def pdf_text(path: str | Path) -> str:
    path = Path(path)
    TEXT_DIR.mkdir(parents=True, exist_ok=True)
    cache = TEXT_DIR / f"{path.stem}.txt"
    if cache.exists():
        return cache.read_text(encoding="utf-8")
    parts: list[str] = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            if text:
                parts.append(text)
    text = "\n".join(parts)
    cache.write_text(text, encoding="utf-8")
    return text


def sentence_snippets(text: str, keywords: list[str], limit: int = 5) -> list[str]:
    pieces = re.split(r"[。；;\n\r]+", text)
    snippets: list[str] = []
    for piece in pieces:
        cleaned = normalize(piece)
        if not 12 <= len(cleaned) <= 150:
            continue
        if any(keyword in cleaned for keyword in keywords):
            snippets.append(cleaned)
        if len(snippets) >= limit:
            break
    return snippets


def extract_first(text: str, keywords: list[str]) -> str:
    snippets = sentence_snippets(text, keywords, limit=1)
    return snippets[0] if snippets else ""


def extract_rare_clauses(text: str) -> list[str]:
    labels: list[str] = []
    for keyword, label in RARE_RULES:
        if keyword in text and label not in labels:
            labels.append(label)
    return labels


def keyword_hits(product_name: str, text: str) -> list[str]:
    bag = product_name + "\n" + text
    checks = [
        ("分红型", ["分红型", "分红"]),
        ("年金保险", ["年金保险"]),
        ("终身/至105周岁", ["终身", "105周岁", "一百零五周岁", "至105"]),
        ("交清增额", ["交清增额"]),
        ("增额红利", ["增额红利"]),
        ("终了红利", ["终了红利"]),
        ("保证给付", ["保证给付", "保证领取"]),
        ("月领", ["月领", "按月给付"]),
        ("保单贷款", ["保单贷款"]),
    ]
    return [label for label, words in checks if any(word in bag for word in words)]


def infer_start_year(text: str) -> int | None:
    number_map = {
        "一": 1,
        "二": 2,
        "三": 3,
        "四": 4,
        "五": 5,
        "六": 6,
        "七": 7,
        "八": 8,
        "九": 9,
        "十": 10,
    }
    patterns = [
        r"第\s*(\d+)\s*个保单周年日.*?年金",
        r"第\s*([一二三四五六七八九十]+)\s*个保单周年日.*?年金",
        r"第\s*(\d+)\s*个保单年度.*?年金",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.S)
        if not match:
            continue
        raw = match.group(1)
        if raw.isdigit():
            return int(raw)
        if raw == "十一":
            return 11
        if raw.startswith("十") and len(raw) == 2:
            return 10 + number_map.get(raw[1], 0)
        if raw.endswith("十") and len(raw) == 2:
            return number_map.get(raw[0], 1) * 10
        return number_map.get(raw)
    age_match = re.search(r"(\d{2})\s*周岁.*?年金", text)
    if age_match:
        return None
    return None


def build_cashflows(config: ActuarialConfig, dividend_rate: float) -> list[float] | None:
    if not config.annual_premium or not config.regular_benefit or not config.start_year or not config.terminal_age:
        return None
    max_year = max(1, config.terminal_age - config.entry_age)
    flows = [0.0 for _ in range(max_year + 1)]
    for year in range(1, min(config.payment_period, max_year) + 1):
        flows[year] -= config.annual_premium
    last_regular_year = max_year if config.regular_to_terminal else max_year - 1
    for year in range(config.start_year, max(0, last_regular_year) + 1):
        if 0 <= year <= max_year:
            flows[year] += config.regular_benefit * (1 + dividend_rate)
    for year, amount in config.lumps.items():
        if 0 <= year <= max_year:
            flows[year] += amount
    if config.maturity_benefit:
        flows[max_year] += config.maturity_benefit
    return flows


def breakeven_year(flows: list[float] | None) -> int | None:
    if not flows:
        return None
    cumulative = 0.0
    has_outflow = False
    for year, amount in enumerate(flows):
        cumulative += amount
        has_outflow = has_outflow or amount < 0
        if has_outflow and cumulative >= 0:
            return year
    return None


def pct(value: float | None) -> str:
    if value is None or (isinstance(value, float) and (math.isnan(value) or math.isinf(value))):
        return "N/A"
    return f"{value:.2%}"


def grade_from_score(score: float) -> str:
    if score >= 4.1:
        return "A"
    if score >= 3.4:
        return "B+"
    if score >= 3.0:
        return "B"
    if score >= 2.4:
        return "C"
    return "D"


def qualitative_dimensions(product: dict[str, Any], config: ActuarialConfig | None, text: str) -> dict[str, int]:
    hits = product["keyword_hits"]
    start_year = product.get("start_year")
    neutral_irr = product.get("irr_neutral")

    if neutral_irr is not None:
        if neutral_irr >= 0.03:
            yield_score = 5
        elif neutral_irr >= 0.025:
            yield_score = 4
        elif neutral_irr >= 0.02:
            yield_score = 3
        elif neutral_irr >= 0:
            yield_score = 2
        else:
            yield_score = 1
    elif "满期给付已交保险费" in text or "已交保险费总额" in text:
        yield_score = 3
    elif "终了红利" in hits or "交清增额" in hits:
        yield_score = 3
    else:
        yield_score = 2

    if "终身/至105周岁" in hits:
        longevity_score = 5
    elif "终身" in product["product_name"]:
        longevity_score = 5
    elif "定期" in product["product_name"]:
        longevity_score = 2
    else:
        longevity_score = 3

    dividend_score = 5 if "交清增额" in hits else 4 if ("增额红利" in hits or "终了红利" in hits) else 3
    guarantee_score = 5 if "保证给付" in hits else 4 if "满期给付已交保险费" in text else 3
    if product["product_name"] == TARGET_NAME:
        guarantee_score = 2

    if start_year is not None and start_year <= 5:
        income_score = 5
    elif start_year is not None and start_year <= 8:
        income_score = 4
    elif "60周岁" in text or "65周岁" in text:
        income_score = 3
    else:
        income_score = 3

    liquidity_score = 3
    if "保单贷款" in hits:
        liquidity_score += 1
    if "减额交清" in text or "减少基本保险金额" in text:
        liquidity_score += 1
    liquidity_score = min(5, liquidity_score)

    transparency_score = 5 if config else 4 if product.get("manual_path") else 3

    return {
        "收益质量": yield_score,
        "长寿保障": longevity_score,
        "红利增额能力": dividend_score,
        "现金流启动": income_score,
        "给付确定性": guarantee_score,
        "流动性": liquidity_score,
        "参数透明度": transparency_score,
    }


def weighted_score(dimensions: dict[str, int]) -> float:
    weights = {
        "收益质量": 0.25,
        "长寿保障": 0.18,
        "红利增额能力": 0.14,
        "现金流启动": 0.12,
        "给付确定性": 0.13,
        "流动性": 0.08,
        "参数透明度": 0.10,
    }
    return round(sum(dimensions[key] * weight for key, weight in weights.items()), 2)


def analyze_numeric(product: dict[str, Any], config: ActuarialConfig | None) -> dict[str, Any]:
    if not config:
        return {
            "analyzed": False,
            "skip_reason": "缺少公开说明书中可核验的年交保费、基本保险金额、领取金额组合；仅做定性精算评分。",
        }
    conservative = build_cashflows(config, 0.0)
    neutral = build_cashflows(config, 0.01)
    optimistic = build_cashflows(config, 0.025)
    if conservative is None:
        return {"analyzed": False, "skip_reason": config.note or "现金流参数不足。"}

    irr_conservative = calculate_irr(conservative)
    irr_neutral = calculate_irr(neutral)
    irr_optimistic = calculate_irr(optimistic)
    break_even = breakeven_year(conservative)
    rating = generate_rating(
        irr_conservative=irr_conservative,
        irr_neutral=irr_neutral,
        breakeven_year=break_even,
        death_leverage=1.0,
        transparency_score=5,
        product_type="annuity",
    )
    return {
        "analyzed": True,
        "entry_age": config.entry_age,
        "gender": config.gender,
        "payment_period": config.payment_period,
        "annual_premium": config.annual_premium,
        "base_amount": config.base_amount,
        "regular_benefit": config.regular_benefit,
        "start_year": config.start_year,
        "terminal_age": config.terminal_age,
        "maturity_benefit": config.maturity_benefit,
        "irr_conservative": irr_conservative,
        "irr_neutral": irr_neutral,
        "irr_optimistic": irr_optimistic,
        "breakeven_year": break_even,
        "tool_rating": rating,
        "benefit_summary": config.benefit_summary,
        "note": config.note,
    }


def distinctive_summary(product: dict[str, Any]) -> str:
    name = product["product_name"]
    rare = product["rare_clauses"]
    hits = product["keyword_hits"]
    if name == TARGET_NAME:
        return "第5个保单周年日起较早启动年金领取，红利用于购买交清增额，但满期金仅为基本保险金额。"
    if "保证给付期限" in "；".join(rare):
        return "保证给付期设计突出，适合养老年金确定性对比。"
    if "终身" in name:
        return "终身年金形态明确，长寿风险覆盖强。"
    if "交清增额" in hits:
        return "红利通过交清增额或增额机制滚入保障/领取基数，复利属性强于现金红利。"
    if "定期" in name:
        return "定期年金结构，领取期限和资金回收节奏更短，适合作为非终身对照样本。"
    if "月领" in hits:
        return "支持月领或按月给付，现金流颗粒度较细。"
    return product.get("selection_note") or "在售年金分红主险，适合同类条款横向比较。"


def build_products() -> list[dict[str, Any]]:
    data = json.loads(DISCOVERY_JSON.read_text(encoding="utf-8"))
    full_map = {(item["company"], item["product_name"]): item for item in data["full_candidates"]}
    ordered = [data["target"], *data["selected_peers"]]
    products: list[dict[str, Any]] = []

    for order, item in enumerate(ordered, 1):
        full = full_map.get((item["company"], item["product_name"]), item)
        product = {
            "order": order,
            "company": item["company"],
            "product_name": item["product_name"],
            "is_target": item["product_name"] == TARGET_NAME,
            "source_page": full.get("source_page", item.get("source_page", "")),
            "selection_note": item.get("selection_note", ""),
            "documents": full.get("documents", []),
            "terms_url": full.get("terms_url") or item.get("terms_url", ""),
        }

        doc_paths: dict[str, str] = {}
        for doc in product["documents"]:
            category = doc.get("category", "")
            url = doc.get("url", "")
            if category not in {"条款", "产品说明书"}:
                continue
            if not url or not url.lower().split("?", 1)[0].endswith(".pdf") and "getPlanClausePdf" not in url:
                continue
            if category in doc_paths:
                continue
            try:
                doc_paths[category] = download_pdf(product["company"], product["product_name"], category, url)
            except Exception as exc:
                doc_paths[f"{category}_download_error"] = str(exc)

        if "条款" not in doc_paths and item.get("local_terms_path") and Path(item["local_terms_path"]).exists():
            doc_paths["条款"] = item["local_terms_path"]
        if product["is_target"] and "条款" not in doc_paths:
            candidates = list((ROOT / "outputs/peer_selection/terms_clean").glob("*汇丰汇赢丰年2026年金保险*.pdf"))
            if candidates:
                doc_paths["条款"] = str(candidates[0])

        terms_text = pdf_text(doc_paths["条款"]) if doc_paths.get("条款") else ""
        support_texts = []
        for category, path in doc_paths.items():
            if category == "条款" or category.endswith("_download_error"):
                continue
            try:
                support_texts.append(pdf_text(path))
            except Exception:
                pass
        combined = "\n".join([terms_text, *support_texts])
        product["doc_paths"] = doc_paths
        product["terms_path"] = doc_paths.get("条款", "")
        product["manual_path"] = doc_paths.get("产品说明书", "")
        product["terms_text_chars"] = len(terms_text)
        product["keyword_hits"] = keyword_hits(product["product_name"], combined)
        product["rare_clauses"] = extract_rare_clauses(combined)
        product["start_year"] = infer_start_year(terms_text)
        product["insurance_period_snippet"] = extract_first(terms_text, ["保险期间", "终身", "105周岁"])
        product["annuity_snippets"] = sentence_snippets(terms_text, ["年金", "养老年金", "生存保险金"], limit=3)
        product["dividend_snippets"] = sentence_snippets(combined, ["红利", "交清增额", "增额红利", "终了红利"], limit=3)
        product["death_snippet"] = extract_first(terms_text, ["身故保险金", "身故"])
        product["maturity_snippet"] = extract_first(terms_text, ["满期保险金", "满期"])
        product["liquidity_snippet"] = extract_first(terms_text, ["保单贷款", "减少基本保险金额", "减额交清", "退保"])

        config = ACTUARIAL_CONFIGS.get(product["product_name"])
        product.update(analyze_numeric(product, config))
        dimensions = qualitative_dimensions(product, config, combined)
        product["rating_dimensions"] = dimensions
        product["rating_score"] = weighted_score(dimensions)
        product["rating_grade"] = grade_from_score(product["rating_score"])
        product["distinctive_feature"] = distinctive_summary(product)
        if not product.get("benefit_summary"):
            product["benefit_summary"] = product["distinctive_feature"]
        products.append(product)
    return products


def write_json(products: list[dict[str, Any]]) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "target_product": TARGET_NAME,
        "product_count_including_target": len(products),
        "products": products,
        "numeric_actuarial_count": sum(1 for item in products if item.get("analyzed")),
    }
    (OUTPUT_DIR / "huiyingfengnian_20260603_analysis.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )


def md_escape(text: str) -> str:
    return normalize(text).replace("|", "｜")


def write_clause_report(products: list[dict[str, Any]]) -> None:
    CLAUSE_REPORT_DIR.mkdir(parents=True, exist_ok=True)
    lines = [
        "# 汇丰汇赢丰年2026年金保险及20个同类产品条款特色与罕见条款分析",
        "",
        f"- 生成时间：{datetime.now().isoformat(timespec='seconds')}",
        "- 输入清单：`reports/huiyingfengnian_full_peer_discovery_20260603.md` 中的目标产品和20个同类产品。",
        "- 分析工具：`insurance-clause-insights` 读取条款 PDF，并结合产品说明书辅助识别。",
        "- 口径说明：条款为主证据；产品说明书用于补充红利和演示现金流信息；费率表、现金价值表保留在发现清单中追溯，但本报告不做全文抽取；分红利益均为非保证利益。",
        "",
        "## 产品特色总览",
        "",
        "| # | 公司 | 产品 | 关键词命中 | 最独特特色 | 罕见条款 |",
        "|---:|---|---|---|---|---|",
    ]
    for product in products:
        lines.append(
            f"| {product['order']} | {product['company']} | {product['product_name']} | "
            f"{'；'.join(product['keyword_hits']) or '未识别'} | "
            f"{md_escape(product['distinctive_feature'])} | "
            f"{md_escape('；'.join(product['rare_clauses']) or '未识别明显罕见条款')} |"
        )

    lines.extend(["", "## 逐产品条款摘要", ""])
    for product in products:
        lines.extend(
            [
                f"### {product['order']}. {product['company']} - {product['product_name']}",
                "",
                f"- 最独特特色：{product['distinctive_feature']}",
                f"- 罕见条款：{'；'.join(product['rare_clauses']) or '未识别明显罕见条款'}",
                f"- 保险期间证据：{product['insurance_period_snippet'] or '条款文本未直接抽取到'}",
                f"- 年金给付证据：{'；'.join(product['annuity_snippets']) or '条款文本未直接抽取到'}",
                f"- 分红/增额证据：{'；'.join(product['dividend_snippets']) or '条款文本未直接抽取到'}",
                f"- 身故责任证据：{product['death_snippet'] or '条款文本未直接抽取到'}",
                f"- 满期责任证据：{product['maturity_snippet'] or '条款文本未直接抽取到'}",
                f"- 条款 PDF：{product['terms_url']}",
                "",
            ]
        )

    lines.extend(
        [
            "## 关键发现",
            "",
            "- 目标产品的核心罕见点是“红利购买交清增额 + 第5年启动年金 + 满期仅给付基本保险金额”的组合。它不像部分同类产品在满期返还已交保费总额，因此收益表现更依赖长期领取和非保证分红。",
            "- AIA 产品普遍出现增额红利/终了红利语言，偏向红利增额型合同结构；平安和汇丰部分产品明确出现交清增额；安联产品覆盖终身/养老两类年金结构。",
            "- 保证给付、月领、保单贷款、减保/减额交清是同类产品中较常见但仍有区分度的条款；双被保险人、祝寿金、特别生存金未在本次20个均衡样本中成为主流特征。",
        ]
    )
    (CLAUSE_REPORT_DIR / "huiyingfengnian_clause_rare_features_20260603.md").write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8",
    )


def write_actuarial_report(products: list[dict[str, Any]]) -> None:
    ACTUARIAL_REPORT_DIR.mkdir(parents=True, exist_ok=True)
    ranked_all = sorted(products, key=lambda item: item["rating_score"], reverse=True)
    numeric = sorted(
        [item for item in products if item.get("analyzed")],
        key=lambda item: item.get("irr_neutral") if item.get("irr_neutral") is not None else -9,
        reverse=True,
    )
    target = next(item for item in products if item["product_name"] == TARGET_NAME)
    target_rank_all = next(idx for idx, item in enumerate(ranked_all, 1) if item["product_name"] == TARGET_NAME)
    target_rank_numeric = next((idx for idx, item in enumerate(numeric, 1) if item["product_name"] == TARGET_NAME), None)

    lines = [
        "# 汇丰汇赢丰年2026年金保险精算特点与优劣评级",
        "",
        f"- 生成时间：{datetime.now().isoformat(timespec='seconds')}",
        "- 输入：`insurance-clause-insights` 生成的 21 款产品条款特征与罕见条款。",
        "- 工具：调用 `insurance-product-analysis` 的 `calculate_irr` 与 `generate_rating`；公开说明书缺少完整演示参数的产品使用条款维度定性评分。",
        "- 分红假设：保守情景 0 分红；中性情景按年度领取额的 1% 增量；乐观情景按年度领取额的 2.5% 增量。该假设只用于敏感性比较，不代表实际分红。",
        "",
        "## 结论摘要",
        "",
        f"- 目标产品综合定性评级：{target['rating_grade']}，综合分 {target['rating_score']} / 5，在 21 款产品中排名第 {target_rank_all}。",
        f"- 目标产品可核验现金流样例的中性 IRR：{pct(target.get('irr_neutral'))}；在 {len(numeric)} 款具备可核验参数的产品中排名第 {target_rank_numeric}。",
        "- 精算定位：偏长期现金流和红利增额型储蓄，不是收益领先型产品；优势在长寿覆盖、领取较早、合同纪律性和交清增额机制，劣势在满期金弱、早期现金价值/流动性约束、身故杠杆低、分红不保证。",
        "",
        "## 所有产品综合评级",
        "",
        "| 排名 | 公司 | 产品 | 综合评级 | 分数 | 中性IRR | 主要精算特点 |",
        "|---:|---|---|---|---:|---:|---|",
    ]
    for rank, product in enumerate(ranked_all, 1):
        lines.append(
            f"| {rank} | {product['company']} | {product['product_name']} | {product['rating_grade']} | "
            f"{product['rating_score']} | {pct(product.get('irr_neutral'))} | {md_escape(product['distinctive_feature'])} |"
        )

    lines.extend(
        [
            "",
            "## 可核验现金流产品 IRR 排名",
            "",
            "| 排名 | 公司 | 产品 | 年交保费 | 交费期 | 年度领取 | 领取开始 | 保守IRR | 中性IRR | 乐观IRR | 回本年度 |",
            "|---:|---|---|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for rank, product in enumerate(numeric, 1):
        lines.append(
            f"| {rank} | {product['company']} | {product['product_name']} | "
            f"{product.get('annual_premium') or 0:,.0f} | {product.get('payment_period') or ''} | "
            f"{product.get('regular_benefit') or 0:,.0f} | {product.get('start_year') or ''} | "
            f"{pct(product.get('irr_conservative'))} | {pct(product.get('irr_neutral'))} | "
            f"{pct(product.get('irr_optimistic'))} | {product.get('breakeven_year') or '未回本'} |"
        )

    lines.extend(
        [
            "",
            "## 目标产品优劣势",
            "",
            "优势：",
            "- 第5个保单周年日起开始领取，现金流启动早于多数60/65周岁后领取的养老年金。",
            "- 保险期间至105周岁，具备明显长寿风险覆盖属性。",
            "- 红利用于购买交清增额保险，若持续分红，可逐步增加未来给付基础。",
            "- 合同责任清晰，适合用作长期、低波动、专款专用的现金流账户。",
            "",
            "劣势：",
            "- 按条款修正现金流后，满期金仅为基本保险金额，弱于满期返还已交保费总额的同类产品。",
            "- 中性 IRR 在可核验样本中偏低，收益属性不适合与高流动性理财或高收益资产直接竞争。",
            "- 身故给付更接近储蓄型返还逻辑，死亡保障杠杆弱，不应替代寿险保障。",
            "- 分红不保证，交清增额带来的长期增值依赖保险公司实际分红水平。",
            "",
            "## 未做数值 IRR 的产品",
            "",
        ]
    )
    skipped = [item for item in products if not item.get("analyzed")]
    for item in skipped:
        lines.append(f"- {item['company']} / {item['product_name']}：{item.get('skip_reason')}")

    (ACTUARIAL_REPORT_DIR / "huiyingfengnian_actuarial_rating_20260603.md").write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8",
    )


def write_persona_report(products: list[dict[str, Any]]) -> None:
    ACTUARIAL_REPORT_DIR.mkdir(parents=True, exist_ok=True)
    target = next(item for item in products if item["product_name"] == TARGET_NAME)
    lines = [
        "# 汇丰汇赢丰年2026年金保险目标客群画像与规划用途",
        "",
        f"- 生成时间：{datetime.now().isoformat(timespec='seconds')}",
        f"- 目标产品评级：{target['rating_grade']}，综合分 {target['rating_score']} / 5，中性 IRR {pct(target.get('irr_neutral'))}。",
        "- 核心判断：适合重视长期现金流、合同纪律和家庭资产专款专用的保守型客户；不适合追求高收益、短期流动性或高身故杠杆的客户。",
        "",
        "## 画像1：中高净值家庭的教育金/成长金规划客户",
        "",
        "- 客户特征：35-45岁父母，家庭现金流稳定，已配置基础保障，希望把一笔资金隔离为孩子未来教育、留学或成年后启动资金。",
        "- 匹配逻辑：产品第5个保单周年日起开始形成年金现金流，可作为教育阶段外的长期补充现金流；交清增额红利机制有利于把非保证分红继续滚入合同，而不是被随意消费。",
        "- 使用边界：它不是短期教育金工具。如果教育支出发生在5年内，或需要确定的大额学费支付，应搭配存款、货币基金、短债或教育专户，不应单独依赖该产品。",
        "",
        "## 画像2：40岁左右的退休养老补充客户",
        "",
        "- 客户特征：处于事业稳定期，已完成房贷/基础保障配置，希望建立一条不依赖市场波动的退休后现金流。",
        "- 匹配逻辑：保险期间至105周岁，解决的是长寿风险和晚年现金流持续性；第5年开始领取使客户较早看到合同现金流，心理可见度高。",
        "- 规划价值：可作为社保养老金、企业年金、商业养老账户之外的第三层补充，不追求最高收益，而追求确定合同责任、稳定领取节奏和强制储蓄。",
        "",
        "## 画像3：保守型财富管理客户",
        "",
        "- 客户特征：风险偏好低，不愿承受权益资产大幅波动，接受长期持有，关注资产稳定、分散和可解释性。",
        "- 匹配逻辑：分红险的保证部分与非保证分红拆分清楚，红利购买交清增额可把潜在收益留在保单内复利增长；合同规则比开放式投资账户更强约束。",
        "- 规划价值：适合作为家庭资产负债表中的低波动底仓，不适合作为追求高收益的主力资产。应与现金管理、债券、权益、保障型寿险分工配置。",
        "",
        "## 画像4：有财富传承和家庭现金流安排需求的客户",
        "",
        "- 客户特征：希望把一部分资产通过保险合同进行受益人安排、长期领取安排和家庭财务纪律管理。",
        "- 匹配逻辑：年金险可以通过投保人、被保险人、受益人安排，把现金流和身故利益纳入家庭规划；交清增额使红利留存在合同内，有助于长期账户化管理。",
        "- 使用边界：目标产品身故杠杆不高，不适合替代终身寿险或定期寿险。若核心目标是放大身故传承金额，应另配寿险；本产品更适合“现金流传承”和“专款专用”。",
        "",
        "## 为什么能服务四类规划目标",
        "",
        "| 规划目标 | 可发挥的作用 | 必须注意的限制 |",
        "|---|---|---|",
        "| 子女教育 | 第5年后可提供年度现金流，红利交清增额形成长期补充账户 | 不适合5年内刚性大额学费，需配短期流动资产 |",
        "| 退休养老 | 至105周岁的长期给付框架有助于覆盖长寿风险 | 实际购买力受通胀影响，分红不保证 |",
        "| 财富管理 | 低波动、合同化、强纪律，适合作为家庭稳健资产底仓 | 中性IRR不领先，不能替代高收益投资组合 |",
        "| 财富传承 | 可通过保险合同受益安排和持续现金流实现专款专用 | 身故杠杆弱，若追求传承放大需搭配寿险 |",
        "",
        "## 不适合人群",
        "",
        "- 未来5年内有购房、创业、留学等大额不确定支出的客户。",
        "- 希望获得高收益或高流动性的投资型客户。",
        "- 尚未完成医疗险、重疾险、定期寿险等基础保障的家庭。",
        "- 主要目标是高额身故保障或财富传承放大的客户。",
    ]
    (ACTUARIAL_REPORT_DIR / "huiyingfengnian_customer_personas_20260603.md").write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    products = build_products()
    write_json(products)
    write_clause_report(products)
    write_actuarial_report(products)
    write_persona_report(products)
    print(
        json.dumps(
            {
                "products": len(products),
                "numeric_actuarial": sum(1 for item in products if item.get("analyzed")),
                "clause_report": str(CLAUSE_REPORT_DIR / "huiyingfengnian_clause_rare_features_20260603.md"),
                "actuarial_report": str(ACTUARIAL_REPORT_DIR / "huiyingfengnian_actuarial_rating_20260603.md"),
                "persona_report": str(ACTUARIAL_REPORT_DIR / "huiyingfengnian_customer_personas_20260603.md"),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
