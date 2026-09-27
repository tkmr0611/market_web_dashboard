"""indicators.toml に並べた指標を取得して、サイト用の JSON（site/data/dashboard.json）を書き出す。"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import logging
import os
import time
import tomllib
from pathlib import Path

import pandas as pd
import requests

from .sources import SOURCES

ROOT = Path(__file__).resolve().parents[1]
JST = dt.timezone(dt.timedelta(hours=9), "JST")
META_DEFAULTS = {"unit": "", "decimals": 2, "change": "pct", "note": ""}
META_KEYS = ("id", "name", "section", "category", "symbol", *META_DEFAULTS)

log = logging.getLogger("collector")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--config", type=Path, default=ROOT / "indicators.toml")
    ap.add_argument("--out", type=Path, default=ROOT / "site" / "data" / "dashboard.json")
    ap.add_argument(
        "--previous",
        help="前回出力した JSON の URL かパス。取得に失敗した指標はここから引き継ぐ（省略時は --out の既存ファイル）",
    )
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)-7s %(message)s")

    config = tomllib.loads(args.config.read_text(encoding="utf-8"))
    start = dt.date.today() - dt.timedelta(days=round(365.25 * config.get("history_years", 5)))
    previous = load_previous(args.previous or args.out)

    indicators, failed = [], 0
    for spec in config["indicators"]:
        source = SOURCES[spec["source"]]
        meta = {**META_DEFAULTS, **{k: spec[k] for k in META_KEYS if k in spec}}
        label = source.label(spec) if hasattr(source, "label") else source.LABEL
        meta |= {"source": label, "source_url": source.link(spec)}
        try:
            summary = summarize(retry(lambda: source.fetch(spec, start)), start, meta["decimals"])
            indicators.append(meta | summary | {"error": None})
            log.info("%-16s %s  %s", spec["id"], summary["latest"]["date"], summary["latest"]["value"])
        except Exception as e:
            failed += 1
            message = f"{type(e).__name__}: {e}"[:300]
            warn(spec["id"], message)
            # 前回の値を残しつつ、表示設定（名前など）は最新の indicators.toml に合わせる
            indicators.append(previous.get(spec["id"], {}) | meta | {"error": message})

    if failed == len(indicators):
        log.error("すべての指標の取得に失敗したので出力しません")
        return 1

    payload = {
        "generated_at": now_jst(),
        "indicators": indicators,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    log.info("%s に書き出しました（%d 件中 %d 件失敗）", args.out, len(indicators), failed)
    return 0


def summarize(series: pd.Series, start: dt.date, decimals: int) -> dict:
    s = pd.to_numeric(series, errors="coerce").dropna().sort_index()
    s = s[~s.index.duplicated(keep="last")]
    s = s[s.index >= pd.Timestamp(start)].round(decimals)
    if len(s) < 2:
        raise ValueError(f"データ点が {len(s)} 個しかありません")
    dates = s.index.strftime("%Y-%m-%d").tolist()
    values = s.tolist()
    step = s.index.to_series().diff().median()
    return {
        "frequency": "monthly" if step > pd.Timedelta(days=20) else "daily",
        "latest": {"date": dates[-1], "value": values[-1]},
        "previous": {"date": dates[-2], "value": values[-2]},
        "fetched_at": now_jst(),
        "series": {"dates": dates, "values": values},
    }


def retry(fn, attempts: int = 3, wait: float = 5.0):
    for i in range(attempts):
        try:
            return fn()
        except Exception as e:
            if i == attempts - 1:
                raise
            log.info("  リトライします (%s)", e)
            time.sleep(wait * (i + 1))


def load_previous(src: str | Path) -> dict[str, dict]:
    try:
        if str(src).startswith(("http://", "https://")):
            r = requests.get(str(src), timeout=30)
            r.raise_for_status()
            data = r.json()
        else:
            data = json.loads(Path(src).read_text(encoding="utf-8"))
    except Exception as e:
        log.info("前回データは使いません（%s）", e)  # 初回は無くて当然
        return {}
    return {item["id"]: item for item in data.get("indicators", []) if item.get("series")}


def warn(indicator_id: str, message: str) -> None:
    if os.environ.get("GITHUB_ACTIONS"):
        print(f"::warning title={indicator_id}::{message}")  # Actions の実行結果に注釈として出る
    else:
        log.warning("%s: %s", indicator_id, message)


def now_jst() -> str:
    return dt.datetime.now(JST).isoformat(timespec="seconds")
