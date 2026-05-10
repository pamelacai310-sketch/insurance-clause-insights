from __future__ import annotations

import json
import logging
import re
from pathlib import Path

import pdfplumber

from .config import (
    CATEGORY_RULES,
    FEATURE_HINTS,
    FEATURE_LABEL_RULES,
    FIELD_DISPLAY_NAMES,
    FIELD_PATTERNS,
    KEY_FACT_FIELDS,
)
from .models import ContractRecord

logger = logging.getLogger(__name__)


def normalize_text(text: str) -> str:
    text = text.replace("\u3000", " ")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def extract_age(text: str) -> int | None:
    """从文本中提取年龄

    Examples:
        >>> extract_age("40岁")
        40
        >>> extract_age("被保险人年龄：30周岁")
        30
    """
    match = re.search(r"(\d+)\s*[岁周岁]", text)
    if match:
        try:
            return int(match.group(1))
        except (ValueError, IndexError):
            pass
    return None


def extract_premium(text: str) -> float | None:
    """从文本中提取保费金额

    Examples:
        >>> extract_premium("年交保费10,000元")
        10000.0
        >>> extract_premium("首年保费1万元")
        10000.0
    """
    match = re.search(r"([\d,]+(?:\.\d+)?)\s*(万)?元", text)
    if match:
        try:
            value = float(match.group(1).replace(",", ""))
            if match.group(2) == "万":
                value *= 10000
            return value
        except (ValueError, IndexError):
            pass
    return None


def extract_rate(text: str) -> float | None:
    """从文本中提取利率（百分比形式）

    Examples:
        >>> extract_rate("保证利率3.5%")
        0.035
        >>> extract_rate("最低保证利率：3.0 percent")
        0.03
    """
    match = re.search(r"(\d+(?:\.\d+)?)\s*[%％]", text)
    if match:
        try:
            return float(match.group(1)) / 100
        except (ValueError, IndexError):
            pass
    return None


def normalize_gender(text: str) -> str | None:
    """标准化性别为 M/F

    Examples:
        >>> normalize_gender("男性")
        'M'
        >>> normalize_gender("女")
        'F'
    """
    text = text.lower()
    if "男" in text or "male" in text:
        return "M"
    elif "女" in text or "female" in text:
        return "F"
    return None


def is_contract_record(record: dict) -> bool:
    bag = " ".join(
        str(record.get(key, ""))
        for key in ("category", "link_text", "url")
    ).lower()
    return any(keyword in bag for keyword in ("条款", "保险合同", "合同文本", "policy", "terms", "clause"))


def extract_text_from_pdf(pdf_path: Path) -> tuple[str, int]:
    full_text: list[str] = []
    pages = 0
    with pdfplumber.open(pdf_path) as pdf:
        pages = len(pdf.pages)
        for page in pdf.pages:
            text = page.extract_text() or ""
            if text:
                full_text.append(text)
    return "\n".join(full_text), pages


def extract_fields(text: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    for field, aliases in FIELD_PATTERNS.items():
        value = ""
        for alias in aliases:
            pattern = rf"(?:{alias})[：:\s]+([^\n]{{2,60}})"
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                raw_value = normalize_text(match.group(1))

                # 对特定字段使用专门的数值提取器
                if field == "entry_age":
                    age = extract_age(raw_value)
                    if age is not None:
                        value = str(age)
                elif field == "annual_premium":
                    premium = extract_premium(raw_value)
                    if premium is not None:
                        value = str(premium)
                elif field == "guaranteed_rate":
                    rate = extract_rate(raw_value)
                    if rate is not None:
                        value = str(rate)
                elif field == "gender":
                    gender = normalize_gender(raw_value)
                    if gender is not None:
                        value = gender
                else:
                    value = raw_value

                break
        fields[field] = value
    return fields


def infer_category(product_name: str, insurance_type: str, text: str) -> str:
    bag = " ".join([product_name, insurance_type, text[:3000]])
    bag = normalize_text(bag)
    for category, patterns in CATEGORY_RULES:
        if any(re.search(pattern, bag, re.IGNORECASE) for pattern in patterns):
            return category
    return "未分类"


def _extract_clause_blocks(text: str) -> list[str]:
    matches = re.findall(
        r"(第[一二三四五六七八九十百零\d]+条.*?)(?=第[一二三四五六七八九十百零\d]+条|$)",
        text,
        flags=re.S,
    )
    blocks: list[str] = []
    for block in matches[:50]:
        cleaned = normalize_text(block)
        if 10 <= len(cleaned) <= 220:
            blocks.append(cleaned)
        elif len(cleaned) > 220:
            blocks.append(cleaned[:220])
    return blocks


def _extract_feature_sentences(text: str) -> list[str]:
    pieces = re.split(r"[。；;\n\r]+", text)
    candidates: list[str] = []
    for piece in pieces:
        cleaned = normalize_text(piece)
        if not 10 <= len(cleaned) <= 140:
            continue
        if any(hint in cleaned for hint in FEATURE_HINTS) or re.search(r"\d", cleaned):
            candidates.append(cleaned)
    return candidates


def dedupe_preserve_order(items: list[str]) -> list[str]:
    seen: set[str] = set()
    unique_items: list[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            unique_items.append(item)
    return unique_items


def build_feature_candidates(fields: dict[str, str], text: str) -> list[str]:
    candidates: list[str] = []
    for field in KEY_FACT_FIELDS:
        value = fields.get(field, "")
        if value:
            candidates.append(f"{FIELD_DISPLAY_NAMES.get(field, field)}: {value}")
    candidates.extend(_extract_clause_blocks(text))
    candidates.extend(_extract_feature_sentences(text))
    return dedupe_preserve_order(candidates)[:40]


def label_feature(snippet: str) -> str:
    for label, keywords in FEATURE_LABEL_RULES:
        if any(keyword in snippet for keyword in keywords):
            return label
    if ":" in snippet:
        prefix = snippet.split(":", 1)[0].strip()
        return prefix[:18] or "特色条款"
    return snippet[:18] or "特色条款"


def load_contract_records(crawl_json_path: Path) -> tuple[list[ContractRecord], dict[str, int]]:
    records = json.loads(crawl_json_path.read_text(encoding="utf-8"))
    contracts: list[ContractRecord] = []
    category_counts: dict[str, int] = {}

    for record in records:
        if not is_contract_record(record):
            continue

        pdf_path = Path(str(record.get("path", "")))
        if not pdf_path.exists():
            logger.warning("跳过缺失 PDF: %s", pdf_path)
            continue

        try:
            text, pages = extract_text_from_pdf(pdf_path)
        except Exception as exc:  # pragma: no cover - depends on PDFs
            logger.warning("解析 PDF 失败 %s: %s", pdf_path, exc)
            continue

        if not normalize_text(text):
            logger.warning("跳过空文本 PDF: %s", pdf_path)
            continue

        upstream_info = record.get("pdf_info", {}) or {}
        fields = extract_fields(text)
        for field_name in KEY_FACT_FIELDS:
            if not fields.get(field_name):
                value = normalize_text(str(upstream_info.get(field_name, "")))
                if value:
                    fields[field_name] = value

        product_name = normalize_text(
            str(upstream_info.get("product_name", "")) or str(record.get("product", "未知产品"))
        )
        category = infer_category(product_name, fields.get("insurance_type", ""), text)
        category_counts[category] = category_counts.get(category, 0) + 1

        contracts.append(
            ContractRecord(
                company=normalize_text(str(record.get("company", ""))),
                product_name=product_name,
                category=category,
                pdf_path=str(pdf_path),
                source_url=normalize_text(str(record.get("url", ""))),
                key_facts={field: fields.get(field, "") for field in KEY_FACT_FIELDS if fields.get(field, "")},
                pages=pages,
                full_text=text,
                feature_candidates=build_feature_candidates(fields, text),
                # 精算参数
                entry_age=int(fields["entry_age"]) if fields.get("entry_age") else None,
                gender=fields.get("gender"),
                annual_premium=float(fields["annual_premium"]) if fields.get("annual_premium") else None,
                dividend_type=fields.get("dividend_type"),
                guaranteed_rate=float(fields["guaranteed_rate"]) if fields.get("guaranteed_rate") else None,
            )
        )

    return contracts, category_counts
