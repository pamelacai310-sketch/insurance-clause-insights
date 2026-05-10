from __future__ import annotations

import math
import re
from collections import defaultdict
from typing import Optional

from .config import FEATURE_HINTS
from .models import ComparedProduct, ComparisonGroup, ContractRecord, UniqueFeature
from .parsing import label_feature, extract_premium


def _extract_sum_assured(key_facts: dict[str, str]) -> float | None:
    """从key_facts中提取保险金额"""
    sum_assured_text = key_facts.get("sum_insured", "")
    if sum_assured_text:
        return extract_premium(sum_assured_text)
    return None


def _extract_payment_period(key_facts: dict[str, str]) -> int | None:
    """从key_facts中提取缴费期间年数"""
    payment_period_text = key_facts.get("payment_period", "")
    if payment_period_text:
        match = re.search(r"(\d+)\s*年", payment_period_text)
        if match:
            return int(match.group(1))
    return None


def _char_ngrams(text: str) -> set[str]:
    compact = re.sub(r"\s+", "", text)
    grams: set[str] = set()
    for size in (2, 3):
        if len(compact) < size:
            continue
        grams.update(compact[idx : idx + size] for idx in range(len(compact) - size + 1))
    return grams


def _jaccard(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0
    union = left | right
    if not union:
        return 0.0
    return len(left & right) / len(union)


def _keyword_bonus(snippet: str) -> float:
    hits = sum(1 for hint in FEATURE_HINTS if hint in snippet)
    digit_bonus = 0.12 if re.search(r"\d", snippet) else 0.0
    keyword_bonus = min(0.28, hits * 0.04)
    return keyword_bonus + digit_bonus


def _uniqueness_score(snippet: str, peer_snippets: list[str]) -> float:
    own_grams = _char_ngrams(snippet)
    max_similarity = 0.0
    for peer in peer_snippets:
        similarity = _jaccard(own_grams, _char_ngrams(peer))
        if similarity > max_similarity:
            max_similarity = similarity
    rarity = 1.0 - max_similarity
    length_factor = min(1.0, math.log(max(len(snippet), 10), 10))
    return round((rarity * 0.75 + _keyword_bonus(snippet)) * length_factor, 4)


def select_comparison_groups(
    contracts: list[ContractRecord],
    min_products: int,
    preferred_category: Optional[str] = None,
) -> tuple[dict[str, list[ContractRecord]], dict[str, int]]:
    grouped: dict[str, list[ContractRecord]] = defaultdict(list)
    for contract in contracts:
        grouped[contract.category].append(contract)

    counts = {category: len(items) for category, items in grouped.items()}
    if preferred_category:
        selected = grouped.get(preferred_category, [])
        if len(selected) < min_products:
            available = ", ".join(f"{name}:{count}" for name, count in sorted(counts.items(), key=lambda item: (-item[1], item[0])))
            raise ValueError(
                f"类别“{preferred_category}”仅有 {len(selected)} 份条款，未达到 {min_products} 份。当前类别数量：{available}"
            )
        return {preferred_category: selected}, counts

    eligible = {category: items for category, items in grouped.items() if len(items) >= min_products}
    if not eligible:
        available = ", ".join(f"{name}:{count}" for name, count in sorted(counts.items(), key=lambda item: (-item[1], item[0])))
        raise ValueError(f"没有类别达到至少 {min_products} 份条款。当前类别数量：{available}")

    return eligible, counts


def _pick_unique_features(contract: ContractRecord, peers: list[ContractRecord], top_n: int) -> list[UniqueFeature]:
    peer_snippets = [
        snippet
        for peer in peers
        if peer.product_name != contract.product_name or peer.company != contract.company
        for snippet in peer.feature_candidates
    ]

    scored: list[tuple[float, str]] = []
    for snippet in contract.feature_candidates:
        score = _uniqueness_score(snippet, peer_snippets)
        scored.append((score, snippet))

    chosen: list[UniqueFeature] = []
    chosen_grams: list[set[str]] = []
    for score, snippet in sorted(scored, key=lambda item: item[0], reverse=True):
        grams = _char_ngrams(snippet)
        if any(_jaccard(grams, existing) >= 0.72 for existing in chosen_grams):
            continue
        chosen.append(
            UniqueFeature(
                label=label_feature(snippet),
                snippet=snippet,
                score=score,
            )
        )
        chosen_grams.append(grams)
        if len(chosen) >= top_n:
            break

    return chosen


def compare_contracts(
    contracts: list[ContractRecord],
    min_products: int = 20,
    preferred_category: Optional[str] = None,
    top_n: int = 3,
) -> tuple[list[ComparisonGroup], dict[str, int]]:
    eligible_groups, counts = select_comparison_groups(
        contracts=contracts,
        min_products=min_products,
        preferred_category=preferred_category,
    )

    results: list[ComparisonGroup] = []
    for category, items in sorted(eligible_groups.items(), key=lambda item: (-len(item[1]), item[0])):
        compared_products: list[ComparedProduct] = []
        for contract in sorted(items, key=lambda item: (item.company, item.product_name)):
            compared_products.append(
                ComparedProduct(
                    company=contract.company,
                    product_name=contract.product_name,
                    category=contract.category,
                    pdf_path=contract.pdf_path,
                    source_url=contract.source_url,
                    key_facts=contract.key_facts,
                    unique_features=_pick_unique_features(contract, items, top_n=top_n),
                    # 精算参数
                    entry_age=contract.entry_age,
                    gender=contract.gender,
                    annual_premium=contract.annual_premium,
                    sum_assured=_extract_sum_assured(contract.key_facts),
                    payment_period=_extract_payment_period(contract.key_facts),
                    insurance_period=contract.key_facts.get("insurance_period"),
                    dividend_type=contract.dividend_type,
                    guaranteed_rate=contract.guaranteed_rate,
                )
            )

        results.append(
            ComparisonGroup(
                category=category,
                product_count=len(items),
                products=compared_products,
            )
        )

    return results, counts
