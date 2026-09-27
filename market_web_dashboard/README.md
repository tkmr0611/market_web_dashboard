# Market Dashboard

日米の株価指数・国債利回り・失業率・為替を一覧表示する、自分用のダッシュボードです。
データの収集から公開まで無料で動きます。

```
GitHub Actions（毎時）                          GitHub Pages
┌─────────────────────────────┐               ┌──────────────────────┐
│ python -m collector         │  site/ を     │ index.html / app.js  │
│  ├ Yahoo Finance (yfinance) │  デプロイ ──▶ │ data/dashboard.json  │──▶ ブラウザ
│  ├ FRED (CSV)               │               └──────────────────────┘
│  └ 財務省 国債金利 (CSV)      │
└─────────────────────────────┘
```

- **収集**: Python（`collector/`）。`indicators.toml` に並べた指標を取得して `site/data/dashboard.json` を作る
- **表示**: 静的な HTML/JS（`site/`）。外部ライブラリなし。ミニチャートは SVG で自前描画
- **実行・公開**: GitHub Actions が 1 時間ごとに収集して GitHub Pages に公開

## なぜ Cloudflare Workers ではなく GitHub Actions か

| | GitHub Actions + Pages（採用） | Cloudflare Workers + Cron |
|---|---|---|
| Python | 普通の Python。pandas も yfinance もそのまま使える | Python Workers はベータで、yfinance や pandas は動かない。実質 JS で書くことになる |
| 実行時間 | 1 回 6 時間まで | 無料プランは CPU 10ms/回。財務省の CSV（約 1MB）を読むだけで超えかねない |
| Yahoo からの取得 | 普通に取れる | Cloudflare の IP は Yahoo に弾かれることがある |
| 費用 | 公開リポジトリなら Actions も Pages も無料・無制限 | 無料 |

Cloudflare は表示側（Cloudflare Pages）で使うと便利な場面があります。詳しくは後述の「Cloudflare Pages に載せたい場合」を参照してください。

## セットアップ（初回だけ・10 分くらい）

1. GitHub で新しいリポジトリを **Public** で作る（例: `market-dashboard`）。Private にすると GitHub Pages が有料になります
2. このフォルダを push する

   ```bash
   git init -b main
   git add .
   git commit -m "Initial commit"
   git remote add origin https://github.com/<ユーザー名>/market-dashboard.git
   git push -u origin main
   ```

3. リポジトリの **Settings → Pages → Build and deployment → Source** を **GitHub Actions** にする
4. **Actions** タブ → `update-dashboard` → **Run workflow** で 1 回手動実行する（push 時の実行は、手順 3 の前だと失敗するため）
5. `https://<ユーザー名>.github.io/market-dashboard/` を開く

以降は毎時自動で更新されます。取得に失敗した指標があると、Actions の実行結果に警告が出ます。画面では、その指標の名前の横に ⚠ が付いて前回の値が表示されます。

## ローカルで動かす

```bash
pip install -r requirements.txt
python -m collector
python -m http.server 8000 -d site
```

ブラウザで http://localhost:8000 を開きます。

## 指標を増やす

`indicators.toml` に `[[indicators]]` ブロックを足すだけです。国を増やすときは `[countries]` にも 1 行足します。

```toml
[[indicators]]
id = "vix"                 # 一意な ID
name = "VIX"
country = "US"
category = "株価指数"
source = "yahoo"           # yahoo / fred / mof
symbol = "^VIX"
decimals = 2
change = "pct"             # pct（%表示）/ bp（金利）/ diff（差）
```

- Yahoo のティッカーは https://finance.yahoo.com で検索します（例: ユーロ/円 `EURJPY=X`、金先物 `GC=F`、DAX `^GDAXI`）
- FRED の系列 ID は https://fred.stlouisfed.org で検索します（例: 米 CPI `CPIAUCSL`、FF 金利 `DFF`）
- 新しい取得元（e-Stat、日銀など）を足すときは、`collector/sources/` にモジュールを作って `SOURCES` に登録します。書き方は `collector/sources/__init__.py` を参照してください

## データについての注意

| 指標 | 取得元 | 注意 |
|---|---|---|
| 株価指数・為替・米 10/30 年債 | Yahoo Finance | 15〜20 分程度の遅延。取引時間中は当日の途中値 |
| TOPIX | Yahoo（ETF 1306） | TOPIX 指数そのものは無料で安定して取れる配信元が無いので、連動 ETF の価格で代用しています |
| 日本国債 | 財務省 | 翌営業日に公表されるので 1 営業日遅れます |
| 米 2 年債 | FRED | Yahoo に 2 年債が無いため。1 営業日遅れます |
| 日本の失業率 | FRED（OECD） | 総務省の公表より 1 か月ほど遅れます。すぐ知りたい場合は e-Stat API（無料登録）の取得元を足してください |
| 米失業率 | FRED | 雇用統計の発表当日に反映されます |

実装上のメモ:

- FRED はブラウザ風の User-Agent を付けるとタイムアウトさせられます。`requests` の既定のまま使ってください
- Yahoo のデータには、価格が 1/10 で記録された日が混ざることがあります（1306.T で実例あり）。価格系の指標では、前後 1 週間の中央値から 2 倍以上ずれた点を捨てています
- 公開リポジトリの定期実行は、60 日間リポジトリに動きが無いと GitHub に自動停止されます。ワークフローの最後で有効化し直していますが、それでも止まった場合は Actions タブから再開できます。止まる前には GitHub からメールが届きます。画面も、3 時間以上更新が無いとヘッダーに ⚠ が出ます

## Cloudflare Pages に載せたい場合

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

## ファイル構成

```
indicators.toml          表示する指標の一覧（ここを編集して拡張）
collector/
  build.py               取得 → 整形 → JSON 書き出し
  sources/
    yahoo.py             Yahoo Finance（yfinance）
    fred.py              FRED
    mof.py               財務省 国債金利情報
site/
  index.html, app.js, style.css
  data/dashboard.json    収集結果（自動生成・コミットしない）
.github/workflows/update.yml   毎時実行 → GitHub Pages へ公開
```
