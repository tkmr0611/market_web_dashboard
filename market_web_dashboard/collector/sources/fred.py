"""FRED（セントルイス連銀）。API キー不要の CSV 配信を使う。"""

from __future__ import annotations

import datetime as dt
import io

import pandas as pd
import requests

LABEL = "FRED"
CSV_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv"


def fetch(spec: dict, start: dt.date) -> pd.Series:
    # ブラウザ風の User-Agent を付けるとボット判定でタイムアウトさせられるので、requests の既定のままにする
    r = requests.get(CSV_URL, params={"id": spec["symbol"], "cosd": start.isoformat()}, timeout=60)
    r.raise_for_status()
    df = pd.read_csv(io.StringIO(r.text), na_values=["."])
    return pd.Series(
        pd.to_numeric(df.iloc[:, 1], errors="coerce").to_numpy(),
        index=pd.to_datetime(df.iloc[:, 0]),
    )


def link(spec: dict) -> str:
    return f"https://fred.stlouisfed.org/series/{spec['symbol']}"
