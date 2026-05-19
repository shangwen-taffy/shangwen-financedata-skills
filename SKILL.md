---
name: shangwen-automatic-finance-data
description: Fetch, normalize, and package China A-share financial data across five layers: market quotes, fundamentals, news, research reports, and announcements/disclosures. Use when the user asks for stock data by Chinese company name, ticker, or A-share code, including requests such as today's quote, K-line, order book, PE/PB, market cap, turnover, company basics, financial snapshots, F10 text, stock news, global finance news, research report lists/PDFs, forecasts, announcements, or disclosure summaries. Excludes iwencai and tushare unless the skill is later extended.
---

# Shangwen Automatic Finance Data

## Workflow

Use this skill to turn a natural-language A-share data request into a zipped data package.

1. Parse the requested stock targets, layers, date range, and output location.
2. Resolve Chinese names to A-share codes when needed. Prefer exact matches from `akshare.stock_info_a_code_name`; fall back to user-provided code if resolution is ambiguous.
3. Select only the requested layers. Do not fetch all five layers unless the user asks for a full package.
4. Use the provider map in `references/data-map.md` to choose primary and fallback sources. Do not use `iwencai` or `tushare`.
5. Apply safety limits before fetching large document sets. For research reports, default to the most recent 20 reports, prefer the last 12 months, and do not download more than 20 PDFs unless the user explicitly requests a different limit.
6. Run `scripts/fetch_data.py` when the request fits the default pipeline. If dependencies are missing and the user approves installation, install `akshare`, `mootdx`, `requests`, and `pandas` in the active Python environment.

```powershell
python scripts/fetch_data.py --query "中国平安今天行情和公司基础数据" --layers quote,fundamentals --out output
```

If `python` is not on PATH, use the Python executable available in the local environment.

For PowerShell environments that garble Chinese command-line arguments, write a UTF-8 JSON request file and use:

```powershell
python scripts/fetch_data.py --request-json request.json
```

7. Return the generated `.zip` path and briefly list successful layers and provider errors, if any.

## Default Layer Selection

Map natural-language requests to these layer keys:

- `quote`: today quote, realtime quote, market data, K-line,盘口,五档,逐笔,PE,PB,市值,换手率
- `fundamentals`: 公司基础数据,基本面,F10,财务快照,季报,EPS,ROE,净利润,主营收入
- `news`: 个股新闻,快讯,财联社,全球资讯,财经新闻
- `research`: 研报,机构预期,EPS预测,PDF研报
- `announcements`: 公告,披露,巨潮,公告全文,最新摘要,分红,股东大会

When the user says "今天的行情数据", include realtime quote, daily K-line where available, valuation fields, market cap, and turnover. Add order book or transaction detail only when a provider can fetch it reliably in the local environment.

## Research Defaults

For `research`, distinguish report types:

- `equity research`: research institution reports about a specific listed company or ticker.
- `industry research`: reports about an industry, sector, or theme.
- `macro/strategy research`: market, macro, allocation, or strategy reports.

When the user does not give a limit, fetch at most 20 recent reports and download at most 20 PDFs. Prefer the last 12 months when the provider supports date filtering. Record the actual count and any PDF download failures in `manifest.json`.

## Output Contract

Always package outputs as JSON and CSV in a zip. For long-form source material, also keep the original or extracted text.

Read `references/output-contract.md` before changing file names, manifest fields, or packaging behavior.

## Provider Rules

Read `references/data-map.md` before adding or changing sources. Current policy:

- Use `mootdx`, Tencent Finance, Eastmoney/东方财富 public endpoints via `akshare`, CNINFO/巨潮 via `akshare`, and other free/public sources.
- Do not use `iwencai` because it requires paid credentials.
- Do not use `tushare` because the user does not want it.
- Treat `akshare` high-frequency Eastmoney calls as fragile; rate-limit, retry conservatively, and record provider errors in `manifest.json`.
- Never hard-code API keys or session tokens in this skill. Use environment variables documented in `assets/.env.example`.

## Extending The Skill

To add a new data source:

1. Add its layer, capability, auth requirements, and priority to `references/data-map.md`.
2. Add environment variables to `assets/.env.example` when credentials are needed.
3. Add or patch a collector in `scripts/fetch_data.py`, keeping provider errors non-fatal.
4. Preserve the zip layout from `references/output-contract.md`.
5. Run the quick validator and a small fetch test.

## Validation

After edits, run:

```powershell
python C:\Users\HUAWEI\.codex\skills\.system\skill-creator\scripts\quick_validate.py C:\Users\HUAWEI\Desktop\数据源skill\shangwen-automatic-finance-data
```

If the bundled Python runtime is needed, replace `python` with its absolute executable path.
