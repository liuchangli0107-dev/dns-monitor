# 🛡️ Olivia DNS 流量守護系統

這套系統建構於 macOS 環境，結合 **CoreDNS**、**Python** 與 **Telegram Bot**，實現全自動的網路連線即時監控與每日彙整報告。

## 🏗️ 系統架構

* **錄影機 (CoreDNS)**：透過 `LaunchDaemon` 背景執行，即時將 DNS 請求寫入 `dns_query.log`。
* **巡邏員 (watcher.py)**：即時追蹤 Log，發現新網域立刻透過 Telegram 通知，並備份紀錄。
* **彙整員 (analyzer.py)**：由 `crontab` 定期觸發，每天早上彙整前一天的所有新網域連線。
* **資料庫 (report/)**：存放每日發送過的報告內容（`.flag`），作為備份與狀態鎖。

---

## 📂 目錄結構

所有檔案均位於：`~/dns-monitor/`

```text
.
├── analyzer.py            # 每日彙整腳本 (Crontab 執行)
├── watcher.py             # 即時監控腳本 (手動或背景執行)
├── config.json            # 敏感設定 (Token, Chat ID) - 不上 Git
├── config.json.example    # 設定檔範本
├── Corefile               # CoreDNS 邏輯配置
├── my_whitelist.txt       # 排除不記錄的白名單網域
├── dns_query.log          # 原始 DNS 連線日誌
├── notified_history.txt   # 已通知過的歷史紀錄 (防止重複)
├── report/                # 存放發送過的報告內容 (*.flag) - 不上 Git
└── README.md              # 專案說明文件

```

---

## 🔧 核心指令手冊

### 1. 服務啟動與維護 (CoreDNS)

當您修改了 `Corefile` 或 `my_whitelist.txt` 時，必須重啟服務：

```bash
# 重新載入並啟動
sudo launchctl unload /Library/LaunchDaemons/com.coredns.monitor.plist
sudo launchctl load -w /Library/LaunchDaemons/com.coredns.monitor.plist

# 檢查進程是否活著 (應顯示 /opt/homebrew/bin/coredns)
ps aux | grep coredns

```

### 2. 啟動即時監控 (Watcher)

建議在終端機開啟一個視窗執行，或放入背景：

```bash
python3 ~/dns-monitor/watcher.py

```

### 3. 手動觸發每日彙整 (Analyzer)

測試是否能正確讀取昨天的紀錄並發報：

```bash
python3 ~/dns-monitor/analyzer.py

```

---

## ⏰ 自動化排程 (Crontab)

確保系統每 30 分鐘自動檢查一次是否有漏掉的報告。執行 `crontab -e` 並確認內容：

```text
*/30 * * * * /usr/bin/python3 /Users/miyukian/dns-monitor/analyzer.py >> /Users/miyukian/dns-monitor/cron_log.log 2>&1

```

---

## 🛡️ 安全性與 Git 規範

本專案已設定 `.gitignore`，請確保以下敏感資訊不會上傳至 GitHub：

1. **`config.json`**：內含 Telegram Bot Token。
2. **`report/`**：內含實際的瀏覽紀錄備份。
3. **`*.log`**：連線原始紀錄。

**初次部署時：**
請將 `config.json.example` 複製為 `config.json` 並填入正確的 Token。

---

## 💡 日常維護

* **清空日誌**：若 `dns_query.log` 過大，執行 `> ~/dns-monitor/dns_query.log`。
* **檢查備份**：您可以到 `report/` 資料夾查看過去每一天發送給您的 Telegram 訊息備份。