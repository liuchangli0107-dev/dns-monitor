import sqlite3
import subprocess
import os
import sys
from datetime import datetime, timedelta

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(BASE_DIR)

DB_PATH = os.path.join(BASE_DIR, "dns_monitor.db")


def init_scheduler_db():
    """初始化 system_status 表"""
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
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
    conn.close()


def get_last_processed_date():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        "SELECT last_run_date FROM system_status WHERE task_name='daily_analysis' ORDER BY last_run_date DESC LIMIT 1"
    )
    row = cur.fetchone()
    conn.close()
    return row[0] if row else "2026-03-01"  # 預設起始日期


def has_logs(date_str):
    """檢查當天是否有日誌資料，避免空跑"""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        "SELECT COUNT(*) FROM dns_logs WHERE timestamp LIKE ?", (f"{date_str}%",)
    )
    count = cur.fetchone()[0]
    conn.close()
    return count > 50  # 超過 50 筆才視為有效日誌


# --- 執行流程 ---
init_scheduler_db()
last_date_str = get_last_processed_date()
last_date = datetime.strptime(last_date_str, "%Y-%m-%d")
yesterday = datetime.now() - timedelta(days=1)

current_check = last_date + timedelta(days=1)

while current_check <= yesterday:
    target_date = current_check.strftime("%Y-%m-%d")
    if has_logs(target_date):
        print(f"🕵️ 發現缺失日期 {target_date}，啟動補發...")
        # 調用 analyzer 並帶上 --record 確保紀錄狀態
        subprocess.run(
            [
                sys.executable,
                os.path.join(BASE_DIR, "analyzer.py"),
                target_date,
                "--type",
                "both",
                "--record",
            ]
        )
    else:
        print(f"⏭️ {target_date} 無足夠日誌，跳過紀錄。")
        # 即使沒資料也紀錄，避免下次重複檢查
        conn = sqlite3.connect(DB_PATH)
        conn.execute(
            "INSERT OR IGNORE INTO system_status (task_name, last_run_date) VALUES (?, ?)",
            ("daily_analysis", target_date),
        )
        conn.commit()
        conn.close()

    current_check += timedelta(days=1)
