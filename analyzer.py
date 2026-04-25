# 1. 標準庫 (Standard Library)
import argparse
import base64
import json
import os
import site
import sqlite3
import sys
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
from config import is_whitelisted

# 強制加入用戶套件路徑，確保 subprocess 找得到 Crypto
user_site = site.getusersitepackages()
if user_site not in sys.path:
    sys.path.append(user_site)

# --- 定義歸類規則 ---
DOMAIN_GROUPS = {
    # --- Cloud & Development ---
    "CloudDevEnv": [
        "cloudworkstations.dev",
        "run.app",
        "googleworkstations.com",
        "console.cloud.google.com",
        "cloud.google.com",
        "gemini.google.com",
    ],
    "Firebase": [
        "firebase",
        "app-measurement.com",
        "firebaselogging",
        "firebase.io",
        "firebaseio.com",
        "firebase.google.com",
        "web.app",
        "firebaseapp.com",
    ],
    "GitHub": [
        "github.com",
        "githubassets.com",
        "githubusercontent.com",
        "githubcopilot.com",
        "github-cloud.s3.amazonaws.com",
    ],
    "ChatGPT": ["chatgpt.com", "openai.com"],
    # --- Social & Communication ---
    "Line": ["line-apps.com", "line.me"],
    "Facebook": ["facebook.com", "fbcdn.net", "messenger.com"],
    "Instagram": ["instagram.com", "cdninstagram.com"],
    "Discord": ["discord", "discordapp", "discord.gg"],
    # --- Productivity & Work ---
    "JobSearch": ["104.com.tw"],
    "Meeting": ["zoom.us", "webex.com", "microsoft.com/microsoft-teams"],
    "Canva": ["canva.com", "canva-static.com"],
    "Grammarly": "grammarly",
    # --- Security & Blocking ---
    "AdsTracker": [
        "ads",
        "track",
        "pixel",
        "analytics",
        "sync",
        "match",
        "inline.app",
        "scarabresearch.com",
    ],
    "NoiseBlock": ["msedge.net", "azurefd.net"],
    "AppleService": ["apple.com", "icloud.com", "mzstatic.com", "safebrowsing.apple"],
    # --- Entertainment ---
    "Podcast": ["firstory.me"],
    "Gaming": [
        "steam",
        "roblox",
        "epicgames",
        "riotgames",
        "battlenet",
        "minecraft",
        "nintendo",
        "playstation",
        "xbox",
    ],
    "Spotify": [
        "spotify.com",
        "spotify.net",
        "spotify.dev",
        "googleusercontent.com/spotify.com",  # 針對您這次看到的特殊格式
    ],
    # --- Google Ecosystem ---
    "YouTube": [
        "youtube.com",
        "googlevideo.com",
        "ytimg.com",
        "youtu.be",
        "youtube-nocookie.com",
    ],
    "GoogleSearch": [
        "www.google.com",
        "m.google.com",
        "csp.withgoogle.com",
        "google.com.tw",
    ],
    "GoogleDocs": ["classroom.google.com", "docs.google", "drive.google"],
    "Gmail": ["mail.google", "accounts.google"],
    "GoogleSystem": [
        "play.google.com",
        "android.clients",
        "gstatic.com",
        "safebrowsing.google.com",
        "mtalk.google.com",
        "this-url-does-not-exist",
        ".invalid",
        "google.com",
    ],
}

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "dns_monitor.db")


def update_system_status(target_date):
    """更新 SQLite 紀錄表 (自動排程模式才呼叫)"""
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "INSERT INTO system_status (task_name, last_run_date) VALUES (?, ?)",
        ("daily_analysis", target_date),
    )
    conn.commit()
    conn.close()


# 供 scheduler 與 analyzer 共用
def get_current_period(weekly_schedule):
    day_now = datetime.now().strftime("%A")
    time_now = datetime.now().strftime("%H:%M")
    today_schedule = weekly_schedule.get(day_now, {})

    for period_name, (start, end) in today_schedule.items():
        if start <= time_now <= end:
            return period_name, start, end
    return None, None, None


def send_telegram(token, chat_id, message, photo_paths=None):
    if not token or not chat_id:
        return False
    base_url = f"https://api.telegram.org/bot{token}"
    requests.post(
        f"{base_url}/sendMessage",
        json={"chat_id": chat_id, "text": message, "parse_mode": "Markdown"},
    )
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


def push_to_cloud(dev_name, sorted_data):
    # 1. 讀取 config.json
    try:
        with open("config.json", "r", encoding="utf-8") as f:
            config_dict = json.load(f)
    except Exception as e:
        print(f"❌ 無法讀取 config.json: {e}")
        return False

    url = config_dict.get("store_url")
    if not url:
        return False

    print(f"store_url: {url}")

    # 2. 準備 RSA 公鑰
    try:
        with open("public.pem", "rb") as f:
            key_content = f.read()
        recipient_key = RSA.import_key(key_content)
        cipher = PKCS1_OAEP.new(key=recipient_key, hashAlgo=SHA1)
    except Exception as e:
        print(f"❌ 公鑰讀取失敗: {e}")
        return False

    print(f"🚀 開始單筆同步 {dev_name} 數據...")
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
                    "status": "online",
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                }
            )

        # 轉為緊湊 JSON 並檢查長度
        json_str = json.dumps(batch_payload, separators=(",", ":"))

        # --- 自動調節邏輯 ---
        current_batch_size = len(chunk)
        if len(json_str) > RSA_MAX_LENGTH and current_batch_size > 1:
            # 如果兩筆太長，就退回只抓一筆
            print(f"⚠️ 長度為 {len(json_str)} 超標，自動切換為單筆模式...")
            chunk = [chunk[0]]  # 只取第一筆
            batch_payload = [batch_payload[0]]
            json_str = json.dumps(batch_payload, separators=(",", ":"))
            current_batch_size = 1

        # --- 執行傳送 ---
        end_idx = i + current_batch_size
        try:
            encrypted = cipher.encrypt(json_str.encode("utf-8"))
            base64_data = base64.b64encode(encrypted).decode("utf-8")
            payload = {"device_id": dev_name, "data": base64_data}

            resp = requests.post(url, json=payload, headers=headers, timeout=10)

            if resp.status_code == 200:
                print(
                    f"  ✅ [{i+1}~{min(end_idx, 20)}/20] 同步成功 (長度: {len(json_str)})"
                )
            else:
                print(f"  ⚠️ [{i+1}~{min(end_idx, 20)}/20] 同步異常: {resp.status_code}")

            time.sleep(0.1)
        except Exception as e:
            print(f"  ❌ [{i+1}/20] 嚴重錯誤: {e} | 長度: {len(json_str)}")

        # 根據實際傳送的筆數增加索引 (可能是 +1 或 +2)
        i += current_batch_size

    return True


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
    cursor.execute(
        "SELECT telegram_token, telegram_chat_id, device_name FROM devices WHERE ip_address = '127.0.0.1'"
    )
    config = cursor.fetchone()
    dev_name = config["device_name"] if config else "Unknown"

    if start_t and end_t:
        # 時段查詢
        start_str = f"{target_date} {start_t}:00"
        end_str = f"{target_date} {end_t}:59"
        query = "SELECT domain, COUNT(*) as count FROM dns_logs WHERE timestamp BETWEEN ? AND ? GROUP BY domain"
        cursor.execute(query, (start_str, end_str))
        target_display = f"{target_date} {start_t}~{end_t}"
        print(
            f"SELECT domain, COUNT(*) as count FROM dns_logs WHERE timestamp BETWEEN '{start_str}' AND '{end_str}' GROUP BY domain;"
        )
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
        if is_whitelisted(domain):
            continue

        matched_group = None
        for group_name, keywords in DOMAIN_GROUPS.items():
            if isinstance(keywords, list):
                if any(k in domain.lower() for k in keywords):
                    matched_group = group_name
                    break
            elif keywords in domain.lower():
                matched_group = group_name
                break

        final_key = matched_group if matched_group else domain
        grouped_data[final_key] = grouped_data.get(final_key, 0) + count

    # 排序
    sorted_data = sorted(
        [{"domain": k, "count": v} for k, v in grouped_data.items()],
        key=lambda x: x["count"],
        reverse=True,
    )

    if not sorted_data:
        print(f"📭 {target_date} {period_name} 時段無日誌數據。")
        if record and period_name:
            conn = sqlite3.connect(DB_PATH)
            # 標記為 2 (執行完成但無數據)
            conn.execute(
                """
                INSERT OR REPLACE INTO schedule_status (
                    device_name, period_name, date, status, start_at, end_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """,
                (dev_name, period_name, target_date, 2, args.start, args.end),
            )
            conn.commit()
            conn.close()
        return  # 結束執行

    # 產生圖表
    photos = []
    if chart_type in ["pie", "both"]:
        photos.append(pie_chart.generate_pie(sorted_data, target_display, dev_name))
    if chart_type in ["bar", "both"]:
        photos.append(
            bar_chart.generate_dns_bar(sorted_data[:10], target_display, dev_name)
        )

    # 組合報表
    msg = f"🛡️ *{dev_name} Top 20 通報* ({target_display}):\n"
    for i, row in enumerate(sorted_data[:20], 1):
        msg += f"{i}. `{row['domain']}` ({row['count']}次)\n"
    msg += f"━━━━━━━━━━━━\n⏰ 執行: {datetime.now().strftime('%H:%M:%S')}"

    if config:
        # 發送與紀錄
        success = send_telegram(
            config["telegram_token"],
            config["telegram_chat_id"],
            msg,
            [p for p in photos if p],
        )

        if success and record:
            # 如果帶有 period_name，更新 schedule_status (課表模式)
            if period_name:
                conn = sqlite3.connect(DB_PATH)
                # 使用 REPLACE 確保「沒紀錄就新增，有紀錄就更新」
                conn.execute(
                    """
                    INSERT OR REPLACE INTO schedule_status (
                        device_name, period_name, date, status, start_at, end_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                """,
                    (dev_name, period_name, target_date, 1, args.start, args.end),
                )
                conn.commit()
                conn.close()
                print(f"✅ {period_name} 狀態已確保更新為 1")
            else:
                # 否則更新 system_status (每日補發模式)
                update_system_status(target_display)

        # 同步至雲端
        success = push_to_cloud(dev_name, sorted_data)
        if success:
            print(f"✅ {target_display} 已成功同步至雲端")

    print(msg)
    conn.close()


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

    args = parser.parse_args()

    # 執行分析，並把 record 參數傳進去
    analyze_and_report(
        args.date,
        args.type,
        record=args.record,
        start_t=args.start,
        end_t=args.end,
        period_name=args.period,
    )
