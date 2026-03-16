import sqlite3
import os

# 自動抓取當前路徑
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "dns_monitor.db")

def init_db():
    # 1. 如果舊的資料庫存在，先刪除它以確保結構更新
    if os.path.exists(DB_PATH):
        try:
            os.remove(DB_PATH)
            print(f"🗑️ 已刪除舊資料庫: {DB_PATH}")
        except PermissionError:
            print(f"❌ 無法刪除資料庫，請先停止正在運行的 watcher.py 或關閉 DB Browser")
            return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    print("🚀 正在建立新資料庫結構...")

    # 2. 建立設備表 (包含 Telegram 金鑰欄位)
    # 只有當 token 與 chat_id 同時存在時，watcher.py 才會發送通知
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS devices (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ip_address TEXT UNIQUE,
        device_name TEXT,
        owner TEXT,
        telegram_token TEXT,
        telegram_chat_id TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')

    # 3. 建立 DNS 日誌表
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS dns_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        device_name TEXT,
        client_ip TEXT,
        domain TEXT,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')

    # 4. 預先插入您的核心設備與 Telegram 資訊
    # 請在此處填入您的真實 Token 與 Chat ID
    default_devices = [
        ('127.0.0.1', 'iMac-Server', 'Charlie', None, None),
        ('192.168.1.10', 'Olivia-MacBook', 'Olivia', None, None),
        ('192.168.1.20', 'Owen-MacBook', 'Owen', None, None)
    ]
    
    cursor.executemany(
        'INSERT INTO devices (ip_address, device_name, owner, telegram_token, telegram_chat_id) VALUES (?, ?, ?, ?, ?)', 
        default_devices
    )

    conn.commit()
    conn.close()
    print(f"✅ 資料庫初始化完成！位置: {DB_PATH}")

if __name__ == "__main__":
    init_db()