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

# 紀錄用戶狀態： {chat_id: 'WAITING_DATE'}
user_states = {}

def get_bot_config():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT telegram_token, telegram_chat_id FROM devices WHERE telegram_token IS NOT NULL")
    rows = cur.fetchall()
    conn.close()
    return (rows[0][0], [str(row[1]) for row in rows]) if rows else (None, [])

def send_tg_message(token, chat_id, text):
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    requests.post(url, data={"chat_id": chat_id, "text": text, "parse_mode": "Markdown"})

def handle_command(token, chat_id, text):
    chat_id = str(chat_id)
    _, authorized_chats = get_bot_config()

    if chat_id not in authorized_chats:
        return

    # 1. 初始指令
    if text == "/report":
        user_states[chat_id] = "WAITING_DATE"
        send_tg_message(token, chat_id, "📅 *請輸入查詢日期與小時*\n\n格式範例：\n• `2026-03-21 15` (特定時報表)\n• `2026-03-21` (當日全天報表)\n\n直接輸入內容即可：")
        return

    # 2. 處理後續輸入
    if user_states.get(chat_id) == "WAITING_DATE":
        input_data = text.strip()
        
        # 簡單驗證格式 (至少要有日期格式)
        if len(input_data) < 10:
            send_tg_message(token, chat_id, "❌ 格式似乎不正確，請重新輸入（例如：2026-03-21 15）")
            return

        send_tg_message(token, chat_id, f"🔍 正在為您生成 `{input_data}` 的數據報表...")
        
        # 執行您剛改好的 analyzer.py
        # 這裡直接把輸入的字串傳進去，因為您的 analyzer.py 已支援 "YYYY-MM-DD HH"
        subprocess.run([
            sys.executable, 
            "analyzer.py", 
            input_data, 
            "--type", "both"
        ])
        
        # 完成後清除狀態
        del user_states[chat_id]

def start_polling():
    token, _ = get_bot_config()
    if not token: return
    
    last_update_id = 0
    print(f"🤖 DNS 互動機器人已啟動 (對話模式)...")
    
    while True:
        try:
            api_url = f"https://api.telegram.org/bot{token}/getUpdates"
            resp = requests.get(api_url, params={"offset": last_update_id + 1, "timeout": 30}, timeout=35).json()

            if "result" in resp:
                for update in resp["result"]:
                    last_update_id = update["update_id"]
                    if "message" in update and "text" in update["message"]:
                        msg = update["message"]
                        handle_command(token, msg["chat"]["id"], msg["text"])
        except Exception as e:
            time.sleep(5)

if __name__ == "__main__":
    start_polling()