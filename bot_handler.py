from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import threading
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


def search_domain_stats(keyword, page=0):
    per_page = 20
    offset = page * per_page
    try:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        count_query = "SELECT COUNT(*) FROM (SELECT 1 FROM dns_logs WHERE domain LIKE ? GROUP BY strftime('%m-%d %H:%M', timestamp), domain)"
        cur.execute(count_query, (f"%{keyword.strip()}%",))
        total_count = cur.fetchone()[0]
        if total_count == 0:
            return None, None
        total_page = (total_count + per_page - 1) // per_page if total_count > 0 else 0
        query = "SELECT strftime('%m-%d %H:%M', timestamp) AS tm, domain, COUNT(*) FROM dns_logs WHERE domain LIKE ? GROUP BY tm, domain ORDER BY timestamp DESC LIMIT ? OFFSET ?;"
        cur.execute(query, (f"%{keyword.strip()}%", per_page, offset))
        rows = cur.fetchall()
        conn.close()
        res = f"🔍 *「{keyword}」追蹤 (共 {total_count} 筆)*\n━━━━━━━━━━━━\n"
        for tm, dom, cnt in rows:
            res += f"`{tm}` | **{cnt}次**\n└ `{dom[:30]}`\n"
        res += f"\n━━━━━━━━━━━━\n📖 第 {page+1} / {total_page} 頁\n"
        keyboard = []
        nav_buttons = []
        if total_page > 4:
            nav_buttons.append({"text": f"⏮️", "callback_data": f"search_p_0_{keyword}"})
        if page > 0:
            nav_buttons.append({"text": f"⬅️", "callback_data": f"search_p_{page-1}_{keyword}"})
        if (offset + per_page) < total_count:
            nav_buttons.append({"text": f"➡️", "callback_data": f"search_p_{page+1}_{keyword}"})
        if total_page > 4:
            nav_buttons.append({"text": f"⏭️", "callback_data": f"search_p_{total_page - 1}_{keyword}"})
        if nav_buttons:
            keyboard.append(nav_buttons)
        keyboard.append([{"text": "🚫 結束搜尋", "callback_data": "cancel"}])
        reply_markup = {"inline_keyboard": keyboard}
        return res, reply_markup
    except Exception as e:
        print(f"search_domain_stats ❌ 錯誤: {e}", flush=True)
        return "❌ 搜尋時發生錯誤", None


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
    if chat_id not in authorized_chats:
        return user_states
    cmd = text.split("@")[0].lower()
    if cmd in ["/help", "/start", "hi", "你好"]:
        return cmd_help(token, chat_id, user_states)
    if cmd in ["/cancel", "取消"]:
        return cmd_cancel(token, chat_id, user_states)
    if cmd in ["/report", "報表"]:
        return cmd_report(token, chat_id, user_states)
    if cmd in ["/search", "搜尋"]:
        return cmd_search(token, chat_id, user_states)
    state = user_states.get(chat_id)
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
            # 💡 這裡要接收兩個回傳值：result (文字) 和 reply_markup (按鈕)
            result, reply_markup = search_domain_stats(input_text) 
            if result:
                send_tg_message(token, chat_id, result, reply_markup)
            else:
                send_tg_message(
                    token,
                    chat_id,
                    f"❌ 找不到 `{input_text}`，請重試或輸入 `/cancel`：",
                )
    return user_states


def handle_callback(token, chat_id, callback_query, user_states):
    data = callback_query["data"]
    callback_id = callback_query["id"]
    chat_id = str(chat_id)
    if data == "search":
        user_states = cmd_search(token, chat_id, user_states)
    elif data.startswith("search_p_"):
        _, _, page_str, keyword = data.split("_", 3)
        page = int(page_str)
        result, reply_markup = search_domain_stats(keyword, page)
        if result:
            url = f"https://api.telegram.org/bot{token}/editMessageText"
            payload = {
                "chat_id": chat_id,
                "message_id": callback_query["message"]["message_id"],
                "text": result,
                "parse_mode": "Markdown",
                "reply_markup": json.dumps(reply_markup)
            }
            requests.post(url, data=payload, timeout=10)
        else:
            # 如果真的沒資料了，彈出一個小通知 (Toast) 提醒即可，不用發新訊息
            requests.post(
                f"https://api.telegram.org/bot{token}/answerCallbackQuery",
                data={"callback_query_id": callback_query["id"], "text": "❌ 沒有更多結果了", "show_alert": False}
            )
    elif data == "help":
        user_states = cmd_help(token, chat_id, user_states)
    elif data == "report":
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
    print(f"start_polling 🤖 Bot 已啟動，工作目錄: {BASE_DIR}", flush=True)
    last_update_id = 0
    error_count = 0
    user_states = {}
    while True:
        try:
            url = f"https://api.telegram.org/bot{token}/getUpdates"
            resp_obj = requests.get(
                url, params={"offset": last_update_id + 1, "timeout": 50}, timeout=60
            )
            resp_obj.raise_for_status()  # 💡 增加這一行，若伺服器噴錯 (如 502) 會拋出異常，避免解析 JSON 失敗
            resp = resp_obj.json()
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
            if error_count >= 5:
                print(
                    "start_polling 🚨 連線持續失敗，主動結束進程由 Launchd 重啟。",
                    flush=True,
                )
                sys.exit(1)
            time.sleep(wait_time)


class WebhookHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        try:
            content_length = int(self.headers["Content-Length"])
            post_data = self.rfile.read(content_length)
            data = json.loads(post_data)
            dev_name = data.get("device", "Unknown")
            domain = data.get("domain")
            if domain:
                conn = sqlite3.connect(DB_PATH)
                cur = conn.cursor()
                cur.execute(
                    "SELECT ip_address FROM devices WHERE device_name = ?", (dev_name,)
                )
                result = cur.fetchone()
                client_ip = result[0] if result else "127.0.0.1"
                cur.execute(
                    "INSERT INTO dns_logs (client_ip, domain, timestamp) VALUES (?, ?, DATETIME('now','localtime'))",
                    (client_ip, domain),
                )
                conn.commit()
                conn.close()
                print(
                    f"📡 Webhook 補強成功: {dev_name} ({client_ip}) -> {domain}",
                    flush=True,
                )
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(b'{"status":"success"}')
        except Exception as e:
            print(f"❌ Webhook 處理失敗: {e}", flush=True)
            self.send_response(500)
            self.end_headers()


def start_webhook_server():
    server = HTTPServer(("0.0.0.0", 8080), WebhookHandler)
    print("🌐 Webhook 接收站已啟動 (Port 8080)...", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    t = threading.Thread(target=start_webhook_server, daemon=True)
    t.start()
    start_polling()
