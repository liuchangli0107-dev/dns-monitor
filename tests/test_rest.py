import json
import urllib.request
from pathlib import Path

# 1. 讀取 API Key
BASE_DIR = Path(__file__).resolve().parent.parent 
CONFIG_PATH = BASE_DIR / "config.json"

try:
    with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
        config_data = json.load(f)
        API_KEY = config_data.get("api_key", "")
        MODEL = config_data.get("model", "")
except Exception as e:
    print(f"❌ 無法讀取 config.json: {e}")
    exit(1)

# 2. 直接呼叫 Google AI Studio 的底層 API 端點
print("🤖 正在直接透過 HTTP 呼叫 Google AI Studio API...")
URL = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent?key={API_KEY}"

# 構造最簡單的請求 Payload
payload = {
    "contents": [{
        "parts": [{"text": "這是一個系統測試，請只回傳 'OK' 兩個字。"}]
    }]
}

req = urllib.request.Request(
    URL, 
    data=json.dumps(payload).encode('utf-8'), 
    headers={'Content-Type': 'application/json'}
)

# 3. 執行與錯誤捕捉
try:
    with urllib.request.urlopen(req) as response:
        result = json.loads(response.read().decode('utf-8'))
        text_response = result['candidates'][0]['content']['parts'][0]['text']
        print(f"✅ 連線成功！AI 回覆: {text_response.strip()}")
        print("💡 結論：您的 API Key 完全正常，問題 100% 出在 google-genai SDK 的相容性。")
        
except urllib.error.HTTPError as e:
    error_msg = e.read().decode('utf-8')
    print(f"❌ API 拒絕連線 (HTTP {e.code})")
    print(f"詳細原因: {error_msg}")
    print("💡 結論：可能是 API Key 無效，或該 Key 沒有存取 gemini-1.5-flash 的權限。")
except Exception as e:
    print(f"❌ 網路層錯誤: {e}")