from flask import Flask, request, jsonify
import threading
import os
from dotenv import load_dotenv
from stock_sync import sync_stock_mercari_to_base, sync_stock_base_to_mercari, extract_hinban, log

# .envファイルを読み込み
load_dotenv()

app = Flask(__name__)

@app.route("/webhook/mercari", methods=["POST"])
def webhook_mercari():
    """メルカリからのWebhook受信（売上通知）"""
    try:
        body = request.get_json()
        log("=== メルカリWebhook受信 ===")
        log(str(body))
        
        # メルカリの売上通知から品番を抽出
        # ※実際のメルカリWebhookのフォーマットに応じて調整が必要
        if body and 'product_name' in body:
            hinban = extract_hinban(body['product_name'])
            if hinban:
                # 非同期で在庫同期を実行
                threading.Thread(target=sync_stock_mercari_to_base, args=(hinban,)).start()
                return jsonify({"status": "ok", "hinban": hinban}), 200
        
        return jsonify({"status": "ok", "message": "no action"}), 200
    except Exception as e:
        log(f"❌ メルカリWebhookエラー: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/webhook/base", methods=["POST"])
def webhook_base():
    """BASEからのWebhook受信（売上通知）"""
    try:
        body = request.get_json()
        log("=== BASEWebhook受信 ===")
        log(str(body))
        
        # BASEの売上通知から品番を抽出
        # ※BASEのWebhookフォーマットに応じて調整
        if body and 'item' in body:
            item_title = body['item'].get('title', '')
            item_detail = body['item'].get('detail', '')
            
            hinban = extract_hinban(item_title) or extract_hinban(item_detail)
            if hinban:
                # 非同期で在庫同期を実行
                threading.Thread(target=sync_stock_base_to_mercari, args=(hinban,)).start()
                return jsonify({"status": "ok", "hinban": hinban}), 200
        
        return jsonify({"status": "ok", "message": "no action"}), 200
    except Exception as e:
        log(f"❌ BASEWebhookエラー: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/webhook", methods=["POST"])
def webhook():
    """汎用Webhook（LINEなど、既存のもの）"""
    body = request.get_json()
    print("=== Webhook受信 ===")
    print(body)

    # グループIDが含まれていれば表示
    if body and "events" in body:
        for event in body["events"]:
            src = event.get("source", {})
            if src.get("type") == "group":
                print(f"グループID: {src.get('groupId')}")

    return "OK", 200

@app.route("/health", methods=["GET"])
def health():
    """ヘルスチェック"""
    return jsonify({"status": "running"}), 200

if __name__ == "__main__":
    log("🚀 Webhookサーバー起動: http://localhost:5000")
    log("  - メルカリ: /webhook/mercari")
    log("  - BASE: /webhook/base")
    app.run(host='0.0.0.0', port=5000, debug=True)