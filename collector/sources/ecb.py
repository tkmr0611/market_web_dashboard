"""ECB（欧州中央銀行）Data Portal の API。ユーロ圏の政策金利・国債イールドカーブ・失業率など。

symbol は「データセット/系列キー」（例: FM/D.U2.EUR.4F.KR.DFR.LEV）。
https://data.ecb.europa.eu/ で系列を開くと、ページ上部に「FM.D.U2.EUR.4F.KR.DFR.LEV」の形で載っている
（先頭の「FM.」をデータセット名として / で区切る）。
"""

from __future__ import annotations

import datetime as dt
import functools
import io

import pandas as pd
import requests

LABEL = "ECB"
API_URL = "https://data-api.ecb.europa.eu/service/data/{symbol}"


def fetch(spec: dict, start: dt.date) -> pd.Series:
    return _load(spec["symbol"], start).copy()


def link(spec: dict) -> str:
    flow, key = spec["symbol"].split("/", 1)
    return f"https://data.ecb.europa.eu/data/datasets/{flow}/{flow}.{key}"


@functools.cache
def _load(symbol: str, start: dt.date) -> pd.Series:
    """イールドギャップで同じ系列（10 年など）を何度も使うのでキャッシュ。"""
    params = {"format": "csvdata", "detail": "dataonly", "startPeriod": start.isoformat()}
    r = requests.get(API_URL.format(symbol=symbol), params=params, timeout=60)
    r.raise_for_status()
    df = pd.read_csv(io.StringIO(r.text))
    # 月次は「2026-08」の形なので、月初の日付になる
    return pd.Series(pd.to_numeric(df["OBS_VALUE"], errors="coerce").to_numpy(), index=pd.to_datetime(df["TIME_PERIOD"]))
