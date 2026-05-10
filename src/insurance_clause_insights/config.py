from __future__ import annotations

from pathlib import Path

UPSTREAM_REPO_URL = "https://github.com/pamelacai310-sketch/insurance-crawler-push.git"
DEFAULT_UPSTREAM_DIR = Path(".cache/insurance-crawler-push")
DEFAULT_OUTPUT_ROOT = Path("outputs")

CATEGORY_RULES: list[tuple[str, tuple[str, ...]]] = [
    ("增额终身寿险", ("增额终身寿险", "增额.*终身", "终身.*增额")),
    ("终身寿险", ("终身寿险", "终身生命保险")),
    ("定期寿险", ("定期寿险",)),
    ("两全保险", ("两全保险", "生死两全")),
    ("年金保险", ("养老年金", "教育年金", "年金保险", "年金")),
    ("重疾险", ("重大疾病保险", "重大疾病", "重疾保险", "重疾")),
    ("医疗险", ("医疗保险", "百万医疗", "住院医疗", "高端医疗", "门急诊")),
    ("防癌险", ("防癌", "恶性肿瘤保险")),
    ("意外险", ("意外伤害保险", "意外险")),
    ("护理险", ("护理保险", "长期护理")),
    ("万能险", ("万能型", "万能保险")),
]

FIELD_PATTERNS: dict[str, tuple[str, ...]] = {
    "product_name": ("产品名称", "保险产品名称"),
    "insurance_type": ("险种类型", "保险类型"),
    "insurance_period": ("保险期间", "保障期限"),
    "payment_period": ("缴费期间", "缴费年期", "交费期"),
    "waiting_period": ("等待期", "观察期"),
    "sum_insured": ("保险金额", "基本保额"),
    "effective_date": ("生效日期", "起保日期"),
    "company_name": ("保险公司", "承保公司"),
}

FIELD_DISPLAY_NAMES: dict[str, str] = {
    "product_name": "产品名称",
    "insurance_type": "保险类型",
    "insurance_period": "保险期间",
    "payment_period": "缴费期间",
    "waiting_period": "等待期",
    "sum_insured": "保险金额",
    "effective_date": "生效日期",
    "company_name": "保险公司",
}

FEATURE_HINTS: tuple[str, ...] = (
    "等待期",
    "观察期",
    "犹豫期",
    "保险期间",
    "保障期限",
    "缴费期间",
    "缴费年期",
    "交费期",
    "保证续保",
    "身故保险金",
    "全残保险金",
    "生存保险金",
    "满期保险金",
    "祝寿金",
    "年金",
    "重大疾病",
    "重疾",
    "轻症",
    "中症",
    "医疗",
    "住院",
    "门急诊",
    "质子重离子",
    "外购药",
    "豁免",
    "责任免除",
    "免责",
    "减保",
    "现金价值",
    "保单贷款",
    "投保年龄",
)

FEATURE_LABEL_RULES: list[tuple[str, tuple[str, ...]]] = [
    ("等待期", ("等待期", "观察期")),
    ("保障期限", ("保险期间", "保障期限")),
    ("缴费期间", ("缴费期间", "缴费年期", "交费期")),
    ("保证续保", ("保证续保",)),
    ("年金责任", ("年金", "生存保险金", "祝寿金", "养老年金")),
    ("身故/全残责任", ("身故保险金", "全残保险金")),
    ("重疾责任", ("重大疾病", "重疾", "中症", "轻症")),
    ("医疗责任", ("医疗", "住院", "门急诊", "质子重离子", "外购药")),
    ("豁免责任", ("豁免",)),
    ("现金价值/减保", ("现金价值", "减保", "保单贷款")),
    ("免责条款", ("责任免除", "免责")),
    ("投保规则", ("投保年龄", "生效日期")),
]

KEY_FACT_FIELDS: tuple[str, ...] = (
    "insurance_type",
    "insurance_period",
    "payment_period",
    "waiting_period",
    "sum_insured",
)
