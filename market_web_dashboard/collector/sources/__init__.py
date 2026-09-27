"""データ取得元の登録簿。

取得元を増やすときは、このフォルダにモジュールを作って
    LABEL: str                                 … 画面に出す出典名
    fetch(spec, start) -> pandas.Series        … index=日付, 値=float の Series
    link(spec) -> str                          … 出典ページの URL
を定義し、下の SOURCES に登録する。spec は indicators.toml の 1 ブロック（dict）。
"""

from . import fred, mof, yahoo

SOURCES = {
    "yahoo": yahoo,
    "fred": fred,
    "mof": mof,
}
