import time
import requests
import sqlite3
import os
import sys
import subprocess
from datetime import datetime

# 自動偵測目錄，確保三台電腦通用
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(BASE_DIR)
DB_PATH = os.path.join(BASE_DIR, "dns_monitor.db")

user_states = {}

def get_bot_config():
    """獲取 Token 與 授權 Chat ID"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute("SELECT telegram_token, telegram_chat_id FROM devices WHERE telegram_token IS NOT NULL")
        rows = cur.fetchall()
        conn.close()
        return (rows[0][0], [str(row[1]) for row in rows]) if rows else (None, [])
    except Exception as e:
        print(f"❌ 資料庫讀取失敗: {e}")
        return None, []

def send_tg_message(token, chat_id, text):
    """發送訊息"""
    try:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        requests.post(url, data={"chat_id": chat_id, "text": text, "parse_mode": "Markdown"}, timeout=10)
    except:
        pass 

def search_domain_stats(keyword):
    """搜尋邏輯"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        query = """
            SELECT strftime('%m-%d %H:00', timestamp) AS hr, domain, COUNT(*) 
            FROM dns_logs WHERE domain LIKE ? GROUP BY 1, 2 ORDER BY 1 DESC LIMIT 20
        """
        cur.execute(query, (f"%{keyword.strip()}%",))
        rows = cur.fetchall()
        conn.close()
        if not rows: return None
        res = f"📊 *「{keyword}」時段統計*\n━━━━━━━━━━━━\n"
        for hr, dom, cnt in rows:
            res += f"`{hr}` | **{cnt}** | `{dom[:25]}`\n"
        return res
    except:
        return "❌ 搜尋時發生錯誤"

def handle_command(token, chat_id, text):
    chat_id = str(chat_id)
    _, authorized_chats = get_bot_config()
    if chat_id not in authorized_chats: return
    
    cmd = text.split('@')[0].lower()

    if cmd in ["/help", "/start"]:
        send_tg_message(token, chat_id, "🤖 *DNS 助理*\n📊 `/report` - 生成報表\n🔍 `/search` - 搜尋網域\n🚫 `/cancel` - 取消操作")
        return

    if cmd == "/cancel":
        user_states.pop(chat_id, None)
        send_tg_message(token, chat_id, "✅ 已取消目前操作。")
        return

    # --- 修改後的報表模式引導 ---
    if cmd == "/report":
        user_states[chat_id] = {'type': 'report'}
        guide_msg = (
            "📅 *報表模式*\n\n"
            "格式範例：\n"
            "• `2026-03-21 15` (特定時報表)\n"
            "• `2026-03-21` (當日全天報表)\n\n"
            "直接輸入內容即可："
        )
        send_tg_message(token, chat_id, guide_msg)
        return

    if cmd == "/search":
        user_states[chat_id] = {'type': 'search'}
        send_tg_message(token, chat_id, "🔍 *搜尋模式*\n請輸入關鍵字 (例如 `google`)：")
        return

    state = user_states.get(chat_id)
    if state:
        input_text = text.strip()
        if state['type'] == 'report':
            send_tg_message(token, chat_id, f"⌛ 正在生成 `{input_text}` 報表...")
            # 使用 sys.executable 確保環境一致
            subprocess.run([sys.executable, "analyzer.py", input_text, "--type", "both"])
            user_states.pop(chat_id, None)
        elif state['type'] == 'search':
            result = search_domain_stats(input_text)
            if result:
                send_tg_message(token, chat_id, result)
                user_states.pop(chat_id, None)
            else:
                send_tg_message(token, chat_id, f"❌ 找不到 `{input_text}`，請重試或輸入 `/cancel`：")

def start_polling():
    token, _ = get_bot_config()
    if not token:
        print("🚨 找不到 Token，程式結束。")
        sys.exit(1)

    last_update_id = 0
    error_count = 0
    print(f"🤖 Bot 已啟動，工作目錄: {BASE_DIR}")

    while True:
        try:
            url = f"https://api.telegram.org/bot{token}/getUpdates"
            resp = requests.get(url, params={"offset": last_update_id + 1, "timeout": 30}, timeout=35).json()
            
            if resp.get("ok"):
                error_count = 0 
                for update in resp.get("result", []):
                    last_update_id = update["update_id"]
                    if "message" in update and "text" in update["message"]:
                        handle_command(token, update["message"]["chat"]["id"], update["message"]["text"])
            else:
                raise Exception(f"Telegram API 回傳錯誤: {resp.get('description')}")

        except Exception as e:
            error_count += 1
            # 遞增等待機制，最高 60 秒
            wait_time = min(error_count * 10, 60) 
            print(f"📡 連線異常 ({error_count}/5): {e}")
            
            # 核心優化：連線失敗多次則結束，由 Launchd 重啟
            if error_count >= 5:
                print("🚨 連線持續失敗，主動結束進程由 Launchd 重啟。")
                sys.exit(1)
            
            time.sleep(wait_time)

if __name__ == "__main__":
    start_polling()