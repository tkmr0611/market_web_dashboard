"""日本銀行「時系列統計データ検索サイト」の API。コールレートなど。

symbol は「DB 名/系列コード」（例: FM01/STRDCLUCON）。どちらも検索サイトの系列情報に載っている。
"""

from __future__ import annotations

import csv
import datetime as dt
import io

import pandas as pd
import requests

LABEL = "日本銀行"
API_URL = "https://www.stat-search.boj.or.jp/api/v1/getDataCode"


def fetch(spec: dict, start: dt.date) -> pd.Series:
    db, code = spec["symbol"].split("/", 1)
    params = {"format": "csv", "lang": "en", "db": db, "code": code, "startDate": start.strftime("%Y%m")}
    records = {}
    while True:
        r = requests.get(API_URL, params=params, timeout=60)
        r.raise_for_status()
        rows = list(csv.reader(io.StringIO(r.content.decode("utf-8"))))
        meta = {row[0]: row[1:] for row in rows if row and row[0] in ("STATUS", "MESSAGE", "NEXTPOSITION")}
        if meta.get("STATUS", [""])[0] != "200":
            raise ValueError(f"日銀 API エラー: {meta.get('MESSAGE')}")
        header = next(i for i, row in enumerate(rows) if row and row[0] == "SERIES_CODE")
        for row in rows[header + 1 :]:
            if len(row) >= 8 and row[7] not in ("", "null"):
                records[_parse_date(row[6])] = float(row[7])
        next_position = (meta.get("NEXTPOSITION") or [""])[0]
        if not next_position:
            break
        params["startPosition"] = next_position  # 件数が多いと分割して返ってくる
    return pd.Series(records, dtype=float)


def link(spec: dict) -> str:
    return "https://www.stat-search.boj.or.jp/"


def _parse_date(text: str) -> pd.Timestamp:
    # 日次は YYYYMMDD、月次は YYYYMM
    return pd.Timestamp(int(text[:4]), int(text[4:6]), int(text[6:8]) if len(text) == 8 else 1)
