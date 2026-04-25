# upgrade_db_v2.py
import sqlite3
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "dns_monitor.db")


def upgrade_db():
    if not os.path.exists(DB_PATH):
        print("❌ 找不到資料庫，請先執行 init_db.py")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    print("🚀 正在升級資料庫結構...")

    # 建立課表執行狀態表 (使用您設計的結構)
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
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP, -- 進入時段的時間
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP, -- 發送通報的時間
        UNIQUE(device_name, period_name, date)
    )
    """
    )

    conn.commit()
    conn.close()
    print("✅ schedule_status 資料表已準備就緒！")


if __name__ == "__main__":
    upgrade_db()
