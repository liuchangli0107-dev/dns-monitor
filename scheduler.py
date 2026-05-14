import base64
import json
import os
import sqlite3
import subprocess
import sys
import time
from datetime import datetime, timedelta

import requests
from Crypto.Cipher import PKCS1_OAEP
from Crypto.Hash import SHA1
from Crypto.PublicKey import RSA

from analyzer import save_schedule_status
from config import get_device_config, process_domain
from init_db import ensure_schema

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(BASE_DIR)
DB_PATH = os.path.join(BASE_DIR, "dns_monitor.db")

def log_print(message, **kwargs):
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    kwargs['flush'] = True
    print(f"[{now}] {message}", **kwargs)


def init_scheduler_db():
    ensure_schema(DB_PATH)


def get_last_processed_date():
    conn = sqlite3.connect(DB_PATH, timeout=20)
    cur = conn.cursor()
    cur.execute(
        "SELECT last_run_date FROM system_status WHERE task_name='daily_analysis' ORDER BY last_run_date DESC LIMIT 1"
    )
    row = cur.fetchone()
    conn.close()
    return row[0] if row else "2026-03-01"  # 預設起始日期


def has_logs(date_str):
    conn = sqlite3.connect(DB_PATH, timeout=20)
    cur = conn.cursor()
    cur.execute(
        "SELECT COUNT(*) FROM dns_logs WHERE timestamp LIKE ?", (f"{date_str}%",)
    )
    count = cur.fetchone()[0]
    conn.close()
    return count > 0


def is_already_sent(device_name, period_name, date_str, start_t, end_t):
    conn = sqlite3.connect(DB_PATH, timeout=20)
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
            log_print(f"✅ 狀態為 {status}，已發送過或無數據，跳過...")
            return True  # 只要是 1 (成功) 或 2 (無數據)，絕對跳過！

        # 如果是 0，代表之前嘗試過但沒成功
        # 我們將超時時間拉長到 20 分鐘 (1200秒)，避開 10 分鐘一次的排程衝突
        last_time = datetime.strptime(updated_at, "%Y-%m-%d %H:%M:%S")
        if (datetime.now() - last_time).total_seconds() > 1200:
            log_print(f"⚠️ 狀態為 0 且已過 20 分鐘，判定為真崩潰，重啟任務...")
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
                log_print(f"🕵️ 偵測到已結束課程: {p_name} ({end_t}) 尚未發報，準備補發...")

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
                    log_print(f"✅ {p_name} 補發成功")
                else:
                    log_print(f"❌ {p_name} 補發失敗，待下次循環重試")


def push_to_cloud(dev_name, sorted_data, recorded_at=None):
    # 統一將 recorded_at 處理為 YYYY-MM-DD HH:MM:SS
    if not recorded_at:
        recorded_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    elif len(recorded_at) == 10:  # 若僅傳入 YYYY-MM-DD
        recorded_at = f"{recorded_at} 00:00:00"
    elif len(recorded_at) == 13:  # 若傳入 YYYY-MM-DD HH
        recorded_at = f"{recorded_at}:00:00"

    # 1. 讀取 config.json
    try:
        with open("config.json", "r", encoding="utf-8") as f:
            config_dict = json.load(f)
    except Exception as e:
        log_print(f"❌ 無法讀取 config.json: {e}")
        return False

    url = config_dict.get("store_url")
    if not url:
        return False

    log_print(f"store_url: {url}")

    # 2. 準備 RSA 公鑰
    try:
        with open("public.pem", "rb") as f:
            key_content = f.read()
        recipient_key = RSA.import_key(key_content)
        cipher = PKCS1_OAEP.new(key=recipient_key, hashAlgo=SHA1)
    except Exception as e:
        log_print(f"❌ 公鑰讀取失敗: {e}")
        return False

    log_print(f"🚀 開始單筆同步 {dev_name} 數據...")
    headers = {"Content-Type": "application/json"}

    # 定義 RSA 2048-bit PKCS1_OAEP 的安全長度天花板
    RSA_MAX_LENGTH = 214

    # 3. 循環處理全部數據
    i = 0
    total_items = len(sorted_data)
    while i < total_items:
        # 嘗試抓取兩筆資料
        chunk = sorted_data[i : i + 2]
        if not chunk:
            break

        # 準備當前的 Payload (先嘗試兩筆)
        batch_payload = []
        for row in chunk:
            batch_payload.append({"domain": row["domain"], "count": row["count"]})

        # 轉為緊湊 JSON 並檢查長度
        json_str = json.dumps(batch_payload, separators=(",", ":"))

        # --- 自動調節邏輯 ---
        current_batch_size = len(chunk)
        if len(json_str) > RSA_MAX_LENGTH and current_batch_size > 1:
            # 如果兩筆太長，就退回只抓一筆
            log_print(f"⚠️ 長度為 {len(json_str)} 超標，自動切換為單筆模式...")
            chunk = [chunk[0]]  # 只取第一筆
            batch_payload = [batch_payload[0]]
            json_str = json.dumps(batch_payload, separators=(",", ":"))
            current_batch_size = 1

        # --- 執行傳送 ---
        end_idx = i + current_batch_size
        try:
            encrypted = cipher.encrypt(json_str.encode("utf-8"))
            base64_data = base64.b64encode(encrypted).decode("utf-8")
            payload = {
                "device_id": dev_name,
                "report_type": "10m_stats",
                "recorded_at": recorded_at,
                "data": base64_data,
            }

            resp = requests.post(url, json=payload, headers=headers, timeout=10)

            if resp.status_code == 200:
                log_print(
                    f" ✅ [{i+1}~{min(end_idx, total_items)}/{total_items}] 同步成功 (長度: {len(json_str)})"
                )
            else:
                log_print(
                    f" ⚠️ [{i+1}~{min(end_idx, total_items)}/{total_items}] 同步異常: {resp.status_code} | URL: {url} | Payload: {json.dumps(payload, ensure_ascii=False)} | Response: {resp.text}"
                )

            time.sleep(0.1)
        except Exception as e:
            log_print(f" ❌ [{i+1}/{total_items}] 嚴重錯誤: {e} | 長度: {len(json_str)}")

        # 根據實際傳送的筆數增加索引 (可能是 +1 或 +2)
        i += current_batch_size

    return True


def process_10m_stats():
    conn = sqlite3.connect(DB_PATH, timeout=20)
    cur = conn.cursor()
    cur.execute(
        "SELECT last_run_date FROM system_status WHERE task_name='10m_stats' ORDER BY last_run_date DESC LIMIT 1"
    )
    row = cur.fetchone()
    if row:
        last_time = datetime.strptime(row[0], "%Y-%m-%d %H:%M:%S")
    else:
        now = datetime.now()
        minutes = (now.minute // 10) * 10
        last_time = now.replace(minute=minutes, second=0, microsecond=0) - timedelta(minutes=10)

    now = datetime.now()
    current_block_start = now.replace(minute=(now.minute // 10) * 10, second=0, microsecond=0)
    
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    while last_time < current_block_start:
        window_start = last_time
        window_end = last_time + timedelta(minutes=10)
        
        start_str = window_start.strftime("%Y-%m-%d %H:%M:%S")
        end_str = (window_end - timedelta(seconds=1)).strftime("%Y-%m-%d %H:%M:%S")
        
        query = "SELECT domain, COUNT(*) as count FROM dns_logs WHERE timestamp BETWEEN ? AND ? GROUP BY domain"
        cursor.execute(query, (start_str, end_str))
        all_rows = cursor.fetchall()
        
        grouped_data = {}
        for r in all_rows:
            domain, count = r["domain"], r["count"]
            final_key, should_skip = process_domain(domain)

            if should_skip or final_key == "🚫 AdsTracker":
                continue

            grouped_data[final_key] = grouped_data.get(final_key, 0) + count
            
        for d, c in grouped_data.items():
            cursor.execute(
                "INSERT INTO dns_10m_stats (window_start, window_end, domain, count) VALUES (?, ?, ?, ?)",
                (start_str, end_str, d, c)
            )
            
        cursor.execute(
            "INSERT INTO system_status (task_name, last_run_date) VALUES (?, ?)",
            ("10m_stats", window_end.strftime("%Y-%m-%d %H:%M:%S")),
        )
        
        conn.commit()
        log_print(f"📊 已計算 10 分鐘統計: {start_str} ~ {end_str}")
        
        last_time = window_end
        
    # === 新增：上傳尚未同步的 10 分鐘統計資料 ===
    config = get_device_config()
    dev_name = config["device_name"] if config else "Unknown"
    
    # 找出所有尚未上傳的 window_start
    cursor.execute("SELECT DISTINCT window_start FROM dns_10m_stats WHERE is_uploaded = 0 ORDER BY window_start ASC")
    unuploaded_windows = [r[0] for r in cursor.fetchall()]
    
    for w_start in unuploaded_windows:
        # 取得該 window 的所有資料
        cursor.execute("SELECT domain, count FROM dns_10m_stats WHERE window_start = ?", (w_start,))
        window_data = cursor.fetchall()
        
        # 轉換為 sorted_data 格式
        sorted_data = [{"domain": row["domain"], "count": row["count"]} for row in window_data]
        sorted_data = sorted(sorted_data, key=lambda x: x["count"], reverse=True)
        
        if sorted_data:
            success = push_to_cloud(dev_name, sorted_data, recorded_at=w_start)
            if success:
                cursor.execute("UPDATE dns_10m_stats SET is_uploaded = 1 WHERE window_start = ?", (w_start,))
                conn.commit()
                log_print(f"☁️ 已成功上傳 {w_start} 的 10 分鐘統計資料")
            else:
                log_print(f"⚠️ {w_start} 統計資料上傳失敗，待下次重試")
        else:
            # 如果某區間完全沒有資料，也標記為已上傳
            cursor.execute("UPDATE dns_10m_stats SET is_uploaded = 1 WHERE window_start = ?", (w_start,))
            conn.commit()

    conn.close()


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
        log_print(f"🕵️ {now_str} 發現缺失日期 {target_date}，啟動補發...")

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
        log_print(f"⏭️ {now_str} 無足夠日誌 {target_date} ，跳過紀錄。")
        # 即使沒資料也紀錄，避免下次重複檢查
        conn = sqlite3.connect(DB_PATH, timeout=20)
        conn.execute(
            "INSERT OR IGNORE INTO system_status (task_name, last_run_date) VALUES (?, ?)",
            ("daily_analysis", target_date),
        )
        conn.commit()
        conn.close()

    current_check += timedelta(days=1)

manage_smart_schedule()
process_10m_stats()
