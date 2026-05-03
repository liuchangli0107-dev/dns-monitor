# 簡化版範例：agent_service.py
import time
from google import genai

def run_agent():
    client = genai.Client(api_key="你的_API_KEY")
    while True:
        # 這裡可以放監聽 Telegram 訊息或監控某個指令檔的邏輯
        # 接收到指令後，調用 Gemini 進行檔案讀寫
        print("Gemini Agent 正在待命中...")
        time.sleep(60)

if __name__ == "__main__":
    run_agent()