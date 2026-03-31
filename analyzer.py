import sqlite3
import os
import requests
import sys
import argparse
from datetime import datetime, timedelta
from config import is_whitelisted

import pie_chart
import bar_chart

# --- 定義歸類規則 ---
DOMAIN_GROUPS = {
    "Grammarly 服務": "grammarly",
    "YouTube 服務": ["youtube.com", "googlevideo.com", "ytimg.com", "youtu.be"],
    "Google 教育/協作": ["classroom.google.com", "docs.google", "drive.google"],
    "Google 網頁與搜尋": [
        "www.google.com",
        "m.google.com",
        "csp.withgoogle.com",
        "google.com.tw",
    ],
    "Google 系統/商店": ["play.google.com", "android.clients", "gstatic.com"],
    "Gmail/帳號": ["mail.google", "accounts.google"],
    "ChatGPT/OpenAI": ["chatgpt.com", "openai.com"],
    "Canva": ["canva.com", "canva-static.com"],
    "遠端會議": ["zoom.us", "webex.com", "microsoft.com/microsoft-teams"],
    "GitHub 服務": [
        "github.com",
        "githubassets.com",
        "githubusercontent.com",
        "githubcopilot.com",
        "github-cloud.s3.amazonaws.com",
    ],
    "🎙️ Podcast/串流": ["firstory.me"],
    "💬 LINE 通訊": ["line-apps.com", "line.me"],
    "💼 104": ["104.com.tw"],
    "🚫 廣告與追蹤": [
        "ads",
        "track",
        "pixel",
        "analytics",
        "sync",
        "match",
        "inline.app",
        "scarabresearch.com",
    ],
    "🚫 攔截雜訊": ["msedge.net", "azurefd.net"],
    "📱 Instagram": ["instagram.com", "cdninstagram.com"],
    "📱 Facebook": ["facebook.com", "fbcdn.net", "messenger.com"],
    "💬 Discord 通訊": ["discord", "discordapp", "discord.gg"],
    "🎮 Steam 平台": ["steam", "steampowered", "steamcommunity"],
    "🎮 Roblox 遊戲": ["roblox", "rbxcdn"],
    "🎮 Epic Games": ["epicgames", "fortnite"],
    "🎮 三大主機平台": ["nintendo", "playstation", "xbox"],
    "🎮 英雄聯盟": ["riotgames", "leagueoflegends", "pvp.net"],
    "🎮 麥塊 (Minecraft)": ["minecraft", "mojang"],
    "🎮 暴雪 (Blizzard)": [
        "battlenet",
        "blizzard",
        "hearthstone",
        "battle.net",
        "akamaized.net",
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


def analyze_and_report(target_time, chart_type="both", record=False):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # 1. 查詢資料
    cursor.execute(
        "SELECT domain, COUNT(*) as count FROM dns_logs WHERE timestamp LIKE ? GROUP BY domain",
        (f"{target_time}%",),
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
        photos.append(pie_chart.generate_pie(sorted_data, target_time, dev_name))
    if chart_type in ["bar", "both"]:
        photos.append(
            bar_chart.generate_dns_bar(sorted_data[:10], target_time, dev_name)
        )

    # 4. 組合報表
    msg = f"🛡️ *{dev_name} Top 20 通報* ({target_time}):\n"
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
            update_system_status(target_time)
            print(f"✅ {target_time} 已紀錄至 system_status")

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
