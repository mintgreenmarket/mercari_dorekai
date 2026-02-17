"""
BASE API トークン取得（簡易版）
手動でブラウザから認証コードを取得して変換
"""

import os
import requests
from dotenv import load_dotenv

load_dotenv()

CLIENT_ID = os.getenv('BASE_CLIENT_ID')
CLIENT_SECRET = os.getenv('BASE_CLIENT_SECRET')

def get_tokens_from_code(auth_code):
    """認証コードからトークンを取得"""
    url = 'https://api.thebase.in/1/oauth/token'
    
    # 複数のredirect_uriを試す
    redirect_uris = [
        'http://localhost:8000/callback',
        'https://example.com/callback',
        'https://localhost/callback',
        'http://localhost/callback'
    ]
    
    for redirect_uri in redirect_uris:
        payload = {
            'grant_type': 'authorization_code',
            'client_id': CLIENT_ID,
            'client_secret': CLIENT_SECRET,
            'code': auth_code,
            'redirect_uri': redirect_uri
        }
        
        try:
            print(f"\n試行中: redirect_uri={redirect_uri}")
            response = requests.post(url, data=payload, timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                print("\n✅ トークン取得成功！")
                print("\n" + "="*60)
                print(".envファイルに以下を追加してください")
                print("="*60)
                print(f'BASE_REFRESH_TOKEN={data.get("refresh_token")}')
                print(f'BASE_ACCESS_TOKEN={data.get("access_token")}')
                print("="*60)
                
                # 自動更新
                update = input("\n.envファイルを自動更新しますか？ (y/n): ")
                if update.lower() == 'y':
                    update_env_file(data.get("refresh_token"), data.get("access_token"))
                return True
            else:
                print(f"  ❌ 失敗: {response.status_code} - {response.text}")
        except Exception as e:
            print(f"  ❌ エラー: {e}")
    
    print("\n❌ すべてのredirect_uriで失敗しました")
    return False

def update_env_file(refresh_token, access_token):
    """。envファイルを更新"""
    try:
        env_path = os.path.join(os.path.dirname(__file__), '.env')
        
        with open(env_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        for i, line in enumerate(lines):
            if line.startswith('BASE_REFRESH_TOKEN='):
                lines[i] = f'BASE_REFRESH_TOKEN={refresh_token}\n'
            elif line.startswith('BASE_ACCESS_TOKEN='):
                lines[i] = f'BASE_ACCESS_TOKEN={access_token}\n'
        
        with open(env_path, 'w', encoding='utf-8') as f:
            f.writelines(lines)
        
        print(f"✅ .envファイルを更新しました: {env_path}")
    except Exception as e:
        print(f"❌ .envファイルの更新に失敗: {e}")

def main():
    print("="*60)
    print("BASE API トークン取得（簡易版）")
    print("="*60)
    
    if not CLIENT_ID or not CLIENT_SECRET:
        print("\n❌ .envファイルにBASE_CLIENT_IDとBASE_CLIENT_SECRETを設定してください")
        return
    
    print("\n【手順】")
    print("1. 以下のURLをブラウザで開いてください：")
    print()
    
    # 複数のredirect_uriで認証URLを生成
    for redirect_uri in ['https://example.com/callback', 'http://localhost:8000/callback']:
        auth_url = (
            f"https://api.thebase.in/1/oauth/authorize?"
            f"response_type=code&"
            f"client_id={CLIENT_ID}&"
            f"redirect_uri={redirect_uri}&"
            f"scope=read_items write_items&"
            f"state=random123"
        )
        print(f"   {auth_url}")
        print()
    
    print("2. BASEにログインして「許可」をクリック")
    print("3. リダイレクト後、URLから「code=」以降の文字列をコピー")
    print("   例: http://example.com/callback?code=XXXXX")
    print("       → XXXXXの部分をコピー")
    print()
    
    auth_code = input("認証コードを貼り付けてください: ").strip()
    
    if not auth_code:
        print("❌ 認証コードが入力されていません")
        return
    
    get_tokens_from_code(auth_code)

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️ 処理を中断しました")
    except Exception as e:
        print(f"\n❌ エラー: {e}")
        import traceback
        traceback.print_exc()
