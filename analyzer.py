import sqlite3
import os
import requests
import sys
import time
from datetime import datetime, timedelta

# 自動抓取檔案所在的目錄
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "dns_monitor.db")

def get_db_connection():
    """建立連線並加入 timeout 解決併發鎖定問題"""
    # timeout=10 確保若資料庫被 watcher.py 鎖定，會自動等待 10 秒
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    return conn

def send_telegram(token, chat_id, message):
    """加入重試機制與延長超時時間，解決連線失敗問題"""
    if not token or not chat_id or token == 'None' or chat_id == 'None':
        print("⚠️ 跳過發送：未設定 Telegram 金鑰")
        return 
        
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": message, "parse_mode": "Markdown"}
    
    # 增加重試機制，最多嘗試 3 次
    for i in range(3):
        try:
            # 將 timeout 增加到 20 秒，應對較慢的網路環境
            response = requests.post(url, json=payload, timeout=20)
            if response.status_code == 200:
                print(f"✅ 報表已成功發送至 Telegram (第 {i+1} 次嘗試)")
                return
            else:
                print(f"❌ 發送失敗，狀態碼: {response.status_code}")
        except Exception as e:
            print(f"🔄 第 {i+1} 次連線失敗，正在重試... ({e})")
            time.sleep(3) # 等待 3 秒後再次嘗試
            
    print("❌ 經過多次嘗試後仍無法連線至 Telegram。")

def analyze_report(target_date_str=None):
    # --- 1. 日期邏輯處理 ---
    if target_date_str:
        try:
            target_date = datetime.strptime(target_date_str, '%Y-%m-%d')
            is_manual = True
        except ValueError:
            print("❌ 日期格式錯誤，請使用 YYYY-MM-DD")
            return
    else:
        target_date = datetime.now() - timedelta(days=1)
        is_manual = False

    date_start = target_date.strftime('%Y-%m-%d 00:00:00')
    date_end = target_date.strftime('%Y-%m-%d 23:59:59')
    display_date = target_date.strftime('%Y-%m-%d')

    print(f"\n📊 正在產生 {display_date} 的分析報表...")

    conn = get_db_connection()
    cursor = conn.cursor()

    # --- 2. 獲取具備金鑰的設備 ---
    cursor.execute("""
        SELECT device_name, telegram_token, telegram_chat_id 
        FROM devices 
        WHERE telegram_token IS NOT NULL 
          AND telegram_token != '' 
          AND LENGTH(telegram_token) > 5
    """)
    admin_devices = cursor.fetchall()

    print(f"{'='*45}")
    print(f" 🔑 具備 Telegram 金鑰之設備清單")
    print(f"{'='*45}")
    if not admin_devices:
        print(" (⚠️ 查詢無資料：請確認資料庫中已填寫 Token 並點擊 Write Changes)")
    else:
        for row in admin_devices:
            masked_token = f"{row['telegram_token'][:6]}..."
            print(f"設備: {row['device_name']:<15} | Token: {masked_token:<10} | ID: {row['telegram_chat_id']}")
    print(f"{'='*45}")

    # --- 3. 核心數據統計 ---
    cursor.execute("SELECT COUNT(*) FROM dns_logs WHERE timestamp BETWEEN ? AND ?", (date_start, date_end))
    total_queries = cursor.fetchone()[0]

    if total_queries == 0:
        print(f"ℹ️ {display_date} 無任何紀錄，取消分析。")
        conn.close()
        return

    # 各設備統計 (含佔比)
    cursor.execute("""
        SELECT device_name, COUNT(*) as count 
        FROM dns_logs 
        WHERE timestamp BETWEEN ? AND ?
        GROUP BY device_name 
        ORDER BY count DESC
    """, (date_start, date_end))
    device_stats = cursor.fetchall()

    # 熱門網域統計
    cursor.execute("""
        SELECT domain, COUNT(*) as count 
        FROM dns_logs 
        WHERE timestamp BETWEEN ? AND ?
        GROUP BY domain 
        ORDER BY count DESC 
        LIMIT 10
    """, (date_start, date_end))
    top_domains = cursor.fetchall()

    # --- 4. 終端機顯示與佔比 ---
    print(f"\n📱 各設備活動量統計 (總計: {total_queries})")
    print(f"{'-'*45}")
    for row in device_stats:
        pct = (row['count'] / total_queries) * 100
        print(f"設備: {row['device_name']:<15} | 查詢: {row['count']:>5} 次 ({pct:>5.1f}%)")

    print(f"\n🌍 熱門存取網域 Top 10")
    print(f"{'-'*45}")
    for i, row in enumerate(top_domains, 1):
        pct = (row['count'] / total_queries) * 100
        print(f"{i:>2}. {row['domain']:<28} | {row['count']:>4} 次 ({pct:>5.1f}%)")
    print(f"{'='*45}\n")

    # --- 5. 組合 Telegram 訊息 ---
    type_label = "手動回溯" if is_manual else "每日自動"
    msg = f"🛡️ *DNS {type_label}通報* ({display_date})\n"
    msg += f"━━━━━━━━━━━━━━━\n"
    msg += f"📈 *當日總查詢量*: `{total_queries}`\n\n"
    
    msg += f"📱 *各設備佔比*:\n"
    for row in device_stats:
        pct = (row['count'] / total_queries) * 100
        msg += f"• {row['device_name']}: `{row['count']}` 次 ({pct:.1f}%)\n"

    msg += f"\n🌍 *熱門網域排行 (Top 5)*:\n"
    for i, row in enumerate(top_domains[:5], 1):
        pct = (row['count'] / total_queries) * 100
        msg += f"{i}. {row['domain']}: `{pct:.1f}%`\n"

    msg += f"━━━━━━━━━━━━━━━\n"
    msg += f"💡 _結束時間: {datetime.now().strftime('%Y-%m-%d %H:%M')}_"

    # --- 6. 發送報表 ---
    for admin in admin_devices:
        send_telegram(admin['telegram_token'], admin['telegram_chat_id'], msg)

    conn.close()

if __name__ == "__main__":
    if len(sys.argv) > 1:
        analyze_report(sys.argv[1])
    else:
        analyze_report()