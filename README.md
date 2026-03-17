# DNS Monitor & Family Protector 🛡️

這是一套基於 macOS (iMac-Server) 運作的家庭 DNS 監控系統。透過 **CoreDNS** 攔截請求，並結合 **Python** 背景監控腳本與 **Telegram Bot**，實現 24/7 的流量監測、設備自動識別與每日統計通報。

## 🌟 系統架構

* **DNS Server**: 由 CoreDNS 擔任，負責解析請求並將紀錄輸出至 `dns_query.log`。
* **Watcher (`watcher.py`)**: 背景守護進程，負責即時解析日誌並同步至 SQLite 資料庫。
* **Analyzer (`analyzer.py`)**: 數據統計引擎，每日定時發送「佔比分析」報表至 Telegram。
* **Database**: SQLite (`dns_monitor.db`) 存儲設備清單、查詢紀錄與 API 金鑰。

## 🛠️ 安裝與初始化

### 1. macOS 權限修正 (重要)
由於 macOS 的安全機制，必須對 CoreDNS 二進制檔進行簽署，否則無法透過防火牆接收 Tailscale 設備的 UDP 53 埠請求：
```bash
sudo codesign --force --deep --sign - /usr/local/bin/coredns

```

### 2. 資料庫初始化

執行以下指令建立所需的資料表：

```bash
python3 init_db.py

```

*註：請至 `devices` 資料表填入您的 Telegram `token` 與 `chat_id`。*

## ⚙️ 服務管理 (Launchd)

為了確保開機自動啟動與崩潰自動重啟，系統採用 macOS 標配的 `launchd` 進行管理。

### 核心服務清單

* `com.charlie.coredns.plist`: 負責 CoreDNS 解析服務。
* `com.charlie.dns-watcher.plist`: 負責 `watcher.py` 監控腳本。

### 啟動與重新載入

```bash
# 載入並啟動服務
sudo launchctl load -w /Library/LaunchDaemons/com.charlie.coredns.plist
sudo launchctl load -w /Library/LaunchDaemons/com.charlie.dns-watcher.plist

```

## 📅 自動化排程 (Crontab)

### 每日報表推送

每日 **00:05** 自動統計「昨日」數據並發送 Telegram 通報：

```bash
# 執行 crontab -e 加入以下內容
5 0 * * * /usr/bin/python3 /Users/YOURNAE/dns-monitor/analyzer.py >> /Users/YOURNAE/dns-monitor/analyzer.log 2>&1

```

## 🧹 日誌維護 (Maintenance)

隨著運行時間增長，`.log` 檔案會逐漸佔用空間。使用 `truncate` 指令可以在**不停止服務**的情況下，安全地將日誌大小重置為零：

```bash
# 清空專案目錄下所有的日誌檔案
truncate -s 0 /Users/YOURNAE/dns-monitor/*.log

```

### 💡 維護小筆記：
如果您希望日誌清理也自動化，可以考慮在 `crontab` 裡多加一行，例如每週一凌晨清理一次：
`0 0 * * 1 truncate -s 0 /Users/YOURNAE/dns-monitor/*.log`

## 📊 數據統計細節

* **自動設備識別**：新設備接入時會自動建立 `Device-末碼` 紀錄。建議手動至資料庫修改 `device_name`（如改為 `Olivia_iPhone`）以優化報表易讀性。
* **LEFT JOIN 統計**：分析腳本採用 `LEFT JOIN` 邏輯，確保當日「零活動」的設備也會出現在清單中。

---

**Maintainer**: Charlie Liu
**Last Updated**: 2026-03-17