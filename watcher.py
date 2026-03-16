import time
import requests
import os
import json
import re

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE_DIR, 'config.json')
LOG_FILE = os.path.join(BASE_DIR, 'dns_query.log')
DOMAIN_REGEX = r'^[a-zA-Z0-9][-a-zA-Z0-9]{0,62}(\.[a-zA-Z0-9][-a-zA-Z0-9]{0,62})+$'

# 全域設定快取，避免重複讀取硬碟
cached_config = None

def is_valid_domain(domain):
    if not domain or len(domain) > 253: return False
    if re.match(r'^\d{1,3}(\.\d{1,3}){3}$', domain): return False
    if domain.endswith(('.local', '.arpa', '.lan')): return False
    return bool(re.match(DOMAIN_REGEX, domain))

def load_config():
    global cached_config
    if cached_config is None:
        if not os.path.exists(CONFIG_PATH):
            raise FileNotFoundError("找不到 config.json")
        with open(CONFIG_PATH, 'r') as f:
            cached_config = json.load(f)
    return cached_config

# 已記錄的網域集（避免重複通知）
seen_domains = set()

def send_telegram(domain):
    config = load_config()
    msg = f"🔔 Olivia 存取新網域：\n{domain}"
    url = f"https://api.telegram.org/bot{config['TELEGRAM_TOKEN']}/sendMessage"
    try:
        requests.post(url, data={'chat_id': config['TELEGRAM_CHAT_ID'], 'text': msg}, timeout=5)
    except Exception as e:
        print(f"發送失敗: {e}")

def monitor():
    print("🚀 Telegram 監控腳本啟動中...")
    
    # 第一次啟動先讀取現有內容，避免把舊紀錄當成新通知
    with open(LOG_FILE, 'r') as f:
        for line in f:
            if "[INFO]" in line:
                parts = line.split()
                if len(parts) >= 2:
                    domain = parts[-1].rstrip('.')
                    seen_domains.add(domain)

    # 開始監控新產生的日誌
    with open(LOG_FILE, 'r') as f:
        f.seek(0, os.SEEK_END)
        while True:
            line = f.readline()
            if not line:
                time.sleep(1)
                continue
            
            if "[INFO]" in line:
                parts = line.split()
                if len(parts) >= 2:
                    domain = parts[-1].rstrip('.')
                    if is_valid_domain(domain) and domain not in seen_domains:
                        print(f"發現新域名: {domain}")
                        send_telegram(domain)
                        seen_domains.add(domain)

if __name__ == "__main__":
    monitor()
