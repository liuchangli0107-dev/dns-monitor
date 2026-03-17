import sqlite3
import os
import requests
import sys
from datetime import datetime, timedelta

# 設定路徑
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "dns_monitor.db")
REPORT_FLAG_DIR = os.path.join(BASE_DIR, "report")

# 確保 report 資料夾存在
if not os.path.exists(REPORT_FLAG_DIR):
    os.makedirs(REPORT_FLAG_DIR)

def get_db_connection():
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    return conn

def send_telegram(token, chat_id, message):
    if not token or not chat_id or token == 'None' or chat_id == 'None':
        return False
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": message, "parse_mode": "Markdown"}
    try:
        response = requests.post(url, json=payload, timeout=20)
        return response.status_code == 200
    except:
        return False

def analyze_and_report(target_date=None):
    is_manual = target_date is not None
    # 如果沒傳日期，預設分析「昨天」
    if not target_date:
        target_date = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
    
    # --- Flag 判斷邏輯 ---
    # 只有在非手動（自動排程）的情況下才檢查 Flag
    flag_file = os.path.join(REPORT_FLAG_DIR, f"{target_date}.flag")
    if not is_manual and os.path.exists(flag_file):
        print(f"⏩ {target_date} 的報表已發送過，跳過執行。")
        return

    conn = get_db_connection()
    cursor = conn.cursor()

    # 搜尋模式 (相容日期與小時)
    search_pattern = f"{target_date}%"

    # 1. 取得總查詢量
    cursor.execute("SELECT COUNT(*) FROM dns_logs WHERE timestamp LIKE ?", (search_pattern,))
    total_queries = cursor.fetchone()[0]

    # 2. 取得 Telegram 配置
    cursor.execute("SELECT telegram_token, telegram_chat_id FROM devices WHERE telegram_token IS NOT NULL LIMIT 1")
    config = cursor.fetchone()

    # 3. 熱門網域 Top 10
    query_domains = """
    SELECT domain, COUNT(*) as count
    FROM dns_logs
    WHERE timestamp LIKE ?
    GROUP BY domain
    ORDER BY count DESC
    LIMIT 10
    """
    cursor.execute(query_domains, (search_pattern,))
    top_domains = cursor.fetchall()

    # 4. 組合訊息
    type_label = "手動回溯" if is_manual else "自動發送"
    msg = f"🛡️ *DNS {type_label}通報* ({target_date})\n"
    msg += f"━━━━━━━━━━━━\n"
    msg += f"📈 *查詢總量*: `{total_queries}`\n\n"
    
    msg += f"🌍 *熱門存取網域 Top 10*:\n"
    if top_domains and total_queries > 0:
        for i, row in enumerate(top_domains, 1):
            pct = (row['count'] / total_queries) * 100
            msg += f"{i}. `{row['domain']}`\n   共 `{row['count']}` 次 ({pct:.1f}%)\n"
    else:
        msg += "_無資料紀錄_\n"
        
    msg += f"━━━━━━━━━━━━\n"
    msg += f"⏰ 執行時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"

    # 5. 發送報表並建立 Flag
    if config:
        success = send_telegram(config['telegram_token'], config['telegram_chat_id'], msg)
        if success and not is_manual:
            with open(flag_file, 'w') as f:
                f.write(f"Sent at {datetime.now()}")
            print(f"✅ {target_date} 報表發送成功，已建立標記檔。")
    else:
        print(msg.replace('*', '').replace('`', ''))

    conn.close()

if __name__ == "__main__":
    # 支援多參數合併 (處理 2026-03-17 15 格式)
    input_date = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else None
    analyze_and_report(input_date)