# メルカリ ⇔ BASE 在庫連動システム

## 📋 概要
メルカリShopsとBASEショップの在庫を双方向で自動連動するシステムです。
商品名・説明文の**最初の数字を品番**として商品を紐付けます。

## ✨ 機能
- ✅ **双方向同期**: メルカリで売れたらBASEの在庫を0に、BASEで売れたらメルカリの在庫を0に
- ✅ **品番自動抽出**: 商品名・説明文から自動で品番を検出
- ✅ **リアルタイム連動**: Webhook経由で即座に同期
- ✅ **定期同期**: 30分ごとに全商品の在庫を自動チェック
- ✅ **手動実行**: 個別の品番や全商品を手動で同期可能

## 📁 ファイル構成
```
base_products_fetcher.py   # BASE商品取得スクリプト（全商品→CSV）
stock_sync.py              # 在庫同期メインスクリプト
webhook_server.py          # Webhookサーバー（リアルタイム同期用）
stock_sync_scheduler.py    # 定期実行スクリプト
.env                       # BASE API認証設定（要作成）
.env.example               # 設定テンプレート
products_base.csv          # BASE商品データ（自動生成）
base_products_fetcher.bat  # BASE商品取得用
stock_sync.bat             # 手動実行用
webhook_server.bat         # Webhookサーバー起動用
stock_sync_scheduler.bat   # 定期実行起動用
stock_sync_log.txt         # 実行ログ
```

## ⚙️ 初期設定

### 1. 必要なパッケージをインストール
```bash
pip install flask requests schedule
```

### 2. .env ファイルを作成
`.env.example` をコピーして `.env` にリネームし、実際の値を入力します。

```bash
BASE_CLIENT_ID=あなたのクライアントID
BASE_CLIENT_SECRET=あなたのクライアントシークレット
BASE_REFRESH_TOKEN=あなたのリフレッシュトークン
BASE_ACCESS_TOKEN=あなたのアクセストークン
BASE_SHOP_ID=dorekai
```

**BASE API認証情報の取得方法:**
1. BASE Developers (https://developers.thebase.com/) にアクセス
2. アプリを作成してCLIENT_ID・CLIENT_SECRETを取得
3. OAuth認証を実行してREFRESH_TOKEN・ACCESS_TOKENを取得
4. または、WordPress管理画面 → BASE商品メニューで認証後、データベースから取得

### 3. BASE商品データを取得
**重要: 在庫連動の前に、まずBASE商品をCSVに保存してください**

```
base_products_fetcher.bat をダブルクリック
```

- BASE APIから全商品を取得して `products_base.csv` に保存
- API制限で全商品取得できない場合でも、取得できた分だけ連動可能
- 定期的に実行して最新の商品情報に更新することを推奨

### 4. products_mercari.csv の確認
- 品番列が正しく入力されているか確認
- 品番は商品名の最初の数字（例: "607 SOBRE..." → 品番: 607）

## 🚀 使い方

### 🔹 定期自動同期（推奨）
30分ごとに自動で全商品の在庫を同期します。

**起動:**
```
stock_sync_scheduler.bat をダブルクリック
```
または
```bash
python stock_sync_scheduler.py
```

**動作:**
- 起動時に1度全商品を同期
- その後30分ごとに自動実行
- バックグラウンドで動作

---

### 🔹 Webhookリアルタイム同期
メルカリ/BASEからのWebhookを受信して即座に在庫を同期します。

**起動:**
```
webhook_server.bat をダブルクリック
```
または
```bash
python webhook_server.py
```

**Webhook URL設定:**
- **メルカリ用**: `http://あなたのサーバー:5000/webhook/mercari`
- **BASE用**: `http://あなたのサーバー:5000/webhook/base`

**※注意:**
- 外部からアクセスできるようにポート転送/ngrokなどが必要
- メルカリShops/BASEの管理画面でWebhook URLを設定

---

### 🔹 手動同期
個別に在庫を同期したい場合に使用します。

**起動:**
```
stock_sync.bat をダブルクリック
```

**選択肢:**
1. **全商品同期** - すべての商品の在庫を一括チェック
2. **メルカリ→BASE** - 品番を指定してBASEの在庫を0にする
3. **BASE→メルカリ** - 品番を指定してメルカリの在庫を0にする

---

## 📊 動作ロジック

### 品番抽出ルール
```python
商品名: "607 SOBRE ソブレ キャバドレス..."
→ 品番: "607"

商品名: "EmiriaWiz エミリアウィズ..."
説明文: "123 新品未使用..."
→ 品番: "123" (説明文から抽出)
```

### 在庫同期ルール
```
メルカリ在庫: 0, BASE在庫: 1
→ BASE在庫を0に更新

BASE在庫: 0, メルカリ在庫: 1
→ メルカリ在庫を0に更新（CSV更新）

両方とも在庫あり、または両方とも在庫なし
→ 何もしない
```
BASE API取得制限
現在、BASE APIでは約644件までしか取得できない制限があります。
**対策:**
1. **CSV方式（推奨）**: `base_products_fetcher.py` で取得できた商品のみ連動
   - `stock_sync.py` の `USE_BASE_CSV = True` に設定（デフォルト）
   - 取得できた644件だけでも在庫連動可能
2. **BASE側に問い合わせ**: 全商品取得の可否を確認（別途対応必要）

現状では **取得できた644件のみ在庫連動** されます。残りの商品は手動で管理してください。

### 
## 📝 ログ確認
すべての同期処理は `stock_sync_log.txt` に記録されます。

```
[2026-02-17 10:30:15] 🔄 全商品在庫同期を開始
[2026-02-17 10:30:16] ✅ メルカリ商品読込: 644件
[2026-02-17 10:30:20] ✅ BASE商品読込: 644件
[2026-02-17 10:30:20] 📊 共通品番: 620件
[2026-02-17 10:30:22] 🔄 メルカリ在庫0 → BASE在庫を0に (品番: 607)
[2026-02-17 10:30:23] ✅ 在庫同期完了: 3件を同期
```

## ⚠️ 制約事項

### メルカリShops API
現在、メルカリShopsの在庫更新はCSVのみ対応しています。
**実際にメルカリShopsの在庫を変更するには**、以下のいずれかが必要です：

1. **手動アップロード**: 更新後の `products_mercari.csv` を管理画面からアップロード
2. **Selenium自動化**: 既存の `mercari_shops_exhibitor.py` を拡張して在庫更新機能を追加
3. **公式API待ち**: メルカリShopsが在庫更新APIを提供するまで待つ

### BASE API
BASE APIの在庫更新は `/items/edit` エンドポイントを使用します。
トークンの有効期限切れに注意してください（定期的な再認証が必要）。

## 🔧 トラブルシューティング

### Q: BASEの在庫が更新されない
**A:** 以下を確認してください：
- `.env` ファイルの `BASE_ACCESS_TOKEN` が正しいか
- トークンの有効期限が切れていないか
- `stock_sync_log.txt` にエラーメッセージがないか

### Q: 品番が認識されない
**A:** 商品名または説明文の**最初**に数字があることを確認してください。
```
OK: "607 キャバドレス..."
NG: "キャバドレス 607" (最初にない)
```

### Q: メルカリの在庫が実際に減らない
**A:** 現在はCSV更新のみです。メルカリShops管理画面から手動でCSVをアップロードするか、Selenium自動化を追加してください。

## 📞 サポート
問題が発生した場合は `stock_sync_log.txt` を確認してください。
