import json
import urllib.request
from pathlib import Path

# 1. 讀取 API Key
BASE_DIR = Path("/Users/nangei/dns-monitor").resolve()
CONFIG_PATH = BASE_DIR / "config.json"

try:
    with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
        API_KEY = json.load(f).get("api_key", "")
except Exception as e:
    print(f"❌ 無法讀取 config.json: {e}")
    exit(1)

print("🔍 正在向 Google 查詢這把 Key 真正可用的模型清單...")
URL = f"https://generativelanguage.googleapis.com/v1beta/models?key={API_KEY}"

try:
    req = urllib.request.Request(URL)
    with urllib.request.urlopen(req) as response:
        data = json.loads(response.read().decode('utf-8'))
        
        print("\n✅ 查詢成功！您的 Key 支援以下 Gemini 模型：")
        found = False
        for model in data.get('models', []):
            name = model.get('name', '')
            if 'gemini' in name:
                print(f" 🔹 {name}")
                found = True
        
        if not found:
            print(" ⚠️ 糟糕！您的 Key 似乎沒有綁定任何 Gemini 模型的存取權限。")

except urllib.error.HTTPError as e:
    print(f"❌ 查詢失敗 (HTTP {e.code})")
    print(f"詳細原因: {e.read().decode('utf-8')}")
except Exception as e:
    print(f"❌ 發生未知的網路錯誤: {e}")