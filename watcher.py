import time
import os
import sqlite3
import re

# 自動抓取路徑
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "dns_monitor.db")
LOG_FILE = os.path.join(BASE_DIR, "dns_query.log")

# --- 核心修正：精準匹配 [INFO] IP - Domain ---
LOG_PATTERN = re.compile(r'\[INFO\]\s+(?P<ip>[\d\.]+)(?::\d+)?\s+-\s+(?P<domain>[^\s]+)')

def init_db_connection():
    conn = sqlite3.connect(DB_PATH)
    return conn, conn.cursor()

def get_device_name(cursor, ip):
    cursor.execute("SELECT device_name FROM devices WHERE ip_address = ?", (ip,))
    result = cursor.fetchone()
    if result:
        return result[0]
    else:
        # 自動根據 IP 末碼命名 (例如 .71 -> Device-71)
        suffix = ip.split('.')[-1]
        device_name = f"Device-{suffix}"
        cursor.execute("INSERT INTO devices (ip_address, device_name) VALUES (?, ?)", (ip, device_name))
        print(f"🆕 發現新裝置: {ip} (命名為 {device_name})")
        return device_name

def monitor():
    print(f"🚀 DNS 監控修正版啟動...")
    conn, cursor = init_db_connection()
    try:
        with open(LOG_FILE, "r") as file:
            file.seek(0, 2) # 跳到末尾只讀新 Log
            while True:
                line = file.readline()
                if not line:
                    time.sleep(0.5)
                    continue
                match = LOG_PATTERN.search(line)
                if match:
                    ip = match.group("ip")
                    domain = match.group("domain").strip().rstrip('.')
                    # 過濾系統雜訊
                    if any(x in domain for x in [":53", "CoreDNS", "Reloading"]): continue
                    
                    device_name = get_device_name(cursor, ip)
                    try:
                        cursor.execute(
                            "INSERT INTO dns_logs (device_name, client_ip, domain, timestamp) VALUES (?, ?, ?, datetime('now', 'localtime'))",
                            (device_name, ip, domain)
                        )
                        conn.commit()
                        print(f"✅ 成功寫入: {device_name} ({ip}) -> {domain}")
                    except sqlite3.Error as e:
                        print(f"❌ DB 寫入失敗: {e}")
    except Exception as e:
        print(f"💥 錯誤: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    monitor()