"""データ取得元の登録簿。

取得元を増やすときは、このフォルダにモジュールを作って
    LABEL: str                                 … 画面に出す出典名
    fetch(spec, start) -> pandas.Series        … index=日付, 値=float の Series
    link(spec) -> str                          … 出典ページの URL
を定義し、下の SOURCES に登録する。spec は indicators.toml の 1 ブロック（dict）。
出典名が spec によって変わる場合は、LABEL の代わりに label(spec) -> str を定義してもよい（spread.py）。
"""

from . import boj, ecb, fred, mof, mof_tb, spread, yahoo

SOURCES = {
    "yahoo": yahoo,
    "fred": fred,
    "mof": mof,
    "mof_tb": mof_tb,
    "boj": boj,
    "ecb": ecb,
    "spread": spread,
}
