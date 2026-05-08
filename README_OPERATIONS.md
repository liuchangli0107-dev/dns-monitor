# DNS Monitor 安裝與操作手冊

本專案是一個基於 Python 的 DNS 監控系統，具備自動同步、錯誤通知及狀態回報功能。

## 1. 系統需求
- 作業系統：macOS
- Python 版本：建議 Python 3.10+
- 依賴項：`google-auth`, `google-api-core`, `urllib3` 等（請查看 `requirements.txt`）

## 2. 安裝步驟

### 2.1 環境準備
1. 將專案複製到目標目錄：`cd /Users/nangei/dns-monitor`
2. 安裝必要套件：
   ```bash
   pip3 install -r requirements.txt
   ```

### 2.2 設定檔配置
請依序檢查目錄下的設定檔，確保參數正確：
- `config.json`: 設定核心監控參數。
- `policy.yaml`: DNS 過濾與監控規則。
- **注意：** 請勿將 `token.pickle` 及任何包含 `client_secrets.json` 等敏感資訊上傳至公開倉儲。

## 3. 服務管理 (LaunchAgents)
本專案使用 `launchd` 管理背景服務。

**啟用服務：**
```bash
launchctl load ~/Library/LaunchAgents/com.charlie.dns-watcher.plist
```

## 4. 日誌與維護
- **日誌路徑：**
  - `watcher.log` / `watcher_err.log`: 監控器紀錄
  - `sync_agent.log` / `sync_agent_error.log`: 同步錯誤紀錄
- **資料庫檢查：** 使用 `init_db.py` 可進行資料庫初始化或升級。

## 5. 安全注意事項
- **嚴禁洩露：** `token.pickle` (OAuth 權杖)、`client_secrets.json` (Google API 金鑰) 以及 Telegram Bot Token。
- **權限管理：** 確保這些檔案僅擁有讀寫權限 (`chmod 600`)：
  ```bash
  chmod 600 /Users/nangei/dns-monitor/token.pickle
  ```

## 6. 進階網域管控 (不需 sudo)
本專案透過 CoreDNS 實現網域管理，無需修改系統 `/etc/hosts`。
- **CoreDNS 攔截：** 修改 `/Users/nangei/dns-monitor/Corefile`。
- **黑名單設定：** 修改 `/Users/nangei/dns-monitor/my_blacklist.txt`。
- **套用設定：** 修改後執行 `./restart.sh` 即可生效。
