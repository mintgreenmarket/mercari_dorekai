"""
在庫連動システム - 定期実行スクリプト
30分ごとに全商品の在庫を同期
"""

import schedule
import time
from stock_sync import full_sync, log

def job():
    """定期実行ジョブ"""
    try:
        full_sync()
    except Exception as e:
        log(f"❌ 定期実行エラー: {e}")

if __name__ == '__main__':
    log("🚀 定期在庫同期システム起動")
    log("📅 実行間隔: 30分ごと")
    
    # 起動時に1度実行
    job()
    
    # 30分ごとに実行
    schedule.every(30).minutes.do(job)
    
    while True:
        schedule.run_pending()
        time.sleep(60)
