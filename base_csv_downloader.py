"""
BASE管理画面からCSVをダウンロードするスクリプト
ログインして商品一覧CSVをダウンロード
"""

import os
import time
import glob
from pathlib import Path
from datetime import datetime
from playwright.sync_api import sync_playwright
from dotenv import load_dotenv

# .envファイルを読み込み
load_dotenv()

# ===== 設定 =====
SCRIPT_DIR = Path(__file__).parent
ROOT_DIR = SCRIPT_DIR

# BASE管理画面のURL
BASE_ADMIN_URL = 'https://admin.thebase.com/'
BASE_LOGIN_URL = 'https://admin.thebase.com/users/login'
BASE_ITEMS_URL = 'https://admin.thebase.com/items'
BASE_CSV_DOWNLOAD_URL = 'https://admin.thebase.com/apps/92/download'

# 認証情報（環境変数から取得）
BASE_EMAIL = os.getenv('BASE_EMAIL')
BASE_PASSWORD = os.getenv('BASE_PASSWORD')

# ダウンロード保存先
DOWNLOAD_DIR = ROOT_DIR / 'downloads'
OUTPUT_CSV = ROOT_DIR / 'stock' / 'products_base.csv'

# ブラウザデータ保存先（ログイン情報維持用）
USER_DATA_DIR = SCRIPT_DIR / '.browser_data'

# ダウンロードディレクトリを作成
DOWNLOAD_DIR.mkdir(exist_ok=True)
USER_DATA_DIR.mkdir(exist_ok=True)
(ROOT_DIR / 'stock').mkdir(exist_ok=True)

def wait_for_download(download_dir: Path, timeout: int = 30) -> Path:
    """
    ダウンロードが完了するまで待機
    
    Args:
        download_dir: ダウンロードディレクトリ
        timeout: タイムアウト秒数
    
    Returns:
        ダウンロードされたファイルのパス
    """
    start_time = time.time()
    
    while time.time() - start_time < timeout:
        # .crdownload や .tmp ファイルがなくなるまで待機
        temp_files = list(download_dir.glob('*.crdownload')) + list(download_dir.glob('*.tmp'))
        if not temp_files:
            # 最新のCSVファイルを取得
            csv_files = list(download_dir.glob('*.csv'))
            if csv_files:
                latest_file = max(csv_files, key=lambda p: p.stat().st_mtime)
                return latest_file
        
        time.sleep(0.5)
    
    raise TimeoutError(f"ダウンロードが {timeout} 秒以内に完了しませんでした")

def download_base_csv():
    """BASE管理画面からCSVをダウンロード"""
    
    print("="*60)
    print("  BASE CSV ダウンロード")
    print("="*60)
    
    # 認証情報のチェック
    if not BASE_EMAIL or not BASE_PASSWORD:
        print("\n❌ エラー: BASE_EMAIL と BASE_PASSWORD を .env ファイルに設定してください")
        print("\n.env ファイルに以下を追加:")
        print("BASE_EMAIL=your_email@example.com")
        print("BASE_PASSWORD=your_password")
        return False
    
    # ダウンロードディレクトリをクリア（作業用のみ）
    for old_file in DOWNLOAD_DIR.glob('base_products_*.csv'):
        try:
            old_file.unlink()
        except Exception:
            pass
    
    print(f"\n📂 ダウンロード先: {DOWNLOAD_DIR}")
    print(f"📧 ログインメール: {BASE_EMAIL}")
    
    with sync_playwright() as p:
        # ブラウザを起動（ダウンロード設定付き + ログイン情報保存）
        browser = p.chromium.launch_persistent_context(
            user_data_dir=str(USER_DATA_DIR),
            headless=False,  # ログイン確認のため表示
            downloads_path=str(DOWNLOAD_DIR),
            accept_downloads=True,
            viewport={'width': 1280, 'height': 800}
        )
        
        page = browser.new_page()
        
        try:
            # ログインページに移動
            print("\n🔐 BASE管理画面にログイン中...")
            page.goto(BASE_LOGIN_URL, wait_until='networkidle')
            
            # すでにログイン済みかチェック（リダイレクトされた場合）
            if 'login' not in page.url:
                print("✅ セッションが有効です - ログイン済み")
            else:
                # ログインフォームが表示されている場合のみ入力
                print("📝 ログイン情報を入力中...")
                try:
                    page.fill('input[name="data[User][mail_address]"]', BASE_EMAIL)
                    page.fill('input[name="data[User][password]"]', BASE_PASSWORD)
                    
                    # ログインボタンをクリック
                    page.click('button[type="submit"]')
                    
                    # ログイン完了を待機
                    print("⏳ ログイン処理中...")
                    time.sleep(5)  # 待機時間を延長
                    
                    # 確認コード入力画面かチェック（最優先）
                    current_url = page.url.lower()
                    if 'verify' in current_url or 'confirm' in current_url or 'code' in current_url or 'authentication' in current_url:
                        print("\n🔐 確認コード入力画面を検出しました")
                        print("💡 ブラウザで確認コードを入力してログインを完了してください")
                        print("⏳ ログイン完了後、Enterキーを押してください...")
                        input()
                        print("✅ 続行します")
                    
                    # セキュリティ確認など他の認証画面もチェック
                    else:
                        try:
                            # よくある確認コード入力フィールド
                            verification_selectors = [
                                'input[type="text"][name*="code"]',
                                'input[type="text"][name*="verify"]',
                                'input[name*="verification"]',
                                'input[placeholder*="コード"]',
                                'input[placeholder*="確認"]'
                            ]
                            
                            for selector in verification_selectors:
                                if page.is_visible(selector, timeout=1000):
                                    print("\n🔐 確認コード入力フィールドを検出しました")
                                    print("💡 ブラウザで確認コードを入力してログインを完了してください")
                                    print("⏳ ログイン完了後、Enterキーを押してください...")
                                    input()
                                    print("✅ 続行します")
                                    break
                        except Exception:
                            pass
                    
                    # ログイン成功を確認（確認コードチェック後）
                    time.sleep(2)
                    if 'login' in page.url:
                        print(f"⚠️ 現在のURL: {page.url}")
                        print("❌ ログイン失敗: 認証情報を確認してください")
                        print("💡 ブラウザで手動ログインして、Enterキーを押してください...")
                        input()
                        print("✅ 続行します")
                    
                    print("✅ ログイン成功")
                    
                except Exception as e:
                    print(f"❌ ログインエラー: {e}")
                    return False
            
            # CSVダウンロードページに移動
            print("\n📥 CSVダウンロードページへ移動中...")
            page.goto(BASE_CSV_DOWNLOAD_URL, wait_until='networkidle')
            time.sleep(2)
            
            # 「登録済み商品の情報を編集するためのCSVファイル」ラジオボタンを選択
            print("📋 登録済み商品CSVを選択中...")
            try:
                # labelをクリック（inputが遮られている場合があるため）
                page.click('label[for="downloadTypeall1"]')
                print("✅ CSVタイプを選択")
                time.sleep(1)
            except Exception as e:
                print(f"⚠️ ラジオボタンの選択に失敗: {e}")
                # 失敗しても続行（デフォルトで選択されている可能性）
            
            # CSVダウンロードボタンをクリック
            print("📥 CSVをダウンロード中...")
            
            download_clicked = False
            # ダウンロードボタンのセレクタ候補
            download_selectors = [
                'button.c-primaryBtn.c-primaryBtn--full',  # クラス名での特定
                'button[type="button"].c-primaryBtn',
                'button.c-primaryBtn:has-text("ダウンロード")',
                'button:has-text("CSV")',
                'button:has-text("CSVをダウンロード")',
            ]
            
            for selector in download_selectors:
                try:
                    if page.is_visible(selector, timeout=2000):
                        print(f"✓ ダウンロードボタン発見: {selector}")
                        
                        # ダウンロード開始
                        with page.expect_download(timeout=30000) as download_info:
                            page.click(selector)
                            print("⏳ ダウンロード処理中...")
                        
                        download = download_info.value
                        
                        # ファイルを保存
                        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                        temp_path = DOWNLOAD_DIR / f'base_products_{timestamp}.csv'
                        shop_raw_path = DOWNLOAD_DIR / f'dorekai-base-shop-{timestamp}.csv'
                        download.save_as(temp_path)
                        
                        print(f"✅ ダウンロード完了: {temp_path.name}")

                        # BASEから取得した元CSVを別名で保存
                        import shutil
                        shutil.copy(temp_path, shop_raw_path)
                        print(f"✅ 元CSV保存: {shop_raw_path}")
                        
                        # ファイルを最終的な場所にコピー
                        shutil.copy(temp_path, OUTPUT_CSV)
                        print(f"✅ ファイル保存: {OUTPUT_CSV}")
                        
                        download_clicked = True
                        break
                        
                except Exception as e:
                    print(f"  ⚠️ {selector} での試行失敗: {e}")
                    continue
            
            if not download_clicked:
                print("\n⚠️ 自動ダウンロードに失敗しました")
                print("💡 手動でCSVダウンロードボタンをクリックしてください...")
                print(f"   保存先: {DOWNLOAD_DIR}")
                
                # 手動操作のため待機
                print("\n⏳ CSVダウンロード後、Enterキーを押してください...")
                input()
                
                # ダウンロードファイルをチェック
                csv_files = list(DOWNLOAD_DIR.glob('*.csv'))
                if csv_files:
                    latest_file = max(csv_files, key=lambda p: p.stat().st_mtime)
                    print(f"✅ ファイル検出: {latest_file.name}")
                    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                    shop_raw_path = DOWNLOAD_DIR / f'dorekai-base-shop-{timestamp}.csv'
                    
                    import shutil
                    shutil.copy(latest_file, shop_raw_path)
                    print(f"✅ 元CSV保存: {shop_raw_path}")
                    shutil.copy(latest_file, OUTPUT_CSV)
                    print(f"✅ ファイル保存: {OUTPUT_CSV}")
                else:
                    print("❌ CSVファイルが見つかりませんでした")
                    return False
            
            # ファイルの内容を確認
            if OUTPUT_CSV.exists():
                import pandas as pd
                try:
                    # Shift-JISでの読み込みを試みる（BASEのCSVはShift-JIS）
                    df = pd.read_csv(OUTPUT_CSV, encoding='shift-jis', nrows=5)
                    print(f"\n📊 ダウンロード結果:")
                    print(f"   列数: {len(df.columns)}")
                    print(f"   列名: {', '.join(df.columns[:5])}...")
                    
                    # 行数を確認（全行読み込み）
                    df_full = pd.read_csv(OUTPUT_CSV, encoding='shift-jis')
                    print(f"   商品数: {len(df_full)} 件")
                    
                    return True
                    
                except Exception as e:
                    print(f"⚠️ CSVファイルの読み込みエラー: {e}")
                    # UTF-8でも試してみる
                    try:
                        df_full = pd.read_csv(OUTPUT_CSV, encoding='utf-8-sig')
                        print(f"✅ UTF-8で読み込み成功: 商品数 {len(df_full)} 件")
                        return True
                    except:
                        return False
            
            return False
            
        except Exception as e:
            print(f"\n❌ エラーが発生しました: {e}")
            import traceback
            traceback.print_exc()
            return False
            
        finally:
            print("\n🔒 ブラウザを閉じています...")
            time.sleep(1)
            try:
                browser.close()
            except Exception as e:
                # ブラウザがすでに閉じられている場合は無視
                print(f"⚠️ ブラウザクローズ時の警告: {e}")
                pass

def main():
    """メイン処理"""
    success = download_base_csv()
    
    if success:
        print("\n" + "="*60)
        print("✅ 処理完了")
        print("="*60)
        print(f"\n📄 出力ファイル: {OUTPUT_CSV}")
        print(f"💡 このファイルが all_stock.py で使用されます")
    else:
        print("\n" + "="*60)
        print("❌ 処理失敗")
        print("="*60)
        print("\n💡 手動でダウンロードする場合:")
        print(f"   1. {BASE_ITEMS_URL} にアクセス")
        print("   2. CSVダウンロードボタンをクリック")
        print(f"   3. ダウンロードしたファイルを {OUTPUT_CSV} に保存")

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️ 処理を中断しました")
    except Exception as e:
        print(f"\n❌ エラーが発生しました: {e}")
        import traceback
        traceback.print_exc()
