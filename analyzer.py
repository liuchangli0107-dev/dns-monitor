import sqlite3
import os
import requests
import sys
import argparse
import pie_chart
import bar_chart
import base64
import json
import time
from datetime import datetime, timedelta
from config import is_whitelisted
from Crypto.PublicKey import RSA
from Crypto.Cipher import PKCS1_OAEP
from Crypto.Hash import SHA1

# --- 定義歸類規則 ---
DOMAIN_GROUPS = {
    # --- Cloud & Development ---
    "CloudDevEnv": ["cloudworkstations.dev", "run.app", "googleworkstations.com"],
    "Firebase": [
        "firebase",
        "app-measurement.com",
        "firebaselogging",
        "firebase.io",
        "firebaseio.com",
        "firebase.google.com",
    ],
    "GitHub": [
        "github.com",
        "githubassets.com",
        "githubusercontent.com",
        "githubcopilot.com",
        "github-cloud.s3.amazonaws.com",
    ],
    "ChatGPT": ["chatgpt.com", "openai.com"],
    # --- Google Ecosystem ---
    "GoogleSearch": [
        "www.google.com",
        "m.google.com",
        "csp.withgoogle.com",
        "google.com.tw",
    ],
    "GoogleDocs": ["classroom.google.com", "docs.google", "drive.google"],
    "GoogleSystem": ["play.google.com", "android.clients", "gstatic.com"],
    "YouTube": ["youtube.com", "googlevideo.com", "ytimg.com", "youtu.be"],
    "Gmail": ["mail.google", "accounts.google"],
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
        return

    url = config_dict.get("store_url")
    if not url:
        return

    print(f"store_url: {url}")

    # 2. 準備 RSA 公鑰
    try:
        with open("public.pem", "rb") as f:
            key_content = f.read()
        recipient_key = RSA.import_key(key_content)
        cipher = PKCS1_OAEP.new(key=recipient_key, hashAlgo=SHA1)
    except Exception as e:
        print(f"❌ 公鑰讀取失敗: {e}")
        return

    print(f"🚀 開始單筆同步 {dev_name} 數據...")
    headers = {"Content-Type": "application/json"}

    # 3. 循環傳送 Top 15
    for i, row in enumerate(sorted_data[:15], 1):
        # 封裝為單筆陣列，保持與後端 PHP foreach 兼容
        single_payload = [
            {
                "domain": row["domain"],
                "count": row["count"],
                "status": "online",
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }
        ]

        # 轉為緊湊 JSON
        json_str = json.dumps(single_payload, separators=(",", ":"))

        try:
            # 加密
            encrypted = cipher.encrypt(json_str.encode("utf-8"))
            # 修正處：b64encode (移除底線)
            base64_data = base64.b64encode(encrypted).decode("utf-8")

            # 構建傳送封包
            payload = {"device_id": dev_name, "data": base64_data}

            resp = requests.post(url, json=payload, headers=headers, timeout=10)

            if resp.status_code == 200:
                print(f"  ✅ [{i}/15] {row['domain']} 同步成功")
            else:
                print(f"  ⚠️ [{i}/15] 同步異常: {resp.status_code}")

            # 輕微延遲確保雲端寫入穩定
            time.sleep(0.05)

        except Exception as e:
            print(f"  ❌ [{i}/15] 加密失敗: {e}")

    print("🏁 雲端同步完成。")


def analyze_and_report(
    target_date, chart_type="both", record=False, start_t=None, end_t=None
):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # --- 關鍵修改：支援精確時段查詢 ---
    if start_t and end_t:
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

    # 1. 查詢資料
    cursor.execute(
        "SELECT domain, COUNT(*) as count FROM dns_logs WHERE timestamp LIKE ? GROUP BY domain",
        (f"{target_display}%",),
    )
    all_rows = cursor.fetchall()

    cursor.execute(
        "SELECT telegram_token, telegram_chat_id, device_name FROM devices WHERE ip_address = '127.0.0.1'"
    )
    config = cursor.fetchone()
    dev_name = config["device_name"] if config else "Unknown"

    # 2. 過濾與合併
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

    # 3. 排序與產圖
    sorted_data = sorted(
        [{"domain": k, "count": v} for k, v in grouped_data.items()],
        key=lambda x: x["count"],
        reverse=True,
    )
    photos = []
    if chart_type in ["pie", "both"]:
        photos.append(pie_chart.generate_pie(sorted_data, target_display, dev_name))
    if chart_type in ["bar", "both"]:
        photos.append(
            bar_chart.generate_dns_bar(sorted_data[:10], target_display, dev_name)
        )

    # 4. 組合報表
    msg = f"🛡️ *{dev_name} Top 20 通報* ({target_display}):\n"
    for i, row in enumerate(sorted_data[:20], 1):
        msg += f"{i}. `{row['domain']}` ({row['count']}次)\n"
    msg += f"━━━━━━━━━━━━\n⏰ 執行: {datetime.now().strftime('%H:%M:%S')}"

    # 5. 發送與紀錄
    if config:
        success = send_telegram(
            config["telegram_token"],
            config["telegram_chat_id"],
            msg,
            [p for p in photos if p],
        )
        if success and record:
            update_system_status(target_display)
            print(f"✅ {target_display} 已紀錄至 system_status")

        push_to_cloud(dev_name, sorted_data)

    print(msg)
    conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "date",  # 這裡建議統一用 date，跟 scheduler 呼叫時一致
        nargs="?",
        default=(datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d"),
    )
    parser.add_argument("--type", choices=["pie", "bar", "both"], default="both")

    # 關鍵點：請確認下面這行在 parser 區塊中只出現這唯一一次
    parser.add_argument(
        "--record", action="store_true", help="是否紀錄至 system_status 表"
    )

    args = parser.parse_args()

    # 執行分析，並把 record 參數傳進去
    analyze_and_report(args.date, args.type, record=args.record)
