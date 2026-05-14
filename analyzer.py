# 1. 標準庫 (Standard Library)
import argparse
import base64
import json
import os
import sqlite3
import time
from datetime import datetime, timedelta

import requests

# 2. 本地模組 (Local Modules)
import bar_chart
import pie_chart
from config import get_device_config, process_domain
from init_db import ensure_schema

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(BASE_DIR)
DB_PATH = os.path.join(BASE_DIR, "dns_monitor.db")


def log_print(message, **kwargs):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{now}] {message}", **kwargs)


# 更新 SQLite 紀錄表 (自動排程模式才呼叫)
def update_system_status(target_date):
    conn = sqlite3.connect(DB_PATH, timeout=20)
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


def send_telegram(token, chat_id, message, reply_markup=None, photo_paths=None):
    if not token or not chat_id:
        return False
    base_url = f"https://api.telegram.org/bot{token}"
    payload = {"chat_id": chat_id, "text": message, "parse_mode": "Markdown"}
    if reply_markup:
        payload["reply_markup"] = json.dumps(reply_markup)
    requests.post(f"{base_url}/sendMessage", json=payload, timeout=10)
    if photo_paths:
        for p_path in photo_paths:
            if os.path.exists(p_path):
                with open(p_path, "rb") as photo:
                    requests.post(
                        f"{base_url}/sendPhoto",
                        data={"chat_id": chat_id},
                        files={"photo": photo},
                        timeout=10,
                    )
    return True


def save_schedule_status(dev_name, period_name, target_date, status, start, end):
    conn = sqlite3.connect(DB_PATH, timeout=20)
    conn.execute(
        "INSERT OR REPLACE INTO schedule_status (device_name, period_name, date, status, start_at, end_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)",
        (dev_name, period_name, target_date, status, start, end),
    )
    conn.commit()
    conn.close()


def search_domain_stats(keyword, page=0):
    per_page = 20
    offset = page * per_page
    try:
        conn = sqlite3.connect(DB_PATH, timeout=20)
        cur = conn.cursor()
        count_query = "SELECT COUNT(*) FROM (SELECT 1 FROM dns_logs WHERE domain LIKE ? GROUP BY strftime('%m-%d %H:%M', timestamp), domain)"
        cur.execute(count_query, (f"%{keyword.strip()}%",))
        total_count = cur.fetchone()[0]
        if total_count == 0:
            return None, None
        total_page = (total_count + per_page - 1) // per_page if total_count > 0 else 0
        query = "SELECT strftime('%m-%d %H:%M', timestamp) AS tm, domain, COUNT(*) FROM dns_logs WHERE domain LIKE ? GROUP BY tm, domain ORDER BY timestamp DESC LIMIT ? OFFSET ?;"
        cur.execute(query, (f"%{keyword.strip()}%", per_page, offset))
        rows = cur.fetchall()
        conn.close()
        res = f"🔍 *「{keyword}」追蹤 (共 {total_count} 筆)*\n━━━━━━━━━━━━\n"
        for tm, dom, cnt in rows:
            res += f"`{tm}` | **{cnt}次**\n└ `{dom[:30]}`\n"
        res += f"\n━━━━━━━━━━━━\n📖 第 {page+1} / {total_page} 頁\n"
        keyboard = []
        nav_buttons = []
        if total_page > 4:
            nav_buttons.append({"text": f"⏮️", "callback_data": f"search_p_0_{keyword}"})
        if page > 0:
            nav_buttons.append({"text": f"⬅️", "callback_data": f"search_p_{page-1}_{keyword}"})
        if (offset + per_page) < total_count:
            nav_buttons.append({"text": f"➡️", "callback_data": f"search_p_{page+1}_{keyword}"})
        if total_page > 4:
            nav_buttons.append({"text": f"⏭️", "callback_data": f"search_p_{total_page - 1}_{keyword}"})
        if nav_buttons:
            keyboard.append(nav_buttons)
        keyboard.append([{"text": "🚫 結束搜尋", "callback_data": "cancel"}])
        reply_markup = {"inline_keyboard": keyboard}
        return res, reply_markup
    except Exception as e:
        log_print(f"search_domain_stats ❌ 錯誤: {e}")
        return "❌ 搜尋時發生錯誤", None


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
    conn = sqlite3.connect(DB_PATH, timeout=20)
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
                timeout=10,
            )
        else:
            success = send_telegram(
                config["telegram_token"],
                config["telegram_chat_id"],
                msg,
                photo_paths=[p for p in photos if p],
                reply_markup=reply_markup,
            )

            if success and record:
                if period_name:
                    save_schedule_status(
                        dev_name, period_name, target_date, 1, start_t, end_t
                    )
                else:
                    update_system_status(target_date)


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

    ensure_schema(DB_PATH)

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
