# BASE CSV ダウンローダー

BASE管理画面からCSVをダウンロードして、正確な在庫数を取得するスクリプトです。

## 🎯 目的

BASE APIの在庫数が不正確なため、管理画面から直接CSVをダウンロードして正確な在庫数を取得します。

## ⚙️ 事前準備

### 1. 環境変数の設定

`.env` ファイルに以下を追加してください：

```env
BASE_EMAIL=your_email@example.com
BASE_PASSWORD=your_password
```

### 2. 必要なパッケージのインストール

```bash
pip install playwright pandas python-dotenv
playwright install chromium
```

## 🚀 使用方法

### 基本実行

```bash
python base_csv_downloader.py
```

### 処理の流れ

1. BASE管理画面にログイン
2. 商品一覧ページに移動
3. CSVダウンロードボタンを自動クリック
4. ダウンロードしたCSVを `products_base.csv` に保存

### 自動ダウンロードが失敗した場合

スクリプトが自動でダウンロードボタンを見つけられない場合：

1. ブラウザが開いたまま待機状態になります
2. 手動でCSVダウンロードボタンをクリックしてください
3. ダウンロード完了後、Enterキーを押してください

## 📊 出力

### 出力ファイル

- `products_base.csv` - 最新の商品・在庫データ
- `downloads/base_products_YYYYMMDD_HHMMSS.csv` - タイムスタンプ付きバックアップ

### CSV列

- 品番
- 商品ID
- 商品名
- 在庫数 / 現在の在庫数
- 公開状態
- その他（BASE管理画面のCSV形式に依存）

## 🔗 連携

ダウンロードした `products_base.csv` は自動的に `all_stock.py` で使用されます。

```bash
# BASE在庫を更新
python base_csv_downloader.py

# 全プラットフォームの在庫を確認
cd stock
python all_stock.py
```

## ⚠️ 注意事項

### ログイン情報のセキュリティ

- `.env` ファイルは必ず `.gitignore` に追加してください
- パスワードは平文で保存されるため、取り扱いに注意してください

### BASE管理画面の変更

BASE管理画面のUIが変更された場合、CSVダウンロードボタンのセレクタを更新する必要があります。

### ブラウザ表示

ログイン確認のため、ブラウザは非ヘッドレスモード（表示あり）で起動します。

## 🛠️ トラブルシューティング

### ログインに失敗する

- `.env` ファイルのメールアドレスとパスワードを確認
- BASEアカウントが有効か確認
- 2段階認証が有効になっている場合は無効化が必要

### CSVダウンロードボタンが見つからない

- BASE管理画面のUIが変更された可能性があります
- 手動でダウンロードしてください
- 開発者に報告してスクリプトを更新してもらってください

### ダウンロードが途中で止まる

- タイムアウト設定を延長（現在30秒）
- ネットワーク接続を確認

## 📝 コード例

### .envファイル

```env
# BASE認証情報
BASE_EMAIL=shop@example.com
BASE_PASSWORD=SecurePassword123

# その他のBASE設定（all_stock.pyでは不要になりました）
# BASE_CLIENT_ID=...
# BASE_CLIENT_SECRET=...
# BASE_REFRESH_TOKEN=...
```

## ✅ 完了メッセージ

正常に完了すると以下のメッセージが表示されます：

```
============================================================
✅ 処理完了
============================================================

📄 出力ファイル: C:\...\products_base.csv
💡 このファイルが all_stock.py で使用されます
```

## 🔄 定期実行

毎日自動実行する場合は、Windows タスクスケジューラやcronで設定してください。

```bash
# 例：毎日午前9時に実行
# タスクスケジューラで以下のコマンドを登録
python C:\Users\...\base_csv_downloader.py
```
