# DNS Monitor & Family Protector 🛡️

這是一套強大的 DNS 監控與管理系統，專為 macOS 環境設計 (iMac 與 MacBook)。它整合了 **CoreDNS** 進行 DNS 請求攔截與過濾，結合 **Python** 背景服務實現 24/7 的流量監測、智能數據分析、自動設備識別，並透過 **Telegram Bot** 及 **雲端同步** 提供多管道的即時通報與數據彙報。從實時攔截惡意網域到生成詳盡的週期性報告，本系統構築了一個全面且具備自我恢復能力的 DNS 安全與洞察體系。

## 📖 目錄
- [核心功能概覽](#🌟-核心功能概覽)
- [系統架構詳解](#🛡️-系統架構詳解)
- [安裝與初始化](#🛠️-安裝與初始化)
- [服務管理 (Launchd)](#⚙️-服務管理-launchd)
- [常用指令速查](#⚡-常用指令速查)
- [日誌維護](#🧹-日誌維護)
- [數據統計與分析細節](#📊-數據統計與分析細節)
- [功能更新紀錄](#📈-功能更新紀錄)
- [雲端整合架構](#☁️-雲端整合架構)

---

### 🌟 核心功能概覽

本系統的核心目標是提供一套自動化的 DNS 解決方案，確保網絡使用的透明度與安全性：

*   **智能 DNS 過濾與攔截：** 透過 CoreDNS 配置，有效阻擋惡意、廣告或不適宜的網域。
*   **全時段 DNS 流量監測：** 持續記錄所有設備的 DNS 查詢，確保「凡走過必留下痕跡」。
*   **智能數據分析與歸類：** 自動過濾背景雜訊，並將有意義的 DNS 請求歸類，提供清晰易懂的報告。
*   **多管道即時通報：** 透過 Telegram 即時發送 Top 20 網域報告與視覺化圖表。
*   **雲端數據同步與備份：** 加密分析結果並同步至雲端，支援遠程監控與數據備份。
*   **自動化排程與自我修復：** 確保報告按時生成，並具備故障後自動補發缺失報告的能力。

---

### 🛡️ 系統架構詳解

本系統由多個協同工作的組件構成，旨在提供一個穩健且智能的 DNS 監控解決方案：

*   **DNS 核心服務 (CoreDNS):**
    *   **角色:** 作為本地 DNS 伺服器，負責解析所有 DNS 請求。
    *   **關鍵功能:**
        *   **DNS 請求攔截與過濾:** 根據 `Corefile` 配置，直接阻擋特定網域 (`msedge.net`, `tm-azurefd.net`, `inline.app`) 及 `my_blacklist.txt` 中的網域。
        *   **詳細日誌輸出:** 將所有 DNS 查詢記錄到 `dns_query.log`，為後續分析提供原始數據。
*   **日誌監測與數據攝入 (Watcher - `watcher.py`):**
    *   **角色:** 持續監聽 CoreDNS 產生的日誌文件。
    *   **關鍵功能:**
        *   **實時日誌解析:** 從 `dns_query.log` 中提取客戶端 IP 和查詢域名。
        *   **智能設備識別:** 自動識別新設備並記錄其 IP 地址與預設名稱。
        *   **數據持久化:** 將解析後的 DNS 查詢記錄儲存到 `dns_monitor.db` 資料庫。
*   **數據分析與報告生成 (Analyzer - `analyzer.py`):**
    *   **角色:** 讀取資料庫中的 DNS 記錄，進行深度分析並生成可視化報告。
    *   **關鍵功能:**
        *   **智能雜訊過濾:** 根據 `config.py` 中的 `WHITELIST_PATTERNS` 過濾掉系統背景流量（如 CDN、API 通訊、廣告追蹤器）。
        *   **網域智能歸類:** 將相關的網域（如 `youtube.com`, `googlevideo.com`）合併到預設分類（如「📺 YouTube」），提高報告可讀性。
        *   **Top 20 統計與視覺化:** 統計指定時間範圍內（日或特定時段）訪問量最高的 Top 20 網域，並生成圓餅圖和長條圖。
        *   **Telegram 報告推送:** 將分析結果（文本摘要及圖表）發送至預設的 Telegram 頻道或群組。
        *   **雲端數據加密同步:** 使用 RSA 加密將分析報告安全地同步至遠端雲端服務 (如 Google Cloud Run API)，實現異地備份與集中管理。
*   **自動排程管理 (Scheduler - `scheduler.py`):**
    *   **角色:** 負責在預設時間（如每日、特定課表時段）觸發 `analyzer.py` 執行。
    *   **關鍵功能:**
        *   **按時自動執行:** 根據內部定義的排程自動啟動數據分析與報告生成流程。
        *   **斷點續傳機制:** 檢查 `system_status` 或 `schedule_status` 表，自動補發因電腦關機或其他原因而錯過的歷史報告。
*   **核心配置與數據定義 (`config.py`, `config.json`):**
    *   **角色:** 儲存系統運行所需的關鍵參數與規則。
    *   **關鍵內容:** `DOMAIN_GROUPS` (網域分類定義), `WHITELIST_PATTERNS` (白名單規則), Telegram API 設定, 雲端同步 URL 等。
*   **本地數據庫 (SQLite - `dns_monitor.db`):**
    *   **角色:** 儲存所有 DNS 查詢日誌、設備信息、排程狀態以及其他系統運行數據。
    *   **關鍵作用:** 輕量級、高效能的數據儲存方案，支援系統的離線操作與數據查詢。
*   **網域管理輔助工具 (`list_domains.py`):**
    *   **角色:** 提供快速挖掘並篩選「未分類」或「隱藏」網域的輔助工具。
    *   **關鍵功能:**
        *   **智慧篩選:** 整合 `config.py` 的過濾規則，自動排除已知的白名單與 CDN 流量。
        *   **快速導出:** 將清單導出至 `.txt` 文件，方便進行分類規則的迭代與更新。
        *   **彈性查詢:** 支援日期篩選或相對天數，精準追蹤特定時段的異常網域。
*   **macOS 服務管理 (Launchd Plists):**
    *   **角色:** 確保 CoreDNS 和 `watcher.py` 作為系統後台服務自動啟動和運行。
    *   **關鍵功能:** 開機自啟動、故障自動重啟。

---

### 🛠️ 安裝與初始化

#### 1. macOS 權限修正
```bash
sudo codesign --force --deep --sign - /usr/local/bin/coredns
```

#### 2. 環境建置與初始化
建議使用專案內建的依賴檔：
```bash
sudo chown -R $(whoami) .
python3 -m pip install -r requirements.txt
python3 init_db.py
```
*註：請至 `dns_monitor.db` 中的 `devices` 資料表填入您的 Telegram `token` 與 `chat_id`。首次啟動時，系統會自動在 `devices` 表為本機建立一筆 IP 為 `127.0.0.1` 的紀錄。*

#### 3. Google Drive 配置同步 (可選)
本系統支援從 Google Drive 同步 `config.json`。這允許遠程管理系統配置，並在同步配置的同時檢查 GitHub 上的代碼更新，實現無感升級。
*   **OAuth 2.0 驗證**：初次執行需通過 `client_secrets.json` 授權，並產生永久權杖 `token.pickle` 供背景靜默執行。

---

### ⚙️ 服務管理 (Launchd)

為了確保開機自動啟動與崩潰自動重啟，系統採用 macOS 標配的 `launchd` 進行管理。

#### 核心服務清單
*   `com.charlie.coredns.plist`: 負責 CoreDNS 解析服務。
*   `com.charlie.dns-watcher.plist`: 負責 `watcher.py` 監控腳本。
*   `com.charlie.dns-scheduler.plist`: 負責 `scheduler.py` 自動排程。

#### 啟動指令範例
```bash
# 複製檔案至系統目錄
sudo cp com.charlie.* /Library/LaunchDaemons/
# 修正權限
sudo chown root:wheel /Library/LaunchDaemons/com.charlie.*
sudo chmod 644 /Library/LaunchDaemons/com.charlie.*
# 載入服務
sudo launchctl load -w /Library/LaunchDaemons/com.charlie.*
```

---

### ⚡ 常用指令速查

| 功能 | 指令 |
| :--- | :--- |
| **手動分析當日數據** | `python3 analyzer.py "YYYY-MM-DD" --type both` |
| **篩選未分類網域** | `python3 list_domains.py -d 7` |
| **清空所有日誌** | `truncate -s 0 *.log` |
| **查看 CoreDNS 狀態** | `sudo launchctl list \| grep coredns` |

---

### 🧹 日誌維護

隨著運行時間增長，`.log` 檔案會逐漸佔用空間。使用 `truncate` 指令可以在**不停止服務**的情況下，安全地將日誌大小重置為零：

```bash
truncate -s 0 /Users/$(whoami)/dns-monitor/*.log
```

---

### 📊 數據統計與分析細節

本系統不僅僅是記錄次數，更透過智慧過濾與網域歸類，提供最具閱讀價值的分析報告。

1.  **智慧網域歸類**: 將性質相近的網域（如 YouTube 相關域名）彙整為單一分類。
2.  **雜訊過濾機制**: 自動剔除系統通訊、CDN 節點與廣告追蹤器。
3.  **可視化報表**: 包含文字通報、圓餅圖與長條圖，並自動過濾低頻率瑣碎項目。
4.  **斷點續傳**: 檢查 `system_status` 表，若發生漏發，下次啟動時會自動補發缺失報告。

---

### 📈 功能更新紀錄

*   **2026-05-01**: 報表視覺化與過濾強化、Telegram Bot 分頁搜尋、系統自動更新。
*   **2026-04-30**: 支援從 Google Drive 同步 `config.json`。
*   **2026-04-28**: 新增 Webhook 數據攝入接口。
*   **2026-04-25**: 新增課表自動監控功能。
*   **2026-06-07**: 新增網域管理輔助工具功能。

---

### ☁️ 雲端整合架構 (Cloud Backend Integration)

本系統支援將數據分析結果自動同步至雲端平台，實現多設備數據集中管理。

*   **架構**: 採用無伺服器 (Serverless) 架構，後端運行於 Google Cloud Run (`asia-east1`)。
*   **存儲**: 數據持久化至 GCS Bucket，並透過 GCS Fuse 掛載至後端。
*   **安全性**: 所有請求需包含 `X-Monitor-Token` Header，並在推送時對 Payload 進行 RSA 加密，確保隱私。
*   **終端點**: 推送數據至雲端 API，支援異地備份與集中式報表查看。

---

**Maintainer**: Charlie Liu  
**Last Updated**: 2026-06-08
