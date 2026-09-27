"""財務省「国庫短期証券（T-Bill）の入札結果」。3か月・6か月・1年物の平均落札利回り（入札ごと＝ほぼ週次）。

過去分は Excel（fb_historical_data.xls、年度ごとのシート）にまとまっているが、更新は月 1 回程度。
それより新しい分は、入札カレンダー（月ごとのページ）から個別の入札結果ページを辿って補う。
"""

from __future__ import annotations

import datetime as dt
import functools
import io
import re
from urllib.parse import urljoin

import pandas as pd
import requests

LABEL = "財務省"
HISTORY_URL = "https://www.mof.go.jp/jgbs/reference/appendix/fb_historical_data.xls"
CALENDAR_URL = "https://www.mof.go.jp/jgbs/auction/calendar/{yymm}.htm"
# 年限 → (発行日から償還日までの日数の範囲, 入札カレンダー上の表記)
TENORS = {
    "3か月": ((80, 100), "3ヶ月"),
    "6か月": ((170, 195), "6ヶ月"),
    "1年": ((350, 380), "1年"),
}
RECENT_MONTHS = 3  # 入札カレンダーを遡る月数（Excel の更新遅れを埋める分）


def fetch(spec: dict, start: dt.date) -> pd.Series:
    if spec["symbol"] not in TENORS:
        raise KeyError(f"年限 {spec['symbol']!r} は未対応です（候補: {', '.join(TENORS)}）")
    s = _history(spec["symbol"])
    recent = _recent(spec["symbol"], s.index.max() if len(s) else pd.Timestamp(start))
    s = pd.concat([s, recent])
    return s[~s.index.duplicated(keep="last")].sort_index()


def link(spec: dict) -> str:
    return "https://www.mof.go.jp/jgbs/auction/calendar/index.htm"


def _history(tenor: str) -> pd.Series:
    (lo, hi), _ = TENORS[tenor]
    records = {}
    for df in _load_history().values():
        for row in df.itertuples(index=False):
            # 回号が数値の行だけがデータ行。列: 回号, 入札日, 発行日, 償還日, …, 平均利回（9 列目）
            if not isinstance(row[0], (int, float)) or pd.isna(row[0]):
                continue
            auction, issue, maturity, yield_ = row[1], row[2], row[3], row[8]
            try:
                days = (pd.Timestamp(maturity) - pd.Timestamp(issue)).days
            except (TypeError, ValueError):
                continue
            if lo <= days <= hi:
                records[pd.Timestamp(auction)] = pd.to_numeric(yield_, errors="coerce")
    return pd.Series(records, dtype=float)


@functools.cache
def _load_history() -> dict[str, pd.DataFrame]:
    r = requests.get(HISTORY_URL, timeout=60)
    r.raise_for_status()
    return pd.read_excel(io.BytesIO(r.content), sheet_name=None, header=None)


def _recent(tenor: str, after: pd.Timestamp) -> pd.Series:
    _, label = TENORS[tenor]
    records = {}
    for date, url in _calendar_results(label):
        if date > after:
            records[date] = _auction_yield(url)
    return pd.Series(records, dtype=float)


def _calendar_results(label: str) -> list[tuple[pd.Timestamp, str]]:
    """直近数か月の入札カレンダーから、指定年限の T-Bill 入札結果ページ（日付, URL）を集める。"""
    results = []
    month = dt.date.today().replace(day=1)
    for _ in range(RECENT_MONTHS):
        for row in _calendar_rows(month.strftime("%y%m")):
            if f"国庫短期証券（{label}）" not in re.sub(r"<[^>]+>", "", row):
                continue
            m = re.search(r'href="\s*([^"]*tbill[^"]*resul(\d{8})\.htm)"', row)
            if m:
                results.append((pd.Timestamp(m.group(2)), urljoin(CALENDAR_URL, m.group(1))))
        month = (month - dt.timedelta(days=1)).replace(day=1)
    return results


def _calendar_rows(yymm: str) -> list[str]:
    r = requests.get(CALENDAR_URL.format(yymm=yymm), timeout=60)
    if r.status_code == 404:
        return []  # 先の月などページが無い
    r.raise_for_status()
    return re.findall(r"<tr.*?</tr>", r.content.decode("utf-8", "replace"), re.S)


def _auction_yield(url: str) -> float:
    r = requests.get(url, timeout=60)
    r.raise_for_status()
    text = re.sub(r"\s+", "", re.sub(r"<[^>]+>", " ", r.content.decode("utf-8", "replace")))
    m = re.search(r"募入平均利回り[）)]?[（(]([－−\-△▲]?[\d.]+)[％%]", text)
    if not m:
        raise ValueError(f"平均利回りが見つかりません: {url}")
    value = m.group(1)
    return -float(value[1:]) if value[0] in "－−-△▲" else float(value)
