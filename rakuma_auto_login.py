"""
ラクマの自動ログイン機能
ログイン確認メール送信まで自動化
"""
import os
import time
from dotenv import load_dotenv
from playwright.sync_api import Page, TimeoutError

# .envファイル読み込み
load_dotenv(r"C:\Users\progr\Desktop\Python\mercari_dorekai\.env")

RAKUMA_EMAIL = os.getenv("RAKUMA_EMAIL")
RAKUMA_PASSWORD = os.getenv("RAKUMA_PASSWORD")
RAKUMA_LOGIN_URL = "https://fril.jp/login"


def auto_login_rakuma(page: Page, force_login: bool = False) -> bool:
    """
    ラクマへの自動ログイン
    
    Args:
        page: Playwright ページオブジェクト
        force_login: True の場合、既にログイン済みでも再ログインを試みる
        
    Returns:
        bool: ログイン成功で True、失敗で False
    """
    try:
        # 環境変数確認
        if not RAKUMA_EMAIL or not RAKUMA_PASSWORD:
            print("⚠️ ラクマのログイン情報が .env に設定されていません")
            print("   RAKUMA_EMAIL と RAKUMA_PASSWORD を設定してください")
            return False
            
        if "your_rakuma_email" in RAKUMA_EMAIL or "your_rakuma_password" in RAKUMA_PASSWORD:
            print("⚠️ .env のラクマログイン情報をご自身のものに変更してください")
            return False
        
        print(f"🔐 ラクマへの自動ログインを開始...")
        
        # ログインページへ移動
        if force_login or not is_logged_in_rakuma(page):
            print(f"   ログインページへ移動: {RAKUMA_LOGIN_URL}")
            page.goto(RAKUMA_LOGIN_URL, timeout=30000, wait_until='load')
            time.sleep(2)
            
            # メールアドレス入力
            try:
                email_input = page.locator('input[name="email"], input[type="email"], input[placeholder*="メール"]').first
                email_input.fill(RAKUMA_EMAIL)
                print(f"   ✅ メールアドレス入力完了")
                time.sleep(0.5)
            except Exception as e:
                print(f"   ❌ メールアドレス入力フィールドが見つかりません: {e}")
                return False
            
            # パスワード入力
            try:
                password_input = page.locator('input[name="password"], input[type="password"], input[placeholder*="パスワード"]').first
                password_input.fill(RAKUMA_PASSWORD)
                print(f"   ✅ パスワード入力完了")
                time.sleep(0.5)
            except Exception as e:
                print(f"   ❌ パスワード入力フィールドが見つかりません: {e}")
                return False
            
            # ログインボタンをクリック
            try:
                login_button = page.locator('button[type="submit"], input[type="submit"], button:has-text("ログイン")').first
                login_button.click()
                print(f"   ✅ ログインボタンをクリック")
                time.sleep(3)
            except Exception as e:
                print(f"   ❌ ログインボタンが見つかりません: {e}")
                return False
            
            # ログイン確認メール送信が必要かチェック
            page_content = page.content().lower()
            if "確認コード" in page_content or "認証コード" in page_content or "メール" in page_content:
                print(f"\n📧 ログイン確認メールの送信が必要です")
                return handle_verification_email(page)
            
            # ログイン成功確認
            time.sleep(2)
            if is_logged_in_rakuma(page):
                print(f"✅ ラクマへの自動ログイン成功")
                return True
            else:
                print(f"❌ ログイン後の確認に失敗しました")
                return False
        else:
            print(f"✅ 既にログイン済みです")
            return True
            
    except Exception as e:
        print(f"❌ 自動ログイン中にエラーが発生: {e}")
        return False


def handle_verification_email(page: Page) -> bool:
    """
    ログイン確認メールの送信処理
    
    Args:
        page: Playwright ページオブジェクト
        
    Returns:
        bool: 成功で True
    """
    try:
        print(f"   確認メール送信ボタンを探しています...")
        
        # 送信ボタンを探してクリック
        send_button_selectors = [
            'button:has-text("送信")',
            'button:has-text("確認コードを送信")',
            'button:has-text("メールを送信")',
            'input[type="submit"][value*="送信"]',
            'button[type="submit"]'
        ]
        
        button_clicked = False
        for selector in send_button_selectors:
            try:
                button = page.locator(selector).first
                if button.is_visible(timeout=2000):
                    button.click()
                    print(f"   ✅ 確認メール送信ボタンをクリック")
                    button_clicked = True
                    break
            except:
                continue
        
        if not button_clicked:
            print(f"   ℹ️ 確認メール送信ボタンが見つかりませんでした（既に送信済みの可能性）")
        
        time.sleep(2)
        
        print(f"\n📧 ログイン確認メールが送信されました")
        print(f"   メールボックスを確認して、確認コードを入力してください")
        print(f"   ブラウザで操作を完了後、[ENTER] キーを押してください")
        
        input()  # ユーザーの操作待ち
        
        # 確認後のログイン状態チェック
        time.sleep(2)
        if is_logged_in_rakuma(page):
            print(f"✅ ログイン確認完了")
            return True
        else:
            print(f"⚠️ ログイン確認が完了していないようです")
            return False
            
    except Exception as e:
        print(f"❌ 確認メール送信処理中にエラー: {e}")
        return False


def is_logged_in_rakuma(page: Page) -> bool:
    """ラクマでログイン済みかどうかを判定する"""
    try:
        from bs4 import BeautifulSoup
        html = page.content()
        soup = BeautifulSoup(html, 'html.parser')
        
        # ログイン済みの場合、ユーザーメニューが存在
        # ログイン未済みの場合、ログインボタンが存在
        import re
        login_button = soup.find('a', {'href': re.compile(r'login|signin', re.IGNORECASE)})
        is_logged_in = login_button is None
        
        return is_logged_in
    except Exception as e:
        print(f"  ⚠️ ログイン状態判定エラー: {e}")
        return False


if __name__ == "__main__":
    """テスト実行用"""
    from playwright.sync_api import sync_playwright
    
    script_dir = os.path.dirname(os.path.abspath(__file__))
    user_data_dir = os.path.join(script_dir, 'rakuma_user_data')
    
    with sync_playwright() as p:
        browser = p.chromium.launch_persistent_context(
            user_data_dir=user_data_dir,
            headless=False,
            timeout=60000
        )
        page = browser.pages[0] if browser.pages else browser.new_page()
        
        # 自動ログインテスト
        success = auto_login_rakuma(page, force_login=False)
        
        if success:
            print("\n✅ テスト成功")
        else:
            print("\n❌ テスト失敗")
        
        input("\n処理を終了するには [ENTER] キーを押してください...")
        browser.close()
