# Shangwen Automatic Finance Data

一个用于自动采集、整理和打包 A 股金融数据的 Codex Skill / 数据源工具。当前重点支持个股研报数据获取、研报索引导出、PDF 原文下载与结果归档，适合用于投研资料整理、金融数据分析前置处理和自动化研究流水线。

## 功能特性

- 支持按股票代码和股票名称获取个股研报数据
- 支持筛选最近指定时间范围内的研报
- 支持导出研报索引为 `JSON` 和 `CSV`
- 支持下载研报 PDF 原文
- 自动生成 `manifest.json`，记录查询条件、数据来源、输出文件和错误信息
- 自动打包输出目录为 `.zip`
- 已验证示例：`601318 中国平安` 最近 12 个月研报数据

## 项目结构

```text
.
├── finalize_research_package.py      # 研报数据后处理、PDF 下载和打包脚本
├── request_research_601318.json      # 示例请求配置
├── output/                           # 示例输出结果
└── shangwen-automatic-finance-data/   # Skill 目录
```

## 快速开始

### 1. 安装依赖

```bash
pip install requests
```

### 2. 准备输入数据

脚本需要一个已经包含研报索引的来源目录，目录内应包含：

```text
source-dir/
├── manifest.json
└── research/
    └── research_list.json
```

### 3. 运行后处理脚本

```bash
python finalize_research_package.py \
  --source-dir output/你的来源目录 \
  --out-root output \
  --today 2026-05-19 \
  --months 12 \
  --limit 20
```

参数说明：

| 参数 | 说明 | 默认值 |
|---|---|---|
| `--source-dir` | 原始研报数据目录 | 必填 |
| `--out-root` | 输出根目录 | `output` |
| `--today` | 数据筛选截止日期 | `2026-05-19` |
| `--months` | 优先筛选最近几个月 | `12` |
| `--limit` | 最多保留多少篇研报 | `20` |

## 输出结果

运行完成后会生成类似如下目录：

```text
output/
└── 601318_中国平安_research_20260519_020143/
    ├── manifest.json
    ├── research/
    │   ├── research_list.json
    │   ├── research_list.csv
    │   └── pdf/
    │       ├── 01_2026-04-30_华源证券_....pdf
    │       └── ...
    └── raw/
        └── akshare_research_list_full.json
```

同时会生成对应的压缩包：

```text
601318_中国平安_research_20260519_020143.zip
```

## 示例结果

以 `601318 中国平安` 为例，当前示例输出包含：

- 原始研报记录：202 条
- 最近 12 个月符合条件记录：27 条
- 最终选取研报：20 篇
- 成功下载 PDF：20 份
- 输出格式：`JSON`、`CSV`、`PDF`、`manifest.json`

## 数据来源

当前流程中涉及的数据来源包括：

- AkShare：研报列表数据
- 东方财富：研报 PDF 文件下载

请在使用时遵守对应数据源的网站条款、版权要求和访问频率限制。

## 适用场景

- 个股研报批量整理
- 投研资料归档
- 金融数据分析前的数据准备
- 自动化研究报告流水线
- LLM / Agent 投研工作流的数据输入层

## 注意事项

- PDF 下载依赖外部链接可访问性，部分链接可能失效或返回非 PDF 内容
- 输出中的 `manifest.json` 会记录 provider 状态、文件列表和错误信息，建议优先查看该文件判断任务是否完整成功
- 当前脚本更偏向研报数据后处理，如果需要完整 Skill 分发，建议补充 `SKILL.md`、`agents/openai.yaml` 和标准化 `scripts/` 目录

## License

MIT License
```
