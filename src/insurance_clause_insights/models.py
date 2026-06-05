from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class UniqueFeature:
    label: str
    snippet: str
    score: float


@dataclass
class FeatureAudit:
    label: str
    classification: str
    sample_count: int
    sample_total: int
    sample_frequency: float
    uniqueness_score: float
    target_only: bool = False
    shared_by_same_company: bool = False


@dataclass
class ContractRecord:
    company: str
    product_name: str
    category: str
    pdf_path: str
    source_url: str
    key_facts: dict[str, str] = field(default_factory=dict)
    pages: int = 0
    full_text: str = ""
    feature_candidates: list[str] = field(default_factory=list)
    # 精算参数（可选）
    entry_age: int | None = None
    gender: str | None = None
    annual_premium: float | None = None
    dividend_type: str | None = None
    guaranteed_rate: float | None = None
    feature_audit: list[FeatureAudit] = field(default_factory=list)
    common_features: list[str] = field(default_factory=list)
    relative_features: list[str] = field(default_factory=list)
    rare_features: list[str] = field(default_factory=list)


@dataclass
class ComparedProduct:
    company: str
    product_name: str
    category: str
    pdf_path: str
    source_url: str
    key_facts: dict[str, str] = field(default_factory=dict)
    unique_features: list[UniqueFeature] = field(default_factory=list)
    # 精算参数（可选）
    entry_age: int | None = None
    gender: str | None = None
    annual_premium: float | None = None
    sum_assured: float | None = None
    payment_period: int | None = None
    insurance_period: str | None = None
    dividend_type: str | None = None
    guaranteed_rate: float | None = None
    feature_audit: list[FeatureAudit] = field(default_factory=list)
    common_features: list[str] = field(default_factory=list)
    relative_features: list[str] = field(default_factory=list)
    rare_features: list[str] = field(default_factory=list)


@dataclass
class ComparisonGroup:
    category: str
    product_count: int
    products: list[ComparedProduct] = field(default_factory=list)
