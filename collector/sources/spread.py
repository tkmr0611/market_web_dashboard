"""2 つの系列の差（1 本目 − 2 本目）。イールドギャップ（10 年 − 3 か月など）に使う。

indicators.toml では legs に、他の取得元での指定を 2 つ書く:
    legs = [{ source = "mof", symbol = "10年" }, { source = "mof_tb", symbol = "3か月" }]
日付は 1 本目に合わせる。2 本目は直近の値を引き継ぐので、週次（T-Bill の入札など）と日次の差も取れる。
"""

from __future__ import annotations

import datetime as dt

import pandas as pd


def fetch(spec: dict, start: dt.date) -> pd.Series:
    a, b = (_sources()[leg["source"]].fetch(leg, start) for leg in _legs(spec))
    a = pd.to_numeric(a, errors="coerce").dropna().sort_index()
    b = pd.to_numeric(b, errors="coerce").dropna().sort_index()
    a, b = a[~a.index.duplicated(keep="last")], b[~b.index.duplicated(keep="last")]
    b_on_a = b.reindex(a.index.union(b.index)).ffill().reindex(a.index)
    return (a - b_on_a).dropna()


def label(spec: dict) -> str:
    return " / ".join(dict.fromkeys(_sources()[leg["source"]].LABEL for leg in _legs(spec)))


def link(spec: dict) -> str:
    first = _legs(spec)[0]
    return _sources()[first["source"]].link(first)


def _legs(spec: dict) -> list[dict]:
    legs = spec.get("legs", [])
    if len(legs) != 2:
        raise ValueError("spread には legs を 2 つ指定してください")
    return legs


def _sources():
    from . import SOURCES  # 循環 import を避けるため遅延

    return SOURCES
