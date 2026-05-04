import json
import os
from pathlib import Path
from google import genai

# 1. 穩定偵測路徑
BASE_DIR = Path(__file__).resolve().parent.parent 
CONFIG_PATH = BASE_DIR / "config.json"
FILE_PATH = BASE_DIR / "watcher.py"

# 2. 讀取配置
def load_config():
    if not CONFIG_PATH.exists():
        alt_config = Path(__file__).resolve().parent / "config.json"
        if alt_config.exists():
            with open(alt_config, 'r', encoding='utf-8') as f:
                return json.load(f)
        raise FileNotFoundError(f"找不到設定檔: {CONFIG_PATH}")
    with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
        return json.load(f)

try:
    config_data = load_config()
    PROJECT_ID = config_data.get("project_id", "")
    API_KEY = config_data.get("api_key", "")
    LOCATION = config_data.get("location", "")
    MODEL = config_data.get("model", "")
    if not API_KEY:
        raise ValueError("API Key 在 config.json 中未設定或為空值")
    if not MODEL:
        raise ValueError("MODEL 在 config.json 中未設定或為空值")
except Exception as e:
    print(f"❌ 配置讀取失敗: {e}")
    exit(1)

# 3. 初始化 Client
# client = genai.Client(api_key=API_KEY)
client = genai.Client(api_key=API_KEY, http_options={'api_version': 'v1'})

def run_test():
    if not FILE_PATH.exists():
        print(f"❌ 找不到目標檔案: {FILE_PATH}")
        return

    with open(FILE_PATH, 'r', encoding='utf-8') as f:
        content = f.read()

    print(f"🤖 正在透過 Google AI Studio (API Key) 呼叫 Gemini...")
    
    prompt = f"請直接回傳以下 Python 代碼，僅在最頂部加入一行註解 '# Verified by Gemini Agent 2026'，其餘內容原封不動：\n\n{content}"
    
    try:
        # 使用明確的版本號以確保存取權限
        response = client.models.generate_content(
            model=MODEL,
            contents=prompt
        )

        raw_text = response.text.strip()
        
        # 移除 Markdown 標籤的邏輯
        if "```python" in raw_text:
            new_code = raw_text.split("```python")[1].split("```")[0].strip()
        elif "```" in raw_text:
            new_code = raw_text.split("```")[1].split("```")[0].strip()
        else:
            new_code = raw_text
        
        with open(FILE_PATH, 'w', encoding='utf-8') as f:
            f.write(new_code)
        
        print(f"✅ 成功！watcher.py 已更新。")
        print(f"使用 Google AI Studio 免費額度執行。")
        
    except Exception as e:
        print(f"❌ Gemini 呼叫失敗: {e}")
        print(f"💡 建議：若仍 404，可前往 Console 檢查是否已在 {LOCATION} 啟用 Vertex AI。")

if __name__ == "__main__":
    run_test()