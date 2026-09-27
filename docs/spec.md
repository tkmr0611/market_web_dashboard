# Market Dashboard 詳細仕様

セットアップと日々の使い方は [README](../README.md) を参照してください。このドキュメントは、仕組みと各部品の動きを説明します。

## 1. 概要

日米の株価指数・国債利回り・失業率・為替を 1 画面で見るための、自分用のダッシュボードです。
サーバーを持たず、無料の範囲で「データ収集 → 静的サイトの生成 → 公開」を自動で回します。

```
GitHub Actions（毎時）                          GitHub Pages
┌─────────────────────────────┐               ┌──────────────────────┐
│ python -m collector         │  site/ を     │ index.html / app.js  │
│  ├ Yahoo Finance (yfinance) │  デプロイ ──▶ │ data/dashboard.json  │──▶ ブラウザ
│  ├ FRED (CSV)               │               └──────────────────────┘
│  └ 財務省 国債金利 (CSV)      │
└─────────────────────────────┘
```

| 層 | 実装 | 役割 |
|---|---|---|
| 設定 | `indicators.toml` | 表示する指標・国・表示形式を宣言する。唯一の編集ポイント |
| 収集 | `collector/`（Python） | 各取得元から時系列を取り、整形して `site/data/dashboard.json` を書き出す |
| 表示 | `site/`（HTML/CSS/JS） | JSON を読んで表とチャートを描く。外部ライブラリなし |
| 実行・公開 | `.github/workflows/update.yml` | 毎時収集して GitHub Pages に公開する |

## 2. ファイル構成

```
indicators.toml          表示する指標の一覧（ここを編集して拡張）
requirements.txt         yfinance / pandas / requests
collector/
  __main__.py            `python -m collector` の入口
  build.py               取得 → 整形 → JSON 書き出し
  sources/
    __init__.py          取得元の登録簿（SOURCES）
    yahoo.py             Yahoo Finance（yfinance）
    fred.py              FRED
    mof.py               財務省 国債金利情報
site/
  index.html, app.js, style.css
  data/dashboard.json    収集結果（自動生成・コミットしない）
.github/workflows/update.yml   毎時実行 → GitHub Pages へ公開
docs/spec.md             このドキュメント
```

## 3. 設定ファイル `indicators.toml`

### トップレベル

| キー | 型 | 説明 |
|---|---|---|
| `history_years` | 数値 | チャート用に遡って取得する年数（既定 5）。取得開始日は `今日 − 365.25 × history_years 日` |
| `[countries]` | 表 | `国コード = "表示名"`。書いた順に国カードが並ぶ |
| `[[indicators]]` | 配列 | 指標の定義。上から順に表示される |

### `[[indicators]]` のキー

| キー | 必須 | 既定値 | 説明 |
|---|---|---|---|
| `id` | ○ | | 一意な ID。前回データの引き継ぎや、画面で開いている行の管理に使う |
| `name` | ○ | | 表示名 |
| `country` | ○ | | `[countries]` のキー。この国のカードに表示される |
| `category` | ○ | | 国カード内の小見出し。初めて出てきた順に並ぶ |
| `source` | ○ | | `yahoo` / `fred` / `mof`（`collector/sources/__init__.py` の `SOURCES` のキー） |
| `symbol` | ○ | | 取得元での識別子。Yahoo のティッカー、FRED の系列 ID、財務省 CSV の列名（`2年` など） |
| `decimals` | | `2` | 小数点以下の桁数。収集時の丸めと表示の両方に使う |
| `change` | | `pct` | 前回比の表し方（下表） |
| `unit` | | `""` | 値の後ろに付ける単位 |
| `note` | | `""` | 詳細欄に出す注記 |
| `weekends` | | `false` | Yahoo のみ。`true` で土日のデータを残す（暗号資産など） |

`change` の種類:

| 値 | 用途 | 前回比の表示 | 例 |
|---|---|---|---|
| `pct` | 株価・為替 | 変化率（小数 2 桁）+ 値幅 | `+1.23%` / `+456.78` |
| `bp` | 金利 | 差 × 100 を bp で。桁数は `decimals − 2` | `+3.5bp` |
| `diff` | 失業率など | 値の差。`unit` が `%` なら `pt` を付ける | `−0.1pt` |

`change = "pct"` の指標は、Yahoo 取得時の外れ値除去（後述）の対象にもなります。

### 現在の指標

| 国 | 区分 | 指標 | 取得元 / シンボル |
|---|---|---|---|
| 日本 | 株価指数 | 日経平均株価 | Yahoo `^N225` |
| 日本 | 株価指数 | TOPIX 連動 ETF (1306) | Yahoo `1306.T` |
| 日本 | 国債利回り | 国債 2年 / 10年 / 30年 | 財務省 `2年` / `10年` / `30年` |
| 日本 | 雇用 | 完全失業率（季調） | FRED `LRUNTTTTJPM156S` |
| 日本 | 為替 | ドル/円 | Yahoo `JPY=X` |
| 米国 | 株価指数 | S&P 500 / NASDAQ 総合 / NY ダウ | Yahoo `^GSPC` / `^IXIC` / `^DJI` |
| 米国 | 国債利回り | 国債 2年 | FRED `DGS2` |
| 米国 | 国債利回り | 国債 10年 / 30年 | Yahoo `^TNX` / `^TYX` |
| 米国 | 雇用 | 失業率 | FRED `UNRATE` |

## 4. 収集（`collector/`）

### 実行方法

```
python -m collector [--config PATH] [--out PATH] [--previous URL_OR_PATH]
```

| 引数 | 既定値 | 説明 |
|---|---|---|
| `--config` | `indicators.toml` | 設定ファイル |
| `--out` | `site/data/dashboard.json` | 出力先 |
| `--previous` | `--out` の既存ファイル | 前回の JSON（URL かパス）。取得に失敗した指標をここから引き継ぐ |

### 処理の流れ（`build.py`）

1. `indicators.toml` を読み、取得開始日を決める
2. 前回の JSON を読む（読めなければ引き継ぎなしで続行）
3. 指標ごとに:
   1. `SOURCES[source].fetch(spec, start)` で時系列（`pandas.Series`、index = 日付）を取る。失敗したら 5 秒 → 10 秒待って最大 3 回試す
   2. `summarize()` で整形する
      - 数値に変換し、欠損を落として日付順に並べる
      - 同じ日付が重複したら後のほうを残す
      - 開始日より前を捨て、`decimals` 桁に丸める
      - 2 点未満ならエラー
      - 日付間隔の中央値が 20 日を超えれば `monthly`、それ以外は `daily` と判定する
   3. 失敗した場合は、前回の値に最新の表示設定（名前など）とエラー文を重ねたものを出力する。前回データも無ければ、系列なしでエラーだけを出力する
4. 全指標が失敗したら何も書かずに終了コード 1 で終わる（公開中のサイトは前回のまま残る）
5. JSON を書き出す

失敗した指標は、GitHub Actions 上では `::warning` 注釈として、ローカルではログの警告として出ます。

### 取得元

各モジュールは次の 3 つを持ちます。`spec` は `indicators.toml` の 1 ブロック（dict）です。

| 名前 | 内容 |
|---|---|
| `LABEL` | 画面に出す出典名 |
| `fetch(spec, start) -> pandas.Series` | index = 日付、値 = float の Series を返す |
| `link(spec) -> str` | 出典ページの URL |

**Yahoo Finance（`yahoo.py`）**

- `yfinance` で日足の終値（`Close`、配当などの調整なし）を取得する
- 日付は取引所の現地日付にそろえる（タイムゾーン情報は捨てる）。取引時間中は最終行が当日の途中値になる
- `weekends = true` でなければ土日の行を捨てる（為替に土日の気配値が混ざるため）
- `change = "pct"` の指標では、前後 7 点の中央値との比が 0.5 以下または 2 以上の点を捨てる。価格が 1/10 で記録された日が混ざることがあるため（1306.T で実例あり）。ゼロ近辺を動く金利には効かないので対象外にしている

**FRED（`fred.py`）**

- API キー不要の CSV（`fredgraph.csv?id=<系列>&cosd=<開始日>`）を使う
- 欠損値は `.` で表されるので NaN として読む
- ブラウザ風の User-Agent を付けるとボット判定でタイムアウトさせられるので、`requests` の既定の User-Agent のまま使う

**財務省 国債金利情報（`mof.py`）**

- 2 本の CSV（`data/jgbcm_all.csv` = 1974 年〜前月末、`jgbcm.csv` = 当月分）を読んで 1 つの表にまとめる
- 文字コードは Shift_JIS（cp932）。日付は和暦（例: `R8.9.25`）なので、元号の略字（M/T/S/H/R）から西暦に直す
- 見出し行は先頭列が `基準日` の行。和暦として読めない行（注記など）は無視する
- `-`（その年限の国債が未発行）は欠損として扱う
- 表は 1 回の実行中キャッシュして、2 年・10 年・30 年で使い回す
- 列名が無ければ、使える列名の一覧を付けてエラーにする

## 5. 出力 JSON（`site/data/dashboard.json`）

```jsonc
{
  "generated_at": "2026-09-27T10:17:42+09:00",   // 生成時刻（JST）
  "countries": [{ "code": "JP", "name": "日本" }, ...],
  "indicators": [
    {
      // indicators.toml から（既定値を補ったもの）
      "id": "nikkei225", "name": "日経平均株価", "country": "JP", "category": "株価指数",
      "symbol": "^N225", "unit": "", "decimals": 2, "change": "pct", "note": "",
      // 取得元から
      "source": "Yahoo Finance", "source_url": "https://finance.yahoo.com/quote/%5EN225",
      // 取得結果
      "frequency": "daily",                          // daily / monthly
      "latest":   { "date": "2026-09-25", "value": 45000.12 },
      "previous": { "date": "2026-09-24", "value": 44800.00 },
      "fetched_at": "2026-09-27T10:17:30+09:00",     // この指標の取得に成功した時刻
      "series": { "dates": ["2021-09-27", ...], "values": [29500.1, ...] },
      "error": null                                  // 失敗時はエラー文（最大 300 文字）
    }
  ]
}
```

- 取得に失敗し、前回データがある場合: `error` に文字列が入り、`latest` / `series` / `fetched_at` は前回のもの
- 取得に失敗し、前回データも無い場合: `series` などは無く、設定値と `error` だけになる
- 容量を抑えるため、空白なしで出力する

## 6. 表示（`site/`）

外部ライブラリを使わない静的ページです。チャートは SVG を自前で描いています。

### 画面構成

- **ヘッダー**: タイトル、最終更新時刻（「○分前」付き）、チャート期間の切り替え（1M / 3M / 1Y / 5Y）
- **国カード**: `countries` の順に 1 枚ずつ。カード内は `category` ごとに小見出しを付けて並べる
- **各行の列**: 指標名 / 現在値 / 前回比 / 期間変化 / 推移（スパークライン） / 日付
- **詳細**: 行をクリックすると、その下に軸付きの大きいチャート、出典リンク、最終取得時刻、注記、エラーを表示する。もう一度クリックすると閉じる

### 動作

| 項目 | 内容 |
|---|---|
| データの読み込み | `data/dashboard.json` をキャッシュなしで読む。開いたままのタブも 10 分ごとに読み直す |
| 読み込み失敗 | 前に読めたデータがあれば表示を続け、ヘッダーに「⚠ 再読み込みに失敗」と出す |
| 更新停止の検知 | `generated_at` から 3 時間を過ぎると、ヘッダーに「⚠ 更新が止まっている可能性があります」と出す。経過時間の表示は 1 分ごとに更新 |
| 指標の取得失敗 | 名前の横に ⚠ を付ける（マウスを乗せるとエラー文）。前回データも無ければ「取得できませんでした」と表示する |
| 期間の切り替え | 選んだ期間は `localStorage` に保存する（既定は 1Y）。最新日から N か月前までを表示し、点が 12 個未満のとき（月次データの 1M など）は 12 点まで遡る |
| 前回比 | `latest` と `previous` の差を `change` の種類に従って表示（3 章の表） |
| 期間変化 | 表示中の期間の最初の点と最後の点の差。マウスを乗せると起点の日付が出る |
| スパークライン | 期間の最初の値の水準に点線を引く（そこより上か下かがひと目で分かる） |
| 詳細チャート | 右側に目盛り（1・2・2.5・5 刻みで約 5 本）、下側に日付（幅 420px 未満は 3 個、それ以上は 5 個） |
| ホバー | どちらのチャートも、縦線が最寄りの日付に吸い付き、値と日付をツールチップに出す |
| 日付の書式 | 日次は `9/25 (木)`、月次は `2026年8月` |
| 色 | 上昇 = 緑、下落 = 赤、変化なし = 灰。日本式（上昇 = 赤）にしたければ `style.css` の `--up` / `--down` を入れ替える |
| ダークモード | OS の設定に合わせて自動で切り替わる |
| スマホ（幅 640px 以下） | 前回比・期間変化・日付の列を隠し、前回比は現在値の下に小さく出す。スパークラインも小さくする |
| 再描画 | 画面の幅が変わったときだけ描き直す（スマホのスクロールで高さだけ変わる場合は無視） |
| 安全性 | DOM は `createElement` と `textContent` で組み立て、`innerHTML` は使わない。出典リンクは `http(s)` の URL だけを使う |

## 7. 実行・公開（GitHub Actions）

`.github/workflows/update.yml`（ワークフロー名 `update-dashboard`）

| 項目 | 内容 |
|---|---|
| きっかけ | 毎時 17 分（UTC 基準の cron。GitHub 側の混雑で数分〜数十分遅れることがある）、手動実行、`main` への push |
| build ジョブ | Python 3.12 を用意 → `pip install` → `python -m collector --previous <公開中サイト>/data/dashboard.json` → `site/` を Pages 用の成果物としてアップロード |
| deploy ジョブ | `actions/deploy-pages` で GitHub Pages に公開 |
| 同時実行 | `concurrency: pages` で 1 本ずつ実行する（実行中のものは取り消さない） |
| タイムアウト | 15 分 |
| 定期実行の維持 | 公開リポジトリは 60 日間動きが無いと定期実行が自動停止されるため、定期実行のたびに `gh api` でワークフローを有効化し直す。それでも止まった場合は Actions タブから再開できる（止まる前に GitHub からメールが届く） |

前回データは、リポジトリにコミットせず、公開中のサイトから取ります。そのため `site/data/*.json` は `.gitignore` に入っています。

## 8. 設計判断: Cloudflare Workers ではなく GitHub Actions を使う理由

| | GitHub Actions + Pages（採用） | Cloudflare Workers + Cron |
|---|---|---|
| Python | 普通の Python。pandas も yfinance もそのまま使える | Python Workers はベータで、yfinance や pandas は動かない。実質 JS で書くことになる |
| 実行時間 | 1 回 6 時間まで | 無料プランは CPU 10ms/回。財務省の CSV（約 1MB）を読むだけで超えかねない |
| Yahoo からの取得 | 普通に取れる | Cloudflare の IP は Yahoo に弾かれることがある |
| 費用 | 公開リポジトリなら Actions も Pages も無料・無制限 | 無料 |

## 9. データについての注意

| 指標 | 取得元 | 注意 |
|---|---|---|
| 株価指数・為替・米 10/30 年債 | Yahoo Finance | 15〜20 分程度の遅延。取引時間中は当日の途中値 |
| TOPIX | Yahoo（ETF 1306） | TOPIX 指数そのものは無料で安定して取れる配信元が無いので、連動 ETF の価格で代用している（騰落率はほぼ一致） |
| 日本国債 | 財務省 | 翌営業日に公表されるので 1 営業日遅れる |
| 米 2 年債 | FRED | Yahoo に 2 年債が無いため。1 営業日遅れる |
| 日本の失業率 | FRED（OECD） | 総務省の公表より 1 か月ほど遅れる。すぐ知りたい場合は e-Stat API（無料登録）の取得元を足す |
| 米失業率 | FRED | 雇用統計の発表当日に反映される |

米 10 年債を終値ベースでそろえたい場合は、`source = "fred"`、`symbol = "DGS10"`、`decimals = 2` に変えます。

## 10. 公開先を Cloudflare Pages にする場合

リポジトリを Private にしたい場合や、Cloudflare Access（無料）で自分しか見られないようにしたい場合は、公開先を Cloudflare Pages にできます。

1. Cloudflare で Pages プロジェクトを「Direct Upload」で作る（例: `market-dashboard`）
2. API トークン（権限: Cloudflare Pages Edit）を作る。そのトークンとアカウント ID を、リポジトリの Secrets に `CLOUDFLARE_API_TOKEN` と `CLOUDFLARE_ACCOUNT_ID` として登録する
3. `.github/workflows/update.yml` を次のように変える
   - `configure-pages` / `upload-pages-artifact` のステップと `deploy` ジョブを消す
   - `--previous` の URL を `https://market-dashboard.pages.dev/data/dashboard.json` にする
   - 最後に次のステップを足す

   ```yaml
         - uses: cloudflare/wrangler-action@v3
           with:
             apiToken: ${{ secrets.CLOUDFLARE_API_TOKEN }}
             accountId: ${{ secrets.CLOUDFLARE_ACCOUNT_ID }}
             command: pages deploy site --project-name=market-dashboard
   ```

Cloudflare Pages の Git 連携（自動ビルド）は使いません。毎時ビルドすると、無料枠（月 500 回）を超えるためです。
Private リポジトリの Actions は月 2,000 分まで無料です。1 回 1〜2 分 × 毎時で、ほぼ上限に近くなります。気になる場合は cron を 2 時間おきにしてください。
