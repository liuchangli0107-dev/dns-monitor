from datetime import datetime
import getpass
import os
import pickle
import subprocess
import json
import io
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from bot_handler import send_tg_message
from config import get_device_config

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(BASE_DIR)
DB_PATH = os.path.join(BASE_DIR, "dns_monitor.db")
LOCAL_CONFIG_PATH = os.path.join(BASE_DIR, "config.json")
KEY_FILE_PATH = os.path.join(BASE_DIR, 'client_secrets.json')
TOKEN_PATH = os.path.join(BASE_DIR, 'token.pickle')

def log_print(message):
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f"[{now}] {message}", flush=True)

def load_local_config():
    if not os.path.exists(LOCAL_CONFIG_PATH):
        default_config = {"remote_file_id": "請填入新的ID"}
        with open(LOCAL_CONFIG_PATH, 'w') as f:
            json.dump(default_config, f, indent=4)
        return default_config
    with open(LOCAL_CONFIG_PATH, 'r') as f:
        return json.load(f)

def get_drive_service():
    creds = None
    if os.path.exists(TOKEN_PATH):
        with open(TOKEN_PATH, 'rb') as token:
            creds = pickle.load(token)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                KEY_FILE_PATH, ['https://www.googleapis.com/auth/drive.readonly'])
            creds = flow.run_local_server(port=0)
        with open(TOKEN_PATH, 'wb') as token:
            pickle.dump(creds, token)
    return build('drive', 'v3', credentials=creds)


def get_remote_config():
    service = get_drive_service()
    local_settings = load_local_config()
    remote_file_id = local_settings.get("remote_file_id")
    if not remote_file_id:
        log_print("⚠️ 警告：請先在本地 config.json 中填寫正確的 remote_file_id")
        return {}
    request = service.files().get_media(fileId=remote_file_id)
    fh = io.BytesIO()
    downloader = MediaIoBaseDownload(fh, request)
    done = False
    while not done:
        status, done = downloader.next_chunk()
    return json.loads(fh.getvalue().decode('utf-8'))


def apply_schedules(remote_config):
    if 'schedules' in remote_config:
        log_print(f"📡 成功讀取雲端課表，共計 {len(remote_config['schedules'])} 條規則")
        for sch in remote_config['schedules']:
            # 範例邏輯：列印出目前讀到的設定
            log_print(f"裝置: {sch['device']} | 星期: {sch['day']} | 時段: {sch['start']}-{sch['end']}")
    else:
        log_print("⚠️ 雲端檔案中找不到 'schedules' 欄位")


def sync_git_and_restart():
    config = get_device_config()
    token = config.get('telegram_token')
    chat_id = config.get('telegram_chat_id')
    dev_name = config.get('device_name', 'Unknown')
    current_user = getpass.getuser()

    log_print(f"🔄 檢查 Git 更新... (執行者: {current_user}, 路徑: {BASE_DIR})")
    
    try:
        # 💡 終極解法：直接在指令夾帶 -c safe.directory='*' 繞過所有環境變數檢查
        result = subprocess.run(['git', '-c', 'safe.directory=*', 'pull', 'origin', 'main'], cwd=BASE_DIR, capture_output=True, text=True)
        
        if result.returncode != 0:
            error_report = (
                f"❌ **Git 同步失敗 ({dev_name})**\n"
                f"━━━━━━━━━━━━\n"
                f"👤 帳號：`{current_user}`\n"
                f"📂 路徑：`{BASE_DIR}`\n"
                f"⚠️ 錯誤：\n`{result.stderr.strip()}`"
            )
            if token and chat_id:
                send_tg_message(token, chat_id, error_report)
            return "ERROR" # 💡 改為回傳字串狀態
        
        if "Already up to date." not in result.stdout:
            # 💡 這裡的 log 指令也要加上 -c
            commit_msg = subprocess.check_output(
                ['git', '-c', 'safe.directory=*', 'log', '-1', '--pretty=%B'], 
                cwd=BASE_DIR, text=True
            ).strip()
            update_text = (
                "🚀 *系統自動更新通報*\n"
                "━━━━━━━━━━━━\n"
                f"✅ **代碼已更新**\n"
                f"📝 **異動摘要**：\n`{commit_msg}`\n\n"
                "🔄 正在執行重啟服務..."
            )
            if token and chat_id:
                send_tg_message(token, chat_id, update_text)
            log_print("🚀 偵測到新版本，執行重啟...")
            subprocess.run(['bash', os.path.join(BASE_DIR, 'restart.sh')]) 
            return "UPDATED" # 💡 回傳更新成功
            
        return "NO_CHANGE" # 💡 回傳無須更新
        
    except Exception as e:
        error_msg = f"❌ Git 更新失敗: {e}"
        log_print(error_msg)
        if token and chat_id:
            send_tg_message(token, chat_id, error_msg)
        return "ERROR"

if __name__ == "__main__":
    log_print(f"\n🚀 開始執行同步任務...")
    try:
        remote_data = get_remote_config()
        with open(LOCAL_CONFIG_PATH, 'w', encoding='utf-8') as f:
            json.dump(remote_data, f, indent=4, ensure_ascii=False)
        log_print(f"💾 本地 {LOCAL_CONFIG_PATH} 已更新。")
        
        if 'schedules' in remote_data:
            log_print(f"📡 成功讀取雲端課表，共計 {len(remote_data['schedules'])} 條規則")
            
        # 💡 根據新的回傳狀態列印日誌
        status = sync_git_and_restart()  
        if status == "UPDATED":
            log_print("🚀 系統已完成更新並重啟。")
        elif status == "NO_CHANGE":
            log_print("✅ 檢查完成，目前無需更新。")
        elif status == "ERROR":
            log_print("❌ Git 同步發生錯誤，詳情請見 TG 通報。")
            
        log_print(f"🏁 同步任務完成。")
    except Exception as e:
        log_print(f"❌ 同步失敗: {e}")