# upgrade_db_v2.py
import sqlite3
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "dns_monitor.db")


import sqlite3
import os
import logging
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "dns_monitor.db")
LOG_PATH = os.path.join(BASE_DIR, "upgrade_db.log")

logging.basicConfig(
    filename=LOG_PATH,
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)

def upgrade_db():
    if not os.path.exists(DB_PATH):
        msg = "❌ 找不到資料庫，請先執行 init_db.py"
        print(msg)
        logging.error(msg)
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    print("🚀 正在升級資料庫結構 (V2)...")
    logging.info("開始 V2 升級作業...")

    try:
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS schedule_status (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                device_name TEXT NOT NULL,
                period_name TEXT NOT NULL,
                date DATE NOT NULL,
                status INTEGER DEFAULT 0,
                start_at TEXT,
                end_at TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(device_name, period_name, date)
            )
            """
        )
        conn.commit()
        msg = "✅ schedule_status 資料表已準備就緒！"
        print(msg)
        logging.info(msg)
    except Exception as e:
        msg = f"❌ 資料庫升級 V2 失敗: {e}"
        print(msg)
        logging.error(msg)
    finally:
        conn.close()


if __name__ == "__main__":
    upgrade_db()
