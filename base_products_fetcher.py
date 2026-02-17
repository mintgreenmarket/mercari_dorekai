"""
BASE API 商品取得スクリプト
全商品を取得してCSVに保存
"""

import requests
import csv
import json
import re
import time
import os
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, List
from dotenv import load_dotenv

# .envファイルを読み込み
load_dotenv()

# 設定
BASE_API_URL = 'https://api.thebase.in/1/'
OUTPUT_CSV = Path(__file__).parent / 'products_base.csv'
TOKEN_FILE = Path(__file__).parent / 'base_token.json'

# 認証情報（.envから読み込み）
BASE_CLIENT_ID = os.getenv('BASE_CLIENT_ID')
BASE_CLIENT_SECRET = os.getenv('BASE_CLIENT_SECRET')
BASE_REFRESH_TOKEN = os.getenv('BASE_REFRESH_TOKEN')
BASE_ACCESS_TOKEN = os.getenv('BASE_ACCESS_TOKEN')
BASE_SHOP_ID = os.getenv('BASE_SHOP_ID', 'dorekai')

if not all([BASE_CLIENT_ID, BASE_CLIENT_SECRET]):
    print("⚠️ .envファイルが見つからないか、必要な環境変数が設定されていません。")
    print("以下の変数を.envファイルに追加してください：")
    print("BASE_CLIENT_ID=your_client_id")
    print("BASE_CLIENT_SECRET=your_client_secret")
    print("BASE_REFRESH_TOKEN=your_refresh_token")
    print("BASE_ACCESS_TOKEN=your_access_token")
    print("BASE_SHOP_ID=dorekai")
    exit(1)

def save_token(access_token: str, refresh_token: str, expires_in: int):
    """トークンをファイルに保存"""
    data = {
        'access_token': access_token,
        'refresh_token': refresh_token,
        'expires_at': time.time() + expires_in - 60
    }
    with open(TOKEN_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)
    print(f"✅ トークン保存: {TOKEN_FILE}")

def load_token() -> Optional[Dict]:
    """保存されたトークンを読み込み"""
    if not TOKEN_FILE.exists():
        return None
    try:
        with open(TOKEN_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        # 有効期限チェック
        if time.time() < data.get('expires_at', 0):
            return data
        else:
            print("⚠️ トークンの有効期限が切れています")
            return None
    except Exception as e:
        print(f"❌ トークン読込エラー: {e}")
        return None

def refresh_access_token(refresh_token: str) -> Optional[str]:
    """リフレッシュトークンで新しいアクセストークンを取得"""
    try:
        url = 'https://api.thebase.in/1/oauth/token'
        payload = {
            'grant_type': 'refresh_token',
            'client_id': BASE_CLIENT_ID,
            'client_secret': BASE_CLIENT_SECRET,
            'refresh_token': refresh_token,
            'redirect_uri': 'https://example.com/callback'
        }
        
        response = requests.post(url, data=payload, timeout=30)
        if response.status_code == 200:
            data = response.json()
            access_token = data['access_token']
            new_refresh_token = data.get('refresh_token', refresh_token)
            expires_in = data.get('expires_in', 3600)
            
            save_token(access_token, new_refresh_token, expires_in)
            print("✅ アクセストークン更新成功")
            return access_token
        else:
            print(f"❌ トークン更新失敗: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        print(f"❌ トークン更新エラー: {e}")
        return None

def get_access_token() -> Optional[str]:
    """有効なアクセストークンを取得（必要に応じて更新）"""
    # 保存されたトークンをチェック
    token_data = load_token()
    if token_data:
        print("✅ 保存されたトークンを使用")
        return token_data['access_token']
    
    # トークンが無効またはなければリフレッシュ
    print("🔄 アクセストークンを更新中...")
    try:
        return refresh_access_token(BASE_REFRESH_TOKEN)
    except NameError:
        # BASE_REFRESH_TOKENが設定されていない場合、config.pyのトークンを使用
        print("⚠️ リフレッシュトークンが設定されていません。config.pyのトークンを使用します")
        return BASE_ACCESS_TOKEN

def extract_hinban(text: str) -> Optional[str]:
    """商品名・説明文から品番（最初の数字）を抽出"""
    if not text:
        return None
    match = re.match(r'^(\d+)', text.strip())
    return match.group(1) if match else None

def fetch_all_products(access_token: str) -> List[Dict]:
    """BASE APIから全商品を取得"""
    all_items = []
    offset = 0
    limit = 100
    max_retries = 3
    
    print("🔄 BASE商品取得開始...")
    
    while True:
        api_url = f"{BASE_API_URL}items?limit={limit}&offset={offset}&sort=item_id&order=desc"
        
        retries = 0
        response = None
        
        while retries < max_retries:
            try:
                response = requests.get(
                    api_url,
                    headers={'Authorization': f'Bearer {access_token}'},
                    timeout=60
                )
                if response.status_code == 200:
                    break
                elif response.status_code == 401:
                    print("❌ 認証エラー: トークンが無効です")
                    return []
                else:
                    print(f"⚠️ API応答エラー: {response.status_code}")
                    retries += 1
                    time.sleep(2)
            except Exception as e:
                print(f"⚠️ リクエストエラー: {e}")
                retries += 1
                time.sleep(2)
        
        if not response or response.status_code != 200:
            print(f"❌ {offset}件でAPI取得を中断")
            break
        
        try:
            body = response.json()
        except json.JSONDecodeError:
            print("❌ JSONパースエラー")
            break
        
        items = body.get('items', [])
        if not items:
            break
        
        all_items.extend(items)
        print(f"  取得中: {len(all_items)}件...")
        
        offset += limit
        
        if len(items) < limit:
            break
        
        time.sleep(0.3)
    
    print(f"✅ 取得完了: {len(all_items)}件")
    return all_items

def process_products(items: List[Dict]) -> List[Dict]:
    """商品データを加工（品番抽出など）"""
    products = []
    
    for item in items:
        item_id = item.get('item_id', '')
        title = item.get('title', '')
        detail = item.get('detail', '')
        
        # 品番抽出
        hinban = extract_hinban(title) or extract_hinban(detail)
        
        # カテゴリ取得
        categories = []
        if item.get('categories'):
            for cat in item['categories']:
                if isinstance(cat, dict) and 'name' in cat:
                    categories.append(cat['name'])
        
        # バリエーション情報
        variations = item.get('variations', [])
        variation_count = len(variations) if variations else 0
        
        product = {
            '品番': hinban or '',
            '商品ID': item_id,
            '商品名': title,
            '説明文': detail[:200] + '...' if len(detail) > 200 else detail,  # 200文字まで
            '価格': item.get('price', 0),
            '在庫数': item.get('stock', 0),
            'カテゴリ': ', '.join(categories),
            'バリエーション数': variation_count,
            '商品URL': f"https://{BASE_SHOP_ID}.base.shop/items/{item_id}",
            '画像URL': item.get('img1_origin', ''),
            '登録日': item.get('modified', ''),
            '公開状態': item.get('visible', 1),
        }
        
        products.append(product)
    
    return products

def save_to_csv(products: List[Dict]):
    """商品データをCSVに保存"""
    if not products:
        print("⚠️ 保存する商品データがありません")
        return
    
    try:
        with open(OUTPUT_CSV, 'w', encoding='utf-8', newline='') as f:
            fieldnames = products[0].keys()
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(products)
        
        print(f"✅ CSV保存完了: {OUTPUT_CSV}")
        print(f"📊 保存件数: {len(products)}件")
    except Exception as e:
        print(f"❌ CSV保存エラー: {e}")

def show_statistics(products: List[Dict]):
    """統計情報を表示"""
    total = len(products)
    with_hinban = sum(1 for p in products if p['品番'])
    total_stock = sum(int(p['在庫数']) for p in products)
    total_variations = sum(int(p['バリエーション数']) for p in products)
    
    print("\n" + "="*60)
    print("📊 BASE商品統計")
    print("="*60)
    print(f"総商品数:         {total}件")
    print(f"品番あり:         {with_hinban}件 ({with_hinban/total*100:.1f}%)")
    print(f"品番なし:         {total-with_hinban}件")
    print(f"総在庫数:         {total_stock}個")
    print(f"バリエーション総数: {total_variations}個")
    print(f"平均価格:         ¥{sum(int(p['価格']) for p in products) / total:,.0f}")
    print("="*60)

def main():
    """メイン処理"""
    print("="*60)
    print("BASE API 商品取得スクリプト")
    print("="*60)
    
    # アクセストークン取得
    access_token = get_access_token()
    if not access_token:
        print("❌ アクセストークンが取得できません")
        print("\nconfig.pyを確認してください：")
        print("  - BASE_CLIENT_ID")
        print("  - BASE_CLIENT_SECRET")
        print("  - BASE_REFRESH_TOKEN または BASE_ACCESS_TOKEN")
        return
    
    # 商品取得
    items = fetch_all_products(access_token)
    if not items:
        print("❌ 商品が取得できませんでした")
        return
    
    # 商品データ加工
    print("\n🔄 商品データを加工中...")
    products = process_products(items)
    
    # CSV保存
    save_to_csv(products)
    
    # 統計表示
    show_statistics(products)
    
    print("\n✅ 処理完了")

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️ 処理を中断しました")
    except Exception as e:
        print(f"\n❌ エラーが発生しました: {e}")
        import traceback
        traceback.print_exc()
