import json
import os
import sqlite3
import subprocess
import sys
from analyzer import save_schedule_status
from config import get_device_config
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


def is_already_sent(device_name, period_name, date_str, start_t, end_t):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        "SELECT status, updated_at FROM schedule_status WHERE device_name = ? AND period_name = ? AND date = ?",
        (device_name, period_name, date_str),
    )
    row = cur.fetchone()
    conn.close()

    if row is not None:
        status, updated_at = row[0], row[1]

        if status >= 1:
            print(f"✅ 狀態為 {status}，已發送過或無數據，跳過...")
            return True  # 只要是 1 (成功) 或 2 (無數據)，絕對跳過！

        # 如果是 0，代表之前嘗試過但沒成功
        # 我們將超時時間拉長到 20 分鐘 (1200秒)，避開 10 分鐘一次的排程衝突
        last_time = datetime.strptime(updated_at, "%Y-%m-%d %H:%M:%S")
        if (datetime.now() - last_time).total_seconds() > 1200:
            print(f"⚠️ 狀態為 0 且已過 20 分鐘，判定為真崩潰，重啟任務...")
            # 重新掛號 (更新 updated_at)
            save_schedule_status(device_name, period_name, date_str, 0, start_t, end_t)
            return False

        # 狀態為 0 但還沒超過 20 分鐘，讓它慢慢跑，不要干擾
        return True
    else:
        # 完全沒紀錄，初次掛號
        save_schedule_status(device_name, period_name, date_str, 0, start_t, end_t)
        return False


def manage_smart_schedule():

    day_now = datetime.now().strftime("%A")
    time_now = datetime.now().strftime("%H:%M")
    today_str = datetime.now().strftime("%Y-%m-%d")

    config = get_device_config()
    dev_name = config["device_name"]

    with open("config.json", "r", encoding="utf-8") as f:
        config_data = json.load(f)
    today_schedule = config_data.get("weekly_schedule", {}).get(day_now, {})

    for p_name, (start_t, end_t) in today_schedule.items():
        # 核心判定：現在時間是否已經過「課程結束時間」
        if time_now > end_t:

            # 檢查資料庫：是否已發送過
            if not is_already_sent(dev_name, p_name, today_str, start_t, end_t):
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
            ]
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
