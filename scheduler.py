import json
import os
import sqlite3
import subprocess
import sys
from analyzer import get_current_period  # 引用我們寫好的判斷函數
from datetime import datetime, timedelta

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(BASE_DIR)

DB_PATH = os.path.join(BASE_DIR, "dns_monitor.db")


def init_scheduler_db():
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
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        "SELECT COUNT(*) FROM dns_logs WHERE timestamp LIKE ?", (f"{date_str}%",)
    )
    count = cur.fetchone()[0]
    conn.close()
    return count > 0


# 檢查該時段今天是否已經成功發送過 (status>=1)
def is_already_sent(device_name, period_name, date_str):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    # 這裡對應您在 upgrade_db_v2.py 建立的 schedule_status 表
    cur.execute(
        """
        SELECT status FROM schedule_status 
        WHERE device_name = ? AND period_name = ? AND date = ?
    """,
        (device_name, period_name, date_str),
    )
    row = cur.fetchone()
    conn.close()
    return row is not None and row[0] >= 1


def manage_smart_schedule():
    with open("config.json", "r", encoding="utf-8") as f:
        config_data = json.load(f)

    day_now = datetime.now().strftime("%A")
    time_now = datetime.now().strftime("%H:%M")
    today_str = datetime.now().strftime("%Y-%m-%d")
    dev_name = config_data.get("device_name", "Olivia-Macbook")

    today_schedule = config_data.get("weekly_schedule", {}).get(day_now, {})

    for p_name, (start_t, end_t) in today_schedule.items():
        # 核心判定：現在時間是否已經過「課程結束時間」
        if time_now > end_t:

            # 先確保 schedule_status 表中有這筆記錄 (如果沒有就插入，狀態預設為 0)
            conn = sqlite3.connect(DB_PATH)
            conn.execute(
                """
                INSERT OR IGNORE INTO schedule_status (device_name, period_name, date, start_at, end_at, status)
                VALUES (?, ?, ?, ?, ?, 0)
            """,
                (dev_name, p_name, today_str, start_t, end_t),
            )
            conn.commit()
            conn.close()

            # 檢查資料庫：是否已發送過 (status=1)
            if not is_already_sent(dev_name, p_name, today_str):
                print(f"🕵️ 偵測到已結束課程: {p_name} ({end_t}) 尚未發報，準備補發...")

                # 調用 analyzer 進行完整統計
                result = subprocess.run(
                    [
                        sys.executable,
                        os.path.join(BASE_DIR, "analyzer.py"),
                        today_str,
                        "--start",
                        start_t,
                        "--end",
                        end_t,
                        "--period",
                        p_name,
                        "--record",
                    ]
                )

                if result.returncode == 0:
                    print(f"✅ {p_name} 補發成功")
                else:
                    print(f"❌ {p_name} 補發失敗，待下次循環重試")


# --- 執行流程 ---
init_scheduler_db()
last_date_str = get_last_processed_date()
last_date = datetime.strptime(last_date_str, "%Y-%m-%d")
yesterday = datetime.now() - timedelta(days=1)

current_check = last_date + timedelta(days=1)

while current_check <= yesterday:
    target_date = current_check.strftime("%Y-%m-%d")
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if has_logs(target_date):
        print(f"🕵️ {now_str} 發現缺失日期 {target_date}，啟動補發...")

        # 調用 analyzer 並帶上 --record 確保紀錄狀態
        subprocess.run(
            [
                sys.executable,
                os.path.join(BASE_DIR, "analyzer.py"),
                target_date,
                "--type",
                "both",
                "--record",
            ],
            env=env,  # 👈 關鍵：把 PYTHONPATH 塞進去！
        )
    else:
        print(f"⏭️ {now_str} 無足夠日誌 {target_date} ，跳過紀錄。")
        # 即使沒資料也紀錄，避免下次重複檢查
        conn = sqlite3.connect(DB_PATH)
        conn.execute(
            "INSERT OR IGNORE INTO system_status (task_name, last_run_date) VALUES (?, ?)",
            ("daily_analysis", target_date),
        )
        conn.commit()
        conn.close()

    current_check += timedelta(days=1)

manage_smart_schedule()
