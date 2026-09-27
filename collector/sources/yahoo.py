"""Yahoo Finance（yfinance 経由）。株価指数・為替・米国債利回り（^TNX 等）など。"""

from __future__ import annotations

import datetime as dt
from urllib.parse import quote

import pandas as pd
import yfinance as yf

LABEL = "Yahoo Finance"


def fetch(spec: dict, start: dt.date) -> pd.Series:
    hist = yf.Ticker(spec["symbol"]).history(start=start.isoformat(), interval="1d", auto_adjust=False)
    if hist.empty:
        raise ValueError(f"{spec['symbol']} のデータが返ってきませんでした")
    close = hist["Close"].dropna()
    # 取引所の現地日付で揃える（タイムゾーン情報は捨てる）。取引時間中は最終行が当日の途中値になる
    close.index = pd.DatetimeIndex(close.index.date)
    # 為替は土日の日付で気配値が入ることがあるので落とす（暗号資産などを足すときは weekends = true）
    if not spec.get("weekends", False):
        close = close[close.index.dayofweek < 5]
    # Yahoo は価格が 1/10 などで記録された日が混ざることがあるので、価格系（change = pct）は
    # 前後 1 週間の中央値から 2 倍以上ずれた点を捨てる。ゼロ近辺を動く金利には効かないので対象外
    if spec.get("change", "pct") == "pct":
        ratio = close / close.rolling(7, center=True, min_periods=1).median()
        close = close[(ratio > 0.5) & (ratio < 2)]
    return close


def link(spec: dict) -> str:
    return f"https://finance.yahoo.com/quote/{quote(spec['symbol'], safe='')}"
