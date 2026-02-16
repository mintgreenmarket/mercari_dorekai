"""
ラクマの商品を削除するスクリプト
products_rakuma.csv から削除対象・重複対象の商品を読み込み、削除する
"""

import os
import re
import shutil
import pandas as pd
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
import time

# --- 設定 ---
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
RAKUMA_CSV = os.path.join(SCRIPT_DIR, 'products_rakuma.csv')
USER_DATA_DIR = os.path.join(SCRIPT_DIR, 'rakuma_user_data_firefox')
PROCESSED_URLS_FILE = os.path.join(SCRIPT_DIR, 'processed_rakuma_urls.txt')

def load_processed_rakuma_urls():
    """処理済みラクマURLのリストを読み込む"""
    if os.path.exists(PROCESSED_URLS_FILE):
        try:
            with open(PROCESSED_URLS_FILE, 'r', encoding='utf-8') as f:
                processed = set(line.strip() for line in f if line.strip())
            print(f"📋 処理済みURL {len(processed)} 件を読み込みました。")
            return processed
        except Exception as e:
            print(f"⚠️ 処理済みURLファイルの読み込みエラー: {e}")
            return set()
    return set()

def save_processed_rakuma_url(url):
    """処理済みURLをファイルに追記"""
    try:
        with open(PROCESSED_URLS_FILE, 'a', encoding='utf-8') as f:
            f.write(url + '\n')
    except Exception as e:
        print(f"⚠️ 処理済みURLの保存エラー: {e}")

def load_target_urls_from_csv():
    """products_rakuma.csv から削除対象・重複対象のURLを抽出（重複は古い方を削除）"""
    if not os.path.exists(RAKUMA_CSV):
        print(f"❌ CSVファイルが見つかりません: {RAKUMA_CSV}")
        return []
    
    try:
        df = pd.read_csv(RAKUMA_CSV, encoding='utf-8-sig')
        
        # 削除対象
        delete_targets = pd.DataFrame()
        if '削除' in df.columns:
            delete_targets = df[df['削除'] == '削除'].copy()
        
        # 重複対象（品番ごとに新しい1件を残して古い方を削除）
        duplicate_targets = pd.DataFrame()
        if '重複' in df.columns and '品番' in df.columns:
            dup_df = df[df['重複'] == '重複'].copy()
            if not dup_df.empty and 'URL' in dup_df.columns:
                date_col = None
                for col in ['最終更新日時', '商品登録日時']:
                    if col in dup_df.columns:
                        date_col = col
                        break

                dup_df = dup_df.dropna(subset=['URL']).copy()

                if date_col:
                    dup_df['_sort_dt'] = pd.to_datetime(dup_df[date_col], errors='coerce')
                    dup_df['_sort_dt'] = dup_df['_sort_dt'].fillna(pd.Timestamp.min)
                    dup_df = dup_df.sort_values(['品番', '_sort_dt', 'URL'], ascending=[True, False, True])
                    dup_df['_dup_rank'] = dup_df.groupby('品番').cumcount()
                else:
                    dup_df['_dup_rank'] = dup_df.groupby('品番').cumcount()

                duplicate_targets = dup_df[dup_df['_dup_rank'] > 0].copy()
        
        # 統合
        if 'URL' in df.columns:
            combined = pd.concat([delete_targets, duplicate_targets], ignore_index=True)
            combined = combined.dropna(subset=['URL']).drop_duplicates(subset=['URL'])
            urls = combined['URL'].tolist()
            
            print(f"📦 削除対象: {len(delete_targets)} 件")
            print(f"🔁 重複対象（古い方）: {len(duplicate_targets)} 件")
            print(f"✅ 合計: {len(urls)} 件のURLを抽出しました")
            
            return urls
        else:
            print("❌ CSVに'URL'列がありません")
            return []
            
    except Exception as e:
        print(f"❌ CSV読み込みエラー: {e}")
        return []

def convert_to_edit_url(url):
    """URLを編集ページ形式に変換"""
    if '/edit' in url:
        return url
    
    if 'item.fril.jp/' in url:
        # クエリパラメータを除去
        base_url = url.split('?')[0]
        # item.fril.jp/{id} から {id} を抽出
        parts = base_url.split('item.fril.jp/')
        if len(parts) > 1:
            item_id = parts[1].rstrip('/')
            # fril.jp/item/{id}/edit 形式に変換
            return f"https://fril.jp/item/{item_id}/edit"
    
    return url

def build_url_title_map():
    """CSVからURL→商品名のマップを作成"""
    url_to_title = {}
    if not os.path.exists(RAKUMA_CSV):
        return url_to_title
    try:
        df = pd.read_csv(RAKUMA_CSV, encoding='utf-8-sig')
        if 'URL' not in df.columns or '商品名' not in df.columns:
            return url_to_title
        for _, row in df[['URL', '商品名']].dropna().iterrows():
            raw_url = str(row['URL']).strip()
            title = str(row['商品名']).strip()
            if not raw_url or not title:
                continue
            edit_url = convert_to_edit_url(raw_url)
            url_to_title[raw_url] = title
            url_to_title[edit_url] = title
    except Exception as e:
        print(f"⚠️ CSVから商品名マップ作成エラー: {e}")
    return url_to_title

def delete_from_drafts(page, title):
    """下書きページ（出品していた）から削除を試行"""
    if not title:
        return False
    if page.is_closed():
        page = page.context.new_page()
    print(f"  ↪ 下書きページで削除を試行: {title}")
    try:
        page.goto("https://fril.jp/draft", timeout=60000, wait_until="domcontentloaded")
        page.wait_for_timeout(2000)
    except Exception as e:
        print(f"  ⚠️ 下書きページへの移動に失敗: {e}")
        return False

    tab = page.locator('a[href="#after-selling-tab"]')
    if tab.count() > 0:
        tab.click()
        page.wait_for_timeout(1000)

    def normalize_text(text):
        return "".join(text.split())

    def find_item_by_title(match_title):
        return page.locator(
            "div.deal-item",
            has=page.locator("h4.deal-item__heading", has_text=match_title),
        ).first

    # 品番があれば品番優先で探す
    hinban_match = None
    try:
        hinban_match = re.search(r"(\d{3,5})", title)
    except Exception:
        hinban_match = None
    hinban = hinban_match.group(1) if hinban_match else ""

    search_title = title
    if hinban:
        search_title = hinban

    item = find_item_by_title(search_title)
    if item.count() == 0 and len(title) > 12 and not hinban:
        short_title = title[:12]
        print(f"  ⚠️ 完全一致が見つからないため短縮検索: {short_title}")
        item = find_item_by_title(short_title)

    for _ in range(8):
        if item.count() > 0:
            delete_link = item.locator('a[data-method="delete"]').first
            if delete_link.count() == 0:
                delete_link = item.locator('a:has-text("削除")').first
            if delete_link.count() == 0:
                print("  ⚠️ 下書きページで削除リンクが見つかりません")
                return False
            try:
                delete_link.scroll_into_view_if_needed()
            except Exception:
                pass
            page.once("dialog", lambda d: d.accept())
            delete_link.click(timeout=5000)
            page.wait_for_timeout(2000)
            try:
                item.wait_for(state="detached", timeout=10000)
            except Exception:
                pass
            print("  ✅ 下書きページで削除しました")
            return True

        more_button = page.locator('#after-selling-container_button a')
        if more_button.count() > 0 and more_button.is_visible(timeout=1000):
            more_button.click()
            page.wait_for_timeout(1200)
            item = find_item_by_title(search_title)
            if item.count() == 0 and len(title) > 12 and not hinban:
                item = find_item_by_title(title[:12])
            continue
        break

    print("  ⚠️ 下書きページで対象商品が見つかりません")
    return False

def delete_products(product_urls):
    """ラクマの商品を削除する"""
    if not product_urls:
        print("✅ 処理対象のURLがありません")
        return

    url_to_title = build_url_title_map()
    
    # URLを編集ページ形式に変換
    # https://item.fril.jp/{id} → https://fril.jp/item/{id}/edit
    edit_urls = []
    for url in product_urls:
        edit_url = convert_to_edit_url(url)
        edit_urls.append(edit_url)
        if edit_url != url:
            print(f"📝 変換: {url}")
            print(f"    → {edit_url}")
    
    with sync_playwright() as p:
        # Firefoxブラウザを起動（ユーザーデータを保持）
        print("🌐 ブラウザを起動中...")
        browser = p.firefox.launch_persistent_context(
            user_data_dir=USER_DATA_DIR,
            headless=False,
            slow_mo=500
        )
        
        page = browser.pages[0] if browser.pages else browser.new_page()
        
        # 手動ログインの機会を提供
        print("\n" + "=" * 70)
        print("🔐 ログイン確認と手動ログインの時間")
        print("=" * 70)
        print("📌 ブラウザを起動してログイン状態を確認します")
        print("=" * 70)
        
        # マイページに直接遷移（ログイン済みならそのまま表示、未ログインならログインページへ）
        print("\n🌐 マイページを開いています...")
        try:
            page.goto("https://fril.jp/mypage", timeout=30000)
            page.wait_for_timeout(3000)
            
            # 現在のURLを確認
            current_url = page.url
            print(f"📍 現在のURL: {current_url}")
            
            # ログインページにリダイレクトされた場合
            if "login" in current_url.lower():
                print("⚠️ ログインが必要です。")
                # Persistent Contextを使用しているため、通常は自動ログインされるはず
                # 数秒待ってから再確認
                page.wait_for_timeout(5000)
                current_url = page.url
                if "login" in current_url.lower():
                    print("❌ ログインできませんでした。ブラウザで一度手動ログインしてから再実行してください。")
                    browser.close()
                    return
            
            print("✅ ログイン済みです")
        except Exception as e:
            print(f"⚠️ ページ遷移エラー: {e}")
            print("処理を続行します...")
        
        # ログイン後のリダイレクト完了を待つ
        print("\n⏳ ログイン処理の完了を待っています...")
        page.wait_for_timeout(5000)  # 5秒待機してリダイレクト完了を待つ
        
        # 現在のページがログインページやリダイレクト中でないか確認
        current_url = page.url
        print(f"📍 ログイン後のURL: {current_url}")
        
        # もしまだログイン関連のURLなら、リダイレクト完了を待つ
        if "login" in current_url.lower() or "authorize" in current_url.lower() or "callback" in current_url.lower():
            print("🔄 リダイレクト処理中です。完了を待っています...")
            try:
                # ログイン関連のURLでなくなるまで待機（最大30秒）
                page.wait_for_url(
                    lambda url: "login" not in url.lower() and "authorize" not in url.lower() and "callback" not in url.lower(),
                    timeout=30000
                )
                print("✅ リダイレクト完了")
                page.wait_for_timeout(2000)
            except:
                print("⚠️ リダイレクトのタイムアウト。そのまま続行します")
        
        # ログイン確認
        print("\n🔍 ログイン状態を確認中...")
        try:
            page.goto("https://fril.jp/mypage", timeout=60000, wait_until="domcontentloaded")
            page.wait_for_timeout(3000)
        except Exception as e:
            print(f"⚠️ マイページへの遷移エラー: {e}")
            print("現在のページで確認を続けます...")
        
        current_url = page.url
        print(f"📍 確認URL: {current_url}")
        
        if "login" in current_url.lower():
            print("❌ ログインが確認できませんでした")
            print("⚠️ ログインが必要です。処理を中止します。")
            
            # Slack通知を送信（ログイン切れ）
            try:
                import subprocess
                subprocess.run([
                    r"..\venv\Scripts\python.exe", 
                    "send_slack_notification.py",
                    "❌ ラクマ削除: ログインセッションが切れています。手動でログインが必要です。",
                    "error"
                ], cwd=os.path.dirname(os.path.abspath(__file__)))
            except:
                pass
            
            browser.close()
            return
        
        print("✅ ログイン完了を確認しました")
        
        # Cookieを確認してセッション情報を表示
        cookies = browser.cookies()
        fril_cookies = [c for c in cookies if 'fril.jp' in c.get('domain', '')]
        print(f"🍪 ラクマのCookie数: {len(fril_cookies)}")
        
        if fril_cookies:
            print("✅ セッションが確立されました")
            # 主要なCookie名を表示
            cookie_names = [c.get('name', '') for c in fril_cookies]
            print(f"   Cookie名: {', '.join(cookie_names[:5])}")  # 最初の5つを表示
        else:
            print("⚠️ Cookie が見つかりません。セッションが不安定な可能性があります")
        
        # 処理開始
        print(f"\n🗑️ {len(edit_urls)} 件の商品を削除します\n")
        
        success_count = 0
        fail_count = 0
        
        for idx, url in enumerate(edit_urls, 1):
            print(f"[{idx}/{len(edit_urls)}] {url}")
            title = url_to_title.get(url, "")
            
            try:
                # 商品ページにアクセス
                try:
                    # まずマイページにアクセスしてセッションを確認（リトライ付き）
                    retry_count = 0
                    max_retries = 2
                    
                    while retry_count <= max_retries:
                        try:
                            page.goto("https://fril.jp/mypage", timeout=60000, wait_until="domcontentloaded")
                            page.wait_for_timeout(1000)
                            break
                        except Exception as retry_error:
                            retry_count += 1
                            if retry_count > max_retries:
                                raise retry_error
                            print(f"  🔄 リトライ {retry_count}/{max_retries}...")
                            page.wait_for_timeout(3000)
                    
                    if "login" in page.url.lower():
                        print("  ⚠️ セッションが切れています。この商品をスキップします。")
                        continue
                    
                    # 商品編集ページにアクセス
                    page.goto(url, timeout=60000, wait_until="domcontentloaded")
                    page.wait_for_timeout(3000)
                    
                    # ページ遷移後のURLを確認してログイン状態をチェック
                    current_url = page.url
                    print(f"  📍 アクセス先: {current_url}")
                    
                    # 404エラーページのチェック
                    if page.locator('h1.css-s6ybq1:has-text("お探しのページは見つかりませんでした")').count() > 0:
                        print("  ⚠️ ページが見つかりません（削除済みまたは無効なURL）")
                        print("  → 処理済みに記録してスキップします")
                        save_processed_rakuma_url(url)
                        success_count += 1
                        continue
                    
                    if "login" in current_url.lower():
                        print("  ❌ ログインページにリダイレクトされました")
                        print("  🔒 ブラウザでログインしてください...")
                        # ログイン完了を待つ（最大60秒）
                        try:
                            page.wait_for_url(lambda u: "login" not in u.lower() and "edit" in u.lower(), timeout=60000)
                            print("  ✅ ログイン完了、処理を続行します")
                            page.wait_for_timeout(2000)
                        except:
                            print("  ❌ ログインタイムアウト、この商品をスキップします")
                            fail_count += 1
                            continue
                    
                except Exception as goto_error:
                    print(f"  ❌ アクセス失敗: {goto_error}")
                    fail_count += 1
                    continue
                
                # 編集ページで「下書きに保存する」→「確認する」→「下書きに戻す」
                moved_to_draft = False
                try:
                    draft_button = page.locator('button:has-text("下書きに保存する")').first
                    if draft_button.count() > 0:
                        draft_button.click(timeout=5000)
                        print("  📝 「下書きに保存する」をクリック")

                        try:
                            confirm_pre_button = page.locator('button:has-text("確認する")').first
                            if confirm_pre_button.count() > 0:
                                confirm_pre_button.click(timeout=5000)
                                print("  📝 「確認する」をクリック")
                                page.wait_for_timeout(1000)
                        except Exception:
                            pass

                        try:
                            confirm_button = page.locator('button:has-text("下書きに戻す")').first
                            if confirm_button.count() > 0:
                                confirm_button.click(timeout=5000)
                                print("  ✅ 下書きに移動しました")
                                moved_to_draft = True
                                page.wait_for_timeout(2000)
                        except Exception:
                            pass
                except Exception:
                    pass

                if delete_from_drafts(page, title):
                    save_processed_rakuma_url(url)
                    success_count += 1
                    continue

                print("  ⚠️ 下書きページでも削除できませんでした")
                fail_count += 1
                continue
                    
            except Exception as e:
                print(f"  ❌ エラー: {e}")
                fail_count += 1
            
            # 次の商品までの待機
            if idx < len(edit_urls):
                page.wait_for_timeout(2000)
        
        print(f"\n📊 処理完了: 成功 {success_count} 件 / 失敗 {fail_count} 件")
        
        browser.close()

def main():
    print("=" * 60)
    print("ラクマ商品 削除ツール")
    print("=" * 60)
    
    # キャッシュディレクトリを削除（ログイン情報は保持）
    cache_dirs = ['cache2', 'shader-cache', 'ShaderCache', 'startupCache', 
                 'GrShaderCache', 'GraphiteDawnCache']
    for cache_dir_name in cache_dirs:
        cache_path = os.path.join(USER_DATA_DIR, cache_dir_name)
        if os.path.exists(cache_path):
            try:
                shutil.rmtree(cache_path)
                print(f"🗑️ キャッシュを削除: {cache_dir_name}")
            except Exception:
                pass
    
    # 処理済みURLを読み込み
    processed_urls = load_processed_rakuma_urls()
    
    # CSVから対象URLを読み込み
    target_urls = load_target_urls_from_csv()
    
    if not target_urls:
        print("✅ 処理対象がありません")
        return
    
    # URLを編集ページ形式に変換してから比較
    target_edit_urls = [convert_to_edit_url(url) for url in target_urls]
    
    # 未処理のURLのみをフィルタリング
    unprocessed_urls = [url for url in target_edit_urls if url not in processed_urls]
    
    if not unprocessed_urls:
        print(f"✅ すべて処理済みです（既処理: {len(target_edit_urls)} 件）")
        return
    
    print(f"\n📋 未処理: {len(unprocessed_urls)} 件")
    print(f"📋 既処理: {len(target_edit_urls) - len(unprocessed_urls)} 件")
    
    # 削除
    delete_products(unprocessed_urls)

if __name__ == '__main__':
    main()
