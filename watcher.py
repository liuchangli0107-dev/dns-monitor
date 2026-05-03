# Verified by Gemini Agent 2026
# watcher.py
import re
import sqlite3
import os
import subprocess
import sys

# 設定路徑
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "dns_monitor.db")
LOG_FILE = os.path.join(BASE_DIR, "dns_query.log")


def get_db_connection():
    """建立資料庫連線"""
    return sqlite3.connect(DB_PATH, timeout=10)


def get_or_create_device(cursor, ip):
    """自動識別並建立新設備紀錄"""
    cursor.execute("SELECT device_name FROM devices WHERE ip_address = ?", (ip,))
    row = cursor.fetchone()
    if not row:
        last_part = ip.split(".")[-1]
        new_name = f"Device-{last_part}"
        cursor.execute(
            "INSERT INTO devices (ip_address, device_name, owner) VALUES (?, ?, ?)",
            (ip, new_name, "Unknown"),
        )
        print(f"🆕 [新設備] 偵測到 IP: {ip} -> 自動命名為: {new_name}")
        return new_name
    return row[0]


def process_line(line):
    """解析每一行日誌並寫入 DB"""
    if not line.strip():
        return

    # 打印原始日誌供偵錯 (Debug Print)
    print(f"🔍 [收到原始日誌] {line}")

    # 強化版 Regex：支援多重 [INFO] 標籤、空格以及 IPv4 格式
    regex = r"(?:\[INFO\]\s*)+\s*(?P<ip>[\d\.]+)(?::\d+)?\s+-\s+(?P<domain>[^\s]+)"
    match = re.search(regex, line)

    if match:
        ip = match.group("ip")
        domain = match.group("domain").rstrip(".")

        # 處理本機迴圈地址
        if ip == "::1":
            ip = "127.0.0.1"

        try:
            conn = get_db_connection()
            cursor = conn.cursor()

            # 確保設備存在
            get_or_create_device(cursor, ip)

            # 寫入日誌表格 (對應新版 init_db.py 結構)
            cursor.execute(
                "INSERT INTO dns_logs (client_ip, domain, timestamp) VALUES (?, ?, datetime('now', 'localtime'))",
                (ip, domain),
            )
            conn.commit()
            conn.close()
            print(f"✅ [寫入成功] 來源: {ip} | 網域: {domain}")

        except sqlite3.Error as e:
            print(f"❌ [資料庫錯誤] {e}")
        except Exception as e:
            print(f"❌ [系統錯誤] {e}")
    else:
        print(f"⚠️  [解析跳過] 此行格式不符預期，無法匹配 Regex。")


def watch_log():
    """主監控迴圈"""
    print(f"🚀 Watcher 監控引擎已啟動")
    print(f"📂 正在監控檔案: {LOG_FILE}")
    print(f"🗄️  正在寫入資料庫: {DB_PATH}")
    print(f"💡 (提示: 啟動時會先讀取最後 10 筆舊紀錄進行測試)\n")

    # 使用 tail -n 10 -F 確保啟動時有反饋，並處理檔案輪替
    cmd = ["tail", "-n", "10", "-F", LOG_FILE]

    try:
        process = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )

        # 持續讀取輸出
        for line in process.stdout:
            process_line(line.strip())

    except FileNotFoundError:
        print(f"❌ [錯誤] 找不到系統指令 'tail'，請檢查系統路徑。")
    except KeyboardInterrupt:
        print("\n🛑 [停止] 監控服務已手動關閉。")
        process.terminate()
    except Exception as e:
        print(f"❌ [執行時異常] {e}")


if __name__ == "__main__":
    # 檢查必要檔案是否存在
    if not os.path.exists(LOG_FILE):
        print(f"⚠️  日誌檔不存在，正在建立空檔案: {LOG_FILE}")
        with open(LOG_FILE, "w") as f:
            pass

    if not os.path.exists(DB_PATH):
        print(f"❌ [致命錯誤] 找不到資料庫 {DB_PATH}，請先執行 init_db.py")
        sys.exit(1)

    watch_log()