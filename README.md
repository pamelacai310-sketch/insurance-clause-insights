# insurance-clause-insights

一个独立的保险条款横向比较项目，直接复用并同步上游仓库
[`pamelacai310-sketch/insurance-crawler-push`](https://github.com/pamelacai310-sketch/insurance-crawler-push)，
抓取在售保险产品条款 PDF，并在同类产品中筛出 20 款以上合同比较，输出每个具体产品最独特的特色条款。

## 能力范围

- 自动克隆或更新 `insurance-crawler-push`
- 直接调用上游爬虫抓取在售产品条款、费率表、现金价值表
- 从条款 PDF 中提取全文、关键信息、条款候选句
- 自动识别同类产品，如年金险、终身寿险、重疾险、医疗险等
- 只对满足 `20+` 产品数量的类别生成横向比较报告
- 为每个产品输出 3 条最独特的特色描述，并附证据句
- 生成 `Markdown`、`JSON`、`Excel` 三种结果

## 环境要求

- Python 3.9+
- Google Chrome（供上游 Selenium 爬虫使用）
- 可以联网访问保险公司官网

## 安装

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

## 一键运行

```bash
insurance-clause-insights run
```

默认流程会：

1. 同步 `insurance-crawler-push`
2. 运行上游爬虫
3. 读取最新抓取结果
4. 对满足 `20+` 产品的同类条款做横向比较
5. 生成报告到 `outputs/run_<timestamp>/reports/`

## 常用命令

### 仅同步上游仓库

```bash
insurance-clause-insights sync-upstream
```

### 仅抓取数据

```bash
insurance-clause-insights crawl --companies AIA友邦 Allianz安联
```

### 基于既有抓取结果做分析

```bash
insurance-clause-insights analyze \
  --crawl-json outputs/run_20260510_120000/raw/data/insurance_data_20260510_120500.json \
  --category 年金保险
```

### 指定最少比较产品数

```bash
insurance-clause-insights run --min-products 20
```

### 调试时显示浏览器

```bash
insurance-clause-insights run --show-browser
```

## 输出结构

```text
outputs/
└── run_20260510_120000/
    ├── raw/
    │   ├── pdfs/
    │   └── data/
    └── reports/
        ├── comparison_report.md
        ├── comparison_report.json
        └── comparison_report.xlsx
```

## 报告内容

每个可比较类别会输出：

- 类别内产品数量
- 每个产品的公司、产品名、PDF 路径
- 保险期间、缴费期间、等待期等关键字段
- 3 条最独特的特色及对应证据句

## 分析说明

- “独特特色”目前使用规则抽取 + 文本相似度对比完成
- 特色句优先从等待期、缴费期、保证续保、身故责任、年金责任、重疾责任、免责条款等句子中筛选
- 如果某个产品类别不足 20 款，工具会明确提示当前各类别数量

## 说明

- 上游仓库负责抓取，当前项目负责“同类合同对比”和“独特特色提炼”
- 下载的 PDF 与原始数据不纳入 Git 管理
