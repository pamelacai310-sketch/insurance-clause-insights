#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path("/Users/caijiawen/Documents/New project/insurance-clause-insights")
CRAWLER_ROOT = Path("/Users/caijiawen/Documents/New project/insurance-crawler-push")
DATE_SLUG = "20260708"
DEFAULT_MATERIALS = (
    CRAWLER_ROOT
    / "output"
    / f"enterprise_group_products_{DATE_SLUG}"
    / f"enterprise_group_product_materials_{DATE_SLUG}.json"
)
DEFAULT_REPORT = ROOT / "reports" / f"enterprise_group_product_client_analysis_{DATE_SLUG}.md"
DEFAULT_JSON = ROOT / "outputs" / f"enterprise_group_product_client_analysis_{DATE_SLUG}.json"


ANALYSIS_PROFILES: dict[str, dict[str, Any]] = {
    "睿智环球": {
        "positioning": "高端全球团体医疗，适合跨境雇员、外籍员工、核心管理层及其家属保障。",
        "unique_advantages": [
            "保障区域可覆盖全球、全球除美国或亚洲，能支持跨境派驻、海外差旅和高管国际就医安排。",
            "可覆盖雇员家属，适合企业把高端医疗福利从单个员工延伸到家庭责任，增强核心人才黏性。",
            "条款包含住院、日间治疗、门诊、免赔额、自付比例、既往症和续保年龄等关键医疗风控要素，企业可据此做分层福利设计。",
            "相较普通补充医疗，该产品更像国际医疗福利平台，适合解决境内外医疗资源差异和高额医疗不确定性。",
        ],
        "weaknesses": [
            "公开条款显示本保单不会自动续保，企业不能把续年保障视为确定长期承诺。",
            "既往症、等待期、免赔额、自付比例、保障区域和高价医疗机构限制会直接影响员工实际体验。",
            "高端全球医疗成本高，若企业全员配置可能造成福利预算失控，更适合分层配置。",
            "当前 AXA 接口目录未返回 IEG，只能以官网静态 PDF 作为核验材料；正式采购仍需核验销售版本、费率和保障明细表。",
        ],
        "problems_solved": [
            "跨境人才保障",
            "外籍员工本地化福利",
            "高管留任",
            "重大医疗费用波动管理",
            "海外就医和家属保障",
        ],
        "best_fit": "外资企业、跨境业务公司、拥有外籍员工或长期派驻人员的企业，以及希望给核心层做高端医疗分层福利的企业。",
        "avoid": "预算敏感、只需要基础门急诊报销、无法接受续保不确定性或没有跨境医疗需求的企业。",
        "verification": [
            "保障区域版本、美国责任是否包含及对应保费。",
            "网络医院、直付服务、预授权和昂贵医院自付比例。",
            "既往症承保条件、等待期、年度续保和调费规则。",
            "雇员家属加入条件、年龄上限和离职后责任终止规则。",
        ],
    },
    "智选企航": {
        "positioning": "面向企业员工及家属的团体综合医疗，适合中小企业或成长型企业建立基础到中档补充医疗福利。",
        "unique_advantages": [
            "AXA 当前产品目录明确命中 ZXG，并区分 Plan A、Plan B，说明该计划具备标准化方案销售基础。",
            "条款覆盖住院及日间治疗、门诊、处方药、免赔额、自付比例、等待期和续保年龄等医疗计划常用配置。",
            "主被保险人与配偶、子女可作为附属被保险人的条款安排，有利于企业把福利从员工个人扩展到家庭场景。",
            "相较高端全球医疗，ZXG 更适合做预算可控的团体医疗底盘。",
        ],
        "weaknesses": [
            "公开抓取到的是团体综合医疗条款，Plan A/Plan B 的具体保额、免赔额、赔付比例和费率仍需保险单或方案表确认。",
            "等待期、既往症、保障区域、医院定义和处方药限制会影响员工实际获赔。",
            "若企业员工年龄结构偏高或既往症比例高，续保和报价可能与初始方案差异较大。",
        ],
        "problems_solved": [
            "员工基础医疗福利",
            "雇主福利差异化",
            "门急诊和住院补偿",
            "家属保障",
            "招聘竞争力提升",
        ],
        "best_fit": "希望用标准化团体医疗计划提升员工福利、但预算不足以全员配置高端全球医疗的成长型企业。",
        "avoid": "需要明确全球直付网络、百万级高端医疗责任或长期锁定续保条件的企业。",
        "verification": [
            "Plan A 与 Plan B 的正式保障明细、费率表和免赔/赔付比例。",
            "是否支持员工家属自费加入、企业补贴比例和名单变更规则。",
            "等待期豁免、既往症承保和续保调费条件。",
        ],
    },
    "团体C": {
        "positioning": "团体万能型年金，用于企业年金补充、长期激励、递延福利和核心员工留任。",
        "unique_advantages": [
            "万能账户形态适合企业把福利从当期医疗补偿扩展到长期养老或递延奖金安排。",
            "官网产品中心明确提示多样、灵活、专业，条款包含个人账户、部分领取、退保和保留账户等账户型管理要素。",
            "相较医疗险，年金账户更适合绑定服务年限、长期激励和退休金补充。",
            "产品说明书与条款均已从安联公开信息披露下载，可作为正式方案讨论的基础材料。",
        ],
        "weaknesses": [
            "结算利率超过最低保证利率的部分不确定，不能向员工承诺演示收益或历史结算利率。",
            "部分领取、退保、账户归属和离职处理需要企业制度配套，否则容易引发劳动关系和福利归属争议。",
            "它不是医疗或意外保障，不能替代员工健康福利，只能解决长期资金和激励问题。",
            "税务、会计、薪酬递延合规和员工权益归属需要单独审查。",
        ],
        "problems_solved": [
            "核心员工长期留任",
            "递延奖金",
            "补充养老",
            "福利账户化管理",
            "人才激励预算平滑",
        ],
        "best_fit": "现金流稳定、希望建立中长期留才机制或补充养老计划的成熟企业。",
        "avoid": "短期用工比例高、只想降低医疗赔付波动、或希望承诺固定高收益的企业。",
        "verification": [
            "最低保证利率、现行结算利率披露和费用扣除。",
            "账户归属、离职、退休、身故、全残、部分领取和退保规则。",
            "企业缴费与员工权益的税务、会计和劳动合同安排。",
        ],
    },
    "安康福睿": {
        "positioning": "医疗费用型企业员工福利组合，覆盖意外、意外医疗、住院津贴、团体医疗和重大疾病。",
        "unique_advantages": [
            "组件覆盖从意外伤害到医疗费用、住院津贴和重大疾病，适合做一站式员工健康福利。",
            "官网摘要强调价格优惠、手续简单、多种计划，适合企业按员工层级配置不同福利包。",
            "相比单一意外险，福睿更能覆盖疾病医疗和重疾冲击，减少员工因病支出压力。",
            "组件均在安联公开信息披露中命中条款和产品说明书，材料完整度较高。",
        ],
        "weaknesses": [
            "由多个主附险组成，投保、理赔和员工沟通复杂度高于单一产品。",
            "缺少定期寿险组件，若企业关注疾病身故或家庭责任替代，保障完整度弱于安康全盛。",
            "免赔额、赔付比例、等待期和医院范围仍取决于具体方案，不能只看产品计划名称。",
        ],
        "problems_solved": [
            "员工日常医疗费用补偿",
            "意外事故赔付",
            "重疾慰问金或补偿",
            "企业福利标准化",
            "医疗预算可控",
        ],
        "best_fit": "需要在预算可控前提下补齐医疗和重疾福利的中小企业、服务业企业和办公白领团队。",
        "avoid": "需要高端医疗直付、全球医疗网络或疾病身故保障的企业。",
        "verification": [
            "是否包含门急诊、住院、重疾和津贴的具体保额。",
            "免赔额、赔付比例、等待期、医院范围和既往症条件。",
            "员工增减员、职业变更和续保调费规则。",
        ],
    },
    "安顺和悦企业员工福利保险产品计划2.0版": {
        "positioning": "综合意外型员工福利计划，适合企业建立基础意外、意外医疗和住院津贴保障。",
        "unique_advantages": [
            "组件聚焦意外身故/伤残、意外医疗和意外住院津贴，结构清晰，便于全员普惠配置。",
            "官网摘要强调计划任选、手续简单、保障广泛，适合快速补齐企业基础保障。",
            "相较医疗费用型组合，意外型计划更容易控制保费，适合高流动、高外勤或制造服务场景。",
        ],
        "weaknesses": [
            "保障重心是意外，不能充分覆盖疾病医疗、重大疾病或疾病身故。",
            "意外医疗的免赔额、赔付比例、医院范围和职业类别限制会影响实际赔付。",
            "若企业把它作为唯一员工福利，疾病相关风险缺口明显。",
        ],
        "problems_solved": [
            "员工基础意外保障",
            "外勤和通勤事故风险",
            "工伤之外的补充赔付",
            "低预算普惠福利",
            "快速上线团体保障",
        ],
        "best_fit": "外勤、销售、制造、仓储、物业、餐饮等意外风险较高且预算敏感的企业。",
        "avoid": "希望解决疾病医疗、重疾或高端医疗需求的企业。",
        "verification": [
            "员工职业类别是否在承保范围内。",
            "意外医疗免赔额、赔付比例、是否限社保范围。",
            "住院津贴天数、等待期和责任免除。",
        ],
    },
    "意外保障型": {
        "positioning": "安顺和悦2.0 的意外保障取向映射，适合作为低成本全员意外底座。",
        "unique_advantages": [
            "以意外身故/伤残、意外医疗和住院津贴为核心，适合企业用最低复杂度覆盖员工突发事故。",
            "可作为其他医疗福利、高端医疗或年金激励之外的基础保障层。",
            "对高流动岗位更容易解释和落地，员工感知明确。",
        ],
        "weaknesses": [
            "官网产品中心未单列“意外保障型”，本次按安顺和悦2.0综合意外计划及组件映射，正式采购需确认销售方案名称。",
            "保障边界窄，不覆盖普通疾病医疗和重大疾病。",
            "职业类别、危险活动、酒驾、违法行为等责任免除对外勤岗位影响较大。",
        ],
        "problems_solved": [
            "全员事故底线保障",
            "外勤人员风险补位",
            "低预算福利覆盖",
            "工伤外补充赔付",
        ],
        "best_fit": "需要基础意外底座、但暂不配置完整医疗福利的企业。",
        "avoid": "希望通过一张保单解决疾病医疗、重疾和高端医疗的企业。",
        "verification": [
            "正式方案是否以“意外保障型”销售及对应条款组件。",
            "职业类别、危险工种和高风险活动限制。",
            "意外医疗是否限社保范围及免赔额设置。",
        ],
    },
    "安康全盛": {
        "positioning": "更完整的企业员工福利组合，较福睿额外加入团体定期寿险，覆盖疾病身故/家庭责任场景。",
        "unique_advantages": [
            "组件包含意外、定期寿险、住院津贴、团体医疗和重大疾病，覆盖面比福睿更完整。",
            "定期寿险组件能补充疾病身故风险，适合企业为骨干员工提供家庭责任保障。",
            "主险可单独购买的设计提升组合灵活度，企业可按层级和预算拆分配置。",
            "适合把员工福利从医疗报销升级为健康、意外、身故和重疾的综合保障包。",
        ],
        "weaknesses": [
            "保障越完整，保费和核保复杂度越高；对预算紧张企业未必最优。",
            "多组件组合增加理赔路径、责任边界和员工沟通难度。",
            "若企业只需要门急诊或基础意外，全盛可能配置过重。",
        ],
        "problems_solved": [
            "员工家庭责任风险",
            "疾病身故补偿",
            "医疗和重疾冲击",
            "核心岗位福利升级",
            "企业雇主责任形象",
        ],
        "best_fit": "希望构建完整员工福利体系、员工稳定性较高、对核心人才家庭责任有补偿诉求的企业。",
        "avoid": "短期兼职多、预算极低或只需要简单意外险的企业。",
        "verification": [
            "定期寿险保额、疾病身故等待期和责任免除。",
            "各组件是否全部纳入报价，是否支持分层购买。",
            "名单人数、职业类别、健康告知和续保调费规则。",
        ],
    },
    "安康至臻": {
        "positioning": "高端全球团体医疗，适合高管、外籍员工、跨境业务员工和国际化企业福利。",
        "unique_advantages": [
            "官网摘要明确零现金就医、多方位保障、百万级保额和全球服务网络，定位高端医疗。",
            "公开材料包含条款和产品说明书，能支撑企业评估住院、门诊、预授权、保障区域和直付体验。",
            "与普通补充医疗相比，更能解决高额医疗、国际医院、外籍员工和核心层服务体验问题。",
            "可与基础意外或年金产品搭配，形成高管医疗加长期激励的组合福利。",
        ],
        "weaknesses": [
            "保费通常显著高于普通团体医疗，不适合无差别全员配置。",
            "预授权、网络医院、保障区域、等待期、既往症和免赔额会决定实际体验。",
            "高端医疗不是留才账户，也不能解决员工养老或递延奖金问题。",
        ],
        "problems_solved": [
            "高管医疗体验",
            "外籍员工医疗安排",
            "跨境就医",
            "重大医疗费用上限管理",
            "企业国际化福利形象",
        ],
        "best_fit": "跨国公司、外籍员工比例高的企业、金融科技和专业服务机构、需要为管理层配置高端医疗的企业。",
        "avoid": "员工规模大但预算有限、只需社保补充门急诊或不需要全球网络的企业。",
        "verification": [
            "直付网络、预授权、昂贵医院、美国区域和除外医院规则。",
            "年度限额、免赔额、自付比例、既往症和等待期。",
            "家属加入、离职延续和续保年龄上限。",
        ],
    },
}


def md_escape(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip().replace("|", "｜")


def profile_for(product: dict[str, Any]) -> dict[str, Any]:
    requested_name = str(product.get("requested_name", ""))
    if "意外保障型" in requested_name:
        return ANALYSIS_PROFILES["意外保障型"]
    name = f"{requested_name} {product.get('official_name', '')}"
    for key, profile in ANALYSIS_PROFILES.items():
        if key in name:
            return profile
    raise KeyError(f"未配置分析画像: {product.get('requested_name')}")


def doc_counter(product: dict[str, Any]) -> Counter[str]:
    return Counter(doc.get("category", "资料") for doc in product.get("documents", []))


def doc_count_summary(product: dict[str, Any]) -> str:
    docs = product.get("documents", [])
    downloaded = sum(1 for doc in docs if doc.get("downloaded"))
    categories = "；".join(f"{name}{count}" for name, count in doc_counter(product).items())
    return f"{downloaded}/{len(docs)} 已下载；{categories or '无附件'}"


def combined_text(product: dict[str, Any]) -> str:
    parts = [
        product.get("product_center_summary", ""),
        product.get("product_center_notice", ""),
        " ".join(product.get("components", [])),
    ]
    parts.extend(doc.get("text_excerpt", "") for doc in product.get("documents", []))
    return re.sub(r"\s+", " ", " ".join(parts))


def find_signals(product: dict[str, Any]) -> list[str]:
    text = combined_text(product)
    name = f"{product.get('requested_name', '')} {product.get('official_name', '')}"
    signal_rules = [
        ("全球/跨境医疗", ["全球任何国家", "全球服务网络", "全球除美国", "香港地区", "境外"]),
        ("员工家属可纳入", ["配偶", "子女", "附属被保险人", "家属"]),
        ("住院/日间治疗", ["住院", "日间治疗", "住院补贴"]),
        ("门急诊/处方药", ["门诊", "急诊", "处方药"]),
        ("免赔额/自付比例", ["免赔额", "自付比例", "赔付比例"]),
        ("等待期/续保约束", ["等待期", "续保", "不会自动续保"]),
        ("意外身故/伤残", ["意外身故", "意外伤残", "意外伤害保险"]),
        ("重大疾病", ["重大疾病"]),
        ("定期寿险/疾病身故", ["定期寿险", "疾病身故"]),
        ("万能账户/结算利率", ["万能", "个人账户", "保证利率", "结算利率"]),
        ("部分领取/退保", ["部分领取", "退保", "保留账户"]),
    ]
    signals = []
    for label, keywords in signal_rules:
        if label in {"万能账户/结算利率", "部分领取/退保"} and not any(
            keyword in name for keyword in ("万能", "年金")
        ):
            continue
        if label == "员工家属可纳入" and any(keyword in name for keyword in ("万能", "年金")):
            continue
        if label == "全球/跨境医疗" and not any(keyword in name for keyword in ("环球", "全球", "智选企航")):
            continue
        if any(keyword in text for keyword in keywords):
            signals.append(label)
    return signals


def product_material_rows(products: list[dict[str, Any]]) -> list[str]:
    rows = [
        "| 公司 | 请求产品 | 官网命中名 | 资料完整度 | 关键抓取备注 |",
        "|---|---|---|---|---|",
    ]
    for product in products:
        notes = "；".join(product.get("crawl_notes", [])) or "无"
        rows.append(
            "| {company} | {requested} | {official} | {docs} | {notes} |".format(
                company=md_escape(product.get("company")),
                requested=md_escape(product.get("requested_name")),
                official=md_escape(product.get("official_name")),
                docs=md_escape(doc_count_summary(product)),
                notes=md_escape(notes),
            )
        )
    return rows


def comparison_rows(products: list[dict[str, Any]]) -> list[str]:
    rows = [
        "| 产品 | 企业适配定位 | 最突出的企业价值 | 最主要短板 | 解决的问题 |",
        "|---|---|---|---|---|",
    ]
    for product in products:
        profile = profile_for(product)
        rows.append(
            "| {name} | {positioning} | {advantage} | {weakness} | {problems} |".format(
                name=md_escape(product.get("requested_name")),
                positioning=md_escape(profile["positioning"]),
                advantage=md_escape(profile["unique_advantages"][0]),
                weakness=md_escape(profile["weaknesses"][0]),
                problems=md_escape("、".join(profile["problems_solved"][:4])),
            )
        )
    return rows


def render_product_section(product: dict[str, Any]) -> list[str]:
    profile = profile_for(product)
    signals = find_signals(product)
    lines = [
        f"## {product['company']} - {product['requested_name']}",
        "",
        f"- 官网命中名: {product.get('official_name') or '未命中'}",
        f"- 资料完整度: {doc_count_summary(product)}",
        f"- 公开资料信号: {'、'.join(signals) if signals else '未从公开文本中提取到明确关键词'}",
        f"- 企业适配定位: {profile['positioning']}",
        "",
        "### 独特优势",
    ]
    lines.extend(f"- {item}" for item in profile["unique_advantages"])
    lines.append("")
    lines.append("### 主要短板与避坑")
    lines.extend(f"- {item}" for item in profile["weaknesses"])
    lines.append("")
    lines.append("### 能为企业解决的问题")
    lines.extend(f"- {item}" for item in profile["problems_solved"])
    lines.append("")
    lines.append("### 适合与不适合")
    lines.append(f"- 适合: {profile['best_fit']}")
    lines.append(f"- 不适合: {profile['avoid']}")
    lines.append("")
    lines.append("### 正式投保前必须核验")
    lines.extend(f"- {item}" for item in profile["verification"])
    if product.get("components"):
        lines.append("")
        lines.append("### 官网披露组件")
        lines.extend(f"- {component}" for component in product["components"])
    if product.get("crawl_notes"):
        lines.append("")
        lines.append("### 抓取口径备注")
        lines.extend(f"- {note}" for note in product["crawl_notes"])
    lines.append("")
    return lines


def build_structured_summary(products: list[dict[str, Any]]) -> list[dict[str, Any]]:
    summary = []
    for product in products:
        profile = profile_for(product)
        summary.append(
            {
                "company": product.get("company"),
                "requested_name": product.get("requested_name"),
                "official_name": product.get("official_name"),
                "material_summary": doc_count_summary(product),
                "signals": find_signals(product),
                "positioning": profile["positioning"],
                "unique_advantages": profile["unique_advantages"],
                "weaknesses": profile["weaknesses"],
                "problems_solved": profile["problems_solved"],
                "best_fit": profile["best_fit"],
                "avoid": profile["avoid"],
                "verification": profile["verification"],
            }
        )
    return summary


def build_report(products: list[dict[str, Any]], materials_path: Path) -> str:
    generated_at = datetime.now().isoformat(timespec="seconds")
    lines = [
        "# 企业团险产品资料与企业客户适配分析",
        "",
        f"- 生成时间: {generated_at}",
        f"- 输入资料: `{materials_path}`",
        f"- 产品数量: {len(products)}",
        "- 分析边界: 仅基于保险公司官网产品中心、产品基本信息披露、条款和产品说明书；未把宣传页未披露的保额、费率、免赔额或销售方案假定为事实。",
        "",
        "## 资料抓取概览",
        "",
    ]
    lines.extend(product_material_rows(products))
    lines.extend(
        [
            "",
            "## 企业客户适配总览",
            "",
        ]
    )
    lines.extend(comparison_rows(products))
    lines.extend(
        [
            "",
            "## 横向结论",
            "",
            "- 高端全球医疗类（AXA 睿智环球、安联安康至臻）最适合解决高管、外籍员工、跨境派驻和高额医疗服务体验问题，但预算、续保、既往症、预授权和网络医院是核心避坑点。",
            "- 标准团体医疗类（AXA 智选企航、安联安康福睿）适合企业搭建基础到中档福利底盘，重点核验保额、免赔额、赔付比例、等待期和家属加入规则。",
            "- 意外福利类（安联安顺和悦2.0及意外保障型）适合低成本全员普惠和外勤岗位事故风险补位，但不能替代疾病医疗和重疾保障。",
            "- 综合福利类（安联安康全盛）比福睿多定期寿险组件，更适合企业承担员工家庭责任和疾病身故补偿，但复杂度与成本也更高。",
            "- 团体万能年金（安联团体C 2025）解决的是长期激励、补充养老和递延福利，不解决医疗费用；结算利率超保证部分不确定，企业不能向员工刚性承诺收益。",
            "",
        ]
    )
    for product in products:
        lines.extend(render_product_section(product))
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="生成企业团险产品企业客户适配分析报告")
    parser.add_argument("--materials", type=Path, default=DEFAULT_MATERIALS, help="crawler 输出的 materials JSON")
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT, help="Markdown 报告输出路径")
    parser.add_argument("--json-output", type=Path, default=DEFAULT_JSON, help="结构化分析 JSON 输出路径")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    data = json.loads(args.materials.read_text(encoding="utf-8"))
    products = data.get("products", [])
    if len(products) != 8:
        raise RuntimeError(f"期望 8 个目标产品，实际 {len(products)} 个")

    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.json_output.parent.mkdir(parents=True, exist_ok=True)
    report = build_report(products, args.materials)
    args.report.write_text(report, encoding="utf-8")
    args.json_output.write_text(
        json.dumps(
            {
                "generated_at": datetime.now().isoformat(timespec="seconds"),
                "source_materials": str(args.materials),
                "products": build_structured_summary(products),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"Report: {args.report}")
    print(f"JSON: {args.json_output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
