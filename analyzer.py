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
        print(f"⚠️ 發送嘗試出錯: {e}")
    return False

def analyze_and_report(target_date=None):
    """執行分析並發送報表"""
    # 邏輯修正：如果沒帶參數，自動設定為「昨天」
    if not target_date:
        target_date = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
        is_manual = False
    else:
        is_manual = True
    
    conn = get_db_connection()
    cursor = conn.cursor()

    # --- 1. 取得總查詢量 ---
    cursor.execute("SELECT COUNT(l.id) FROM dns_logs l LEFT JOIN devices d ON d.ip_address = l.client_ip WHERE DATE(l.timestamp) = ? AND d.owner != 'Charlie'", (target_date,))
    total_queries = cursor.fetchone()[0]

    # --- 2. 取得配置 ---
    cursor.execute("SELECT telegram_token, telegram_chat_id FROM devices WHERE telegram_token IS NOT NULL LIMIT 1")
    config = cursor.fetchone()
    
    # --- 3. 執行統計查詢 (LEFT JOIN) ---
    query_device = """
    SELECT d.device_name, d.ip_address, COUNT(l.id) as count
    FROM devices d
    LEFT JOIN dns_logs l ON d.ip_address = l.client_ip AND DATE(l.timestamp) = ?
    WHERE d.owner != 'Charlie'
    GROUP BY d.ip_address
    ORDER BY count DESC
    """
    cursor.execute(query_device, (target_date,))
    device_stats = cursor.fetchall()

    # --- 4. 取得熱門網域 Top 10 ---
    query_domains = """
    SELECT l.domain, COUNT(l.id) as count
    FROM dns_logs l
    JOIN devices d ON l.client_ip = d.ip_address
    WHERE DATE(l.timestamp) = ? AND d.owner != 'Charlie'
    GROUP BY l.domain
    ORDER BY count DESC
    LIMIT 10
    """
    cursor.execute(query_domains, (target_date,))
    top_domains = cursor.fetchall()

    # --- 5. 組合訊息 ---
    type_label = "手動回溯" if is_manual else "每日結算"
    msg = f"🛡️ *DNS {type_label}通報* ({target_date})\n"
    msg += f"━━━━━━━━━━━━━━━\n"
    msg += f"📈 *當日總查詢量*: `{total_queries}`\n\n"
    
    msg += f"📱 *各設備佔比*:\n"
    for row in device_stats:
        pct = (row['count'] / total_queries) * 100 if total_queries > 0 else 0
        msg += f"• {row['device_name']}: `{row['count']}` 次 ({pct:.1f}%)\n"
    
    msg += f"\n🌍 *熱門網域 Top 10*:\n"
    if top_domains:
        for i, row in enumerate(top_domains, 1):
            msg += f"{i}. `{row['domain']}` ({row['count']}次)\n"
    else:
        msg += "_今日無存取紀錄_\n"
        
    msg += f"━━━━━━━━━━━━━━━\n"
    msg += f"⏰ 生成時間: {datetime.now().strftime('%H:%M:%S')}"

    # --- 6. 發送與顯示 ---
    print(f"\n--- {type_label}分析結果 ({target_date}) ---")
    print(msg.replace('*', '').replace('`', '')) # 終端機顯示簡潔版

    if config:
        send_telegram(config['telegram_token'], config['telegram_chat_id'], msg)

    conn.close()

if __name__ == "__main__":
    if len(sys.argv) > 1:
        # 手動執行模式: python3 analyzer.py 2026-03-17
        analyze_and_report(sys.argv[1])
    else:
        # 自動模式 (不帶參數): 分析昨天
        analyze_and_report()