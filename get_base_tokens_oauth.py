"""
BASE API トークン取得スクリプト（OAuth認証フロー）
CLIENT_IDとCLIENT_SECRETを使って新規にトークンを取得
"""

import os
import webbrowser
from urllib.parse import urlencode, parse_qs, urlparse
from flask import Flask, request
import requests
import threading
import time
from dotenv import load_dotenv

load_dotenv()

CLIENT_ID = os.getenv('BASE_CLIENT_ID')
CLIENT_SECRET = os.getenv('BASE_CLIENT_SECRET')
REDIRECT_URI = 'http://localhost:8000/callback'

app = Flask(__name__)
auth_code = None
server_shutdown = False

@app.route('/callback')
def callback():
    """OAuth認証後のコールバック"""
    global auth_code, server_shutdown
    
    code = request.args.get('code')
    if code:
        auth_code = code
        server_shutdown = True
        return """
        <html>
        <body>
            <h1>✅ 認証成功！</h1>
            <p>このウィンドウを閉じて、ターミナルに戻ってください。</p>
            <script>setTimeout(function(){ window.close(); }, 3000);</script>
        </body>
        </html>
        """
    else:
        return "❌ 認証失敗", 400

def get_tokens(auth_code):
    """認証コードからトークンを取得"""
    url = 'https://api.thebase.in/1/oauth/token'
    payload = {
        'grant_type': 'authorization_code',
        'client_id': CLIENT_ID,
        'client_secret': CLIENT_SECRET,
        'code': auth_code,
        'redirect_uri': REDIRECT_URI
    }
    
    try:
        response = requests.post(url, data=payload, timeout=30)
        if response.status_code == 200:
            data = response.json()
            return data.get('access_token'), data.get('refresh_token')
        else:
            print(f"❌ トークン取得失敗: {response.status_code}")
            print(response.text)
            return None, None
    except Exception as e:
        print(f"❌ エラー: {e}")
        return None, None

def run_server():
    """Flaskサーバーを起動"""
    app.run(port=8000, debug=False, use_reloader=False)

def main():
    """メイン処理"""
    print("="*60)
    print("BASE API トークン取得スクリプト")
    print("="*60)
    
    print(f"\nデバッグ: CLIENT_ID = '{CLIENT_ID}'")
    print(f"デバッグ: CLIENT_SECRET = '{CLIENT_SECRET}'")
    
    if not CLIENT_ID or CLIENT_ID == 'your_client_id_here' or not CLIENT_SECRET or CLIENT_SECRET == 'your_client_secret_here':
        print("\n❌ .envファイルにBASE_CLIENT_IDとBASE_CLIENT_SECRETを設定してください")
        print("\n現在の値:")
        print(f"  CLIENT_ID: {CLIENT_ID}")
        print(f"  CLIENT_SECRET: {CLIENT_SECRET}")
        return
    
    print(f"\n✅ CLIENT_ID: {CLIENT_ID[:20]}...")
    print(f"✅ CLIENT_SECRET: {CLIENT_SECRET[:20]}...")
    
    # Step 1: 認証URLを生成
    auth_url = 'https://api.thebase.in/1/oauth/authorize?' + urlencode({
        'response_type': 'code',
        'client_id': CLIENT_ID,
        'redirect_uri': REDIRECT_URI,
        'scope': 'read_items write_items',
        'state': 'random_state_string'
    })
    
    print("\n" + "="*60)
    print("Step 1: ブラウザでBASE認証を実行")
    print("="*60)
    print("1. Flaskサーバーを起動します...")
    
    # サーバーを別スレッドで起動
    server_thread = threading.Thread(target=run_server, daemon=True)
    server_thread.start()
    time.sleep(2)
    
    print("2. ブラウザでBASE認証ページを開きます...")
    webbrowser.open(auth_url)
    
    print("\n👉 ブラウザで以下の操作を行ってください：")
    print("   - BASEにログイン")
    print("   - アプリ連携を「許可」をクリック")
    print("   - 自動的にこのスクリプトに戻ります")
    
    # 認証コードを待つ
    print("\n⏳ 認証完了を待っています...")
    while not auth_code and not server_shutdown:
        time.sleep(1)
    
    if not auth_code:
        print("❌ 認証コードが取得できませんでした")
        return
    
    print(f"✅ 認証コード取得成功: {auth_code[:20]}...")
    
    # Step 2: トークンを取得
    print("\n" + "="*60)
    print("Step 2: トークンを取得")
    print("="*60)
    
    access_token, refresh_token = get_tokens(auth_code)
    
    if access_token and refresh_token:
        print("\n✅ トークン取得成功！")
        print("\n" + "="*60)
        print(".envファイルに以下を追加してください")
        print("="*60)
        print(f'BASE_REFRESH_TOKEN="{refresh_token}"')
        print(f'BASE_ACCESS_TOKEN="{access_token}"')
        print("="*60)
        
        # 自動で.envファイルを更新
        update = input("\n.envファイルを自動更新しますか？ (y/n): ")
        if update.lower() == 'y':
            update_env_file(refresh_token, access_token)
    else:
        print("❌ トークン取得に失敗しました")

def update_env_file(refresh_token, access_token):
    """。envファイルを更新"""
    try:
        env_path = os.path.join(os.path.dirname(__file__), '.env')
        
        with open(env_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        updated = False
        for i, line in enumerate(lines):
            if line.startswith('BASE_REFRESH_TOKEN='):
                lines[i] = f'BASE_REFRESH_TOKEN="{refresh_token}"\n'
                updated = True
            elif line.startswith('BASE_ACCESS_TOKEN='):
                lines[i] = f'BASE_ACCESS_TOKEN="{access_token}"\n'
                updated = True
        
        with open(env_path, 'w', encoding='utf-8') as f:
            f.writelines(lines)
        
        print(f"✅ .envファイルを更新しました: {env_path}")
    except Exception as e:
        print(f"❌ .envファイルの更新に失敗: {e}")

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️ 処理を中断しました")
    except Exception as e:
        print(f"\n❌ エラー: {e}")
        import traceback
        traceback.print_exc()
