# Market Dashboard

日米の株価指数・国債利回り・失業率・為替を一覧表示する、自分用のダッシュボードです。
GitHub Actions が 1 時間ごとにデータを集め、GitHub Pages に公開します。

仕組みや各部品の詳しい仕様は [docs/spec.md](docs/spec.md) を参照してください。

## セットアップ

初回だけ行います（10 分くらい）。

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

以降は毎時自動で更新されます。取得に失敗した指標があると、Actions の実行結果に警告が出ます。画面では、その指標の名前の横に ⚠ が付き、前回の値が表示されます。

## ローカルで動かす

Python 3.11 以上が必要です。

```bash
pip install -r requirements.txt
python -m collector                  # site/data/dashboard.json を作る
python -m http.server 8000 -d site   # 表示用のサーバーを起動する
```

ブラウザで http://localhost:8000 を開きます。データを新しくしたいときは `python -m collector` をもう一度実行して、ブラウザを再読み込みします。

## 指標を増やす

`indicators.toml` に `[[indicators]]` ブロックを 1 つ足すだけです。上から書いた順に表示されます。国を増やすときは `[countries]` にも 1 行足します。

```toml
[[indicators]]
id = "vix"                 # 一意な ID
name = "VIX"               # 表示名
country = "US"             # [countries] のキー
category = "株価指数"       # 国カード内の小見出し
source = "yahoo"           # yahoo / fred / mof
symbol = "^VIX"            # 取得元での識別子
decimals = 2               # 小数点以下の桁数
change = "pct"             # pct（株価・為替）/ bp（金利）/ diff（失業率など）
# unit = "%"               # 値の後ろに付ける単位（省略可）
# note = "..."             # 詳細欄に出す注記（省略可）
```

`symbol` の探し方:

| `source` | 探し方 | 例 |
|---|---|---|
| `yahoo` | https://finance.yahoo.com で検索 | ユーロ/円 `EURJPY=X`、金先物 `GC=F`、DAX `^GDAXI` |
| `fred` | https://fred.stlouisfed.org で検索 | 米 CPI `CPIAUCSL`、FF 金利 `DFF` |
| `mof` | 財務省の国債金利の列名 | `1年`、`5年`、`20年`、`40年` |

追加したら、上の「ローカルで動かす」の手順で表示を確認してから push します。push すると自動で公開されます。

新しい取得元（e-Stat、日銀など）を足すときは、`collector/sources/` にモジュールを作り、`collector/sources/__init__.py` の `SOURCES` に登録します。作り方は [docs/spec.md](docs/spec.md#取得元) を参照してください。
