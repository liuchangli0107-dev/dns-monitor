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
    """建立連線並設定 Row Factory 方便讀取欄位"""
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    return conn

def send_telegram(token, chat_id, message):
    """發送 Telegram 訊息"""
    if not token or not chat_id or token == 'None' or chat_id == 'None':
        print("⚠️ 跳過發送：未設定 Telegram 金鑰")
        return 
        
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": message, "parse_mode": "Markdown"}
    
    try:
        response = requests.post(url, json=payload, timeout=20)
        if response.status_code == 200:
            print(f"✅ 報表已成功發送至 Telegram")
            return True
        else:
            print(f"❌ Telegram 發送失敗: {response.text}")
    except Exception as e:
        print(f"⚠️ 發送報表時出錯: {e}")
    return False

def analyze_and_report(target_date=None):
    """執行分析並發送報表"""
    is_manual = target_date is not None
    if not target_date:
        # 預設分析昨天的數據
        target_date = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
    
    conn = get_db_connection()
    cursor = conn.cursor()

    # 判斷輸入格式：如果是 10 字元則是日期，超過則視為包含小時
    # 這裡使用 LIKE 來相容 '2026-03-17%' 或 '2026-03-17 15%'
    search_pattern = f"{target_date}%"

    # --- 1. 取得指定時間總查詢量 ---
    cursor.execute("SELECT COUNT(*) FROM dns_logs WHERE timestamp LIKE ?", (search_pattern,))
    total_queries = cursor.fetchone()[0]

    # --- 2. 取得 Telegram 配置 ---
    cursor.execute("SELECT telegram_token, telegram_chat_id FROM devices WHERE telegram_token IS NOT NULL LIMIT 1")
    config = cursor.fetchone()

    # --- 3. 熱門網域 Top 10 (加上百分比) ---
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

    # --- 4. 組合 Telegram 訊息 ---
    type_label = "手動回溯" if is_manual else "每日全紀錄"
    msg = f"🛡️ *DNS {type_label}通報* ({target_date})\n"
    msg += f"━━━━━━━━━━━━\n"
    msg += f"📈 *當前總查詢量*: `{total_queries}`\n\n"
    
    msg += f"🌍 *熱門存取網域 Top 10*:\n"
    if top_domains and total_queries > 0:
        for i, row in enumerate(top_domains, 1):
            # 計算該網域所佔百分比
            percentage = (row['count'] / total_queries) * 100
            msg += f"{i}. `{row['domain']}`\n   共 `{row['count']}` 次 ({percentage:.1f}%)\n"
    elif total_queries == 0:
        msg += "_該時段無任何查詢紀錄_\n"
    else:
        msg += "_該時段無資料紀錄_\n"
        
    msg += f"━━━━━━━━━━━━\n"
    msg += f"⏰ 生成時間: {datetime.now().strftime('%H:%M:%S')}"

    # 終端機預覽
    print(f"\n--- {type_label}分析結果 ({target_date}) ---")
    print(msg.replace('*', '').replace('`', ''))

    # --- 5. 發送報表 ---
    if config:
        send_telegram(config['telegram_token'], config['telegram_chat_id'], msg)
    else:
        print("⚠️ 提示：未在資料庫中找到有效的 Telegram Token，僅顯示於終端機。")

    conn.close()

if __name__ == "__main__":
    if len(sys.argv) > 1:
        analyze_and_report(sys.argv[1])
    else:
        analyze_and_report()