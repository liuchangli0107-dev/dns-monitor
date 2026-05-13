# 1. 標準庫 (Standard Library)
import argparse
import base64
import json
import os
import sqlite3
import time
from datetime import datetime, timedelta

# 2. 第三方庫 (Third-party Libraries)
import requests
from Crypto.Cipher import PKCS1_OAEP
from Crypto.Hash import SHA1
from Crypto.PublicKey import RSA

# 3. 本地模組 (Local Modules)
import bar_chart
import pie_chart
from config import process_domain, get_device_config

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(BASE_DIR)
DB_PATH = os.path.join(BASE_DIR, "dns_monitor.db")


def log_print(message, **kwargs):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{now}] {message}", **kwargs)


# 更新 SQLite 紀錄表 (自動排程模式才呼叫)
def update_system_status(target_date):
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "INSERT INTO system_status (task_name, last_run_date) VALUES (?, ?)",
        ("daily_analysis", target_date),
    )
    conn.commit()
    conn.close()


def get_current_period(weekly_schedule):
    day_now = datetime.now().strftime("%A")
    time_now = datetime.now().strftime("%H:%M")
    today_schedule = weekly_schedule.get(day_now, {})

    for period_name, (start, end) in today_schedule.items():
        if start <= time_now <= end:
            return period_name, start, end
    return None, None, None


def send_telegram(token, chat_id, message, photo_paths=None, reply_markup=None):
    if not token or not chat_id:
        return False
    base_url = f"https://api.telegram.org/bot{token}"
    payload = {"chat_id": chat_id, "text": message, "parse_mode": "Markdown"}
    if reply_markup:
        payload["reply_markup"] = json.dumps(reply_markup)
    requests.post(f"{base_url}/sendMessage", json=payload)
    if photo_paths:
        for p_path in photo_paths:
            if os.path.exists(p_path):
                with open(p_path, "rb") as photo:
                    requests.post(
                        f"{base_url}/sendPhoto",
                        data={"chat_id": chat_id},
                        files={"photo": photo},
                    )
    return True


def push_to_cloud(
    dev_name, sorted_data, report_type="schedule_event", recorded_at=None
):
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

    # 3. 循環處理 Top 20
    i = 0
    while i < 20:
        # 嘗試抓取兩筆資料
        chunk = sorted_data[i : i + 2]
        if not chunk:
            break

        # 準備當前的 Payload (先嘗試兩筆)
        batch_payload = []
        for row in chunk:
            batch_payload.append(
                {
                    "domain": row["domain"],
                    "count": row["count"],
                }
            )

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
                "report_type": report_type,
                "recorded_at": recorded_at,
                "data": base64_data,
            }

            resp = requests.post(url, json=payload, headers=headers, timeout=10)

            if resp.status_code == 200:
                log_print(
                    f" ✅ [{i+1}~{min(end_idx, 20)}/20] 同步成功 (長度: {len(json_str)})"
                )
            else:
                log_print(
                    f" ⚠️ [{i+1}~{min(end_idx, 20)}/20] 同步異常: {resp.status_code} | URL: {url} | Payload: {json.dumps(payload, ensure_ascii=False)} | Response: {resp.text}"
                )

            time.sleep(0.1)
        except Exception as e:
            log_print(f" ❌ [{i+1}/20] 嚴重錯誤: {e} | 長度: {len(json_str)}")

        # 根據實際傳送的筆數增加索引 (可能是 +1 或 +2)
        i += current_batch_size

    return True


def save_schedule_status(dev_name, period_name, target_date, status, start, end):
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "INSERT OR REPLACE INTO schedule_status (device_name, period_name, date, status, start_at, end_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)",
        (dev_name, period_name, target_date, status, start, end),
    )
    conn.commit()
    conn.close()


def analyze_and_report(
    target_date,
    chart_type="both",
    record=False,
    start_t=None,
    end_t=None,
    period_name=None,
):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # 預設裝置名稱為 Unknown，如果 devices 表中有對應的 IP 就使用資料庫中的名稱
    config = get_device_config()
    dev_name = config["device_name"] if config else "Unknown"

    if start_t and end_t:
        # 時段查詢
        start_str = f"{target_date} {start_t}:00"
        end_str = f"{target_date} {end_t}:59"
        query = "SELECT domain, COUNT(*) as count FROM dns_logs WHERE timestamp BETWEEN ? AND ? GROUP BY domain"
        cursor.execute(query, (start_str, end_str))
        target_display = f"{target_date} {start_t}~{end_t}"
    else:
        # 原有的全天模式
        cursor.execute(
            "SELECT domain, COUNT(*) as count FROM dns_logs WHERE timestamp LIKE ? GROUP BY domain",
            (f"{target_date}%",),
        )
        target_display = target_date

    # 查詢資料
    all_rows = cursor.fetchall()

    # 過濾與合併
    grouped_data = {}
    for row in all_rows:
        domain, count = row["domain"], row["count"]
        final_key, should_skip = process_domain(domain)

        # 這裡過濾掉 AdsTracker 類別，使其不顯示在報表中
        if should_skip or final_key == "🚫 AdsTracker":
            continue

        grouped_data[final_key] = grouped_data.get(final_key, 0) + count

    # 排序
    sorted_data = sorted(
        [{"domain": k, "count": v} for k, v in grouped_data.items()],
        key=lambda x: x["count"],
        reverse=True,
    )

    if not sorted_data:
        if record and period_name:
            # 標記為 2 (執行完成但無數據)
            save_schedule_status(
                dev_name, period_name, target_date, 2, args.start, args.end
            )
            log_print(f"📭 {target_date} {period_name} 時段無日誌數據。")
        else:
            log_print(f"📭 {target_date} 無日誌數據。")
        return  # 結束執行

    # 產生圖表
    photos = []
    if chart_type in ["pie", "both"]:
        photos.append(pie_chart.generate_pie(sorted_data, target_display, dev_name))
    if chart_type in ["bar", "both"]:
        photos.append(bar_chart.generate_dns_bar(sorted_data, target_display, dev_name))

    return photos, sorted_data, target_display, dev_name


def get_report_msg(sorted_data, page, target_date, period_name, dev_name):
    per_page = 20
    total_pages = (len(sorted_data) + (per_page - 1)) // per_page
    start_idx = page * per_page
    end_idx = min(start_idx + per_page, len(sorted_data))

    display_period = period_name if period_name else "每日總結"
    msg = f"🛡️ *{dev_name} {display_period} 通報* ({target_date}) - 第 {page + 1} 頁:\n"
    for i, row in enumerate(sorted_data[start_idx:end_idx], start_idx + 1):
        msg += f"{i}. `{row['domain']}` ({row['count']}次)\n"
    msg += f"━━━━━━━━━━━━\n⏰ 執行: {datetime.now().strftime('%H:%M:%S')}"

    if total_pages > 1:
        msg += f"\n📖 第 {page + 1} / {total_pages} 頁"

    keyboard = []
    nav_buttons = []
    if page > 0:
        nav_buttons.append(
            {
                "text": "⬅️ 上頁",
                "callback_data": f"report_p_{page-1}_{target_date}_{period_name if period_name else 'none'}",
            }
        )
    if page < total_pages - 1:
        nav_buttons.append(
            {
                "text": "➡️ 下頁",
                "callback_data": f"report_p_{page+1}_{target_date}_{period_name if period_name else 'none'}",
            }
        )
    if nav_buttons:
        keyboard.append(nav_buttons)
    reply_markup = {"inline_keyboard": keyboard} if keyboard else None
    return msg, reply_markup


def analyze_and_report(
    target_date,
    chart_type="both",
    record=False,
    start_t=None,
    end_t=None,
    period_name=None,
    page=0,
    is_edit=False,
    message_id=None,
):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    config = get_device_config()
    dev_name = config["device_name"] if config else "Unknown"

    if start_t and end_t:
        start_str = f"{target_date} {start_t}:00"
        end_str = f"{target_date} {end_t}:59"
        query = "SELECT domain, COUNT(*) as count FROM dns_logs WHERE timestamp BETWEEN ? AND ? GROUP BY domain"
        cursor.execute(query, (start_str, end_str))
    else:
        cursor.execute(
            "SELECT domain, COUNT(*) as count FROM dns_logs WHERE timestamp LIKE ? GROUP BY domain",
            (f"{target_date}%",),
        )

    all_rows = cursor.fetchall()
    grouped_data = {}
    for row in all_rows:
        domain, count = row["domain"], row["count"]
        final_key, should_skip = process_domain(domain)

        # 這裡過濾掉 AdsTracker 類別，使其不顯示在報表中
        if should_skip or final_key == "🚫 AdsTracker":
            continue

        grouped_data[final_key] = grouped_data.get(final_key, 0) + count
    sorted_data = sorted(
        [{"domain": k, "count": v} for k, v in grouped_data.items()],
        key=lambda x: x["count"],
        reverse=True,
    )
    conn.close()

    if not sorted_data:
        log_print("無數據")
        return

    # 若非編輯模式才做圖，避免重複圖表
    photos = []
    if not is_edit:
        photos = []
        if chart_type in ["pie", "both"]:
            photos.append(pie_chart.generate_pie(sorted_data, target_date, dev_name))
        if chart_type in ["bar", "both"]:
            photos.append(
                bar_chart.generate_dns_bar(sorted_data, target_date, dev_name)
            )

    msg, reply_markup = get_report_msg(
        sorted_data, page, target_date, period_name, dev_name
    )

    if config:
        if is_edit and message_id:
            # Edit Message Logic
            url = f"https://api.telegram.org/bot{config['telegram_token']}/editMessageText"
            requests.post(
                url,
                json={
                    "chat_id": config["telegram_chat_id"],
                    "message_id": message_id,
                    "text": msg,
                    "parse_mode": "Markdown",
                    "reply_markup": reply_markup,
                },
            )
        else:
            success = send_telegram(
                config["telegram_token"],
                config["telegram_chat_id"],
                msg,
                [p for p in photos if p],
                reply_markup=reply_markup,
            )

            if success and record:
                if period_name:
                    save_schedule_status(
                        dev_name, period_name, target_date, 1, start_t, end_t
                    )
                else:
                    update_system_status(target_date)

            report_type = "schedule_event" if period_name else "daily_summary"
            push_to_cloud(dev_name, sorted_data, report_type, target_date)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "date",
        nargs="?",
        default=(datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d"),
    )
    parser.add_argument("--type", choices=["pie", "bar", "both"], default="both")
    parser.add_argument(
        "--record", action="store_true", help="是否紀錄至 system_status 表"
    )
    parser.add_argument("--start", help="HH:MM")
    parser.add_argument("--end", help="HH:MM")
    parser.add_argument("--period", help="時段名稱")
    parser.add_argument("--page", type=int, default=0, help="頁碼")
    parser.add_argument("--is_edit", help="編輯模式訊息ID")

    args = parser.parse_args()

    # 執行分析，並把 record 參數傳進去
    analyze_and_report(
        args.date,
        args.type,
        record=args.record,
        start_t=args.start,
        end_t=args.end,
        period_name=args.period,
        page=args.page,
        is_edit=bool(args.is_edit),
        message_id=args.is_edit,
    )
