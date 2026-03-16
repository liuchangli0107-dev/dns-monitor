# DNS Monitor & Family Protector 🛡️

這是一套基於 macOS (iMac-Server) 運作的家庭 DNS 監控系統，結合了 **CoreDNS** 進行日誌收集、**Python** 背景守護進程，以及 **Telegram Bot** 即時通報與每日分析。

## 🚀 系統架構

* **DNS Server**: 使用 CoreDNS 攔截並記錄家庭設備的 DNS 查詢。
* **Watcher**: `watcher.py` 透過 `launchd` 在背景 24/7 運作，解析日誌並同步至 SQLite。
* **Database**: 使用 SQLite 存儲設備清單與通報金鑰 (Telegram Token/ChatID)。
* **Analyzer**: `analyzer.py` 提供手動與自動分析功能，計算查詢佔比並發送 Telegram 報表。

## 🛠️ 安裝與設定

### 1. 初始化資料庫

執行以下腳本建立 `devices` 與 `dns_logs` 表格：

```bash
python3 init_db.py

```

> **注意**：請至 `devices` 表格填入您的 Telegram Bot Token 與 Chat ID 才能接收通報。

### 2. 啟動背景監控 (macOS)

系統使用 `launchd` 管理，確保開機自動啟動與崩潰自動重啟：

```bash
launchctl load ~/Library/LaunchAgents/com.charlie.dns-watcher.plist

```

### 3. 設定每日自動分析 (Cron Job)

透過 `crontab -e` 加入排程，每日 23:00 發送當日報表：

```bash
0 23 * * * /usr/bin/python3 ~/dns-monitor/analyzer.py

```

## 📊 使用方法

### 手動回溯特定日期

若需要查詢過去某天的數據，可帶入日期參數：

```bash
python3 analyzer.py 2026-03-16

```

### 設備管理

當新設備連接時，系統會自動在資料庫建立 `Unknown Device` 紀錄。您可以透過 **DB Browser for SQLite** 修改 `device_name` 並設定是否開啟該設備的 Telegram 通知。

## 🔒 隱私與安全

* 資料皆存儲於本地 SQLite 資料庫，不外傳。
* 僅針對資料庫中設有有效金鑰的帳號發送通報。