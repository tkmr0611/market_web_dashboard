"""財務省「国債金利情報」。日本国債の年限別利回り（日次）。

公開 CSV は 2 本に分かれている:
  data/jgbcm_all.csv … 1974 年〜前月末
  jgbcm.csv          … 当月分
どちらも Shift_JIS で、日付は和暦（例: R8.9.25）。
"""

from __future__ import annotations

import csv
import datetime as dt
import functools
import io
import re

import pandas as pd
import requests

LABEL = "財務省"
BASE = "https://www.mof.go.jp/jgbs/reference/interest_rate/"
CSV_URLS = [BASE + "data/jgbcm_all.csv", BASE + "jgbcm.csv"]
ERA_OFFSET = {"M": 1867, "T": 1911, "S": 1925, "H": 1988, "R": 2018}  # 元年 = offset + 1


def fetch(spec: dict, start: dt.date) -> pd.Series:
    table = _load_table()
    if spec["symbol"] not in table.columns:
        raise KeyError(f"列 {spec['symbol']!r} がありません（候補: {', '.join(table.columns)}）")
    return table[spec["symbol"]]


def link(spec: dict) -> str:
    return BASE + "index.htm"


@functools.cache
def _load_table() -> pd.DataFrame:
    """2 本の CSV を読んで 1 つの表（index=日付, 列=年限）にする。2年・10年…で使い回すのでキャッシュ。"""
    frames = []
    for url in CSV_URLS:
        r = requests.get(url, timeout=60)
        r.raise_for_status()
        rows = list(csv.reader(io.StringIO(r.content.decode("cp932"))))
        header = next(row for row in rows if row and row[0] == "基準日")
        records = {}
        for row in rows:
            date = _parse_wareki(row[0]) if row else None
            if date is not None:
                records[date] = [_to_float(x) for x in row[1 : len(header)]]
        frames.append(pd.DataFrame.from_dict(records, orient="index", columns=header[1:]))
    table = pd.concat(frames)
    return table[~table.index.duplicated(keep="last")].sort_index()


def _parse_wareki(text: str) -> pd.Timestamp | None:
    m = re.fullmatch(r"([MTSHR])(\d+)\.(\d+)\.(\d+)", text.strip())
    if not m:
        return None  # 見出し行や注記行
    era, year, month, day = m.groups()
    return pd.Timestamp(ERA_OFFSET[era] + int(year), int(month), int(day))


def _to_float(text: str) -> float | None:
    try:
        return float(text)
    except ValueError:
        return None  # 「-」= 未発行の年限
