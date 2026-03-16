import time
import os
import json
import sqlite3
import requests
import re


# 自動抓取 watcher.py 所在的目錄
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE_DIR, 'config.json')
DB_PATH = os.path.join(BASE_DIR, "dns_monitor.db")
LOG_FILE = os.path.join(BASE_DIR, "dns_query.log")

print(f"DEBUG: 正在嘗試開啟檔案 -> {LOG_FILE}")

def load_config():
    with open(CONFIG_PATH, 'r') as f:
        return json.load(f)

# 正則表達式：匹配 "IP:Port - domain." 格式
# 範例：127.0.0.1:54321 - google.com.
LOG_PATTERN = re.compile(r'(?:(?P<ip>[\d\.]+):\d+\s+-\s+)?(?:\[INFO\]\s+)?(?P<domain>[^\s]+)')

def init_db_connection():
    """建立資料庫連線並回傳 cursor"""
    conn = sqlite3.connect(DB_PATH)
    return conn, conn.cursor()

def get_device_name(cursor, ip):
    """根據 IP 查詢設備名稱，若無則建立新紀錄"""
    cursor.execute("SELECT device_name FROM devices WHERE ip_address = ?", (ip,))
    result = cursor.fetchone()
    if result:
        return result[0]
    else:
        # 自動發現新設備
        cursor.execute("INSERT INTO devices (ip_address, device_name) VALUES (?, ?)", (ip, "Unknown Device"))
        return "Unknown Device"

def send_telegram(message, config):
    """發送 Telegram 通知"""
    token = config['TELEGRAM_TOKEN']
    chat_id = config['TELEGRAM_CHAT_ID']
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": message}
    try:
        requests.post(url, json=payload, timeout=5)
    except Exception as e:
        print(f"❌ Telegram 發送失敗: {e}")

def monitor():
    print(f"🚀 DNS 監控系統啟動 (資料庫同步模式)...")
    print(f"📁 監控檔案: {LOG_FILE}")
    
    conn, cursor = init_db_connection()

    # --- 修正點 1: 不要用 os.path.exists，改用 try-except 直接開啟 ---
    try:
        with open(LOG_FILE, "r") as file:
            print(f"✅ 成功開啟日誌檔")
            # 跳到檔案末尾
            file.seek(0, 2)
            
            while True:
                line = file.readline()
                if not line:
                    time.sleep(0.5)
                    continue

                # 解析日誌行
                match = LOG_PATTERN.search(line)
                if match:
                    # --- 修正點 2: 處理可能為 None 的 IP (例如 [INFO] 行) ---
                    raw_ip = match.group("ip")
                    ip = raw_ip if raw_ip else "127.0.0.1" 
                    domain = match.group("domain").rstrip('.')
                    
                    # 取得設備名稱
                    device_name = get_device_name(cursor, ip)
                    conn.commit()

                    try:
                        cursor.execute(
                            "INSERT INTO dns_logs (device_name, client_ip, domain, timestamp) VALUES (?, ?, ?, datetime('now', 'localtime'))",
                            (device_name, ip, domain)
                        )
                        conn.commit()
                        print(f"📝 INSERT: {domain} (from {device_name})")

                    except sqlite3.Error as e:
                        print(f"❌ 資料庫寫入錯誤: {e}")
                else:
                    if line.strip():
                        print(f"⚠️ 無法解析行: {line.strip()}")
    except FileNotFoundError:
        print(f"❌ 找不到檔案: {LOG_FILE}，請確認路徑或執行 touch {LOG_FILE}")
    except PermissionError:
        print(f"❌ 權限不足: 無法讀取 {LOG_FILE}，請執行 sudo chmod 666 {LOG_FILE}")
    except Exception as e:
        print(f"💥 發生未知錯誤: {e}")

if __name__ == "__main__":
    try:
        monitor()
    except KeyboardInterrupt:
        print("\n🛑 監控已停止")