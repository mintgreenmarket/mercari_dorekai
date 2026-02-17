"""
WordPress データベースから BASE トークンを取得するスクリプト
"""

import mysql.connector
import os
from dotenv import load_dotenv

# WordPress データベース接続情報を入力してください
DB_HOST = "localhost"  # 通常は localhost
DB_NAME = "wordpress_db_name"  # WordPressのデータベース名
DB_USER = "root"  # データベースユーザー名
DB_PASSWORD = ""  # データベースパスワード

def get_tokens_from_wordpress():
    """WordPressのwp_optionsテーブルからBASEトークンを取得"""
    try:
        conn = mysql.connector.connect(
            host=DB_HOST,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD
        )
        cursor = conn.cursor()
        
        # アクセストークン取得
        cursor.execute("SELECT option_value FROM wp_options WHERE option_name = 'base_access_token'")
        result = cursor.fetchone()
        access_token = result[0] if result else None
        
        # リフレッシュトークン取得
        cursor.execute("SELECT option_value FROM wp_options WHERE option_name = 'base_refresh_token'")
        result = cursor.fetchone()
        refresh_token = result[0] if result else None
        
        cursor.close()
        conn.close()
        
        if access_token and refresh_token:
            print("✅ トークン取得成功！")
            print("\n=== .envファイルに追加してください ===")
            print(f'BASE_REFRESH_TOKEN="{refresh_token}"')
            print(f'BASE_ACCESS_TOKEN="{access_token}"')
            print("=" * 50)
            return access_token, refresh_token
        else:
            print("❌ トークンが見つかりませんでした")
            print("WordPressでBASE OAuth認証を実行してください")
            return None, None
            
    except mysql.connector.Error as e:
        print(f"❌ データベース接続エラー: {e}")
        print("\nDB接続情報を確認してください：")
        print(f"  DB_HOST: {DB_HOST}")
        print(f"  DB_NAME: {DB_NAME}")
        print(f"  DB_USER: {DB_USER}")
        return None, None

if __name__ == '__main__':
    print("="*50)
    print("WordPress から BASE トークンを取得")
    print("="*50)
    print("\n⚠️ まず、このスクリプトのDB接続情報を編集してください")
    print("   スクリプトの上部にある以下の変数：")
    print("   - DB_HOST")
    print("   - DB_NAME")
    print("   - DB_USER")
    print("   - DB_PASSWORD")
    print()
    
    input("編集が完了したら Enter を押してください...")
    
    get_tokens_from_wordpress()
