# Data Map

Use this map to route user requests to providers and output files.

## Provider Policy

- Primary free sources: `mootdx`, Tencent Finance, `akshare` wrappers for Eastmoney/东方财富 and CNINFO/巨潮.
- Excluded sources: `iwencai` and `tushare`.
- Package partial success. A failed provider must add an error entry to `manifest.json` instead of stopping the whole package.
- Prefer lower-risk endpoints for routine use. Avoid high-frequency loops against Eastmoney or CNINFO.

## Layers

| Layer | Capability | Primary source | Fallback/source notes | Default files |
|---|---|---|---|---|
| `quote` | realtime quote, daily K-line, PE/PB, market cap, turnover | Tencent Finance full quote + Tencent K-line | `mootdx` can be added for order book | `quote/realtime_quote.*`, `quote/daily_kline.*`, `quote/valuation.*` |
| `fundamentals` | company basic info, quarterly finance fields, F10 text | Tencent Finance light company basics + `akshare` finance reports | `mootdx finance` and `mootdx F10` can be added for richer F10 text | `fundamentals/company_basic.*`, `fundamentals/finance_quarterly.*`, `fundamentals/f10_profile.json` |
| `news` | stock news, CLS flash, global finance news | `akshare` news endpoints | Use low-frequency calls only | `news/stock_news.*`, `news/cls_flash.*`, `news/global_news.*` |
| `research` | research list, PDF download, institutional forecasts | Eastmoney report API via `akshare` or public JSON | THS forecasts only through public `akshare` functions; no iwencai | `research/research_list.*`, `research/forecasts.*`, `research/pdf/` |
| `announcements` | announcement list, full text, latest summaries | CNINFO/巨潮 via `akshare` | `mootdx F10` for quick disclosure summary | `announcements/announcement_list.*`, `announcements/summaries.*`, `announcements/fulltext/` |

## Natural Language Routing

- "今天行情", "行情数据", "实时价格", "K线", "盘口", "估值": `quote`
- "公司资料", "基础数据", "基本面", "财务", "F10": `fundamentals`
- "新闻", "快讯", "资讯": `news`
- "研报", "机构预期", "EPS预测", "PDF": `research`
- "公告", "披露", "分红", "股东大会", "巨潮": `announcements`

## Stock Resolution

Resolve names in this order:

1. Explicit six-digit code, e.g. `601318`.
2. Exchange-qualified code, e.g. `601318.SH`, `000001.SZ`, `430047.BJ`.
3. Chinese name exact match from `akshare.stock_info_a_code_name`.
4. Chinese name contains match only if it returns one clear candidate; otherwise ask the user to confirm.

Market inference:

- Codes starting with `6` or `9`: Shanghai, `.SH`
- Codes starting with `0` or `3`: Shenzhen, `.SZ`
- Codes starting with `4` or `8`: Beijing, `.BJ`

## Research Limits

- Company research means reports published by securities firms or research institutions whose subject includes the ticker or company name.
- Industry research means reports whose industry, sector, or theme matches the user query.
- Default limit: most recent 20 reports.
- Default time range: prefer the last 12 months when the provider supports date filtering.
- Default PDF policy: download at most 20 PDFs. If PDF download fails, keep the report index row and PDF URL.
