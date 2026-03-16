import requests
import os
import json
import re
from datetime import datetime, timedelta

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE_DIR, 'config.json')
LOG_FILE = os.path.join(BASE_DIR, 'dns_query.log')
HISTORY_FILE = os.path.join(BASE_DIR, 'notified_history.txt')
REPORT_DIR = os.path.join(BASE_DIR, 'report')

DOMAIN_REGEX = r'^[a-zA-Z0-9][-a-zA-Z0-9]{0,62}(\.[a-zA-Z0-9][-a-zA-Z0-9]{0,62})+$'

def is_valid_domain(domain):
    if not domain or len(domain) > 253: return False
    if re.match(r'^\d{1,3}(\.\d{1,3}){3}$', domain): return False
    if domain.endswith(('.local', '.arpa', '.lan')): return False
    return bool(re.match(DOMAIN_REGEX, domain))

def load_config():
    with open(CONFIG_PATH, 'r') as f:
        return json.load(f)

def analyze():
    config = load_config()
    yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
    flag_path = os.path.join(REPORT_DIR, f'{yesterday}.flag')

    if os.path.exists(flag_path): return

    history = set()
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, 'r') as f:
            history = set(line.strip() for line in f)

    new_domains = set()
    if os.path.exists(LOG_FILE):
        with open(LOG_FILE, 'r') as f:
            for line in f:
                if "[INFO]" in line:
                    parts = line.split()
                    domain = parts[-1].rstrip('.')
                    if is_valid_domain(domain) and domain not in history:
                        new_domains.add(domain)

    if new_domains:
        msg = f"📅 每日網域報告 ({yesterday})\n──────────────────\n昨日新網域：{len(new_domains)} 個\n\n" + "\n".join(list(new_domains)[:30])
        url = f"https://api.telegram.org/bot{config['TELEGRAM_TOKEN']}/sendMessage"
        r = requests.post(url, data={'chat_id': config['TELEGRAM_CHAT_ID'], 'text': msg})
        
        if r.status_code == 200:
            with open(flag_path, 'w') as f: f.write("\n".join(new_domains))
            with open(HISTORY_FILE, 'a') as f:
                for d in new_domains: f.write(f"{d}\n")

if __name__ == "__main__":
    analyze()