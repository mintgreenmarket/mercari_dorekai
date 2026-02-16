#!/usr/bin/env python3
"""
ヤフオク取り消しスクリプト
products_yahooku.csv から売切れ/重複商品を取り消す
"""

import os
import time
import shutil
import re
import pandas as pd
import logging
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

# --- 設定 ---
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
YAHOOKU_CSV = os.path.join(SCRIPT_DIR, 'products_yahooku.csv')
MERCARI_CSV = os.path.join(SCRIPT_DIR, 'products_mercari.csv')
USER_DATA_DIR = os.path.join(SCRIPT_DIR, 'yahooku_user_data_firefox')
PROCESSED_CANCEL_LOG = os.path.join(SCRIPT_DIR, 'processed_yahooku_cancel_ids.txt')

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)

def log(msg, level="info"):
    """ログ出力"""
    getattr(logging, level)(msg)

def load_processed_ids():
    """処理済みIDを読み込む"""
    if not os.path.exists(PROCESSED_CANCEL_LOG):
        return set()
    with open(PROCESSED_CANCEL_LOG, "r", encoding="utf-8") as f:
        return {line.strip() for line in f if line.strip()}

def save_processed_id(auction_id):
    """処理済みIDを追記"""
    with open(PROCESSED_CANCEL_LOG, "a", encoding="utf-8") as f:
        f.write(f"{auction_id}\n")

def extract_hinban(title):
    """タイトルから品番を抽出"""
    match = re.match(r'^(\d+)', title)
    if match:
        return match.group(1).lstrip('0')
    return None

def load_cancel_targets():
    """取り消し対象のオークションIDリストを取得"""
    if not os.path.exists(YAHOOKU_CSV):
        log(f"❌ CSVファイルが見つかりません: {YAHOOKU_CSV}", level="error")
        return []
    
    if not os.path.exists(MERCARI_CSV):
        log(f"❌ メルカリCSVが見つかりません: {MERCARI_CSV}", level="error")
        return []
    
    try:
        # ヤフオクCSV読み込み
        yahooku_df = pd.read_csv(YAHOOKU_CSV, encoding='utf-8-sig')
        if 'status' not in yahooku_df.columns:
            log("❌ ヤフオクCSVに'status'列がありません", level="error")
            return []
        
        # 出品中のみ
        active_df = yahooku_df[yahooku_df['status'] == '出品中'].copy()
        if active_df.empty:
            log("ℹ️ 出品中の商品がありません")
            return []
        
        # 品番を抽出
        active_df['品番'] = active_df['title'].apply(extract_hinban)
        active_df = active_df.dropna(subset=['品番'])
        
        # メルカリCSV読み込み
        mercari_df = pd.read_csv(MERCARI_CSV, encoding='utf-8-sig')
        
        # 売切れ判定（商品ステータス='1'）
        soldout_hinban = set()
        if '品番' in mercari_df.columns and '商品ステータス' in mercari_df.columns:
            soldout = mercari_df[mercari_df['商品ステータス'].astype(str) == '1']
            soldout_hinban = set(soldout['品番'].astype(str))
        
        # 重複判定（品番ごとに複数行ある＝重複）
        duplicate_hinban = set()
        if '品番' in active_df.columns:
            dup_counts = active_df['品番'].value_counts()
            duplicate_hinban = set(dup_counts[dup_counts > 1].index)
        
        # 取り消し対象
        cancel_targets = []
        for _, row in active_df.iterrows():
            auction_id = row.get('auction_id', '')
            hinban = row.get('品番', '')
            title = row.get('title', '')
            
            if not auction_id:
                continue
            
            reason = []
            if hinban in soldout_hinban:
                reason.append('売切れ')
            if hinban in duplicate_hinban:
                reason.append('重複')
            
            if reason:
                cancel_targets.append({
                    'auction_id': auction_id,
                    'hinban': hinban,
                    'title': title[:50],
                    'reason': '/'.join(reason)
                })
        
        log(f"📦 取り消し対象: {len(cancel_targets)} 件（売切れ/重複）")
        return cancel_targets
        
    except Exception as e:
        log(f"❌ CSV読み込みエラー: {e}", level="error")
        return []

def cancel_auction(page, auction_id, title):
    """オークションを取り消す"""
    try:
        # 商品ページへ移動
        auction_url = f"https://auctions.yahoo.co.jp/jp/auction/{auction_id}#managementMenu"
        log(f"  📍 商品ページ: {auction_url}")
        page.goto(auction_url, timeout=60000, wait_until="domcontentloaded")
        time.sleep(2)
        
        # 「オークションの取り消し」ボタンをクリック
        cancel_button = page.locator('button:has-text("オークションの取り消し")').first
        if cancel_button.count() == 0:
            log(f"  ⚠️ 取り消しボタンが見つかりません", level="warning")
            return False
        
        cancel_button.click(timeout=5000)
        log(f"  ✅ 「オークションの取り消し」をクリック")
        time.sleep(1)
        
        # モーダルのチェックボックスにチェック
        checkbox = page.locator('input[type="checkbox"][name="agreeCheckbox"]').first
        if checkbox.count() > 0:
            checkbox.check(timeout=5000)
            log(f"  ✅ チェックボックスをチェック")
            time.sleep(0.5)
        
        # 「出品を取り消す」ボタンをクリック
        confirm_button = page.locator('button:has-text("出品を取り消す")').first
        if confirm_button.count() > 0 and not confirm_button.is_disabled():
            confirm_button.click(timeout=5000)
            log(f"  ✅ 取り消し実行")
            time.sleep(2)
            return True
        else:
            log(f"  ⚠️ 取り消しボタンが無効またはが見つかりません", level="warning")
            return False
        
    except Exception as e:
        log(f"  ❌ 取り消しエラー: {e}", level="error")
        return False

def main():
    log("=" * 60)
    log("🚀 ヤフオク取り消しツール")
    log("=" * 60)
    
    # キャッシュディレクトリを削除（ログイン情報は保持）
    cache_dirs = ['cache2', 'shader-cache', 'ShaderCache', 'startupCache', 
                 'GrShaderCache', 'GraphiteDawnCache']
    for cache_dir_name in cache_dirs:
        cache_path = os.path.join(USER_DATA_DIR, cache_dir_name)
        if os.path.exists(cache_path):
            try:
                shutil.rmtree(cache_path)
                log(f"🗑️ キャッシュを削除: {cache_dir_name}")
            except Exception:
                pass
    
    # 処理済みIDを読み込み
    processed_ids = load_processed_ids()
    
    # 取り消し対象を取得
    cancel_targets = load_cancel_targets()
    
    if not cancel_targets:
        log("✅ 取り消し対象がありません")
        return
    
    # 未処理のみフィルタ
    unprocessed = [t for t in cancel_targets if t['auction_id'] not in processed_ids]
    
    if not unprocessed:
        log(f"✅ すべて処理済みです（既処理: {len(cancel_targets)} 件）")
        return
    
    log(f"\n📋 未処理: {len(unprocessed)} 件")
    log(f"📋 既処理: {len(cancel_targets) - len(unprocessed)} 件")
    
    with sync_playwright() as p:
        log("\n🌐 ブラウザを起動中...")
        context = p.firefox.launch_persistent_context(
            user_data_dir=USER_DATA_DIR,
            headless=False,
        )
        
        page = context.pages[0] if context.pages else context.new_page()
        
        # ログイン確認
        log("\n🔑 ログイン状態を確認中...")
        page.goto("https://auctions.yahoo.co.jp/my/selling", timeout=60000)
        
        if "login" in page.url.lower():
            log("⚠️ ログインが必要です。ブラウザで手動ログインしてください。")
            log("⏳ ログイン完了後、Enterキーを押してください...")
            input()
            
            try:
                page.wait_for_url(lambda url: "login" not in url.lower(), timeout=600000)
                log("✅ ログイン完了を確認しました")
            except PlaywrightTimeoutError:
                log("❌ ログインタイムアウト", level="error")
                context.close()
                return
        else:
            log("✅ すでにログイン済みです")
        
        log(f"\n🗑️ {len(unprocessed)} 件の商品を取り消します\n")
        
        success_count = 0
        fail_count = 0
        
        for idx, target in enumerate(unprocessed, 1):
            auction_id = target['auction_id']
            title = target['title']
            reason = target['reason']
            
            log(f"[{idx}/{len(unprocessed)}] {auction_id} - {title} ({reason})")
            
            if cancel_auction(page, auction_id, title):
                save_processed_id(auction_id)
                success_count += 1
                time.sleep(3)
            else:
                save_processed_id(auction_id)  # 失敗も記録
                fail_count += 1
                time.sleep(2)
        
        log(f"\n📊 処理完了: 成功 {success_count} 件 / 失敗 {fail_count} 件")
        
        log("\n💤 ブラウザを開いたままにします。手動で閉じてください。")
        context.close()

if __name__ == "__main__":
    main()
