# Shangwen Automatic Finance Data

面向 A 股投研场景的自动化金融数据源 Skill。它把分散在多个公开数据源中的股票行情、基本面、资金、公告新闻和研报数据统一采集、清洗、导出和归档，供 Codex、LLM Agent、量化研究脚本或人工投研流程继续使用。

本项目不是单一的行情测试脚本，而是一个按数据层组织的金融数据采集能力包：覆盖 5 个数据层、13 个接口，并统一输出为结构化 `JSON` / `CSV` / `PDF` / `manifest.json`。

## 核心能力

- 支持 A 股股票代码识别，例如 `601318`、`000001`、`300750`
- 支持沪深市场自动归属，例如 `SH` / `SZ`
- 支持多数据源自动采集与降级 fallback
- 支持行情、估值、K 线、公司资料、财务报表、资金流、公告、新闻、研报等多类数据
- 支持研报 PDF 原文下载
- 支持输出 `JSON`、`CSV`、原始响应和压缩包
- 每次任务生成 `manifest.json`，记录查询参数、数据源、文件列表、错误和耗时
- 适合作为 LLM / Agent 金融研究工作流的数据输入层

## 数据分层

当前设计覆盖 5 个数据层：

| 数据层 | Layer | 说明 |
|---|---|---|
| 行情层 | `quote` | 实时行情、估值指标、历史 K 线 |
| 基本面层 | `fundamentals` | 公司基础资料、财务报表、财务指标 |
| 资金层 | `capital_flow` | 个股资金流、主力资金、北向资金或市场资金相关数据 |
| 资讯公告层 | `news` | 公司公告、公司新闻、市场资讯 |
| 研报层 | `research` | 机构研报索引、盈利预测、评级、PDF 原文 |

## 13 个接口

| 序号 | Layer | Interface | 说明 | 主要数据源 |
|---:|---|---|---|---|
| 1 | `quote` | `realtime_quote` | 个股实时行情，包含价格、涨跌幅、成交量、成交额等 | 腾讯证券 |
| 2 | `quote` | `daily_kline` | 日 K 线 / 历史行情 | 腾讯证券、AkShare、东方财富 |
| 3 | `quote` | `valuation` | 估值指标，如市盈率、市净率、市值等 | 腾讯证券、AkShare、东方财富 |
| 4 | `fundamentals` | `company_basic` | 公司基础信息，如名称、行业、上市市场、主营信息等 | 腾讯证券、AkShare |
| 5 | `fundamentals` | `finance_quarterly` | 季度财务数据，适合做历史财务序列分析 | AkShare |
| 6 | `fundamentals` | `financial_indicator` | 财务指标，如 ROE、毛利率、净利率、负债率等 | AkShare、东方财富 |
| 7 | `capital_flow` | `stock_money_flow` | 个股资金流向 | AkShare、东方财富 |
| 8 | `capital_flow` | `main_money_flow` | 主力资金流、超大单、大单等 | AkShare、东方财富 |
| 9 | `capital_flow` | `northbound_flow` | 北向资金相关数据 | AkShare、东方财富 |
| 10 | `news` | `company_announcement` | 上市公司公告 | AkShare、巨潮资讯、交易所公告 |
| 11 | `news` | `company_news` | 公司新闻、市场资讯 | AkShare、东方财富、腾讯证券 |
| 12 | `research` | `research_list` | 机构研报列表、评级、盈利预测、发布日期等 | AkShare、东方财富 |
| 13 | `research` | `research_pdf` | 研报 PDF 原文下载 | 东方财富 PDF 链接 |

## 数据源

项目使用多个公开金融数据源，并按可用性进行组合：

| 数据源 | 用途 |
|---|---|
| 腾讯证券 | 实时行情、估值、K 线、部分公司基础信息 |
| AkShare | 行情、财务、资金流、公告、新闻、研报索引等统一接口 |
| 东方财富 | 估值、资金流、研报 PDF、部分行情与资讯数据 |
| 巨潮资讯 | 上市公司公告 |
| 交易所公告源 | 上交所、深交所相关公告数据 |
| PDF 原文链接源 | 用于下载机构研报原文 |

> 数据源的实际可用性会受网络、接口变动、访问频率和源站限制影响。任务结果以 `manifest.json` 中记录的 provider 状态为准。

## 输出格式

每次任务会生成一个独立输出目录：

```text
output/
└── {股票代码}_{股票名称}_{时间戳}/
    ├── manifest.json
    ├── quote/
    │   ├── realtime_quote.json
    │   ├── realtime_quote.csv
    │   ├── valuation.json
    │   ├── valuation.csv
    │   ├── daily_kline.json
    │   └── daily_kline.csv
    ├── fundamentals/
    │   ├── company_basic.json
    │   ├── company_basic.csv
    │   ├── finance_quarterly.json
    │   └── finance_quarterly.csv
    ├── capital_flow/
    │   └── *.json / *.csv
    ├── news/
    │   └── *.json / *.csv
    ├── research/
    │   ├── research_list.json
    │   ├── research_list.csv
    │   └── pdf/
    │       └── *.pdf
    └── raw/
        └── 原始接口响应
```

同时会生成对应压缩包：

```text
output/{股票代码}_{股票名称}_{时间戳}.zip
```

## manifest.json

`manifest.json` 是每次任务的索引文件，用于追踪数据采集过程。

典型字段包括：

```json
{
  "query": "601318 quote fundamentals research",
  "generated_at": "2026-05-19T02:01:53+08:00",
  "targets": [
    {
      "input": "601318 中国平安",
      "name": "中国平安",
      "code": "601318",
      "market": "SH"
    }
  ],
  "layers": ["quote", "fundamentals", "research"],
  "providers": [],
  "files": [],
  "errors": []
}
```

其中：

| 字段 | 说明 |
|---|---|
| `query` | 原始任务请求 |
| `generated_at` | 生成时间 |
| `targets` | 股票代码、名称、市场 |
| `layers` | 本次采集的数据层 |
| `providers` | 每个接口的数据源、状态、行数和耗时 |
| `files` | 本次生成的全部文件 |
| `errors` | 失败接口、错误信息和 fallback 情况 |

## 示例：获取中国平安研报

示例目标：

```text
601318 中国平安
```

任务要求：

```text
获取研究机构发布的、研究对象包含 601318 中国平安 的个股研报数据；
只取 research 层；
最多最近 20 篇；
时间范围优先近 12 个月；
输出研报索引 json/csv 并尽量下载 PDF 原文。
```

示例结果：

| 指标 | 数量 |
|---|---:|
| 原始研报记录 | 202 |
| 最近 12 个月符合条件记录 | 27 |
| 最终选取研报 | 20 |
| 成功下载 PDF | 20 |
| 输出格式 | JSON / CSV / PDF / manifest |

## 示例：行情与基本面

示例目标：

```text
601318 quote fundamentals
```

已验证输出包括：

```text
quote/realtime_quote.json
quote/realtime_quote.csv
quote/valuation.json
quote/valuation.csv
quote/daily_kline.json
quote/daily_kline.csv
fundamentals/company_basic.json
fundamentals/company_basic.csv
fundamentals/finance_quarterly.json
fundamentals/finance_quarterly.csv
raw/tencent_realtime_quote.json
manifest.json
```

## 安装依赖

```bash
pip install requests
```

如使用 AkShare 相关接口：

```bash
pip install akshare pandas
```

## 使用方式

根据任务配置采集数据，并将结果输出到 `output/` 目录。

研报后处理与 PDF 打包示例：

```bash
python finalize_research_package.py \
  --source-dir output/601318_601318_20260519_015940 \
  --out-root output \
  --today 2026-05-19 \
  --months 12 \
  --limit 20
```

参数说明：

| 参数 | 说明 |
|---|---|
| `--source-dir` | 原始研报索引所在目录 |
| `--out-root` | 输出根目录 |
| `--today` | 截止日期 |
| `--months` | 优先筛选最近几个月 |
| `--limit` | 最多保留多少条记录 |

## 适用场景

- A 股个股研究资料整理
- LLM 投研 Agent 数据输入
- 研报批量下载和归档
- 财务指标与历史行情分析
- 多数据源金融数据采集实验
- 自动化投研流水线的数据层

## 注意事项

- 本项目依赖公开数据源，接口可用性可能随源站变化而变化
- 外部数据源可能存在访问频率限制
- PDF 下载成功率取决于原始链接是否有效
- 数据仅供研究和学习使用，不构成投资建议
- 使用者应遵守各数据源网站条款、版权要求和当地法律法规

## Roadmap

- [ ] 补全标准 Codex Skill 目录结构
- [ ] 增加统一入口脚本
- [ ] 增加 5 层数据的一键采集配置
- [ ] 增加接口级缓存
- [ ] 增加失败重试和 provider fallback 策略
- [ ] 增加字段标准化 schema
- [ ] 增加更多股票和批量任务支持

## License

MIT License
```
