# init_db.py
import logging
import os
import sqlite3

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "dns_monitor.db")
LOG_PATH = os.path.join(BASE_DIR, "upgrade_db.log")

logging.basicConfig(
    filename=LOG_PATH,
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)


def _dns_10m_stats_column_names(cursor):
    cursor.execute("PRAGMA table_info(dns_10m_stats)")
    return [row[1] for row in cursor.fetchall()]


def ensure_schema(db_path=None, vacuum=False):
    """
    建立或補齊應用程式所需之 SQLite 結構（冪等）。
    供 watcher、scheduler、init_db 等啟動時呼叫，無需另外手動執行 init_db.py。
    """
    path = db_path if db_path is not None else DB_PATH
    conn = sqlite3.connect(path, timeout=20)
    cursor = conn.cursor()

    try:
        # ==========================================
        # 設備表 (devices)
        # ==========================================
        cursor.execute(
            """
        CREATE TABLE IF NOT EXISTS devices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ip_address TEXT UNIQUE NOT NULL,
            device_name TEXT NOT NULL,
            owner TEXT,
            telegram_token TEXT,
            telegram_chat_id TEXT
        )
        """
        )

        cursor.execute(
            """
        INSERT OR IGNORE INTO devices (ip_address, device_name, owner, telegram_token, telegram_chat_id)
        VALUES (?, ?, ?, ?, ?)
        """,
            ("127.0.0.1", "YOUR_DEVICE_NAME", "YOUR_NAME", "YOUR_TOKEN", "YOUR_ID"),
        )

        # ==========================================
        # 日誌表 (dns_logs)
        # ==========================================
        cursor.execute(
            """
        CREATE TABLE IF NOT EXISTS dns_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_ip TEXT NOT NULL,
            domain TEXT NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (client_ip) REFERENCES devices(ip_address)
        )
        """
        )
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_dns_logs_timestamp ON dns_logs(timestamp)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_dns_logs_domain ON dns_logs(domain)")

        # ==========================================
        # 排程狀態表 (schedule_status)
        # ==========================================
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

        # ==========================================
        # 10 分鐘統計表 (dns_10m_stats)
        # ==========================================
        cursor.execute(
            """
        CREATE TABLE IF NOT EXISTS dns_10m_stats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            window_start DATETIME NOT NULL,
            window_end DATETIME NOT NULL,
            domain TEXT NOT NULL,
            count INTEGER NOT NULL,
            is_uploaded INTEGER DEFAULT 0
        )
        """
        )

        cols = _dns_10m_stats_column_names(cursor)
        if cols and "is_uploaded" not in cols:
            cursor.execute(
                "ALTER TABLE dns_10m_stats ADD COLUMN is_uploaded INTEGER DEFAULT 0"
            )

        cursor.execute("CREATE INDEX IF NOT EXISTS idx_10m_stats_window_start ON dns_10m_stats(window_start)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_10m_stats_domain ON dns_10m_stats(domain)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_10m_stats_is_uploaded ON dns_10m_stats(is_uploaded)")

        # ==========================================
        # 排程器用 system_status（原 scheduler.init_scheduler_db）
        # ==========================================
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS system_status (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_name TEXT,
                last_run_date TEXT UNIQUE,
                executed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        conn.commit()

        if vacuum:
            cursor.execute("VACUUM")

    finally:
        conn.close()


def init_db():
    print("🚀 正在初始化/升級資料庫結構...")
    logging.info("開始資料庫初始化/升級作業...")

    try:
        ensure_schema(DB_PATH, vacuum=True)
        msg = "✅ 資料庫初始化/升級完成！所有結構皆已更新至最新版本。"
        print(msg)
        logging.info(msg)
    except Exception as e:
        msg = f"❌ 資料庫初始化/升級失敗: {e}"
        print(msg)
        logging.error(msg)


if __name__ == "__main__":
    init_db()
