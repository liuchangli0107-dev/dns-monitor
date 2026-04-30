import datetime
import os
import pickle
import sqlite3
import subprocess
import json
import io
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(BASE_DIR)
DB_PATH = os.path.join(BASE_DIR, "dns_monitor.db")
LOCAL_CONFIG_PATH = os.path.join(BASE_DIR, "config.json")
KEY_FILE_PATH = os.path.join(BASE_DIR, 'client_secrets.json')
TOKEN_PATH = os.path.join(BASE_DIR, 'token.pickle')

def load_local_config():
    if not os.path.exists(LOCAL_CONFIG_PATH):
        # 如果檔案不存在，建立一個預設範本
        default_config = {"remote_file_id": "請填入新的ID"}
        with open(LOCAL_CONFIG_PATH, 'w') as f:
            json.dump(default_config, f, indent=4)
        return default_config
    
    with open(LOCAL_CONFIG_PATH, 'r') as f:
        return json.load(f)

# 取得最新的 ID
local_settings = load_local_config()
CONFIG_FILE_ID = local_settings.get("remote_file_id")

if not CONFIG_FILE_ID or "請填入" in CONFIG_FILE_ID:
    print("⚠️ 警告：請先在本地 config.json 中填寫正確的 remote_file_id")
    # 這裡可以選擇結束程式或跳過同步

def get_drive_service():
    creds = None
    # 2. 使用 TOKEN_PATH 檢查與讀取[cite: 2]
    if os.path.exists(TOKEN_PATH):
        with open(TOKEN_PATH, 'rb') as token:
            creds = pickle.load(token)
    
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            # 3. 關鍵：使用 KEY_FILE_PATH 取得 client_secrets[cite: 2]
            flow = InstalledAppFlow.from_client_secrets_file(
                KEY_FILE_PATH, ['https://www.googleapis.com/auth/drive.readonly'])
            creds = flow.run_local_server(port=0)
            
        # 4. 使用 TOKEN_PATH 儲存憑證[cite: 2]
        with open(TOKEN_PATH, 'wb') as token:
            pickle.dump(creds, token)
            
    return build('drive', 'v3', credentials=creds)

def get_remote_config():
    """從 Google Drive 下載並解析 JSON，但不寫入資料庫"""
    service = get_drive_service()
    request = service.files().get_media(fileId=CONFIG_FILE_ID)
    fh = io.BytesIO()
    downloader = MediaIoBaseDownload(fh, request)
    done = False
    while not done:
        status, done = downloader.next_chunk()
    # 這裡直接回傳 JSON 物件
    return json.loads(fh.getvalue().decode('utf-8'))

def apply_schedules(remote_config):
    """
    在這裡直接處理下載下來的 schedules 邏輯。
    例如：判斷現在時間是否在某個 device 的限制時間內。
    """
    if 'schedules' in remote_config:
        print(f"📡 成功讀取雲端課表，共計 {len(remote_config['schedules'])} 條規則")
        for sch in remote_config['schedules']:
            # 範例邏輯：列印出目前讀到的設定
            print(f"裝置: {sch['device']} | 星期: {sch['day']} | 時段: {sch['start']}-{sch['end']}")
    else:
        print("⚠️ 雲端檔案中找不到 'schedules' 欄位")

def sync_git_and_restart():
    print("🔄 檢查 Git 更新...")
    result = subprocess.run(['git', 'pull', 'origin', 'main'], capture_output=True, text=True)
    if "Already up to date." not in result.stdout:
        print("🚀 偵測到新版本，執行重啟...")
        # 確保此處路徑正確，建議使用絕對路徑以防萬一
        subprocess.run(['bash', os.path.join(BASE_DIR, 'restart.sh')]) 
        return True
    return False

if __name__ == "__main__":
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"\n🚀 [{now}] 開始執行同步任務...")

    try:
        # 1. 抓取雲端資料
        remote_data = get_remote_config()
        
        # 2. 【新增】將雲端抓到的資料寫入本地 config.json，覆蓋舊設定
        with open(LOCAL_CONFIG_PATH, 'w', encoding='utf-8') as f:
            json.dump(remote_data, f, indent=4, ensure_ascii=False)
        print(f"💾 本地 {LOCAL_CONFIG_PATH} 已更新。")

        # 3. 在記憶體中處理課表邏輯
        if 'schedules' in remote_data:
            print(f"📡 成功讀取雲端課表，共計 {len(remote_data['schedules'])} 條規則")
        
        # 4. 執行 Git 與重啟檢查
        restarted = sync_git_and_restart()
        
        if not restarted:
            print("✅ 無需更新，系統運行中")
        
        print(f"🏁 [{datetime.datetime.now().strftime('%H:%M:%S')}] 同步任務完成。")
        
    except Exception as e:
        print(f"❌ [{now}] 同步失敗: {e}")