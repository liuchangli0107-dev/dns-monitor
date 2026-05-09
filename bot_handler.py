from http.server import BaseHTTPRequestHandler, HTTPServer
import json
from pathlib import Path
import socket
import threading
import time
from google import genai
import requests
import sqlite3
import os
import sys
import subprocess
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(BASE_DIR)
DB_PATH = os.path.join(BASE_DIR, "dns_monitor.db")
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")

def log_print(message, **kwargs):
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    kwargs['flush'] = True
    print(f"[{now}] {message}", **kwargs)

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
        log_print(f"get_bot_config ❌ 資料庫讀取失敗: {e}")
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
        log_print(f"send_tg_message ❌ 發送失敗: {e}")
        pass


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
        log_print(f"search_domain_stats ❌ 錯誤: {e}")
        return "❌ 搜尋時發生錯誤", None


# 執行系統指令並回傳結果 (例如: git version, ls, ps, df)
def run_command(command: str) -> str:
    try:
        # 設定超時防止指令卡死
        result = subprocess.check_output(command, shell=True, stderr=subprocess.STDOUT, timeout=20)
        return result.decode('utf-8')
    except subprocess.CalledProcessError as e:
        return f"指令回傳錯誤代碼: {e.returncode}\n輸出: {e.output.decode('utf-8')}"
    except Exception as e:
        return f"執行異常: {str(e)}"


# 讀取或寫入專案目錄下的特定檔案 (例如: watcher.py, config.json)
def read_local_file(path: str) -> str:
    full_path = os.path.join(BASE_DIR, path)
    try:
        with open(full_path, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        return f"讀取失敗: {str(e)}"


# 寫入或修改專案目錄下的特定檔案內容 (例如: watcher.py, config.json)
def write_local_file(path: str, content: str) -> str:
    full_path = os.path.join(BASE_DIR, path)
    try:
        with open(full_path, 'w', encoding='utf-8') as f:
            f.write(content)
        return f"✅ 檔案 {path} 已更新成功。"
    except Exception as e:
        return f"寫入失敗: {str(e)}"

def cmd_gemini(token, chat_id, user_states):
    user_states[chat_id] = {"type": "gemini"}
    api_key, model_id = get_model_config()
    model_id = model_id.replace("-", " ").title() if model_id else "Gemini 模型"
    reply_markup = {
        "inline_keyboard": [
            [
                {"text": "🚫 取消操作", "callback_data": "cancel"},
            ],
        ]
    }
    guide_msg = (
        f"🤖 *{model_id}*\n\n"
        "現在可以幫您修改程式碼或分析日誌。\n"
        "您可以直接下達自然語言指令，例如：\n"
        "「`列出專案目錄下所有的 Python 檔案`」\n"
        "「`幫我讀取 watcher.log 最後20筆日誌`」\n\n"
        "建議在指令中加入：「`請精簡分析，直接列出重點。`」"
    )
    send_tg_message(token, chat_id, guide_msg, reply_markup)
    return user_states

def cmd_help(token, chat_id, user_states):
    help_msg = "🤖 *DNS 助理*\n📊 `/report` - 生成報表\n🔍 `/search` - 搜尋網域\n🤖 `/gemini` - Gemini\n🚫 `/cancel` - 取消操作"
    reply_markup = {
        "inline_keyboard": [
            [
                {"text": "📊 生成報表", "callback_data": "report"},
                {"text": "🔍 搜尋網域", "callback_data": "search"},
            ],
            [
                {"text": "🤖 Gemini", "callback_data": "gemini"},
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
                {"text": "🤖 操作說明", "callback_data": "help"}
            ],
        ]
    }
    send_tg_message(token, chat_id, "✅ 已取消目前操作。", reply_markup)
    return user_states


def load_system_rules():
    # 使用 pathlib 確保路徑處理正確
    base_path = Path(BASE_DIR)
    host_env_path = base_path / "HOST_ENV.md"
    project_env_path = base_path / "ENV.md"
    rules = []
    
    # 載入操作規範
    if host_env_path.exists():
        rules.append(f"### 操作規範 (HOST_ENV.md):\n{host_env_path.read_text(encoding='utf-8')}")
    
    # 載入專案地圖
    if project_env_path.exists():
        rules.append(f"### 專案結構地圖 (ENV.md):\n{project_env_path.read_text(encoding='utf-8')}")
        
    if not rules:
        return "你是一個專業的系統助理。"
    
    return "\n\n".join(rules)


def get_model_config(): 
    try:
        with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
            config = json.load(f)
            api_key = config.get("api_key")
            model_id = config.get("model", "gemini-3.1-flash-lite-preview")
            return api_key, model_id
    except Exception as e:
        log_print(f"get_model_config ❌ 讀取配置失敗: {e}")
        return None, "gemini-3.1-flash-lite-preview"

def handle_command(token, chat_id, text, user_states):
    chat_id = str(chat_id)
    _, authorized_chats = get_bot_config()
    if chat_id not in authorized_chats:
        return user_states
    
    cmd = text.split("@")[0].lower()
    if cmd in ["/gemini", "gemini"]:
        return cmd_gemini(token, chat_id, user_states)
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
        
        # --- Gemini 邏輯區塊 ---
        if state["type"] == "gemini":
            send_tg_message(token, chat_id, "⌛ Gemini 代理人正在執行任務...")
            
            try:
                # --- 第一階段：初始化 ---
                api_key, model_id = get_model_config()
                if not api_key:
                    send_tg_message(token, chat_id, "❌ API 密鑰未設定。")
                    return user_states

                client = genai.Client(api_key=api_key)
                chat = client.chats.create(
                    model=model_id,
                    config={
                        'tools': [run_command, read_local_file, write_local_file],
                        'system_instruction': f"請嚴格遵守以下操作規範：\n{load_system_rules()}"
                    }
                )
                
                # --- 第二階段：傳送指令 ---
                start_time = time.time()
                response = chat.send_message(input_text)
                end_time = time.time()
                duration = end_time - start_time
                
                # 安全解析回覆內容
                texts = [part.text for part in response.candidates[0].content.parts if hasattr(part, 'text') and part.text]
                reply_text = "".join(texts) if texts else "AI 已完成操作，但未提供文字說明。"
                reply_markup = {
                    "inline_keyboard": [
                        [
                            {"text": "🚫 取消操作", "callback_data": "cancel"},
                        ],
                    ]
                }
                send_tg_message(token, chat_id, f"🤖 *{model_id}代理人回報：*\n\n{reply_text}\n\n⏱️ *回應時間: {duration:.2f}秒*", reply_markup)

            except Exception as e:
                # 統一捕捉所有階段的錯誤並回報給 Telegram
                error_detail = f"❌ 執行失敗: {str(e)}"
                user_states[chat_id] = {"type": ""}
                log_print(f"handle_command DEBUG: {error_detail}") # 終端機也要留紀錄
                send_tg_message(token, chat_id, error_detail)
        # --- Gemini 區塊結束 ---

        elif state["type"] == "report":
            send_tg_message(token, chat_id, f"⌛ 正在生成 `{input_text}` 報表...")
            subprocess.run([sys.executable, "analyzer.py", input_text, "--type", "both"])
            user_states[chat_id] = {"type": ""}
            
        elif state["type"] == "search":
            result, reply_markup = search_domain_stats(input_text) 
            if result:
                send_tg_message(token, chat_id, result, reply_markup)
            else:
                send_tg_message(token, chat_id, f"❌ 找不到 `{input_text}`，請重試或輸入 `/cancel`：")
                
    return user_states


def handle_callback(token, chat_id, callback_query, user_states):
    data = callback_query["data"]
    callback_id = callback_query["id"]
    chat_id = str(chat_id)
    if data == "gemini":
        user_states = cmd_gemini(token, chat_id, user_states)
    if data == "search":
        user_states = cmd_search(token, chat_id, user_states)
    if data.startswith("search_p_"):
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

    if data.startswith("report_p_"):
        _, _, page_str, target_date, period = data.split("_", 4)
        period_val = period if period != "none" else None
        # 改為呼叫編輯模式 (is_edit=True, message_id=...)
        subprocess.run([
            sys.executable, "analyzer.py", target_date, 
            "--page", page_str, 
            "--period", period_val or "", 
            "--is_edit", str(callback_query["message"]["message_id"])
        ])
    if data == "help":
        user_states = cmd_help(token, chat_id, user_states)
    if data == "report":
        user_states = cmd_report(token, chat_id, user_states)
    if data == "cancel":
        user_states = cmd_cancel(token, chat_id, user_states)
    # ⚠️ 必須回傳 answer，手機端按鈕才不會一直轉圈圈
    try:
        requests.post(
            f"https://api.telegram.org/bot{token}/answerCallbackQuery",
            data={"callback_query_id": callback_id},
            timeout=5,
        )
    except Exception as e:
        log_print(f"handle_callback ❌ 回應按鈕事件失敗: {e}")
        pass
    return user_states


def start_polling():
    token, _ = get_bot_config()
    if not token:
        log_print(f"start_polling 🚨 找不到 Token，程式結束。")
        sys.exit(1)
    log_print(f"start_polling 🤖 Bot 已啟動，工作目錄: {BASE_DIR}")
    
    last_update_id = 0
    error_count = 0
    user_states = {}
    
    try:
        resp = requests.get(f"https://api.telegram.org/bot{token}/getUpdates", params={"offset": -1}, timeout=10).json()
        if resp.get("ok") and resp.get("result"):
            last_update_id = resp["result"][0]["update_id"]
        else:
            last_update_id = 0
    except:
        last_update_id = 0
        
    log_print(f"start_polling 🤖 Bot 已啟動，起始 ID: {last_update_id}")
    
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
            log_print(f"start_polling 📡 連線異常 ({error_count}/5): {e}")
            if error_count >= 5:
                log_print(
                    f"start_polling 🚨 連線持續失敗，主動結束進程由 Launchd 重啟。",
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
                log_print(f"📡 Webhook 補強成功: {dev_name} ({client_ip}) -> {domain}")
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(b'{"status":"success"}')
        except Exception as e:
            log_print(f"❌ Webhook 處理失敗: {e}")
            self.send_response(500)
            self.end_headers()


def start_webhook_server():
    try:
        server = HTTPServer(("127.0.0.1", 8080), WebhookHandler)
        server.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        log_print(f"🌐 Webhook 接收站已啟動 (Port 8080)...")
        server.serve_forever()
    except OSError as e:
        if e.errno == 48:
            log_print("❌ 錯誤：端口 8080 已被佔用，請先執行清理指令。")
        else:
            log_print(f"❌ Webhook Server 啟動失敗: {e}")


if __name__ == "__main__":
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    result = sock.connect_ex(('127.0.0.1', 8080))
    if result == 0:
        log_print("🚨 致命錯誤：端口 8080 已被佔用，請先清理進程。")
        sys.exit(1)
    sock.close()
    t = threading.Thread(target=start_webhook_server, daemon=True)
    t.start()
    start_polling()
