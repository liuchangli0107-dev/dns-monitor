# DNS Monitor & Family Protector 🛡️

這是一套強大的 DNS 監控與管理系統，專為 macOS 環境設計 (iMac 與 MacBook)。它整合了 **CoreDNS** 進行 DNS 請求攔截與過濾，結合 **Python** 背景服務實現 24/7 的流量監測、智能數據分析、自動設備識別，並透過 **Telegram Bot** 及 **雲端同步** 提供多管道的即時通報與數據彙報。從實時攔截惡意網域到生成詳盡的週期性報告，本系統構築了一個全面且具備自我恢復能力的 DNS 安全與洞察體系。

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
*   **macOS 服務管理 (Launchd Plists):**
    *   **角色:** 確保 CoreDNS 和 `watcher.py` 作為系統後台服務自動啟動和運行。
    *   **關鍵功能:** 開機自啟動、故障自動重啟。

---

## 🛠️ 安裝與初始化

### 1. macOS 權限修正 (重要)

由於 macOS 的安全機制，必須對 CoreDNS 二進制檔進行簽署，否則無法透過防火牆接收 Tailscale 設備的 UDP 53 埠請求：

```bash
sudo codesign --force --deep --sign - /usr/local/bin/coredns
```

### 2. 資料庫初始化

執行以下指令建立所需的資料表並安裝 Python 依賴：

```bash
sudo chown -R $(whoami) .
python3 -m pip install requests pycryptodome matplotlib
python3 init_db.py
```

*註：請至 `dns_monitor.db` 中的 `devices` 資料表填入您的 Telegram `token` 與 `chat_id`。首次啟動時，系統會自動在 `devices` 表為本機建立一筆 IP 為 `127.0.0.1` 的紀錄。*

### 3. 資料庫升級 (重要)

2026-04-25 新增了課表追蹤功能，若您在其他電腦同步代碼，請務必執行升級腳本以建立 `schedule_status` 表：

```bash
python3 upgrade_db_v2.py
```

### 4. Google Drive 配置同步 (可選，用於遠程配置管理與自動升級)

本系統支援從 Google Drive 同步 `config.json`。這允許遠程管理系統配置，並在同步配置的同時檢查 GitHub 上的代碼更新，實現無感升級。

*   **OAuth 2.0 驗證**：初次執行需通過 `client_secrets.json` 授權，並產生永久權杖 `token.pickle` 供背景靜默執行。
*   **配置範例 (`config.json`)**：
    ```json
    {
        "remote_file_id": "YOUR_GOOGLE_DRIVE_FILE_ID",
        "schedules": {
            "Monday": {
                "Morning_Class": ["08:00", "11:59"],
                "Afternoon_Study": ["13:00", "17:00"]
            }
        },
        "store_url": "YOUR_CLOUD_RUN_API_ENDPOINT"
    }
    ```
    *`remote_file_id` 為您的 Google Drive 上 `config.json` 文件的 ID。*

---

## ⚙️ 服務管理 (Launchd)

為了確保開機自動啟動與崩潰自動重啟，系統採用 macOS 標配的 `launchd` 進行管理。

### 核心服務清單

*   `com.charlie.coredns.plist`: 負責 CoreDNS 解析服務。
*   `com.charlie.dns-watcher.plist`: 負責 `watcher.py` 監控腳本。
*   `com.charlie.dns-scheduler.plist`: 負責 `scheduler.py` 自動排程。

### 啟動與重新載入

```bash
# 複製檔案
sudo cp com.charlie.coredns.plist /Library/LaunchDaemons/com.charlie.coredns.plist
sudo cp com.charlie.dns-watcher.plist /Library/LaunchDaemons/com.charlie.dns-watcher.plist
sudo cp com.charlie.dns-scheduler.plist /Library/LaunchDaemons/com.charlie.dns-scheduler.plist
# 修正擁有者為 root
sudo chown root:wheel /Library/LaunchDaemons/com.charlie.coredns.plist
sudo chown root:wheel /Library/LaunchDaemons/com.charlie.dns-watcher.plist
sudo chown root:wheel /Library/LaunchDaemons/com.charlie.dns-scheduler.plist
# 修正權限為 644
sudo chmod 644 /Library/LaunchDaemons/com.charlie.coredns.plist
sudo chmod 644 /Library/LaunchDaemons/com.charlie.dns-watcher.plist
sudo chmod 644 /Library/LaunchDaemons/com.charlie.dns-scheduler.plist
# 載入並啟動服務
sudo launchctl load -w /Library/LaunchDaemons/com.charlie.coredns.plist
sudo launchctl load -w /Library/LaunchDaemons/com.charlie.dns-watcher.plist
sudo launchctl load -w /Library/LaunchDaemons/com.charlie.dns-scheduler.plist
# 檢查 CoreDNS 狀態
sudo launchctl list | grep coredns
# 檢查 Watcher 狀態
sudo launchctl list | grep dns-watcher
# 檢查 Scheduler 狀態
sudo launchctl list | grep dns-scheduler
```

### 其他指令

```bash
# 停止背景服務
sudo launchctl unload /Library/LaunchDaemons/com.charlie.coredns.plist

# 強制殺掉可能殘留的進程
sudo killall coredns 2>/dev/null

# 重新啟動背景服務
sudo launchctl load -w /Library/LaunchDaemons/com.charlie.coredns.plist

# 重啟服務
sudo launchctl kickstart -k system/com.charlie.coredns
```

### 手動分析數據 (範例)

```bash
# 手動分析 2026-03-21 當天的所有數據並產出圓餅圖與長條圖
python3 analyzer.py "2026-03-21" --type both

# 手動分析 2026-03-21 15:00 到 15:59 時段的數據
python3 analyzer.py "2026-03-21" --start "15:00" --end "15:59" --type both
```

---

## 🧹 日誌維護 (Maintenance)

隨著運行時間增長，`.log` 檔案會逐漸佔用空間。使用 `truncate` 指令可以在**不停止服務**的情況下，安全地將日誌大小重置為零：

```bash
# 清空專案目錄下所有的日誌檔案
truncate -s 0 /Users/$(whoami)/dns-monitor/*.log
```

### 💡 維護小筆記：

如果您希望日誌清理也自動化，可以考慮在 `launchd` 裡多加一個服務，例如每週一凌晨清理一次日誌。

`0 0 * * 1 truncate -s 0 /Users/$(whoami)/dns-monitor/*.log`

---

## 📊 數據統計與分析細節

本系統不僅僅是記錄次數，更透過智慧過濾與網域歸類，提供最具閱讀價值的分析報告。

### 1. 智慧網域歸類 (Domain Grouping)

為了避免報表被瑣碎的子網域拆散，系統會自動將性質相近的請求彙整。例如：

*   **Google 教育/協作**: 整合 `classroom.google.com`、`docs.google.com`、`drive.google.com`。
*   **AI 工具**: 整合 `chatgpt.com` 與 `openai.com`。
*   **影音串流**: 將 `googlevideo.com`、`ytimg.com` 等背景請求統一併入 **YouTube 服務**。
*   **開發工具**: 整合 `github.com` 與各式 `githubassets` 資源。

### 2. 雜訊過濾機制 (Noise Filtering)

系統內建強大的白名單 `config.py`，自動剔除以下非人為操作的背景雜訊：

*   **系統通訊**: Apple/Google 設備的背景授權驗證、憑證檢查 (OCSP/CRL)。
*   **CDN 節點**: 排除 `fastly.net`、`akamai.net` 等底層加速網域。
*   **廣告與追蹤**: 自動過濾 `doubleclick.net`、`analytics.google.com` 等數據採集請求。

### 3. 可視化報表 (Visualization)

每日報表包含三種維度：

*   **文字通報**: 詳細列出 Top 20 訪問量最高的網域及次數。
*   **圓餅圖 (Pie Chart)**: 顯示前 10 名的比例分佈，並將低於 2% 的瑣碎項目自動併入「其他」，確保圖表簡潔。
*   **長條圖 (Bar Chart)**: 針對前 10 大活躍項目進行橫向對比，直觀展現使用重心。

### 4. 狀態管理 (System Status)

分析引擎會將每次「自動執行」的成功紀錄存入 SQLite 的 `system_status` 表。
* **斷點續傳**: 若電腦關機導致漏發，下次啟動時會自動補發所有缺失日期的報告。
* **手動隔離**: 手動執行 `analyzer.py` 預設不紀錄狀態，方便隨時進行歷史數據複查。


---

## 📈 最新功能與優化 (2026-04-25 後)

*   **課表自動監控 (2026-04-25):** 系統現在會根據 `config.json` 內的時段設定（例如：第一節、數理資優），在時段結束後自動統計該時段內的 DNS 請求，並將數據推送至 Cloud Run。
*   **Webhook 數據攝入 (2026-04-28):** 為補強瀏覽器 DNS 的運作特性可能導致的數據缺失，系統已建立 Webhook 接口，允許 Chrome 擴充功能等外部應用直接 POST DNS 數據。API 連線超時設置已優化為 (50, 60) 秒。
*   **Google Drive 配置同步 (2026-04-30):** 支援從 Google Drive 同步 `config.json`，實現遠程配置管理和自動代碼更新。
*   **報表視覺化與過濾強化 (2026-05-01):**
    *   Telegram Bot 搜尋功能進化為分頁機制。
    *   報表與歸類規則更新了視覺化分類符號。
    *   追蹤器過濾列表新增多個域名。
    *   系統自動更新通報功能。

---

**Maintainer**: Charlie Liu
**Last Updated**: 2026-05-04
