from insurance_clause_insights.analysis import build_feature_frequency_audit, compare_contracts
from insurance_clause_insights.models import ContractRecord
from insurance_clause_insights.parsing import infer_category


def build_contract(index: int) -> ContractRecord:
    return ContractRecord(
        company=f"公司{index % 5}",
        product_name=f"样例年金保险{index}",
        category="年金保险",
        pdf_path=f"/tmp/product_{index}.pdf",
        source_url=f"https://example.com/{index}",
        key_facts={
            "insurance_type": "年金保险",
            "insurance_period": "终身",
            "payment_period": "20年",
            "waiting_period": "90天",
        },
        full_text="",
        feature_candidates=[
            "insurance_period: 终身",
            "payment_period: 20年",
            f"第十条 祝寿金责任 产品{index}在第{60 + index}个保单年度开始领取祝寿金",
            "被保险人身故时给付身故保险金",
        ],
    )


def test_infer_category_prefers_annuity() -> None:
    assert infer_category("某某养老年金保险", "", "本合同为养老年金保险") == "年金保险"


def test_compare_contracts_extracts_unique_features() -> None:
    contracts = [build_contract(index) for index in range(21)]
    groups, counts = compare_contracts(contracts, min_products=20, preferred_category="年金保险", top_n=2)

    assert counts["年金保险"] == 21
    assert len(groups) == 1
    assert groups[0].product_count == 21
    first_product = groups[0].products[0]
    assert len(first_product.unique_features) == 2
    assert "祝寿金责任" in first_product.unique_features[0].snippet
    assert "其他" not in first_product.rare_features


def test_feature_frequency_audit_marks_only_low_frequency_as_true_rare() -> None:
    contracts = [build_contract(index) for index in range(21)]
    for contract in contracts:
        contract.feature_candidates.append("本合同支持保单贷款")
    contracts[0].feature_candidates.append("本合同含重大自然灾害意外额外给付")

    audits = build_feature_frequency_audit(
        contracts,
        target_company=contracts[0].company,
        target_product_name=contracts[0].product_name,
    )
    target_audit = {item.label: item for item in audits[(contracts[0].company, contracts[0].product_name)]}

    assert target_audit["保单贷款"].classification == "通用功能"
    assert target_audit["保单贷款"].sample_count == 21
    assert target_audit["意外额外给付"].classification == "真罕见条款"
    assert target_audit["意外额外给付"].sample_count == 1
