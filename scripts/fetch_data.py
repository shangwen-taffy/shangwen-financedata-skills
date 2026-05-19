#!/usr/bin/env python
"""
Fetch and package A-share data for the Shangwen Automatic Finance Data skill.

The script is intentionally dependency-light. It uses optional providers when
installed (`akshare`, `mootdx`, `requests`, `pandas`) and records failures in
manifest.json instead of aborting the whole package.
"""

from __future__ import annotations

import argparse
import csv
import importlib
import json
import os
import re
import shutil
import sys
import time
import zipfile
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable


LAYER_ALIASES = {
    "quote": {"quote", "quotes", "market", "行情", "今天行情", "实时行情", "k线", "盘口", "估值"},
    "fundamentals": {"fundamental", "fundamentals", "basic", "finance", "基础数据", "基本面", "公司基础", "财务", "f10"},
    "news": {"news", "新闻", "资讯", "快讯", "财联社", "全球资讯"},
    "research": {"research", "report", "研报", "机构预期", "预测", "eps预测"},
    "announcements": {"announcement", "announcements", "disclosure", "公告", "披露", "巨潮"},
}

DEFAULT_LAYER_KEYWORDS = {
    "quote": ["行情", "今天", "实时", "k线", "K线", "盘口", "五档", "逐笔", "PE", "PB", "市值", "换手率"],
    "fundamentals": ["基础", "基本面", "公司", "财务", "F10", "季报", "EPS", "ROE", "净利润", "主营收入"],
    "news": ["新闻", "资讯", "快讯", "财联社"],
    "research": ["研报", "机构预期", "预测", "PDF"],
    "announcements": ["公告", "披露", "分红", "股东大会", "巨潮"],
}

STATIC_ALIASES = {
    "中国平安": {"code": "601318", "name": "中国平安", "market": "SH"},
    "平安银行": {"code": "000001", "name": "平安银行", "market": "SZ"},
    "贵州茅台": {"code": "600519", "name": "贵州茅台", "market": "SH"},
    "宁德时代": {"code": "300750", "name": "宁德时代", "market": "SZ"},
}


@dataclass
class ProviderEvent:
    layer: str
    provider: str
    dataset: str
    status: str
    rows: int | None = None
    elapsed_ms: int | None = None
    message: str | None = None


@dataclass
class RunContext:
    query: str
    out_dir: Path
    targets: list[dict[str, str]]
    layers: list[str]
    manifest: dict[str, Any] = field(default_factory=dict)

    def add_provider(self, event: ProviderEvent) -> None:
        self.manifest.setdefault("providers", []).append({k: v for k, v in event.__dict__.items() if v is not None})

    def add_error(self, layer: str, provider: str, dataset: str, message: str) -> None:
        self.manifest.setdefault("errors", []).append(
            {"layer": layer, "provider": provider, "dataset": dataset, "message": str(message)}
        )

    def add_file(self, path: Path) -> None:
        self.manifest.setdefault("files", []).append(str(path.relative_to(self.out_dir)))


def optional_import(name: str) -> Any | None:
    try:
        return importlib.import_module(name)
    except Exception:
        return None


def safe_filename(value: str) -> str:
    value = re.sub(r"[\\/:*?\"<>|]+", "_", value)
    value = re.sub(r"\s+", "_", value).strip("_")
    return value or "a_share_data"


def infer_market(code: str) -> str:
    if code.startswith(("6", "9")):
        return "SH"
    if code.startswith(("0", "3")):
        return "SZ"
    if code.startswith(("4", "8")):
        return "BJ"
    return ""


def normalize_target(raw: str) -> dict[str, str]:
    raw = raw.strip()
    upper = raw.upper()
    m = re.match(r"^(\d{6})[. -]?(SH|SZ|BJ)?$", upper)
    if m:
        code = m.group(1)
        market = m.group(2) or infer_market(code)
        return {"input": raw, "code": code, "market": market, "name": raw}

    if raw in STATIC_ALIASES:
        result = dict(STATIC_ALIASES[raw])
        result["input"] = raw
        return result

    ak = optional_import("akshare")
    if ak is not None and hasattr(ak, "stock_info_a_code_name"):
        try:
            df = ak.stock_info_a_code_name()
            records = records_from_obj(df)
            exact = [r for r in records if str(r.get("name") or r.get("名称") or "") == raw]
            fuzzy = [r for r in records if raw in str(r.get("name") or r.get("名称") or "")]
            matches = exact or fuzzy
            if len(matches) == 1:
                item = matches[0]
                code = str(item.get("code") or item.get("代码") or "").zfill(6)
                name = str(item.get("name") or item.get("名称") or raw)
                return {"input": raw, "code": code, "market": infer_market(code), "name": name}
        except Exception:
            pass

    raise ValueError(f"Cannot resolve stock target: {raw}. Provide a six-digit A-share code.")


def parse_layers(query: str, explicit_layers: str | None) -> list[str]:
    if explicit_layers:
        requested = []
        for item in re.split(r"[,，\s]+", explicit_layers):
            if not item:
                continue
            normalized = None
            lower = item.lower()
            for key, aliases in LAYER_ALIASES.items():
                if lower == key or item in aliases or lower in aliases:
                    normalized = key
                    break
            if normalized is None:
                raise ValueError(f"Unknown layer: {item}")
            if normalized not in requested:
                requested.append(normalized)
        return requested

    found = []
    for key, keywords in DEFAULT_LAYER_KEYWORDS.items():
        if any(word in query for word in keywords):
            found.append(key)
    return found or ["quote"]


def records_from_obj(obj: Any) -> list[dict[str, Any]]:
    if obj is None:
        return []
    if hasattr(obj, "to_dict"):
        try:
            return obj.to_dict(orient="records")
        except TypeError:
            data = obj.to_dict()
            if isinstance(data, dict):
                return [data]
    if isinstance(obj, list):
        return [x if isinstance(x, dict) else {"value": x} for x in obj]
    if isinstance(obj, dict):
        return [obj]
    return [{"value": str(obj)}]


def write_json_csv(ctx: RunContext, layer: str, dataset: str, data: Any) -> int:
    layer_dir = ctx.out_dir / layer
    layer_dir.mkdir(parents=True, exist_ok=True)
    records = records_from_obj(data)

    json_path = layer_dir / f"{dataset}.json"
    json_path.write_text(json.dumps(records, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    ctx.add_file(json_path)

    csv_path = layer_dir / f"{dataset}.csv"
    fieldnames = sorted({key for row in records for key in row.keys()}) if records else ["empty"]
    csv_encoding = "utf-8-sig" if os.environ.get("SHANGWEN_CSV_UTF8_SIG", "1") != "0" else "utf-8"
    with csv_path.open("w", newline="", encoding=csv_encoding) as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        if records:
            writer.writerows(records)
    ctx.add_file(csv_path)
    return len(records)


def target_dataset(ctx: RunContext, target: dict[str, str], dataset: str) -> str:
    if len(ctx.targets) <= 1:
        return dataset
    return f"{target['code']}_{dataset}"


def save_raw(ctx: RunContext, provider: str, dataset: str, data: Any) -> None:
    raw_dir = ctx.out_dir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    path = raw_dir / f"{provider}_{dataset}.json"
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    ctx.add_file(path)


def timed_call(ctx: RunContext, layer: str, provider: str, dataset: str, func: Callable[[], Any]) -> Any | None:
    start = time.time()
    try:
        data = func()
        rows = len(records_from_obj(data))
        ctx.add_provider(
            ProviderEvent(
                layer=layer,
                provider=provider,
                dataset=dataset,
                status="ok",
                rows=rows,
                elapsed_ms=int((time.time() - start) * 1000),
            )
        )
        return data
    except Exception as exc:
        ctx.add_provider(
            ProviderEvent(
                layer=layer,
                provider=provider,
                dataset=dataset,
                status="error",
                elapsed_ms=int((time.time() - start) * 1000),
                message=str(exc),
            )
        )
        ctx.add_error(layer, provider, dataset, str(exc))
        return None


def fetch_tencent_quote(target: dict[str, str]) -> list[dict[str, Any]]:
    requests = optional_import("requests")
    if requests is None:
        raise RuntimeError("requests is not installed")
    code = target["code"]
    prefix = {"SH": "sh", "SZ": "sz", "BJ": "bj"}.get(target.get("market", ""), "")
    if not prefix:
        prefix = "sh" if code.startswith("6") else "sz"
    url = f"https://qt.gtimg.cn/q=s_{prefix}{code}"
    session = requests.Session()
    session.trust_env = os.environ.get("SHANGWEN_USE_PROXY", "0") == "1"
    resp = session.get(url, timeout=int(os.environ.get("SHANGWEN_REQUEST_TIMEOUT", "15")))
    resp.encoding = "gbk"
    text = resp.text.strip()
    save = {
        "provider": "tencent",
        "code": code,
        "market": target.get("market", ""),
        "name": target.get("name", ""),
        "raw": text,
        "url": url,
    }
    parts = text.split("~")
    if len(parts) >= 7:
        save.update(
            {
                "parsed_name": parts[1],
                "price": parts[3],
                "change": parts[4],
                "change_pct": parts[5],
                "volume_lot": parts[6],
            }
        )
    return [save]


def tencent_symbol(target: dict[str, str]) -> str:
    code = target["code"]
    prefix = {"SH": "sh", "SZ": "sz", "BJ": "bj"}.get(target.get("market", ""), "")
    if not prefix:
        prefix = "sh" if code.startswith("6") else "sz"
    return f"{prefix}{code}"


def fetch_tencent_full_parts(target: dict[str, str]) -> list[str]:
    requests = optional_import("requests")
    if requests is None:
        raise RuntimeError("requests is not installed")
    symbol = tencent_symbol(target)
    url = f"https://qt.gtimg.cn/q={symbol}"
    session = requests.Session()
    session.trust_env = os.environ.get("SHANGWEN_USE_PROXY", "0") == "1"
    resp = session.get(url, timeout=int(os.environ.get("SHANGWEN_REQUEST_TIMEOUT", "15")))
    resp.raise_for_status()
    resp.encoding = "gbk"
    text = resp.text.strip()
    if '"' not in text:
        raise RuntimeError(f"Tencent returned unexpected quote data: {text[:120]}")
    return text.split('"', 2)[1].split("~")


def part(parts: list[str], index: int) -> str | None:
    if index >= len(parts):
        return None
    value = parts[index].strip()
    return value if value not in {"", "-"} else None


def as_float(value: str | None) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except ValueError:
        return None


def fetch_tencent_valuation(target: dict[str, str]) -> list[dict[str, Any]]:
    parts = fetch_tencent_full_parts(target)
    return [
        {
            "provider": "tencent",
            "code": part(parts, 2) or target["code"],
            "name": part(parts, 1) or target.get("name", ""),
            "latest_price": as_float(part(parts, 3)),
            "previous_close": as_float(part(parts, 4)),
            "open": as_float(part(parts, 5)),
            "high": as_float(part(parts, 33)),
            "low": as_float(part(parts, 34)),
            "change": as_float(part(parts, 31)),
            "change_pct": as_float(part(parts, 32)),
            "turnover_pct": as_float(part(parts, 38)),
            "pe_ttm": as_float(part(parts, 39)),
            "total_market_cap_yi": as_float(part(parts, 45)),
            "float_market_cap_yi": as_float(part(parts, 44)),
            "pb": as_float(part(parts, 46)),
            "total_shares": as_float(part(parts, 73)),
            "float_shares": as_float(part(parts, 72)),
            "currency": part(parts, 82),
            "quote_time": part(parts, 30),
        }
    ]


def fetch_tencent_company_basic(target: dict[str, str]) -> list[dict[str, Any]]:
    valuation = fetch_tencent_valuation(target)[0]
    return [
        {
            "provider": "tencent",
            "code": valuation.get("code"),
            "name": valuation.get("name"),
            "market": target.get("market", ""),
            "currency": valuation.get("currency"),
            "latest_price": valuation.get("latest_price"),
            "pe_ttm": valuation.get("pe_ttm"),
            "pb": valuation.get("pb"),
            "total_market_cap_yi": valuation.get("total_market_cap_yi"),
            "float_market_cap_yi": valuation.get("float_market_cap_yi"),
            "total_shares": valuation.get("total_shares"),
            "float_shares": valuation.get("float_shares"),
            "quote_time": valuation.get("quote_time"),
        }
    ]


def fetch_tencent_daily_kline(target: dict[str, str]) -> list[dict[str, Any]]:
    requests = optional_import("requests")
    if requests is None:
        raise RuntimeError("requests is not installed")
    symbol = tencent_symbol(target)
    today = datetime.now().strftime("%Y-%m-%d")
    url = f"https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={symbol},day,{today},{today},10,qfq"
    session = requests.Session()
    session.trust_env = os.environ.get("SHANGWEN_USE_PROXY", "0") == "1"
    resp = session.get(url, timeout=int(os.environ.get("SHANGWEN_REQUEST_TIMEOUT", "15")))
    resp.raise_for_status()
    payload = resp.json()
    data = payload.get("data", {}).get(symbol, {})
    rows = data.get("qfqday") or data.get("day") or []
    return [
        {
            "date": row[0],
            "open": row[1],
            "close": row[2],
            "high": row[3],
            "low": row[4],
            "volume": row[5],
            "code": target["code"],
            "name": target.get("name", ""),
            "provider": "tencent",
        }
        for row in rows
    ]


def fetch_akshare_daily_kline(target: dict[str, str]) -> list[dict[str, Any]]:
    ak = optional_import("akshare")
    if ak is None:
        raise RuntimeError("akshare is not installed")
    today = datetime.now().strftime("%Y%m%d")
    df = ak.stock_zh_a_hist(symbol=target["code"], period="daily", start_date=today, end_date=today, adjust="")
    return records_from_obj(df)


def fetch_akshare_company_basic(target: dict[str, str]) -> list[dict[str, Any]]:
    ak = optional_import("akshare")
    if ak is None:
        raise RuntimeError("akshare is not installed")
    df = ak.stock_individual_info_em(symbol=target["code"])
    return records_from_obj(df)


def try_akshare_function(dataset: str, candidates: list[tuple[str, dict[str, Any]]]) -> list[dict[str, Any]]:
    ak = optional_import("akshare")
    if ak is None:
        raise RuntimeError("akshare is not installed")
    errors = []
    for name, kwargs in candidates:
        func = getattr(ak, name, None)
        if func is None:
            continue
        try:
            return records_from_obj(func(**kwargs))
        except Exception as exc:
            errors.append(f"{name}: {exc}")
    raise RuntimeError(f"No akshare function succeeded for {dataset}. " + "; ".join(errors))


def collect_quote(ctx: RunContext, target: dict[str, str]) -> None:
    layer = "quote"
    data = timed_call(ctx, layer, "tencent", "realtime_quote", lambda: fetch_tencent_quote(target))
    if data is not None:
        name = target_dataset(ctx, target, "realtime_quote")
        write_json_csv(ctx, layer, name, data)
        save_raw(ctx, "tencent", name, data)

    data = timed_call(ctx, layer, "tencent", "valuation", lambda: fetch_tencent_valuation(target))
    if data is not None:
        write_json_csv(ctx, layer, target_dataset(ctx, target, "valuation"), data)

    data = timed_call(ctx, layer, "tencent", "daily_kline", lambda: fetch_tencent_daily_kline(target))
    if data is not None:
        write_json_csv(ctx, layer, target_dataset(ctx, target, "daily_kline"), data)


def collect_fundamentals(ctx: RunContext, target: dict[str, str]) -> None:
    layer = "fundamentals"
    data = timed_call(ctx, layer, "tencent", "company_basic", lambda: fetch_tencent_company_basic(target))
    if data is not None:
        write_json_csv(ctx, layer, target_dataset(ctx, target, "company_basic"), data)

    candidates = [
        ("stock_financial_abstract", {"symbol": target["code"]}),
        ("stock_financial_report_sina", {"stock": target["code"], "symbol": "利润表"}),
    ]
    data = timed_call(ctx, layer, "akshare", "finance_quarterly", lambda: try_akshare_function("finance_quarterly", candidates))
    if data is not None:
        write_json_csv(ctx, layer, target_dataset(ctx, target, "finance_quarterly"), data)


def collect_news(ctx: RunContext, target: dict[str, str]) -> None:
    layer = "news"
    data = timed_call(
        ctx,
        layer,
        "akshare",
        "stock_news",
        lambda: try_akshare_function("stock_news", [("stock_news_em", {"symbol": target["code"]})]),
    )
    if data is not None:
        write_json_csv(ctx, layer, target_dataset(ctx, target, "stock_news"), data)

    data = timed_call(
        ctx,
        layer,
        "akshare",
        "global_news",
        lambda: try_akshare_function(
            "global_news",
            [("stock_info_global_em", {}), ("stock_info_global_cls", {})],
        ),
    )
    if data is not None:
        write_json_csv(ctx, layer, target_dataset(ctx, target, "global_news"), data)


def collect_research(ctx: RunContext, target: dict[str, str]) -> None:
    layer = "research"
    candidates = [
        ("stock_research_report_em", {"symbol": target["code"]}),
        ("stock_report_em", {"symbol": target["code"]}),
        ("stock_profit_forecast_ths", {"symbol": target["code"]}),
    ]
    data = timed_call(ctx, layer, "akshare", "research_list", lambda: try_akshare_function("research_list", candidates))
    if data is not None:
        write_json_csv(ctx, layer, target_dataset(ctx, target, "research_list"), data)


def collect_announcements(ctx: RunContext, target: dict[str, str]) -> None:
    layer = "announcements"
    candidates = [
        ("stock_zh_a_disclosure_report_cninfo", {"symbol": target["code"]}),
        ("stock_notice_report", {"symbol": target["code"]}),
        ("stock_notice_report", {"symbol": "全部"}),
    ]
    data = timed_call(ctx, layer, "akshare", "announcement_list", lambda: try_akshare_function("announcement_list", candidates))
    if data is not None:
        write_json_csv(ctx, layer, target_dataset(ctx, target, "announcement_list"), data)


COLLECTORS = {
    "quote": collect_quote,
    "fundamentals": collect_fundamentals,
    "news": collect_news,
    "research": collect_research,
    "announcements": collect_announcements,
}


def make_zip(out_dir: Path, zip_path: Path) -> Path:
    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in out_dir.rglob("*"):
            if path.is_file() and path != zip_path:
                zf.write(path, path.relative_to(out_dir))
    return zip_path


def build_context(args: argparse.Namespace) -> RunContext:
    query = args.query or " ".join(args.symbols)
    layers = parse_layers(query, args.layers)
    targets = [normalize_target(raw) for raw in args.symbols]
    first = targets[0]
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    package_name = safe_filename(f"{first.get('name')}_{first.get('code')}_{stamp}")
    out_root = Path(args.out or os.environ.get("SHANGWEN_OUTPUT_DIR", "output")).resolve()
    out_dir = out_root / package_name
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True)
    ctx = RunContext(query=query, out_dir=out_dir, targets=targets, layers=layers)
    ctx.manifest = {
        "query": query,
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "targets": targets,
        "layers": layers,
        "providers": [],
        "files": [],
        "errors": [],
    }
    return ctx


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fetch and package A-share data as JSON/CSV zip.")
    parser.add_argument("symbols", nargs="*", help="Stock names or A-share codes, e.g. 中国平安 601318")
    parser.add_argument("--query", help="Original natural-language user query")
    parser.add_argument("--layers", help="Comma-separated layer keys: quote,fundamentals,news,research,announcements")
    parser.add_argument("--out", help="Output root directory")
    parser.add_argument("--request-json", help="UTF-8 JSON file with query, symbols, layers, and out fields")
    args = parser.parse_args(argv)

    if args.request_json:
        request_path = Path(args.request_json)
        payload = json.loads(request_path.read_text(encoding="utf-8"))
        args.query = args.query or payload.get("query")
        if not args.symbols:
            args.symbols = payload.get("symbols") or payload.get("targets") or []
        if not args.layers:
            layers = payload.get("layers")
            args.layers = ",".join(layers) if isinstance(layers, list) else layers
        args.out = args.out or payload.get("out")

    if not args.symbols:
        if args.query:
            for alias in STATIC_ALIASES:
                if alias in args.query:
                    args.symbols = [alias]
                    break
        if not args.symbols:
            parser.error("Provide at least one stock name/code, or include a known stock name in --query.")
    return args


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    ctx = build_context(args)

    for target in ctx.targets:
        for layer in ctx.layers:
            collector = COLLECTORS[layer]
            collector(ctx, target)

    manifest_path = ctx.out_dir / "manifest.json"
    manifest_path.write_text(json.dumps(ctx.manifest, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    ctx.add_file(manifest_path)
    manifest_path.write_text(json.dumps(ctx.manifest, ensure_ascii=False, indent=2, default=str), encoding="utf-8")

    zip_path = ctx.out_dir.with_suffix(".zip")
    make_zip(ctx.out_dir, zip_path)
    print(str(zip_path))
    if ctx.manifest.get("errors"):
        print(f"Completed with {len(ctx.manifest['errors'])} provider error(s). See manifest.json.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
