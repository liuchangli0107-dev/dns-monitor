# init_db.py
import sqlite3
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "dns_monitor.db")

def init_db():
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
        print(f"🗑️ 已刪除舊資料庫")

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # 建立設備表
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS devices (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ip_address TEXT UNIQUE NOT NULL,
        device_name TEXT NOT NULL,
        owner TEXT,
        telegram_token TEXT,
        telegram_chat_id TEXT
    )
    ''')

    # 建立日誌表 (移除 device_name，僅保留 IP 以減少冗餘)
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS dns_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        client_ip TEXT NOT NULL,
        domain TEXT NOT NULL,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (client_ip) REFERENCES devices(ip_address)
    )
    ''')

    # 預設插入 MacBook 本機紀錄 (Charlie)
    # 請記得隨後手動更新您的 Telegram Token 與 Chat ID
    cursor.execute('''
    INSERT INTO devices (ip_address, device_name, owner, telegram_token, telegram_chat_id)
    VALUES (?, ?, ?, ?, ?)
    ''', ('127.0.0.1', 'iMac-Server', 'Charlie', 'YOUR_TOKEN', 'YOUR_ID'))

    conn.commit()
    conn.close()
    print(f"✅ 資料庫初始化完成，已預設排除 127.0.0.1 的統計。")

if __name__ == "__main__":
    init_db()