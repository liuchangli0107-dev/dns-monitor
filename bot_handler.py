import time
import requests
import sqlite3
import os
import sys
import subprocess
from datetime import datetime, timedelta

# 強制定位目錄
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(BASE_DIR)
DB_PATH = os.path.join(BASE_DIR, "dns_monitor.db")

def get_bot_config():
    """從資料庫獲取 Token 與 授權的 Chat ID 清單"""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    # 這裡只抓取 devices 表中有紀錄的 chat_id
    cur.execute("SELECT telegram_token, telegram_chat_id FROM devices WHERE telegram_token IS NOT NULL")
    rows = cur.fetchall()
    conn.close()
    
    if not rows:
        return None, []
    
    token = rows[0][0]
    authorized_chats = [str(row[1]) for row in rows]
    return token, authorized_chats

def handle_command(token, chat_id, text):
    """處理指令邏輯"""
    chat_id = str(chat_id)
    token, authorized_chats = get_bot_config()

    # 第二步：安全檢查 - 只反應 devices 表裡的 chat_id
    if chat_id not in authorized_chats:
        print(f"⚠️ 拒絕未授權請求: {chat_id}")
        return

    print(f"📨 收到來自 {chat_id} 的指令: {text}")

    if text.startswith("/report"):
        # 解析日期 (例如 /report 2026-03-23)
        parts = text.split()
        target_date = parts[1] if len(parts) > 1 else (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        
        # 呼叫 analyzer.py (手動查詢不帶 --record)
        subprocess.run([
            sys.executable, 
            "analyzer.py", 
            target_date, 
            "--type", "both"
        ])

def start_polling():
    token, _ = get_bot_config()
    if not token:
        print("❌ 找不到 Telegram Token，請檢查資料庫。")
        return

    api_url = f"https://api.telegram.org/bot{token}/"
    last_update_id = 0
    
    print(f"🤖 DNS Bot 監聽中 (授權模式)...")
    
    while True:
        try:
            # 使用 Long Polling 減少伺服器負擔
            resp = requests.get(f"{api_url}getUpdates", params={
                "offset": last_update_id + 1, 
                "timeout": 30
            }, timeout=35).json()

            if "result" in resp:
                for update in resp["result"]:
                    last_update_id = update["update_id"]
                    if "message" in update and "text" in update["message"]:
                        msg = update["message"]
                        handle_command(token, msg["chat"]["id"], msg["text"])
        
        except Exception as e:
            print(f"📡 網路異常或超時，5秒後重試... ({e})")
            time.sleep(5)

if __name__ == "__main__":
    start_polling()