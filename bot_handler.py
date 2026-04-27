import json
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


def get_bot_config():
    """獲取 Token 與 授權 Chat ID"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute(
            "SELECT telegram_token, telegram_chat_id FROM devices WHERE telegram_token IS NOT NULL"
        )
        rows = cur.fetchall()
        conn.close()
        return (rows[0][0], [str(row[1]) for row in rows]) if rows else (None, [])
    except Exception as e:
        print(f"get_bot_config ❌ 資料庫讀取失敗: {e}", flush=True)
        return None, []


def send_tg_message(token, chat_id, text, reply_markup=None):
    """發送訊息，支援 Inline 按鈕"""
    try:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "Markdown",
        }
        if reply_markup:
            payload["reply_markup"] = json.dumps(reply_markup)  # 必須轉為 JSON 字串

        requests.post(url, data=payload, timeout=10)
    except Exception as e:
        print(f"send_tg_message ❌ 發送失敗: {e}", flush=True)


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
        if not rows:
            return None
        res = f"📊 *「{keyword}」時段統計*\n━━━━━━━━━━━━\n"
        for hr, dom, cnt in rows:
            res += f"`{hr}` | **{cnt}** | `{dom[:25]}`\n"
        return res
    except Exception as e:
        print(f"search_domain_stats ❌ 搜尋時發生錯誤: {e}", flush=True)
        return "❌ 搜尋時發生錯誤"


def cmd_help(token, chat_id, user_states):
    help_msg = "🤖 *DNS 助理*\n📊 `/report` - 生成報表\n🔍 `/search` - 搜尋網域\n🚫 `/cancel` - 取消操作"
    reply_markup = {
        "inline_keyboard": [
            [
                {"text": "📊 生成報表", "callback_data": "report"},
                {"text": "🔍 搜尋網域", "callback_data": "search"},
            ],
            [
                {"text": "🤖 操作說明", "callback_data": "help"},
                {"text": "🚫 取消操作", "callback_data": "cancel"},
            ],
        ]
    }
    send_tg_message(token, chat_id, help_msg, reply_markup)
    return user_states


def cmd_report(token, chat_id, user_states):
    today_str = datetime.now().strftime("%Y-%m-%d")
    hour_str = datetime.now().strftime("%H")
    user_states[chat_id] = {"type": "report"}
    print(
        f"cmd_report DEBUG: 已設定 {chat_id} 狀態: {user_states[chat_id]}", flush=True
    )
    guide_msg = (
        "📅 *報表模式*\n\n"
        "請輸入要查詢的日期或時段：\n"
        f"• `{today_str} {hour_str}` (特定時報表)\n"
        f"• `{today_str}` (當日全天報表)\n\n"
        "💡 *提示*：直接輸入內容即可開始查詢。"
    )
    reply_markup = {
        "inline_keyboard": [
            [
                {"text": "🤖 操作說明", "callback_data": "help"},
                {"text": "🚫 取消操作", "callback_data": "cancel"},
            ],
        ]
    }
    send_tg_message(token, chat_id, guide_msg, reply_markup)
    return user_states


def cmd_search(token, chat_id, user_states):
    user_states[chat_id] = {"type": "search"}
    print(
        f"cmd_search DEBUG: 已設定 {chat_id} 狀態: {user_states[chat_id]}", flush=True
    )
    reply_markup = {
        "inline_keyboard": [
            [
                {"text": "🤖 操作說明", "callback_data": "help"},
                {"text": "🚫 取消操作", "callback_data": "cancel"},
            ],
        ]
    }
    send_tg_message(
        token, chat_id, "🔍 *搜尋模式*\n請輸入關鍵字 (例如 `google`)：", reply_markup
    )
    return user_states


def cmd_cancel(token, chat_id, user_states):
    user_states[chat_id] = {"type": "cancel"}
    print(
        f"cmd_cancel DEBUG: 已取消 {chat_id} 狀態: {user_states[chat_id]}", flush=True
    )
    reply_markup = {
        "inline_keyboard": [
            [
                {"text": "📊 生成報表", "callback_data": "report"},
                {"text": "🔍 搜尋網域", "callback_data": "search"},
            ],
            [
                {"text": "🤖 操作說明", "callback_data": "help"},
                {"text": "🚫 取消操作", "callback_data": "cancel"},
            ],
        ]
    }
    send_tg_message(token, chat_id, "✅ 已取消目前操作。", reply_markup)
    return user_states


def handle_command(token, chat_id, text, user_states):
    chat_id = str(chat_id)
    _, authorized_chats = get_bot_config()
    
    print(f"handle_command DEBUG: {chat_id} user_states: {user_states}", flush=True)

    if chat_id not in authorized_chats:
        return user_states
    
    chat_id = str(chat_id)

    cmd = text.split("@")[0].lower()
    print(f"handle_command 📩 收到指令: {cmd} 來自 Chat ID: {chat_id}", flush=True)

    if cmd in ["/help", "/start", "hi", "你好"]:
        return cmd_help(token, chat_id, user_states)

    if cmd in ["/cancel", "取消"]:
        return cmd_cancel(token, chat_id, user_states)

    # --- 修改後的報表模式引導 ---
    if cmd in ["/report", "報表"]:
        return cmd_report(token, chat_id, user_states)

    if cmd in ["/search", "搜尋"]:
        return cmd_search(token, chat_id, user_states)

    state = user_states.get(chat_id)
    print(f"handle_command DEBUG: {chat_id} user_states: {user_states} state: {state}", flush=True)
    if state:
        input_text = text.strip()
        if state["type"] == "report":
            send_tg_message(token, chat_id, f"⌛ 正在生成 `{input_text}` 報表...")
            # 使用 sys.executable 確保環境一致
            subprocess.run(
                [sys.executable, "analyzer.py", input_text, "--type", "both"]
            )
            user_states[chat_id] = {"type": ""}
        elif state["type"] == "search":
            result = search_domain_stats(input_text)
            if result:
                send_tg_message(token, chat_id, result)
                user_states[chat_id] = {"type": ""}
            else:
                send_tg_message(
                    token,
                    chat_id,
                    f"❌ 找不到 `{input_text}`，請重試或輸入 `/cancel`：",
                )
    return user_states


def handle_callback(token, chat_id, callback_query, user_states):
    """處理按鈕點擊事件"""
    data = callback_query["data"]
    callback_id = callback_query["id"]
    chat_id = str(chat_id)
    
    print(
        f"handle_callback 📩 收到按鈕事件: {data} 來自 Chat ID: {chat_id}", flush=True
    )
    
    print(f"handle_callback DEBUG: {chat_id} 狀態: {user_states}", flush=True)


    if data == "search":
        user_states = cmd_search(token, chat_id, user_states)

    elif data == "help":
        user_states = cmd_help(token, chat_id, user_states)

    elif data == "report":
        print(
            f"handle_callback 📩 收到按鈕事件: {data} 來自 Chat ID: {chat_id}",
            flush=True,
        )
        user_states = cmd_report(token, chat_id, user_states)

    elif data == "cancel":
        user_states = cmd_cancel(token, chat_id, user_states)

    # ⚠️ 必須回傳 answer，手機端按鈕才不會一直轉圈圈
    try:
        requests.post(
            f"https://api.telegram.org/bot{token}/answerCallbackQuery",
            data={"callback_query_id": callback_id},
            timeout=5,
        )
    except Exception as e:
        print(f"handle_callback ❌ 回應按鈕事件失敗: {e}", flush=True)
        pass

    return user_states


def start_polling():
    token, _ = get_bot_config()
    if not token:
        print("start_polling 🚨 找不到 Token，程式結束。")
        sys.exit(1)

    last_update_id = 0
    error_count = 0
    print(f"start_polling 🤖 Bot 已啟動，工作目錄: {BASE_DIR}", flush=True)

    user_states = {}

    while True:
        try:
            url = f"https://api.telegram.org/bot{token}/getUpdates"
            resp = requests.get(
                url, params={"offset": last_update_id + 1, "timeout": 30}, timeout=35
            ).json()
            print(f"start_polling DEBUG: Telegram API 回應: {resp}", flush=True)

            if resp.get("ok"):
                error_count = 0
                for update in resp.get("result", []):
                    last_update_id = update["update_id"]

                    # 情境 A: 使用者打字 (原本的邏輯)
                    if "message" in update and "text" in update["message"]:
                        chat_id = update["message"]["chat"]["id"]
                        user_states.setdefault(chat_id, {"type": ""})
                        user_states = handle_command(
                            token, chat_id, update["message"]["text"], user_states
                        )

                    # 情境 B: 使用者按按鈕 (新增的邏輯)
                    elif "callback_query" in update:
                        chat_id = update["callback_query"]["message"]["chat"]["id"]
                        user_states.setdefault(chat_id, {"type": ""})
                        user_states = handle_callback(
                            token, chat_id, update["callback_query"], user_states
                        )

            else:
                raise Exception(
                    f"start_polling Telegram API 回傳錯誤: {resp.get('description')}"
                )

        except Exception as e:
            error_count += 1
            # 遞增等待機制，最高 60 秒
            wait_time = min(error_count * 10, 60)
            print(f"start_polling 📡 連線異常 ({error_count}/5): {e}", flush=True)

            # 核心優化：連線失敗多次則結束，由 Launchd 重啟
            if error_count >= 5:
                print(
                    "start_polling 🚨 連線持續失敗，主動結束進程由 Launchd 重啟。",
                    flush=True,
                )
                sys.exit(1)

            time.sleep(wait_time)


if __name__ == "__main__":
    start_polling()
