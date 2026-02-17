"""
メルカリ ⇔ BASE 双方向在庫連動システム
品番（商品名・説明文の最初の数字）で商品を紐付け
"""

import re
import csv
import requests
import time
import os
from pathlib import Path
from typing import Optional, Dict, List
from datetime import datetime
from dotenv import load_dotenv

# .envファイルを読み込み
load_dotenv()

# 設定
BASE_API_URL = 'https://api.thebase.in/1/'
MERCARI_CSV_PATH = Path(__file__).parent / 'products_mercari.csv'
BASE_CSV_PATH = Path(__file__).parent / 'products_base.csv'  # CSVから読込用
LOG_FILE = Path(__file__).parent / 'stock_sync_log.txt'
USE_BASE_CSV = True  # Trueの場合CSVから読込、FalseでAPI使用

# BASE API認証情報（.envから読み込み）
BASE_ACCESS_TOKEN = os.getenv('BASE_ACCESS_TOKEN')
BASE_SHOP_ID = os.getenv('BASE_SHOP_ID', 'dorekai')

def log(message: str):
    """ログ出力"""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    log_msg = f"[{timestamp}] {message}"
    print(log_msg)
    with open(LOG_FILE, 'a', encoding='utf-8') as f:
        f.write(log_msg + '\n')

def extract_hinban(text: str) -> Optional[str]:
    """
    テキストから品番（最初の数字）を抽出
    例: "607 SOBRE ソブレ..." → "607"
    """
    if not text:
        return None
    match = re.match(r'^(\d+)', text.strip())
    return match.group(1) if match else None

def get_csv_value(row: Dict, key: str) -> str:
    """Handle BOM-prefixed headers safely."""
    if key in row:
        return row.get(key, '')
    bom_key = '\ufeff' + key
    if bom_key in row:
        return row.get(bom_key, '')
    return ''

def open_csv_with_fallback(path: Path):
    """Open CSV with encoding fallback (utf-8-sig, cp932, utf-8)."""
    for enc in ('utf-8-sig', 'cp932', 'utf-8'):
        try:
            return open(path, 'r', encoding=enc)
        except UnicodeDecodeError:
            continue
    return open(path, 'r', encoding='utf-8', errors='replace')

def get_mercari_products() -> Dict[str, Dict]:
    """
    メルカリCSVから商品情報を読み込み、品番をキーとした辞書を返す
    """
    products = {}
    try:
        with open_csv_with_fallback(MERCARI_CSV_PATH) as f:
            reader = csv.DictReader(f)
            for row in reader:
                hinban = get_csv_value(row, '品番').strip()
                if hinban and hinban.isdigit():
                    products[hinban] = {
                        'hinban': hinban,
                        'name': get_csv_value(row, '商品名'),
                        'price': get_csv_value(row, '価格'),
                        'stock': int(get_csv_value(row, '在庫数') or 0),
                        'product_id': get_csv_value(row, '商品ID'),
                        'status': get_csv_value(row, '商品ステータス')
                    }
        log(f"✅ メルカリ商品読込: {len(products)}件")
        return products
    except Exception as e:
        log(f"❌ メルカリCSV読込エラー: {e}")
        return {}

def get_base_products() -> Dict[str, Dict]:
    """
    BASE商品情報を取得し、品番をキーとした辞書を返す
    USE_BASE_CSV=Trueの場合はCSVから、Falseの場合はAPIから取得
    """
    if USE_BASE_CSV:
        return get_base_products_from_csv()
    else:
        return get_base_products_from_api()

def get_base_products_from_csv() -> Dict[str, Dict]:
    """
    products_base.csvからBASE商品情報を読み込み
    """
    products = {}
    try:
        if not BASE_CSV_PATH.exists():
            log(f"⚠️ {BASE_CSV_PATH} が見つかりません。base_products_fetcher.py を実行してください")
            return {}
        
        with open_csv_with_fallback(BASE_CSV_PATH) as f:
            reader = csv.DictReader(f)
            for row in reader:
                hinban = get_csv_value(row, '品番').strip()
                if hinban:
                    products[hinban] = {
                        'hinban': hinban,
                        'item_id': get_csv_value(row, '商品ID'),
                        'title': get_csv_value(row, '商品名'),
                        'stock': int(get_csv_value(row, '在庫数') or 0),
                        'price': int(get_csv_value(row, '価格') or 0),
                        'variations': []  # CSVにはバリエーション情報なし
                    }
        log(f"✅ BASE商品読込(CSV): {len(products)}件")
        return products
    except Exception as e:
        log(f"❌ BASE CSV読込エラー: {e}")
        return {}

def get_base_products_from_api() -> Dict[str, Dict]:
    """
    BASE APIから商品情報を取得
    """
    if not BASE_ACCESS_TOKEN:
        log("❌ BASE_ACCESS_TOKENが設定されていません")
        return {}
    
    products = {}
    offset = 0
    limit = 100
    
    try:
        while True:
            url = f"{BASE_API_URL}items?limit={limit}&offset={offset}"
            headers = {'Authorization': f'Bearer {BASE_ACCESS_TOKEN}'}
            
            response = requests.get(url, headers=headers, timeout=30)
            if response.status_code != 200:
                log(f"❌ BASE API エラー: {response.status_code}")
                break
            
            data = response.json()
            items = data.get('items', [])
            if not items:
                break
            
            for item in items:
                # 商品名と説明文から品番抽出
                title = item.get('title', '')
                detail = item.get('detail', '')
                
                hinban = extract_hinban(title) or extract_hinban(detail)
                if hinban:
                    products[hinban] = {
                        'hinban': hinban,
                        'item_id': item.get('item_id'),
                        'title': title,
                        'stock': int(item.get('stock', 0)),
                        'price': int(item.get('price', 0)),
                        'variations': item.get('variations', [])
                    }
            
            offset += limit
            if len(items) < limit:
                break
            time.sleep(0.3)
        
        log(f"✅ BASE商品読込: {len(products)}件")
        return products
    except Exception as e:
        log(f"❌ BASE商品取得エラー: {e}")
        return {}

def update_base_stock(item_id: str, new_stock: int) -> bool:
    """
    BASE商品の在庫を更新（API経由）
    USE_BASE_CSV=Trueの場合はCSVも更新
    """
    # API更新
    if BASE_ACCESS_TOKEN:
        try:
            url = f"{BASE_API_URL}items/edit"
            headers = {
                'Authorization': f'Bearer {BASE_ACCESS_TOKEN}',
                'Content-Type': 'application/json'
            }
            payload = {
                'item_id': item_id,
                'stock': new_stock
            }
            
            response = requests.post(url, headers=headers, json=payload, timeout=30)
            if response.status_code == 200:
                log(f"✅ BASE在庫更新成功(API): item_id={item_id}, stock={new_stock}")
                api_success = True
            else:
                log(f"❌ BASE在庫更新失敗(API): {response.status_code} - {response.text}")
                api_success = False
        except Exception as e:
            log(f"❌ BASE在庫更新エラー(API): {e}")
            api_success = False
    else:
        log(f"⚠️ BASE_ACCESS_TOKEN未設定、API更新スキップ")
        api_success = False
    
    # CSV更新（USE_BASE_CSV=Trueの場合）
    csv_success = False
    if USE_BASE_CSV and BASE_CSV_PATH.exists():
        csv_success = update_base_csv_stock(item_id, new_stock)
    
    return api_success or csv_success

def update_base_csv_stock(item_id: str, new_stock: int) -> bool:
    """
    products_base.csvの在庫数を更新
    """
    try:
        rows = []
        updated = False
        
        with open(BASE_CSV_PATH, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            fieldnames = reader.fieldnames
            for row in reader:
                if row.get('商品ID') == item_id:
                    row['在庫数'] = str(new_stock)
                    updated = True
                rows.append(row)
        
        if updated:
            with open(BASE_CSV_PATH, 'w', encoding='utf-8', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(rows)
            log(f"✅ BASE CSV在庫更新: item_id={item_id}, stock={new_stock}")
            return True
        else:
            log(f"⚠️ BASE CSVに商品ID {item_id} が見つかりません")
            return False
    except Exception as e:
        log(f"❌ BASE CSV更新エラー: {e}")
        return False

def update_mercari_csv_stock(hinban: str, new_stock: int) -> bool:
    """
    メルカリCSVの在庫数を更新
    ※実際のメルカリShopsへの更新は別途APIが必要（未実装の可能性）
    """
    try:
        rows = []
        updated = False
        
        with open(MERCARI_CSV_PATH, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            fieldnames = reader.fieldnames
            for row in reader:
                if row.get('品番') == hinban:
                    row['在庫数'] = str(new_stock)
                    updated = True
                rows.append(row)
        
        if updated:
            with open(MERCARI_CSV_PATH, 'w', encoding='utf-8', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(rows)
            log(f"✅ メルカリCSV在庫更新: 品番={hinban}, stock={new_stock}")
            return True
        else:
            log(f"⚠️ メルカリCSVに品番{hinban}が見つかりません")
            return False
    except Exception as e:
        log(f"❌ メルカリCSV更新エラー: {e}")
        return False

def sync_stock_mercari_to_base(hinban: str):
    """
    メルカリで売れた → BASEの在庫を0にする
    """
    log(f"🔄 在庫同期開始: メルカリ({hinban}) → BASE")
    
    base_products = get_base_products()
    if hinban in base_products:
        item = base_products[hinban]
        if item['stock'] > 0:
            success = update_base_stock(item['item_id'], 0)
            if success:
                log(f"✅ 同期完了: BASE商品「{item['title']}」の在庫を0に設定")
            else:
                log(f"❌ 同期失敗: BASE在庫更新エラー")
        else:
            log(f"ℹ️ BASE在庫は既に0です")
    else:
        log(f"⚠️ BASE側に品番{hinban}が見つかりません")

def sync_stock_base_to_mercari(hinban: str):
    """
    BASEで売れた → メルカリの在庫を0にする
    """
    log(f"🔄 在庫同期開始: BASE({hinban}) → メルカリ")
    
    mercari_products = get_mercari_products()
    if hinban in mercari_products:
        item = mercari_products[hinban]
        if item['stock'] > 0:
            success = update_mercari_csv_stock(hinban, 0)
            if success:
                log(f"✅ 同期完了: メルカリ商品「{item['name']}」の在庫を0に設定")
                # TODO: 実際のメルカリShops APIで在庫更新が必要
                log(f"⚠️ メルカリShops APIでの在庫更新は未実装")
            else:
                log(f"❌ 同期失敗: メルカリCSV更新エラー")
        else:
            log(f"ℹ️ メルカリ在庫は既に0です")
    else:
        log(f"⚠️ メルカリ側に品番{hinban}が見つかりません")

def full_sync():
    """
    全商品の在庫を比較し、差異があれば同期
    ※定期実行用
    """
    log("=" * 60)
    log("🔄 全商品在庫同期を開始")
    
    mercari_products = get_mercari_products()
    base_products = get_base_products()
    
    # 共通の品番を抽出
    common_hinbans = set(mercari_products.keys()) & set(base_products.keys())
    log(f"📊 共通品番: {len(common_hinbans)}件")
    
    sync_count = 0
    for hinban in common_hinbans:
        m_stock = mercari_products[hinban]['stock']
        b_stock = base_products[hinban]['stock']
        
        # どちらかが0なら、もう片方も0にする
        if m_stock == 0 and b_stock > 0:
            log(f"🔄 メルカリ在庫0 → BASE在庫を0に (品番: {hinban})")
            update_base_stock(base_products[hinban]['item_id'], 0)
            sync_count += 1
        elif b_stock == 0 and m_stock > 0:
            log(f"🔄 BASE在庫0 → メルカリ在庫を0に (品番: {hinban})")
            update_mercari_csv_stock(hinban, 0)
            sync_count += 1
    
    log(f"✅ 在庫同期完了: {sync_count}件を同期")
    log("=" * 60)

if __name__ == '__main__':
    # テスト実行
    print("在庫連動システム - 手動実行モード")
    print("1. 全商品同期")
    print("2. メルカリ→BASE (品番指定)")
    print("3. BASE→メルカリ (品番指定)")
    
    choice = input("選択してください (1-3): ").strip()
    
    if choice == '1':
        full_sync()
    elif choice == '2':
        hinban = input("品番を入力: ").strip()
        sync_stock_mercari_to_base(hinban)
    elif choice == '3':
        hinban = input("品番を入力: ").strip()
        sync_stock_base_to_mercari(hinban)
    else:
        print("無効な選択です")
