#!/usr/bin/env python3
from __future__ import annotations

import csv
import html
import importlib.util
import json
import math
import re
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urljoin, urlparse

import pdfplumber
import requests


ROOT = Path("/Users/caijiawen/Documents/New project/insurance-clause-insights")
CRAWLER_ROOT = Path("/Users/caijiawen/Documents/New project/insurance-crawler-push")
PRODUCT_ANALYSIS_ROOT = Path("/Users/caijiawen/Documents/New project/insurance-product-analysis")

sys.path.insert(0, str(PRODUCT_ANALYSIS_ROOT))
from actuarial_calculator import calculate_irr  # noqa: E402


DATE_SLUG = "20260604"
TARGET_NAME = "汇丰臻盈世代2025终身寿险（分红型）"
TARGET_DISPLAY_NAME = "汇丰臻盈世代 2025 终身寿险（分红型）"
OUTPUT_DIR = ROOT / f"outputs/zhenyingshidai_{DATE_SLUG}_analysis"
DOC_DIR = OUTPUT_DIR / "docs"
TEXT_DIR = OUTPUT_DIR / "text_cache"
REPORT_DIR = ROOT / "reports"
ACTUARIAL_REPORT_DIR = PRODUCT_ANALYSIS_ROOT / "reports"

HSBC_BASIC_URL = "https://www.hsbcinsurance.com.cn/about-us/information-disclosure/basic-information/"

API_COMPANIES = ["AIA友邦", "Cigna信诺", "PingAn平安", "Allianz安联"]

SELECTED_PEERS: dict[str, list[str]] = {
    "AIA友邦": [
        "友邦盛世经典众享版2026终身寿险（分红型）",
        "友邦传世经典2026终身寿险（分红型）",
        "友邦传世经典2026尊享版终身寿险（分红型）",
        "友邦悦享恒裕2026终身寿险（分红型）",
        "友邦悦享传世2026终身寿险（分红型）",
    ],
    "Cigna信诺": [
        "招商信诺传家典御（尊享版）终身寿险（分红型）",
        "招商信诺信享传耀尊贵版终身寿险（分红型）",
        "招商信诺瑞享鑫生臻享版终身寿险（分红型）",
        "招商信诺和瑞长盈终身寿险（分红型）",
        "招商信诺信享传世尊享版终身寿险（分红型）",
    ],
    "PingAn平安": [
        "平安御享一生终身寿险（分红型）",
        "平安盛世金越（尊享版26Ⅱ）终身寿险（分红型）",
        "平安盈尊优享（C款）终身寿险（分红型）",
        "平安盛世鑫禧（2026）终身寿险（分红型）",
        "平安创御享金越（2026）终身寿险（分红型）",
    ],
    "HSBC汇丰": [
        "汇丰汇传世家终身寿险（分红型）",
        "汇丰臻盈世代2025至尊版终身寿险（分红型）",
        "汇丰臻盈世代2025尊悦版终身寿险（分红型）",
        "汇丰汇盈世代（尊享版）终身寿险（分红型）",
        "汇丰汇盈世代（优享版）终身寿险（分红型）",
    ],
}

SEARCH_KEYWORDS = ["终身保障", "有效保额递增", "红利用于增额", "可保单贷款", "第二投保人设计"]
TRUE_RARE_THRESHOLD = 0.25
COMMON_FEATURE_THRESHOLD = 0.75

RARE_RULES: list[tuple[str, str]] = [
    ("有效保险金额", "有效保险金额递增"),
    ("基本保险金额×(1+1.75%)", "1.75%有效保险金额递增公式"),
    ("基本保险金额×(1+2.0%)", "2.0%有效保险金额递增公式"),
    ("基本保险金额×(1+2%)", "2.0%有效保险金额递增公式"),
    ("购买交清增额保险", "红利用于购买交清增额保险"),
    ("交清增额保险金额", "累计交清增额保险金额纳入利益演示"),
    ("不提供其他红利实现方式", "红利实现方式锁定为交清增额"),
    ("增额红利", "采用增额红利机制"),
    ("终了红利", "含终了红利机制"),
    ("保单贷款", "支持保单贷款"),
    ("保险费自动垫交", "支持保险费自动垫交"),
    ("减额交清", "支持减额交清"),
    ("减少基本保险金额", "支持减少基本保险金额"),
    ("第二投保人", "含第二投保人安排"),
    ("航空意外身故保险金", "含航空意外额外身故给付"),
    ("重大自然灾害意外身故保险金", "含重大自然灾害意外身故给付"),
    ("全残保险金", "含全残责任"),
]

TARGET_IRR_ROWS = [
    {"policy_year": 20, "age": 63, "death_guaranteed": 360000, "death_scenario2": 464968, "surrender_guaranteed": 339343, "surrender_scenario2": 438278},
    {"policy_year": 30, "age": 73, "death_guaranteed": 403409, "death_scenario2": 603442, "surrender_guaranteed": 403409, "surrender_scenario2": 603442},
    {"policy_year": 40, "age": 83, "death_guaranteed": 479825, "death_scenario2": 831274, "surrender_guaranteed": 479825, "surrender_scenario2": 831273},
    {"policy_year": 50, "age": 93, "death_guaranteed": 570725, "death_scenario2": 1145128, "surrender_guaranteed": 570725, "surrender_scenario2": 1145127},
    {"policy_year": 60, "age": 103, "death_guaranteed": 678846, "death_scenario2": 1577494, "surrender_guaranteed": 678845, "surrender_scenario2": 1577492},
    {"policy_year": 62, "age": 105, "death_guaranteed": 702813, "death_scenario2": 1681863, "surrender_guaranteed": 702813, "surrender_scenario2": 1681861},
]

TARGET_CASH_VALUE_CHECKPOINTS = [
    {"policy_year": 1, "age": 44, "cumulative_premium": 50000, "guaranteed_surrender": 9051},
    {"policy_year": 6, "age": 49, "cumulative_premium": 300000, "guaranteed_surrender": 204678},
    {"policy_year": 10, "age": 53, "cumulative_premium": 300000, "guaranteed_surrender": 287872},
    {"policy_year": 20, "age": 63, "cumulative_premium": 300000, "guaranteed_surrender": 339343},
]


def load_crawler_module():
    spec = importlib.util.spec_from_file_location("insurance_crawler_push", CRAWLER_ROOT / "crawler.py")
    if spec is None or spec.loader is None:
        raise RuntimeError("无法加载 insurance-crawler-push/crawler.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


CRAWLER = load_crawler_module()


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "").replace("\u3000", " ")).strip()


def normalize_name(text: str) -> str:
    name = normalize(text)
    return name.replace(" ", "")


def safe_filename(text: str) -> str:
    return re.sub(r'[\\/:*?"<>|\s]+', "_", text)[:150]


def md_escape(text: str) -> str:
    return normalize(text).replace("|", "｜")


def strip_tags(value: str) -> str:
    return normalize(html.unescape(re.sub(r"<[^>]+>", "", value or "")))


def classify_document(label: str, url: str) -> str:
    decoded = unquote(url)
    bag = f"{label} {decoded} {url}".lower()
    category = CRAWLER.classify_pdf(label, url)
    if category != "其他":
        return category
    if any(word in bag for word in ["条款", "terms", "tnc", "clause", "tiaokuan", "productitem"]):
        return "条款"
    if any(word in bag for word in ["说明书", "description", "instruction", "manual", "cpsms"]):
        return "产品说明书"
    if any(word in bag for word in ["费率", "rates", "rate", "premium", "baofei"]):
        return "费率表"
    if any(word in bag for word in ["现金价值", "cashvalue", "cash-value", "surrender"]):
        return "现金价值"
    return category


def add_document(products: dict[tuple[str, str], dict[str, Any]], company: str, product_name: str, doc: dict[str, Any]) -> None:
    product_name = normalize(product_name)
    if not product_name or product_name in CRAWLER.GENERIC_PRODUCT_NAMES:
        return
    key = (company, product_name)
    entry = products.setdefault(
        key,
        {
            "company": company,
            "product_name": product_name,
            "product_code": doc.get("product_code", ""),
            "source_page": doc.get("source_page", ""),
            "documents": [],
        },
    )
    if doc.get("product_code") and not entry.get("product_code"):
        entry["product_code"] = doc["product_code"]
    seen = {(item["category"], item["url"]) for item in entry["documents"]}
    if (doc.get("category", ""), doc.get("url", "")) not in seen:
        entry["documents"].append(doc)


def collect_api_products() -> dict[tuple[str, str], dict[str, Any]]:
    products: dict[tuple[str, str], dict[str, Any]] = {}
    for company in API_COMPANIES:
        config = CRAWLER.TARGETS[company]
        parser = getattr(CRAWLER, config["parser"])
        links = parser(None, config["url"])
        for item in links:
            product_name = CRAWLER.infer_product_name(item)
            category = item.get("category") or classify_document(item.get("text", ""), item.get("url", ""))
            doc = {
                "category": category,
                "url": item.get("url", ""),
                "text": item.get("text", ""),
                "source_page": config["url"],
                "product_code": item.get("plan_code", ""),
                "version_or_date": item.get("version_or_date", "") or item.get("start_date", "") or item.get("online_date", ""),
            }
            add_document(products, company, product_name, doc)
    return products


def collect_hsbc_products(products: dict[tuple[str, str], dict[str, Any]]) -> None:
    response = requests.get(HSBC_BASIC_URL, headers={"User-Agent": "Mozilla/5.0"}, timeout=60)
    response.raise_for_status()
    body = response.text

    for row in re.findall(r"<tr\b[^>]*>(.*?)</tr>", body, flags=re.I | re.S):
        cells = re.findall(r"<td\b[^>]*>(.*?)</td>", row, flags=re.I | re.S)
        if len(cells) >= 4:
            product_name = strip_tags(cells[0])
            product_code = strip_tags(cells[1]) if len(cells) > 1 else ""
            for link_match in re.finditer(r'<a\s+[^>]*href="([^"]+)"[^>]*>(.*?)</a>', row, flags=re.I | re.S):
                href = html.unescape(link_match.group(1))
                label = strip_tags(link_match.group(2))
                url = CRAWLER.normalize_attachment_url(urljoin(HSBC_BASIC_URL, href))
                if not CRAWLER.is_supported_attachment_url(url):
                    continue
                add_document(
                    products,
                    "HSBC汇丰",
                    product_name,
                    {
                        "category": classify_document(label, url),
                        "url": url,
                        "text": label,
                        "source_page": HSBC_BASIC_URL,
                        "product_code": product_code,
                    },
                )

    for link_match in re.finditer(r'<a\s+[^>]*href="([^"]+)"[^>]*>(.*?)</a>', body, flags=re.I | re.S):
        href = html.unescape(link_match.group(1))
        label = strip_tags(link_match.group(2))
        url = CRAWLER.normalize_attachment_url(urljoin(HSBC_BASIC_URL, href))
        if not CRAWLER.is_supported_attachment_url(url):
            continue
        product_name = CRAWLER.normalize_product_name(label)
        add_document(
            products,
            "HSBC汇丰",
            product_name,
            {
                "category": classify_document(label, url),
                "url": url,
                "text": label,
                "source_page": HSBC_BASIC_URL,
            },
        )


def is_whole_life_participating(product: dict[str, Any]) -> bool:
    name = product["product_name"]
    bag = f"{name} {' '.join(doc.get('text', '') + ' ' + doc.get('url', '') for doc in product['documents'])}"
    return ("终身寿" in bag or "whole-life" in bag.lower()) and ("分红" in bag or "participating" in bag.lower())


def document_categories(product: dict[str, Any]) -> list[str]:
    return sorted({doc["category"] for doc in product.get("documents", []) if doc.get("category")})


def product_recency(product: dict[str, Any]) -> tuple[int, int]:
    bag = product["product_name"] + " " + " ".join(doc.get("version_or_date", "") + " " + doc.get("url", "") for doc in product["documents"])
    years = [int(value) for value in re.findall(r"20\d{2}", bag)]
    return (max(years) if years else 0, len(product.get("documents", [])))


def score_candidate(product: dict[str, Any]) -> int:
    name = product["product_name"]
    docs = document_categories(product)
    score = 0
    if "终身寿" in name:
        score += 20
    if "分红型" in name or "分红险" in name:
        score += 20
    if "2026" in name:
        score += 8
    elif "2025" in name:
        score += 6
    if "现金价值" in docs:
        score += 5
    if "费率表" in docs:
        score += 5
    if "产品说明书" in docs:
        score += 4
    if "条款" in docs:
        score += 4
    if any(word in name for word in ["臻", "传世", "世代", "金越", "经典", "尊享", "至尊"]):
        score += 4
    return score


def build_discovery() -> dict[str, Any]:
    products = collect_api_products()
    collect_hsbc_products(products)

    full_candidates = [
        {
            **product,
            "document_categories": document_categories(product),
            "candidate_score": score_candidate(product),
            "recency": product_recency(product),
        }
        for product in products.values()
        if is_whole_life_participating(product)
    ]
    full_candidates.sort(key=lambda item: (item["candidate_score"], item["recency"]), reverse=True)

    selected_peers: list[dict[str, Any]] = []
    missing: list[str] = []
    product_map = {(item["company"], normalize_name(item["product_name"])): item for item in products.values()}
    for company, names in SELECTED_PEERS.items():
        for name in names:
            item = product_map.get((company, normalize_name(name)))
            if not item:
                missing.append(f"{company} / {name}")
                continue
            selected_peers.append({**item, "selection_note": selection_note(company, name)})

    target = product_map.get(("HSBC汇丰", normalize_name(TARGET_NAME)))
    if not target:
        raise RuntimeError(f"未在 HSBC 公开披露页发现目标产品：{TARGET_NAME}")

    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "target": {**target, "selection_note": "目标产品，作为比较基准，不计入20个同类产品。"},
        "selected_peers": selected_peers,
        "full_candidates": full_candidates,
        "missing_selected": missing,
        "search_keywords": SEARCH_KEYWORDS,
        "source_projects": {
            "crawler": str(CRAWLER_ROOT),
            "clause_insights": str(ROOT),
            "product_analysis": str(PRODUCT_ANALYSIS_ROOT),
        },
    }


def selection_note(company: str, name: str) -> str:
    if company == "HSBC汇丰":
        return "汇丰同公司分红型终身寿险，条款语言、红利实现方式和第二投保人安排可比性强。"
    if company == "AIA友邦":
        return "友邦2026/2025序列分红型终身寿险，适合比较增额红利、终了红利和寿险杠杆。"
    if company == "Cigna信诺":
        return "招商信诺在售分红型终身寿险，公开材料覆盖条款、说明书、费率和现金价值。"
    if company == "PingAn平安":
        return "平安2026序列分红型终身寿险，适合比较有效保额递增、保单权益和身故给付结构。"
    return "同类分红型终身寿险候选。"


def preferred_doc(product: dict[str, Any], category: str) -> dict[str, Any] | None:
    candidates = [doc for doc in product.get("documents", []) if doc.get("category") == category and doc.get("url")]
    if not candidates:
        return None

    def rank(doc: dict[str, Any]) -> tuple[int, int, int]:
        url = unquote(doc.get("url", "")).lower()
        score = 0
        if "offstock" not in url and "notsold" not in url and "historical" not in url:
            score += 20
        if "basic-information" in url or "products/life-stages/2025" in url:
            score += 10
        if category == "条款" and any(word in url for word in ["terms", "tnc", "clause", "tiaokuan", "条款"]):
            score += 8
        if category == "产品说明书" and any(word in url for word in ["description", "instruction", "manual", "说明书", "cpsms"]):
            score += 8
        if category == "费率表" and any(word in url for word in ["rates", "rate", "费率"]):
            score += 8
        if category == "现金价值" and any(word in url for word in ["cashvalue", "现金价值"]):
            score += 8
        years = [int(value) for value in re.findall(r"20\d{2}", url)]
        return (score, max(years) if years else 0, -len(url))

    return sorted(candidates, key=rank, reverse=True)[0]


def attachment_suffix(url: str, content_type: str = "") -> str:
    suffix = Path(urlparse(url).path).suffix.lower()
    if suffix in {".pdf", ".xls", ".xlsx"}:
        return suffix
    content_type = content_type.lower()
    if "spreadsheetml" in content_type or "xlsx" in content_type:
        return ".xlsx"
    if "excel" in content_type or "xls" in content_type:
        return ".xls"
    return ".pdf"


def download_document(company: str, product_name: str, category: str, doc: dict[str, Any]) -> str:
    url = doc.get("url", "")
    if not url:
        return ""
    DOC_DIR.mkdir(parents=True, exist_ok=True)
    suffix = attachment_suffix(url)
    path = DOC_DIR / f"{safe_filename(company)}_{safe_filename(product_name)}_{safe_filename(category)}{suffix}"
    if path.exists() and path.stat().st_size > 0:
        return str(path)

    response = requests.get(
        requests.utils.requote_uri(url),
        headers={"User-Agent": "Mozilla/5.0", "Referer": doc.get("source_page") or url},
        timeout=90,
    )
    response.raise_for_status()
    response_suffix = attachment_suffix(url, response.headers.get("Content-Type", ""))
    if response_suffix != path.suffix:
        path = path.with_suffix(response_suffix)
    path.write_bytes(response.content)
    return str(path)


def read_pdf_text(path: str | Path) -> str:
    path = Path(path)
    if path.suffix.lower() != ".pdf":
        return ""
    TEXT_DIR.mkdir(parents=True, exist_ok=True)
    cache = TEXT_DIR / f"{path.stem}.txt"
    if cache.exists():
        return cache.read_text(encoding="utf-8", errors="ignore")
    parts: list[str] = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            if text:
                parts.append(text)
    text = "\n".join(parts)
    cache.write_text(text, encoding="utf-8")
    return text


def split_snippets(text: str, keywords: list[str], limit: int = 3) -> list[str]:
    snippets: list[str] = []
    for piece in re.split(r"[。；;\n\r]+", text):
        item = normalize(piece)
        if not 12 <= len(item) <= 180:
            continue
        if is_low_signal_snippet(item):
            continue
        if any(keyword in item for keyword in keywords):
            snippets.append(item)
        if len(snippets) >= limit:
            break
    return snippets


def is_low_signal_snippet(item: str) -> bool:
    if "目录" in item or "阅读指引" in item:
        return True
    if item.count(".") >= 8 or "......" in item or "．．．．" in item:
        return True
    if len(re.findall(r"\d+\.\d+", item)) >= 3:
        return True
    if re.fullmatch(r"[\d\s.,，、年月日号\[\]（）()A-Za-z\u4e00-\u9fff-]+", item) and len(item) < 26 and "保险期间" not in item:
        return True
    return False


def first_snippet(text: str, keywords: list[str]) -> str:
    snippets = split_snippets(text, keywords, 1)
    return snippets[0] if snippets else ""


def regex_snippet(text: str, patterns: list[str], fallback_keywords: list[str]) -> str:
    compact = normalize(text)
    for pattern in patterns:
        match = re.search(pattern, compact)
        if match:
            return normalize(match.group(0))[:180]
    return first_snippet(text, fallback_keywords)


def keyword_hits(product: dict[str, Any], text: str) -> list[str]:
    docs = set(product.get("document_categories") or document_categories(product))
    bag = f"{product['product_name']}\n{text}"
    checks = [
        ("分红型", ["分红型", "分红保险"]),
        ("终身保障", ["保险期间为被保险人终身", "保险期间为终身", "被保险人终身"]),
        ("有效保额递增", ["有效保险金额", "有效保额", "1+1.75%", "1+2.0%", "1+2%"]),
        ("红利用于增额", ["购买交清增额保险", "交清增额保险金额", "增额红利"]),
        ("可保单贷款", ["保单贷款"]),
        ("第二投保人设计", ["第二投保人"]),
        ("减额交清", ["减额交清"]),
        ("减少基本保险金额", ["减少基本保险金额"]),
        ("全残责任", ["全残保险金"]),
        ("意外额外给付", ["航空意外身故保险金", "重大自然灾害意外身故保险金"]),
    ]
    hits = [label for label, words in checks if any(word in bag for word in words)]
    if "费率表" in docs:
        hits.append("公开费率表")
    if "现金价值" in docs:
        hits.append("公开现金价值全表")
    return hits


def rare_clauses(text: str) -> list[str]:
    found: list[str] = []
    compact = text.replace(" ", "")
    for keyword, label in RARE_RULES:
        if keyword.replace(" ", "") in compact and label not in found:
            found.append(label)
    return found


def build_feature_frequencies(products: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    total = len(products)
    counts: dict[str, int] = defaultdict(int)
    owners: dict[str, list[dict[str, str]]] = defaultdict(list)
    for product in products:
        labels = sorted(set(product.get("raw_keyword_hits", [])) | set(product.get("raw_clause_tags", [])))
        product["_all_feature_labels"] = labels
        for label in labels:
            counts[label] += 1
            owners[label].append({
                "company": product["company"],
                "product_name": product["product_name"],
            })

    stats: dict[str, dict[str, Any]] = {}
    for label, count in counts.items():
        frequency = count / total if total else 0
        if frequency >= COMMON_FEATURE_THRESHOLD:
            classification = "通用功能"
        elif frequency < TRUE_RARE_THRESHOLD:
            classification = "真罕见条款"
        else:
            classification = "相对少见功能"
        stats[label] = {
            "label": label,
            "count": count,
            "total": total,
            "frequency": frequency,
            "uniqueness_score": round(1 - frequency, 4),
            "classification": classification,
            "owners": owners[label],
        }
    return stats


def feature_owner_companies(info: dict[str, Any]) -> set[str]:
    return {owner["company"] for owner in info.get("owners", [])}


def target_weaknesses() -> list[str]:
    return [
        "终身保障、红利用于增额、保单贷款均为样本标配，不构成独有卖点。",
        "保证退保给付IRR从第20年至105岁约0.75%-1.47%，保证收益属性不强。",
        "第6年保证退保值204,678元，约为累计保费300,000元的68.2%，早期退保成本高。",
        "1.75%有效保险金额递增不是独有，且弱于部分2.0%有效保额递增产品。",
        "同公司汇丰多款同系列产品共享第二投保人、交清增额和意外额外给付组合，目标产品并非同公司内唯一。",
    ]


def build_numeric_comparison(product: dict[str, Any]) -> dict[str, Any]:
    if product.get("is_target"):
        checkpoints = []
        for item in TARGET_CASH_VALUE_CHECKPOINTS:
            ratio = item["guaranteed_surrender"] / item["cumulative_premium"] if item["cumulative_premium"] else None
            checkpoints.append({**item, "guaranteed_surrender_to_premium": ratio})
        return {
            "analyzed": True,
            "source_quality": "目标产品公开说明书利益演示表",
            "irr_rows": target_irr_analysis(),
            "cash_value_checkpoints": checkpoints,
            "unresolved_reason": "",
        }
    return {
        "analyzed": False,
        "source_quality": "",
        "irr_rows": [],
        "cash_value_checkpoints": [],
        "unresolved_reason": "缺少已解析的同口径现金价值/利益演示表；未参与收益排名，仅参与条款维度评分。",
    }


def apply_feature_frequency_adjustments(products: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    stats = build_feature_frequencies(products)
    for product in products:
        labels = product.get("_all_feature_labels", [])
        audit: list[dict[str, Any]] = []
        common: list[str] = []
        relative: list[str] = []
        true_rare: list[str] = []
        for label in labels:
            info = stats[label]
            companies = feature_owner_companies(info)
            is_target_feature = product.get("is_target", False)
            shared_by_same_company = is_target_feature and companies == {product["company"]} and info["count"] > 1
            row = {
                "label": label,
                "classification": info["classification"],
                "peer_count": info["count"],
                "peer_total": info["total"],
                "peer_frequency": info["frequency"],
                "uniqueness_score": info["uniqueness_score"],
                "target_only": is_target_feature and info["count"] == 1,
                "shared_by_same_company": shared_by_same_company,
            }
            audit.append(row)
            if info["classification"] == "通用功能":
                common.append(label)
            elif info["classification"] == "真罕见条款":
                true_rare.append(label)
            else:
                relative.append(label)

        product["feature_audit"] = sorted(audit, key=lambda item: (item["peer_frequency"], item["label"]))
        product["common_features"] = common
        product["relative_features"] = relative
        product["true_rare_features"] = true_rare
        product["rare_clauses"] = [label for label in product.get("raw_clause_tags", []) if label in true_rare]
        product["target_weaknesses"] = target_weaknesses() if product.get("is_target") else []
        product["numeric_comparison"] = build_numeric_comparison(product)
        product["distinctive_feature"] = distinctive_summary(product)
        product["rating_dimensions"] = dimension_scores(product)
        product["rating_score"] = weighted_score(product["rating_dimensions"])
        product["rating_grade"] = grade_from_score(product["rating_score"])
    return stats


def distinctive_summary(product: dict[str, Any]) -> str:
    name = product["product_name"]
    hits = set(product.get("raw_keyword_hits", product.get("keyword_hits", [])))
    true_rare = set(product.get("true_rare_features", []))
    relative = set(product.get("relative_features", []))
    if name == TARGET_NAME:
        return "单项功能多数不是独有；相对差异在于双意外额外给付、第二投保人、交清增额和材料透明度的组合，但汇丰同系列产品高度相似。"
    if "至尊版" in name or "尊悦版" in name:
        return "同系列高端版本，适合比较投保年龄、费率、现金价值曲线和第二投保人安排的版本差异。"
    if "含重大自然灾害意外身故给付" in true_rare or "含航空意外额外身故给付" in true_rare:
        return "意外额外给付在样本中相对少见，保障杠杆较普通终身寿险更突出。"
    if "第二投保人设计" in relative and "红利用于增额" in hits:
        return "兼具第二投保人安排与红利增额机制，家庭传承治理属性突出。"
    if "有效保额递增" in hits:
        return "有效保险金额递增有明确公式，但该能力在样本中不罕见，需结合现金价值表现判断优劣。"
    if "公开现金价值全表" in hits and "公开费率表" in hits:
        return "费率表与现金价值全表材料完整，适合做退保价值和保费效率横向比较。"
    return product.get("selection_note") or "分红型终身寿险同类产品，适合横向条款比较。"


def target_irr_analysis() -> list[dict[str, Any]]:
    rows = []
    annual_premium = 50000.0
    payment_period = 6
    for item in TARGET_IRR_ROWS:
        year = item["policy_year"]
        row = dict(item)
        for key in ["death_guaranteed", "death_scenario2", "surrender_guaranteed", "surrender_scenario2"]:
            cashflows = [0.0] * (year + 1)
            for t in range(1, min(payment_period, year) + 1):
                cashflows[t] -= annual_premium
            cashflows[year] += float(item[key])
            row[f"{key}_irr"] = calculate_irr(cashflows)
        rows.append(row)
    return rows


def grade_from_score(score: float) -> str:
    if score >= 4.35:
        return "A"
    if score >= 3.85:
        return "B+"
    if score >= 3.25:
        return "B"
    if score >= 2.6:
        return "C"
    return "D"


def numeric_yield_score(product: dict[str, Any]) -> float:
    comparison = product.get("numeric_comparison", {})
    if not comparison.get("analyzed"):
        return 2.5
    rows = comparison.get("irr_rows") or []
    terminal = rows[-1] if rows else {}
    guaranteed = terminal.get("surrender_guaranteed_irr")
    if guaranteed is None:
        return 2.5
    if guaranteed >= 0.025:
        return 4.5
    if guaranteed >= 0.02:
        return 4.0
    if guaranteed >= 0.015:
        return 3.0
    if guaranteed >= 0.01:
        return 2.5
    return 2.0


def dimension_scores(product: dict[str, Any]) -> dict[str, float]:
    hits = set(product.get("raw_keyword_hits", product.get("keyword_hits", [])))
    raw = set(product.get("raw_clause_tags", []))
    docs = set(product.get("document_categories") or document_categories(product))

    guarantee = 5 if "有效保额递增" in hits else 3
    if "2.0%有效保险金额递增公式" in raw:
        guarantee = 5
    elif "1.75%有效保险金额递增公式" in raw:
        guarantee = 4

    dividend = 3.5 if "红利用于增额" in hits else 2
    if "红利实现方式锁定为交清增额" in raw:
        dividend = 4.5
    elif "含终了红利机制" in raw:
        dividend = 4.0

    liquidity = 2 + 0.4 * int("可保单贷款" in hits) + 0.8 * int("减额交清" in hits) + 0.8 * int("减少基本保险金额" in hits)
    liquidity = min(5, liquidity)
    governance = 4.5 if "第二投保人设计" in hits else 3
    legacy = 3 + 0.7 * int("全残责任" in hits) + 0.8 * int("含航空意外额外身故给付" in raw) + 0.8 * int("含重大自然灾害意外身故给付" in raw)
    if product.get("text_signals", {}).get("life_multiplier_table"):
        legacy += 0.3
    legacy = min(5, legacy)
    transparency = min(5, 1 + len({"条款", "产品说明书", "费率表", "现金价值"} & docs))
    if {"条款", "产品说明书", "费率表", "现金价值"} <= docs:
        transparency = 5

    risk_control = 3.5
    if product.get("text_signals", {}).get("dividend_uncertain"):
        risk_control += 1
    if product.get("text_signals", {}).get("no_base_amount_increase"):
        risk_control -= 1
    risk_control = max(1, min(5, risk_control))

    return {
        "保证利益强度": round(guarantee, 2),
        "非保证红利机制": round(dividend, 2),
        "流动性权益": liquidity,
        "传承治理": governance,
        "身故/全残杠杆": legacy,
        "材料透明度": transparency,
        "风险提示清晰度": risk_control,
        "数值收益": numeric_yield_score(product),
    }


def weighted_score(dimensions: dict[str, float]) -> float:
    weights = {
        "保证利益强度": 0.18,
        "非保证红利机制": 0.14,
        "流动性权益": 0.12,
        "传承治理": 0.14,
        "身故/全残杠杆": 0.16,
        "材料透明度": 0.11,
        "风险提示清晰度": 0.05,
        "数值收益": 0.10,
    }
    return round(sum(dimensions[key] * weight for key, weight in weights.items()), 2)


def analyze_products(discovery: dict[str, Any]) -> list[dict[str, Any]]:
    ordered = [discovery["target"], *discovery["selected_peers"]]
    products: list[dict[str, Any]] = []
    for index, source in enumerate(ordered, 1):
        product = dict(source)
        product["order"] = index
        product["is_target"] = normalize_name(product["product_name"]) == normalize_name(TARGET_NAME)
        product["document_categories"] = document_categories(product)

        selected_docs: dict[str, dict[str, Any]] = {}
        doc_paths: dict[str, str] = {}
        doc_texts: dict[str, str] = {}
        for category in ["条款", "产品说明书", "费率表", "现金价值"]:
            doc = preferred_doc(product, category)
            if not doc:
                continue
            selected_docs[category] = doc
            try:
                path = download_document(product["company"], product["product_name"], category, doc)
                doc_paths[category] = path
                if category in {"条款", "产品说明书"}:
                    doc_texts[category] = read_pdf_text(path)
            except Exception as exc:
                doc_paths[f"{category}_download_error"] = str(exc)

        terms_text = doc_texts.get("条款", "")
        manual_text = doc_texts.get("产品说明书", "")
        combined_text = "\n".join([terms_text, manual_text])
        product["selected_documents"] = selected_docs
        product["doc_paths"] = doc_paths
        product["terms_url"] = selected_docs.get("条款", {}).get("url", "")
        product["manual_url"] = selected_docs.get("产品说明书", {}).get("url", "")
        product["rate_url"] = selected_docs.get("费率表", {}).get("url", "")
        product["cash_value_url"] = selected_docs.get("现金价值", {}).get("url", "")
        product["terms_text_chars"] = len(terms_text)
        product["manual_text_chars"] = len(manual_text)
        product["raw_keyword_hits"] = keyword_hits(product, combined_text)
        product["keyword_hits"] = list(product["raw_keyword_hits"])
        product["raw_clause_tags"] = rare_clauses(combined_text)
        product["rare_clauses"] = list(product["raw_clause_tags"])
        product["text_signals"] = {
            "life_multiplier_table": "160%" in combined_text and "140%" in combined_text and "120%" in combined_text,
            "dividend_uncertain": "分红是不确定" in combined_text or "红利分配是不确定" in combined_text,
            "no_base_amount_increase": "不支持基本保险金额的增加" in combined_text,
        }
        product["insurance_period_snippet"] = regex_snippet(
            terms_text,
            [
                r"本合同的保险期间[^。；]{0,100}终身[^。；]{0,80}",
                r"保险期间[^。；]{0,80}终身[^。；]{0,80}",
                r"保险合同的保险期间[^。；]{0,100}终身[^。；]{0,80}",
            ],
            ["保险期间", "终身"],
        )
        product["effective_amount_snippet"] = regex_snippet(
            combined_text,
            [
                r"有效保险金额[^。；]{0,120}",
                r"基本保险金额×\(1\+[\d.]+%\)[^。；]{0,80}",
                r"基本保险金额\s*[×xX]\s*\(1\+[\d.]+%\)[^。；]{0,80}",
            ],
            ["有效保险金额", "有效保额", "1.75%", "2.0%", "2%"],
        )
        product["dividend_snippets"] = split_snippets(combined_text, ["红利", "交清增额", "增额红利", "终了红利"], 3)
        product["loan_snippet"] = first_snippet(terms_text, ["保单贷款", "贷款"])
        product["second_policyholder_snippet"] = first_snippet(terms_text, ["第二投保人"])
        product["death_snippet"] = first_snippet(terms_text, ["身故保险金", "全残保险金"])
        product["cash_value_snippet"] = first_snippet(terms_text, ["现金价值", "减少基本保险金额", "减额交清", "退保"])
        if product["is_target"]:
            product["target_irr_analysis"] = target_irr_analysis()
        products.append(product)
    apply_feature_frequency_adjustments(products)
    return products


def pct(value: float | None) -> str:
    if value is None or (isinstance(value, float) and (math.isnan(value) or math.isinf(value))):
        return "N/A"
    return f"{value:.2%}"


def pct1(value: float | None) -> str:
    if value is None or (isinstance(value, float) and (math.isnan(value) or math.isinf(value))):
        return "N/A"
    return f"{value:.1%}"


def score_text(value: float | None) -> str:
    if value is None:
        return ""
    return f"{value:.2f}".rstrip("0").rstrip(".")


def money(value: float | int | None) -> str:
    if value is None:
        return ""
    return f"{float(value):,.0f}"


def company_counts(items: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = defaultdict(int)
    for item in items:
        counts[item["company"]] += 1
    return dict(counts)


def write_discovery_outputs(discovery: dict[str, Any]) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    (OUTPUT_DIR / "zhenyingshidai_full_peer_candidates.json").write_text(
        json.dumps(discovery, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )

    csv_path = REPORT_DIR / f"zhenyingshidai_selected_20_peer_products_{DATE_SLUG}.csv"
    with csv_path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.writer(handle)
        writer.writerow(["序号", "公司", "产品", "产品代码", "材料类别", "条款链接", "选择理由"])
        for index, item in enumerate(discovery["selected_peers"], 1):
            writer.writerow([
                index,
                item["company"],
                item["product_name"],
                item.get("product_code", ""),
                "；".join(document_categories(item)),
                preferred_doc(item, "条款").get("url", "") if preferred_doc(item, "条款") else "",
                item.get("selection_note", ""),
            ])

    full = discovery["full_candidates"]
    selected = discovery["selected_peers"]
    counts = company_counts(selected)
    full_counts = company_counts(full)
    lines = [
        f"# {TARGET_DISPLAY_NAME}同类产品全量发现",
        "",
        f"- 生成时间：{discovery['generated_at']}",
        "- 关键词：终身保障、有效保额递增、红利用于增额、可保单贷款、第二投保人设计。",
        "- 数据口径：调用 `insurance-crawler-push` 的 AIA、Cigna、平安、安联公开披露 API；HSBC 使用其公开信息披露静态页面解析，候选阶段不使用每家公司每险种3个产品限制。",
        "- 入选口径：目标产品单列，最终20个同类产品不含目标；AIA、Cigna、平安、HSBC各5款，安联当前公开披露接口未发现满足“分红型终身寿险”的在售候选。",
        "",
        "## 候选池统计",
        "",
        "| 公司 | 分红型终身寿险候选数 | 入选数 |",
        "|---|---:|---:|",
    ]
    for company in sorted(set(full_counts) | set(counts)):
        lines.append(f"| {company} | {full_counts.get(company, 0)} | {counts.get(company, 0)} |")

    lines.extend(
        [
            "",
            "## 目标产品",
            "",
            f"- HSBC汇丰 / {TARGET_NAME}：产品代码 PWB，作为分析基准产品，未计入下方20个同类产品。",
            f"- 条款来源：{preferred_doc(discovery['target'], '条款').get('url', '') if preferred_doc(discovery['target'], '条款') else ''}",
            f"- 产品说明书：{preferred_doc(discovery['target'], '产品说明书').get('url', '') if preferred_doc(discovery['target'], '产品说明书') else ''}",
            "",
            "## 入选20个同类产品",
            "",
            "| # | 公司 | 产品 | 产品代码 | 材料类别 | 选择理由 |",
            "|---:|---|---|---|---|---|",
        ]
    )
    for index, item in enumerate(selected, 1):
        lines.append(
            f"| {index} | {item['company']} | {item['product_name']} | {item.get('product_code', '')} | "
            f"{'；'.join(document_categories(item))} | {md_escape(item.get('selection_note', ''))} |"
        )

    lines.extend(
        [
            "",
            "## 未入选但已发现的主要候选",
            "",
        ]
    )
    selected_keys = {(item["company"], item["product_name"]) for item in selected}
    selected_keys.add((discovery["target"]["company"], discovery["target"]["product_name"]))
    for item in full[:80]:
        if (item["company"], item["product_name"]) in selected_keys:
            continue
        lines.append(
            f"- {item['company']} / {item['product_name']}：候选分 {item['candidate_score']}，材料类别 {'；'.join(item['document_categories']) or '未识别'}。"
        )

    if discovery["missing_selected"]:
        lines.extend(["", "## 缺失提示", ""])
        for item in discovery["missing_selected"]:
            lines.append(f"- 预设入选但未在本次公开披露解析中发现：{item}")

    (REPORT_DIR / f"zhenyingshidai_full_peer_discovery_{DATE_SLUG}.md").write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8",
    )


def write_analysis_json(products: list[dict[str, Any]]) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    feature_frequencies = build_feature_frequencies(products)
    payload = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "target_product": TARGET_NAME,
        "product_count_including_target": len(products),
        "products": products,
        "target_numeric_irr_rows": next(item.get("target_irr_analysis", []) for item in products if item["is_target"]),
        "feature_frequencies": feature_frequencies,
    }
    (OUTPUT_DIR / "zhenyingshidai_20260604_analysis.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )


def write_clause_report(products: list[dict[str, Any]]) -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    target = next(item for item in products if item["is_target"])
    target_audit = target.get("feature_audit", [])
    common_target = [item for item in target_audit if item["classification"] == "通用功能"]
    relative_target = [item for item in target_audit if item["classification"] == "相对少见功能"]
    rare_target = [item for item in target_audit if item["classification"] == "真罕见条款"]
    lines = [
        f"# {TARGET_DISPLAY_NAME}及20个同类产品条款特色与罕见条款分析",
        "",
        f"- 生成时间：{datetime.now().isoformat(timespec='seconds')}",
        f"- 输入清单：`reports/zhenyingshidai_full_peer_discovery_{DATE_SLUG}.md` 中的目标产品和20个同类产品。",
        "- 分析工具：`insurance-clause-insights` 读取条款 PDF 和产品说明书，并按同类样本频率校正条款独特性。",
        f"- 罕见口径：只有样本命中率低于 {TRUE_RARE_THRESHOLD:.0%} 的条款才标为“真罕见条款”；高频功能只作为基础配置，不作为独有卖点。",
        "- 风险口径：分红利益均为非保证利益；本报告只引用公开材料，不构成销售建议。",
        "",
        "## 产品特色总览",
        "",
        "| # | 公司 | 产品 | 通用功能数 | 相对少见数 | 真罕见条款 | 差异化结论 |",
        "|---:|---|---|---:|---:|---|---|",
    ]
    for product in products:
        lines.append(
            f"| {product['order']} | {product['company']} | {product['product_name']} | "
            f"{len(product.get('common_features', []))} | {len(product.get('relative_features', []))} | "
            f"{md_escape('；'.join(product.get('rare_clauses', [])) or '无')} | "
            f"{md_escape(product['distinctive_feature'])} |"
        )

    lines.extend(
        [
            "",
            "## 目标产品独特性审计表",
            "",
            "| 特征 | 分类 | 样本命中 | 独特性分 | 仅目标独有 | 仅汇丰同公司共享 |",
            "|---|---|---:|---:|---|---|",
        ]
    )
    for item in target_audit:
        lines.append(
            f"| {md_escape(item['label'])} | {item['classification']} | "
            f"{item['peer_count']}/{item['peer_total']} ({pct1(item['peer_frequency'])}) | "
            f"{item['uniqueness_score']:.2f} | {'是' if item['target_only'] else '否'} | "
            f"{'是' if item['shared_by_same_company'] else '否'} |"
        )

    lines.extend(
        [
            "",
            "## 反差结论",
            "",
            f"- 不独有项：{'；'.join(item['label'] for item in common_target) or '无'}。",
            f"- 相对少见项：{'；'.join(item['label'] for item in relative_target) or '无'}。",
            f"- 真罕见项：{'；'.join(item['label'] for item in rare_target) or '无'}。",
            "- 结论修正：目标产品不能再被描述为“保单贷款、终身保障、红利增额独特”；这些是本类产品的基础配置。",
            "- 更准确表述：目标产品的差异化来自组合完整度，但该组合在汇丰同系列产品中并不唯一，因此不是强独占卖点。",
            "",
            "## 目标产品弱项",
            "",
        ]
    )
    for item in target.get("target_weaknesses", []):
        lines.append(f"- {item}")

    lines.extend(["", "## 逐产品条款摘要", ""])
    for product in products:
        lines.extend(
            [
                f"### {product['order']}. {product['company']} - {product['product_name']}",
                "",
                f"- 差异化结论：{product['distinctive_feature']}",
                f"- 通用功能：{'；'.join(product.get('common_features', [])) or '无'}",
                f"- 相对少见功能：{'；'.join(product.get('relative_features', [])) or '无'}",
                f"- 真罕见条款：{'；'.join(product.get('rare_clauses', [])) or '无'}",
                f"- 保险期间证据：{product['insurance_period_snippet'] or '条款文本未直接抽取到'}",
                f"- 有效保额证据：{product['effective_amount_snippet'] or '条款文本未直接抽取到'}",
                f"- 分红/增额证据：{'；'.join(product['dividend_snippets']) or '条款文本未直接抽取到'}",
                f"- 保单贷款证据：{product['loan_snippet'] or '条款文本未直接抽取到'}",
                f"- 第二投保人证据：{product['second_policyholder_snippet'] or '条款文本未直接抽取到'}",
                f"- 身故/全残责任证据：{product['death_snippet'] or '条款文本未直接抽取到'}",
                f"- 现金价值/减保证据：{product['cash_value_snippet'] or '条款文本未直接抽取到'}",
                f"- 条款 PDF：{product.get('terms_url', '')}",
                f"- 产品说明书：{product.get('manual_url', '')}",
                f"- 费率表：{product.get('rate_url', '')}",
                f"- 现金价值表：{product.get('cash_value_url', '')}",
                "",
            ]
        )

    lines.extend(
        [
            "## 关键发现",
            "",
            "- 20个同类产品大多满足“终身保障 + 分红型 + 现金价值权益 + 保单贷款”基础特征，不能把这些基础配置当作目标产品独特卖点。",
            "- 目标产品相对少见的方向是“第二投保人 + 双意外额外给付 + 交清增额 + 材料完整”的组合，而不是某一单项条款独有。",
            "- AIA样本更偏增额红利/终了红利语言；平安样本更强调新版号、现金价值和给付倍数；Cigna样本材料完整度较高；HSBC同系列样本与目标产品高度相似，削弱目标产品独占性。",
        ]
    )
    (REPORT_DIR / f"zhenyingshidai_clause_rare_features_{DATE_SLUG}.md").write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8",
    )


def write_actuarial_report(products: list[dict[str, Any]]) -> None:
    ACTUARIAL_REPORT_DIR.mkdir(parents=True, exist_ok=True)
    ranked = sorted(products, key=lambda item: item["rating_score"], reverse=True)
    target = next(item for item in products if item["is_target"])
    target_rank = next(index for index, item in enumerate(ranked, 1) if item["is_target"])
    target_audit = {item["label"]: item for item in target.get("feature_audit", [])}

    lines = [
        f"# {TARGET_DISPLAY_NAME}精算特点与优劣评级",
        "",
        f"- 生成时间：{datetime.now().isoformat(timespec='seconds')}",
        "- 输入：`insurance-clause-insights` 生成的21款分红型终身寿险条款特征与罕见条款。",
        "- 工具：调用 `insurance-product-analysis` 的 `calculate_irr` 计算目标产品公开演示表 IRR；其他产品如缺少同口径现金价值/利益演示解析，则不参与收益排名。",
        "- 目标数值样例：43岁女性、6年交、年交保费50,000元、基本保险金额243,916元，来自目标产品公开产品说明书利益演示表。",
        "",
        "## 结论摘要",
        "",
        f"- 目标产品综合评级：{target['rating_grade']}，综合分 {target['rating_score']} / 5，在21款产品中排名第 {target_rank}。",
        "- 评级解释：本次评分已移除目标产品硬编码满分，并对高频功能降权；目标产品的排名来自同一评分函数，不代表收益率领先。",
        "- 精算定位：偏“长期保证递增身故/全残责任 + 非保证红利交清增额 + 家庭传承治理”的分红型终身寿险；保证收益和早期流动性不是优势。",
        "- 关键修正：保单贷款、终身保障、红利增额不能再被视为独特点；目标产品的可讲优势是组合完整度和材料透明度，且同公司相似产品会削弱独占性。",
        "",
        "## 目标产品优势是否成立",
        "",
        "| 原声称优势 | 样本频率/证据 | 是否成立 | 修正表述 |",
        "|---|---|---|---|",
        f"| 终身保障 | {target_audit.get('终身保障', {}).get('peer_count', 0)}/21 | 否 | 样本标配，只能作为准入条件。 |",
        f"| 红利用于增额 | {target_audit.get('红利用于增额', {}).get('peer_count', 0)}/21 | 否 | 分红型终身寿险常见机制，需比较红利方式和演示结果。 |",
        f"| 可保单贷款 | {target_audit.get('可保单贷款', {}).get('peer_count', 0)}/21 | 否 | 样本标配，不构成差异化。 |",
        f"| 第二投保人设计 | {target_audit.get('第二投保人设计', {}).get('peer_count', 0)}/21 | 部分成立 | 相对少见，但汇丰同系列和友邦部分产品也有。 |",
        f"| 双意外额外给付 | 航空{target_audit.get('含航空意外额外身故给付', {}).get('peer_count', 0)}/21，重大自然灾害{target_audit.get('含重大自然灾害意外身故给付', {}).get('peer_count', 0)}/21 | 成立 | 属相对稀缺的保障杠杆增强点。 |",
        "| 保证收益优势 | 105岁保证退保IRR约1.47% | 否 | 保证收益不强，收益依赖非保证红利。 |",
        "",
        "## 目标产品公开演示表IRR",
        "",
        "| 保单年度 | 年龄 | 保证身故/全残给付 | 非保证情景2身故/全残给付 | 保证退保给付 | 非保证情景2退保给付 | 保证身故IRR | 情景2身故IRR | 保证退保IRR | 情景2退保IRR |",
        "|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in target["target_irr_analysis"]:
        lines.append(
            f"| {row['policy_year']} | {row['age']} | {money(row['death_guaranteed'])} | {money(row['death_scenario2'])} | "
            f"{money(row['surrender_guaranteed'])} | {money(row['surrender_scenario2'])} | "
            f"{pct(row['death_guaranteed_irr'])} | {pct(row['death_scenario2_irr'])} | "
            f"{pct(row['surrender_guaranteed_irr'])} | {pct(row['surrender_scenario2_irr'])} |"
        )

    lines.extend(
        [
            "",
            "## 目标产品早期现金价值回收率",
            "",
            "| 保单年度 | 年龄 | 累计保费 | 保证退保给付 | 保证退保给付/累计保费 |",
            "|---:|---:|---:|---:|---:|",
        ]
    )
    for item in target["numeric_comparison"]["cash_value_checkpoints"]:
        lines.append(
            f"| {item['policy_year']} | {item['age']} | {money(item['cumulative_premium'])} | "
            f"{money(item['guaranteed_surrender'])} | {pct(item['guaranteed_surrender_to_premium'])} |"
        )

    lines.extend(
        [
            "",
            "## 所有产品综合评级",
            "",
            "| 排名 | 公司 | 产品 | 评级 | 分数 | 保证利益强度 | 非保证红利机制 | 流动性权益 | 传承治理 | 身故/全残杠杆 | 材料透明度 | 数值收益 |",
            "|---:|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for index, product in enumerate(ranked, 1):
        dims = product["rating_dimensions"]
        lines.append(
            f"| {index} | {product['company']} | {product['product_name']} | {product['rating_grade']} | {product['rating_score']} | "
            f"{score_text(dims['保证利益强度'])} | {score_text(dims['非保证红利机制'])} | {score_text(dims['流动性权益'])} | "
            f"{score_text(dims['传承治理'])} | {score_text(dims['身故/全残杠杆'])} | {score_text(dims['材料透明度'])} | {score_text(dims['数值收益'])} |"
        )

    lines.extend(
        [
            "",
            "## 数值收益可比性限制",
            "",
            "- 目标产品已从公开说明书演示表计算同口径IRR。",
            "- 其他20款产品尚未解析出统一字段结构的现金价值/利益演示表，因此不参与收益排名；后续需要针对各公司说明书表格单独扩展解析器。",
            "",
            "## 目标产品优劣势",
            "",
            "更稳妥的优势：",
            "- 第二投保人、交清增额、双意外额外给付、全残责任和材料透明度形成较完整的家庭治理/传承配置。",
            "- 公开说明书、费率表、现金价值全表可追溯，便于审计保证现金价值和演示利益。",
            "- 重大自然灾害意外额外给付在样本中较少见，可作为保障杠杆增强点。",
            "",
            "劣势：",
            "- 保证退保给付IRR从第20年至105岁约0.75%-1.47%，若只看保证现金价值，不具备高收益属性。",
            "- 非保证情景2长期退保/身故IRR约2.32%-2.99%，但红利不保证，不能承诺为实际收益。",
            "- 第1年保证退保给付9,051元，显著低于首年保费50,000元；第6年保证退保给付204,678元，也低于累计保费300,000元，早期流动性成本高。",
            "- 基本保险金额不支持增加，后续加保弹性弱；减少基本保险金额会视为部分退保并影响后续利益。",
            "- 1.75%保证递增低于部分市场2.0%有效保额递增产品，若客户只比较保证增长率，目标产品不占优势。",
            "- 与汇丰同系列高端版本相似度高，不能把组合能力包装成目标产品独占卖点。",
        ]
    )

    (ACTUARIAL_REPORT_DIR / f"zhenyingshidai_2025_whole_life_actuarial_rating_{DATE_SLUG}.md").write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8",
    )

    payload = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "target_product": TARGET_NAME,
        "target_rank": target_rank,
        "products": [
            {
                "company": item["company"],
                "product_name": item["product_name"],
                "rating_grade": item["rating_grade"],
                "rating_score": item["rating_score"],
                "rating_dimensions": item["rating_dimensions"],
                "keyword_hits": item["keyword_hits"],
                "rare_clauses": item["rare_clauses"],
                "common_features": item.get("common_features", []),
                "relative_features": item.get("relative_features", []),
                "feature_audit": item.get("feature_audit", []),
                "numeric_comparison": item.get("numeric_comparison", {}),
                "target_irr_analysis": item.get("target_irr_analysis", []),
            }
            for item in ranked
        ],
    }
    (ACTUARIAL_REPORT_DIR / f"zhenyingshidai_2025_whole_life_actuarial_rating_{DATE_SLUG}.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )


def write_persona_report(products: list[dict[str, Any]]) -> None:
    ACTUARIAL_REPORT_DIR.mkdir(parents=True, exist_ok=True)
    target = next(item for item in products if item["is_target"])
    lines = [
        f"# {TARGET_DISPLAY_NAME}目标客群画像与规划用途",
        "",
        f"- 生成时间：{datetime.now().isoformat(timespec='seconds')}",
        f"- 目标产品评级：{target['rating_grade']}，综合分 {target['rating_score']} / 5。",
        "- 核心判断：适合长期持有、重视家庭治理和稳健传承的人群；不适合短期资金周转、高收益投资替代或尚未完成基础保障的家庭。",
        "",
        "## 画像1：中高收入新家庭的子女教育与成长金储备",
        "",
        "- 客户特征：30-45岁父母，收入稳定，已配置医疗、重疾、定寿等基础保障，希望为子女建立一个不易被挪用的长期账户。",
        "- 为什么匹配：目标产品终身有效，现金价值和保单贷款提供中长期备用资金来源；红利购买交清增额可把非保证利益继续留在保单内，避免分红现金化后被日常消费。",
        "- 如何服务教育规划：适合作为孩子大学、留学后备金或成年启动金的长期补充，而不是5年内刚性学费账户。若教育支出时间很近，应搭配存款、货币基金、短债等高流动性资产。",
        "",
        "## 画像2：40-55岁稳健养老补充客户",
        "",
        "- 客户特征：事业和家庭财务进入稳定期，已具备基础养老金或企业年金，希望增加一类不随市场净值波动的终身资产。",
        "- 为什么匹配：保证利益按有效保险金额递增，退保/身故给付在长期逐步提升；保单贷款可在退休阶段提供临时流动性，不必立即解除合同。",
        "- 如何服务退休养老：它不是年金险，不负责按期发放养老金；更适合作为退休资产负债表里的长期储备和医疗、照护、家庭应急资金池。",
        "",
        "## 画像3：保守型财富管理客户",
        "",
        "- 客户特征：风险偏好较低，不能承受权益市场大幅波动，愿意用长持有期换取合同化、规则化和低波动的资产配置。",
        "- 为什么匹配：保证部分、非保证分红、现金价值、保单贷款都能在合同中追溯；费率表和现金价值全表公开，便于做保费效率和退保损失测算。",
        "- 如何服务财富管理：可作为家庭稳健资产底仓的一部分，与现金管理、债券基金、权益资产、保障型寿险分工配置；不应替代高收益投资组合。",
        "",
        "## 画像4：有财富传承和控制权衔接需求的家庭",
        "",
        "- 客户特征：有未成年子女、二代接班、再婚家庭或复杂家庭资产安排，希望通过保险合同明确受益安排和投保人权利衔接。",
        "- 为什么匹配：第二投保人安排可以降低投保人身故后保单控制权空档；身故受益人设计、终身责任和交清增额机制有利于把资产按合同规则传递给指定对象。",
        "- 如何服务财富传承：它更适合“合同化传承、长期资金保全和受益安排”，不是最高杠杆寿险。若目标是用较低保费放大身故保障，应另配定期寿险或高杠杆终身寿险。",
        "",
        "## 四类规划目标对应关系",
        "",
        "| 规划目标 | 可发挥的作用 | 关键限制 |",
        "|---|---|---|",
        "| 子女教育 | 提供中长期现金价值储备和保单贷款备用流动性，红利交清增额帮助账户长期留存 | 不适合5年内刚性学费，早期退保损失高 |",
        "| 退休养老 | 形成退休后可动用的长期寿险资产池，身故/全残责任持续至终身 | 不提供固定年金现金流，需与养老年金或其他现金流资产搭配 |",
        "| 财富管理 | 低波动、合同化、公开现金价值，适合稳健资产底仓 | 保证IRR不高，非保证分红不能承诺 |",
        "| 财富传承 | 第二投保人、受益人、终身保障和交清增额增强传承治理 | 身故杠杆不是最高，复杂家族安排仍需法律和税务工具配合 |",
        "",
        "## 不适合人群",
        "",
        "- 未来5年内有购房、创业、留学等大额不确定支出的人群。",
        "- 追求短期高收益或随时赎回的投资型客户。",
        "- 尚未完成医疗险、重疾险、定期寿险等基础保障配置的家庭。",
        "- 主要目标是最高身故杠杆或最低保费成本的客户。",
    ]
    (ACTUARIAL_REPORT_DIR / f"zhenyingshidai_2025_customer_personas_{DATE_SLUG}.md").write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    discovery = build_discovery()
    write_discovery_outputs(discovery)
    products = analyze_products(discovery)
    write_analysis_json(products)
    write_clause_report(products)
    write_actuarial_report(products)
    write_persona_report(products)
    print(
        json.dumps(
            {
                "selected_peers": len(discovery["selected_peers"]),
                "products_including_target": len(products),
                "missing_selected": discovery["missing_selected"],
                "discovery_report": str(REPORT_DIR / f"zhenyingshidai_full_peer_discovery_{DATE_SLUG}.md"),
                "clause_report": str(REPORT_DIR / f"zhenyingshidai_clause_rare_features_{DATE_SLUG}.md"),
                "actuarial_report": str(ACTUARIAL_REPORT_DIR / f"zhenyingshidai_2025_whole_life_actuarial_rating_{DATE_SLUG}.md"),
                "persona_report": str(ACTUARIAL_REPORT_DIR / f"zhenyingshidai_2025_customer_personas_{DATE_SLUG}.md"),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
