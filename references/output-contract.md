# Output Contract

Create one zip per user request. Include only requested layers unless the user asks for a full package.

## Zip Layout

```text
<name>_<code>_<yyyymmdd>.zip
  manifest.json
  quote/
    realtime_quote.json
    realtime_quote.csv
    daily_kline.json
    daily_kline.csv
    valuation.json
    valuation.csv
  fundamentals/
    company_basic.json
    company_basic.csv
    finance_quarterly.json
    finance_quarterly.csv
    f10_profile.json
  research/
    research_list.json
    research_list.csv
    forecasts.json
    forecasts.csv
    pdf/
  news/
    stock_news.json
    stock_news.csv
    cls_flash.json
    cls_flash.csv
    global_news.json
    global_news.csv
  announcements/
    announcement_list.json
    announcement_list.csv
    summaries.json
    summaries.csv
    fulltext/
  raw/
    <provider>_<dataset>.json
```

## File Rules

- Write every structured dataset as both `.json` and `.csv`.
- Write raw provider responses under `raw/` when useful for debugging or future parsing.
- Write report PDFs under `research/pdf/`.
- Write announcement/news/report long text as `.txt` when a provider returns full text.
- Use UTF-8 with BOM for CSV if Excel compatibility is important.
- Keep original provider field names when they are meaningful; add normalized fields only when useful.

## Manifest

`manifest.json` must include:

```json
{
  "query": "中国平安今天行情和公司基础数据",
  "generated_at": "2026-05-18T22:00:00+08:00",
  "targets": [
    {
      "input": "中国平安",
      "name": "中国平安",
      "code": "601318",
      "market": "SH"
    }
  ],
  "layers": ["quote", "fundamentals"],
  "providers": [],
  "files": [],
  "errors": []
}
```

Each provider entry should record layer, provider name, dataset, status, row count if known, and elapsed time when available.

Each error entry should record layer, provider, dataset, message, and whether another provider succeeded.
