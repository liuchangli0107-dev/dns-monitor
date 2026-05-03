# DNS Monitor & Family Protector 🛡️

這是一套基於 macOS (iMac and MacBook) 運作的家庭 DNS 監控系統。透過 **CoreDNS** 攔截請求，並結合 **Python** 背景監控腳本與 **Telegram Bot**，實現 24/7 的流量監測、設備自動識別與每日統計通報。從即時攔截到週期性的統計報表，形成了一個封閉且具備自我修復能力的環環相扣體系。

三層防線的技術需求與運作邏輯：

---

### 🛡️ 全自動 DNS 守護系統架構

#### 第一層：Chrome 擴充套件 (即時哨兵)
**核心需求：** 針對「極敏感」或「特定網站」的即時監控。
* **動作：** 當瀏覽器發起請求時，擴充套件第一時間捕捉網域。
* **通知機制：** 透過 Telegram Bot API 立即推播訊息。
* **優點：** **零延遲**。適合用於偵測孩子是否打開了受限網站，或是需要第一時間知道的關鍵存取。
* **技術點：** 使用 `chrome.webRequest` 或 `declarativeNetRequest` 攔截。

#### 第二層：Python 日誌攔截 (數據地基)
**核心需求：** 默默守護，確保「凡走過必留下痕跡」。
* **動作：** Python 腳本（如之前的 `dns_monitor.py`）持續監聽網路接口或與 DNS 服務器對接。
* **存儲：** 將原始請求（Domain, Timestamp, Client IP）寫入 **`dns_logs`** 原始數據表。
* **優點：** **全面性**。不限於瀏覽器（如 Line、Spotify、Docker 更新等流量都能捕捉）。

#### 第三層：Python 自動化調度與分析 (智能管家)
**核心需求：** 將大數據轉化為可閱讀的「課表式報表」。
* **動作：** `scheduler.py` 根據課表（如：數理資優、Legal Debate）定時啟動。
* **分析：** `analyzer.py` 讀取 DB，過濾掉白名單與背景雜訊，統計 Top 20 網域。
* **通知與同步：**
    * **TG 通報：** 發送該時段的圓餅圖/長條圖報表。
    * **雲端同步：** 將數據推送到 Google Cloud Run 的 API 後端。
* **狀態防禦：** 實作 `schedule_status` (0/1/2)，具備 **20 分鐘超時自動補發** 與 **重複發報攔截** 功能。

---

### 🚀 後續優化方向

1.  **儀表板整合**：將 Cloud Run 的 API 數據對接 React 面板，實現「一眼看全家」。
2.  **異常警報 (Anomaly Detection)**：如果某時段出現大量未見過的國外網域，自動發送「紅字警告」。
3.  **自動化清理**：加入 Artifact Registry 清理，降低雲端成本。

---


## 🌟 系統架構

* **DNS Server**: 由 CoreDNS 擔任，負責解析請求並將紀錄輸出至 `dns_query.log`。
* **Watcher (`watcher.py`)**: 背景守護進程，負責即時解析日誌並同步至 SQLite 資料庫。
* **Analyzer (`analyzer.py`)**: 數據統計引擎，每日定時發送「佔比分析」報表至 Telegram。
* **Database**: SQLite 存儲設備清單、查詢紀錄與 API 金鑰。
* **Cloud Sync**: 支援將分析結果推送到 Google Cloud Run 後端，供 React 面板顯示。

## 🛠️ 安裝與初始化

### 1. macOS 權限修正 (重要)
由於 macOS 的安全機制，必須對 CoreDNS 二進制檔進行簽署，否則無法透過防火牆接收 Tailscale 設備的 UDP 53 埠請求：
```bash
sudo codesign --force --deep --sign - /usr/local/bin/coredns

```

### 2. 資料庫初始化

執行以下指令建立所需的資料表：

```bash
sudo chown -R $(whoami) .
python3 -m pip install requests
python3 init_db.py

```

*註：請至 `devices` 資料表填入您的 Telegram `token` 與 `chat_id`。*


### 3. 資料庫升級 (重要)
2026-04-25 新增了課表追蹤功能，若您在其他電腦同步代碼，請務必執行升級腳本以建立 `schedule_status` 表：
```bash
python3 upgrade_db_v2.py

```

## ⚙️ 服務管理 (Launchd)

為了確保開機自動啟動與崩潰自動重啟，系統採用 macOS 標配的 `launchd` 進行管理。

### 核心服務清單

* `com.charlie.coredns.plist`: 負責 CoreDNS 解析服務。
* `com.charlie.dns-watcher.plist`: 負責 `watcher.py` 監控腳本。

### 啟動與重新載入

```bash
# 複製檔案
sudo cp com.charlie.coredns.plist /Library/LaunchDaemons/com.charlie.coredns.plist
sudo cp com.charlie.dns-watcher.plist /Library/LaunchDaemons/com.charlie.dns-watcher.plist
# 修正擁有者為 root
sudo chown root:wheel /Library/LaunchDaemons/com.charlie.coredns.plist
sudo chown root:wheel /Library/LaunchDaemons/com.charlie.dns-watcher.plist
# 修正權限為 644
sudo chmod 644 /Library/LaunchDaemons/com.charlie.coredns.plist
sudo chmod 644 /Library/LaunchDaemons/com.charlie.dns-watcher.plist
# 載入並啟動服務
sudo launchctl load -w /Library/LaunchDaemons/com.charlie.coredns.plist
sudo launchctl load -w /Library/LaunchDaemons/com.charlie.dns-watcher.plist
# 檢查 CoreDNS 狀態
sudo launchctl list | grep coredns
# 檢查 Watcher 狀態
sudo launchctl list | grep dns-watcher

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

## 📅 自動化排程 (Crontab)

系統現在採用 **自動補發機制**。透過 `scheduler.py` 檢查資料庫狀態，確保即使電腦曾關機，開機後也會自動補發缺失日期的報表。

### 1. 啟用自動排程 (Scheduler)
建議每 10 分鐘或每小時執行一次 `scheduler.py`。它會自動判斷是否需要呼叫 `analyzer.py` 生成報表。

```bash
# 確認 Python 路徑
which python3

# 編輯 cron: crontab -e
# 每 10 分鐘檢查一次執行狀態
*/10 * * * * /usr/bin/python3 /Users/$(whoami)/dns-monitor/scheduler.py >> /Users/$(whoami)/dns-monitor/scheduler.log 2>&1

```

### 2. 檢查以下這兩個 macOS 的安全設定，這是 iMac 能否自動化跑起來的最後一關：
這是 macOS 最常擋掉 Cron 的地方。請依照以下步驟操作：
* 點擊左上角  -> **系統設定**。
* 進入 **隱私權與安全性** -> **全磁碟存取權限**。
* 點擊下方的 **「+」** 號。
* 這時會跳出檔案視窗，請按快捷鍵 `Command + Shift + G`。
* 輸入路徑：`/usr/sbin/cron` 並按 Enter。
* 選中 `cron` 並確保它的**開關是開啟的**。
* *(同樣建議把 `/usr/bin/python3` 也加進去並開啟)*


### 3. 手動分析 2026-03-21 15 的數據並產出圖表
```bash
python3 analyzer.py "2026-03-21 15" --type both

```

## 🧹 日誌維護 (Maintenance)

隨著運行時間增長，`.log` 檔案會逐漸佔用空間。使用 `truncate` 指令可以在**不停止服務**的情況下，安全地將日誌大小重置為零：

```bash
# 清空專案目錄下所有的日誌檔案
truncate -s 0 /Users/$(whoami)/dns-monitor/*.log

```

### 💡 維護小筆記：
如果您希望日誌清理也自動化，可以考慮在 `crontab` 裡多加一行，例如每週一凌晨清理一次：
`0 0 * * 1 truncate -s 0 /Users/$(whoami)/dns-monitor/*.log`

## 📊 數據統計與分析細節

本系統不僅僅是記錄次數，更透過智慧過濾與網域歸類，提供最具閱讀價值的分析報告。

### 1. 智慧網域歸類 (Domain Grouping)
為了避免報表被瑣碎的子網域拆散，系統會自動將性質相近的請求彙整。例如：
* **Google 教育/協作**: 整合 `classroom.google.com`、`docs.google.com`、`drive.google.com`。
* **AI 工具**: 整合 `chatgpt.com` 與 `openai.com`。
* **影音串流**: 將 `googlevideo.com`、`ytimg.com` 等背景請求統一併入 **YouTube 服務**。
* **開發工具**: 整合 `github.com` 與各式 `githubassets` 資源。

### 2. 雜訊過濾機制 (Noise Filtering)
系統內建強大的白名單 `config.py`，自動剔除以下非人為操作的背景雜訊：
* **系統通訊**: Apple/Google 設備的背景授權驗證、憑證檢查 (OCSP/CRL)。
* **CDN 節點**: 排除 `fastly.net`、`akamai.net` 等底層加速網域。
* **廣告與追蹤**: 自動過濾 `doubleclick.net`、`analytics.google.com` 等數據採集請求。

### 3. 可視化報表 (Visualization)
每日報表包含三種維度：
* **文字通報**: 詳細列出 Top 20 訪問量最高的網域及次數。
* **圓餅圖 (Pie Chart)**: 顯示前 10 名的比例分佈，並將低於 2% 的瑣碎項目自動併入「其他」，確保圖表簡潔。
* **長條圖 (Bar Chart)**: 針對前 10 大活躍項目進行橫向對比，直觀展現使用重心。

### 4. 狀態管理 (System Status)
分析引擎會將每次「自動執行」的成功紀錄存入 SQLite 的 `system_status` 表。
* **斷點續傳**: 若電腦關機導致漏發，下次啟動時會自動補發所有缺失日期的報告。
* **手動隔離**: 手動執行 `analyzer.py` 預設不紀錄狀態，方便隨時進行歷史數據複查。

## 2026-04-25 新增功能
課表自動監控 
* **系統現在會根據 config.json 內的時段設定（例如：第一節、數理資優），在時段結束後自動統計該時段內的 DNS 請求。**
* **雲端同步: 呼叫 push_to_cloud 將數據推送至 Cloud Run**


## 2026-04-28 新增功能
補強瀏覽器DNS的運作特性導致數據缺失的解決方案
* **建立了 Webhook 接口：讓 Chrome 擴充功能直接把資料 POST 回來。**
* **優化了 API 連線：(50, 60) 的超時設定。**


## 2026-04-30 新增功能
Google Drive 配置同步
* **OAuth 2.0 驗證**：初次執行需通過 `client_secrets.json` 授權，並產生永久權杖 `token.pickle` 供背景靜默執行。
* **自動 Git Pull**：在同步配置的同時，自動檢查 GitHub 上的代碼更新，實現無感升級。
* **配置範例 (`config.json`)**：
    ```json
    {
        "remote_file_id": "YOUR_GOOGLE_DRIVE_FILE_ID",
        "schedules": [...]
    }
    ```

## 2026-05-01 功能優化
強化分頁UI與自動更新通報聯動
* **Telegram Bot 搜尋功能進化分頁機制**  
* **報表與歸類規則更新視覺化分類符號**
* **追蹤器過濾新增域名**
* **系統自動更新通報**

---

**Maintainer**: Charlie Liu
**Last Updated**: 2026-05-01
