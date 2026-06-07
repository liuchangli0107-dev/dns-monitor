import json
import os
import re
import sqlite3

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(BASE_DIR)
DB_PATH = os.path.join(BASE_DIR, "dns_monitor.db")

DOMAIN_GROUPS = {
    "☁️ CloudDevEnv": [
        "cloudworkstations.dev",
        "run.app",
        "googleworkstations.com",
        "console.cloud.google.com",
        "cloud.google.com",
    ],
    "🔥 Firebase": [
        "firebase",
        "app-measurement.com",
        "firebaselogging",
        "firebase.io",
        "firebaseio.com",
        "firebase.google.com",
        "web.app",
        "firebaseapp.com",
    ],
    "🤖 Azure DevOps": ["dev.azure.com", "visualstudio.com"],
    "🤖 Coze AI": ["coze.com"],
    "🤖 Gemini": [
        "generativelanguage",
        "googleusercontent",
        "bard",
        "generativelanguage.googleapis.com",
        "notebooklm.google",
        "ai.google.dev",
        "ai.dev",
    ],
    "🤖 Cursor": ["cursor", "cursor.sh", "anysphere", "cursor.com", "anysphere.co"],
    "🤖 GitHub Copilot": [
        "copilot",
        "copilot.microsoft.com",
        "individual.githubcopilot.com",
        "copilot-proxy.githubusercontent.com",
    ],
    "🤖 OpenAI": [
        "openai",
        "api.openai.com",
        "chatgpt.com",
        "openai.com",
        "identitatem.com",
    ],
    "🤖 Claude / Anthropic": ["anthropic", "claude.ai", "api.anthropic.com"],
    "🤖 OpenRouter": ["openrouter.ai"],
    "🤖 Ollama / Local AI": ["ollama.com", "registry.ollama.ai"],
    "🐙 GitHub": [
        "github.com",
        "githubassets.com",
        "githubusercontent.com",
        "githubcopilot.com",
        "github-cloud.s3.amazonaws.com",
    ],
    "💻 VS Code Sync": ["vscode-cdn.net"],
    "🟢 Line": ["line-apps.com", "line.me"],
    "🔵 Facebook": ["facebook.com", "fbcdn.net", "messenger.com"],
    "📸 Instagram": ["instagram.com", "cdninstagram.com"],
    "👾 Discord": ["discord", "discordapp", "discord.gg"],
    "🔍 Job Search": ["104.com.tw"],
    "📞 Meeting": ["zoom.us", "webex.com", "microsoft.com/microsoft-teams"],
    "🎨 Canva": ["canva.com", "canva-static.com"],
    "✍️ Grammarly": ["grammarly"],
    "🏫 Fuhsing School": ["fhjh.tp.edu.tw", "fhjh.tp"],
    "🚫 AdsTracker": [
        "ads",
        "track",
        "pixel",
        "analytics",
        "sync",
        "match",
        "inline.app",
        "scarabresearch.com",
        "adjust.com",
        "appsflyer.com",
        "app-measurement.com",
        "unity3d.com",
        "ssp.hinet.net",
        "popin.cc",
        "scupio.com",
        "likr.com.tw",
        "avivid.tv",
        "doubleclick.net",
        "googleadservices.com",
        "googlesyndication.com",
        "scorecardresearch.com",
        "rubiconproject.com",
        "pubmatic.com",
        "openx.net",
        "criteo.com",
        "adbrn.com",
        "liadm.com",
        "onead.com.tw",
        "botbonnie",
        "maac.app",
        "aralego",
        "holmesmind",
        "lndata",
        "innity",
        "taboola",
        "adbro",
        "adpushup",
        "flashtalking",
        "mediago",
        "themoneytizer",
        "doubleverify",
        "confiant",
        "lijit",
        "indexww",
        "revjet",
        "somplo",
        "onelink.me",
        "mktoresp.com",
        "igodigital.com",
        "googletagservices.com",
        "f-counter.net",
    ],
    "🛒 SHOPLINE": [
        "sunwayig.com",
        "shoplineimg.com",
    ],
    "🧹 NoiseBlock": ["msedge.net", "azurefd.net"],
    "🍎 Apple Service": [
        "apple.com",
        "icloud.com",
        "mzstatic.com",
        "safebrowsing.apple",
    ],
    "📡 Observability": ["sentry.io", "datadoghq.com", "pndsn.com"],
    "🌐 CDN": [
        "cdnjs.cloudflare.com",
        "jsdelivr.net",
        "unpkg.com",
        "akamaihd.net",
        "akamaized.net",
        "cloudfront.net",
        "fastly.net",
        "wp.com",
        "rsc.cdn77.org",
        "ampproject.org",
        "fonts.net",
        "mathjax.org",
        "plyr.io",
        "tailwindcss.com",
        "plot.ly",
        "playwright.dev",
        "gravatar.com",
        "bp.blogspot.com",
        "hpsmart.com",
    ],
    "🌐 Cloud Infrastructure": [
        "vercel-dns",  # Vercel 動態部署節點
        "execute-api",  # AWS API Gateway
        "cloudshell.dev",  # Google Cloud Shell
    ],
    "🎯 Web Analytics": [
        "clarity.ms",
        "google-analytics.com",
        "googletagmanager.com",
        "mixpanel.com",
        "akstat.io",
        "amplitude.com",
        "hotjar.com",
        "hotjar.io",
        "scorecardresearch.com",
        "tritondigital.com",
        "mouseflow",
        "cookielaw",
        "privacy-mgmt",
        "cxense",
        "permutive",
        "branch.io",
        "onesignal",
        "webpushr",
    ],
    "🛒 E-commerce & Portals": [
        "momo.com.tw",
        "momoshop.com.tw",
        "pchome.com.tw",
        "shopee.tw",
        "temu.com",
        "yahoo.com",
        "mobile01.com",
        "line-website.com",
        "linkedin.com",
        "shoplineapp.com",
        "shoplytics.com",
    ],
    "📰 News Media": [
        "ltn.com.tw",
        "setn.com",
        "storm.mg",
        "mirrormedia.mg",
        "ithome.com.tw",
    ],
    "🏛️ Taiwan Gov": [
        "gov.tw",
        "taoyuanairport.com.tw",
        "junyiacademy.org",
        "legis-pedia.com",
        "housefeel.com.tw",
        "johnhouse.tw",
        "pongo.com.tw"
    ],
    "🎙️ Podcast": ["firstory.me"],
    "🎮 Gaming": [
        "steam",
        "roblox",
        "epicgames",
        "riotgames",
        "battlenet",
        "minecraft",
        "nintendo",
        "playstation",
        "xbox",
        "h5games.usercontent.goog",
        "1v1lol.org",
        "1v1lolunblocked.org",
        "hero-wars.com",
        "gamesnacks.com",
        "freegames.com",
        "playsidegames.app",
    ],
    "🍿 Entertainment & Fiction": [
        "69shuba.cx",
        "drxsw.com",
        "reddit.com",
        "redditstatic.com",
    ],
    "🎵 Spotify": [
        "spotify.com",
        "spotify.net",
        "spotify.dev",
        "googleusercontent.com/spotify.com",
    ],
    "📺 YouTube": [
        "youtube.com",
        "googlevideo.com",
        "ytimg.com",
        "youtu.be",
        "youtube-nocookie.com",
    ],
    "🔎 Google Search": [
        "www.google.com",
        "m.google.com",
        "csp.withgoogle.com",
        "google.com.tw",
    ],
    "📝 Google Docs": ["classroom.google.com", "docs.google", "drive.google"],
    "📧 Gmail": ["mail.google", "accounts.google"],
    "⚙️ Google System": [
        "play.google.com",
        "android.clients",
        "gstatic.com",
        "safebrowsing.google.com",
        "mtalk.google.com",
        "this-url-does-not-exist",
        ".invalid",
        "google.com",
    ],
}

# === 統一白名單設定 (純背景雜訊過濾) ===
WHITELIST_PATTERNS = [
    # --- 0. 基礎區域網路與常規過濾 ---
    r"localhost",
    r"127\.0\.0\.1",
    r"lan$",
    r"local$",
    # --- 1. Google 系統雜訊 (排除人為服務) ---
    r"dns\.google$",  # DNS 解析
    r"remotedesktop-pa\.googleapis\.com$",  # Chrome 遠端桌面背景連線
    r"safesearch\.googleapis\.com$",  # Google 搜尋的安全過濾 API
    r"instantmessaging-pa\.googleapis\.com$",  # Google 服務的即時訊息背景通訊
    r"ssl\.gstatic\.com$",  # 網頁載入必要的加密靜態資源
    r"www\.gstatic\.com$",  # Google 靜態資源
    r"play\.google\.com$",  # Google Play 商店自動檢查更新
    r"android\.clients\.google\.com$",  # Android 系統底層通訊
    r"lh3\.google\.com$",  # Google 服務的圖片頭像/縮圖預覽
    r"www\.googleadservices\.com$",  # Google 廣告服務
    r"clients[24]\.google\.com$",  # 封殺 Google 剩餘的背景 API
    r".*\.gstatic\.com$",  # 靜態資源 (如字體)
    r".*\.googleapis\.com$",  # 系統 API 通訊
    r".*\.googlezip\.net$",  # 數據壓縮
    r".*\.gvt2\.com$",  # 軟體更新
    r".*googletagmanager\.com$",  # 追蹤器
    r".*googlesyndication\.com$",  # 廣告系統
    r".*doubleclick\.net$",  # 廣告系統
    r".*google-analytics\.com$",  # 流量統計
    r".*clients6\.google\.com$",  # 封殺 Google 的背景同步 API
    r".*\.gvt1\.com$",  # 封殺 Google 軟體分發
    # --- 2. Apple 系統雜訊 ---
    r".*apple\.com$",  # 包含 apple.com 及子網域
    r".*icloud\.com$",  # 包含 icloud.com 及其子網域
    r".*apple-mapkit.*$",  # Apple 地圖相關
    r".*apple-dns\.net$",  # Apple 內部解析
    r".*apple-relay.*$",  # Apple 隱私中繼服務
    r".*\.me\.com$",  # 舊款 iCloud 服務
    r".*\.fastly\.net$",  # 涵蓋 h3.apis.apple.map.fastly.net
    r".*\.apple-cloudkit\.com$",  # CloudKit 同步
    r".*\.mzstatic\.com$",  # App Store 靜態資源
    r".*\.aaplimg\.com$",  # 系統圖標與資源
    r".*\.icloud-content\.com$",  # iCloud 照片與文件內容
    r".*\.apple-support\.com$",  # Apple 支援
    r".*\.akadns\.net$",  # 封殺 Apple 用的 Akamai 節點
    r".*\.akahost\.net$",  # 封殺 Akamai 託管節點
    # --- 3. Microsoft & 開發工具雜訊 ---
    r"default\.exp-tas\.com$",  # Microsoft 背景遙測
    r"in\.appcenter\.ms$",  # Microsoft App Center 崩潰回報
    r"sentry\.io",  # 錯誤回報 (Grammarly/VS Code)
    r"cp\.cute-cursors\.com$",  # 游標外掛
    r"app-analytics-services\.com$",  # 軟體內置的行為分析工具
    r"solomon\.cute-cursors\.com$",  # 游標外掛的後台數據
    r"mobile\.events\.data\.microsoft\.com$",  # Microsoft 軟體的背景數據蒐集 (遙測)
    r"api\.telegram\.org$",  # Bot 程式通訊不需記錄
    r"api\.individual\.githubcopilot\.com$",  # Copilot 個人版授權驗證
    r"o.*\.ingest\.sentry\.io$",  # Sentry 錯誤回報系統
    r".*solomon\.cute-cursors\.com$",  # 游標外掛
    r".*\.microsoft\.com$",  # Windows/Office 遙測
    r".*\.msedge\.net$",  # Microsoft Edge 背景服務
    r".*\.visualstudio\.com$",  # 擴充商店
    r".*\.vscode-cdn\.net$",  # VS Code 靜態資源
    r".*\.vsassets\.io$",  # 擴充套件圖示
    r".*\.trafficmanager\.net$",  # 流量調度
    r".*cute-cursors\.com$",  # 游標外掛
    r".*\.gitkraken\.(dev|com)$",  # GitKraken 開發工具通訊與遙測
    r".*\.doublemax\.net$",  # 廣告系統
    r".*\.p-n\.io$",  # 封殺某些第三方插件使用的追蹤
    r".*\.sentry\.io$",  # 廣泛封殺 Sentry
    # --- 4. 網路安全性、CDN 與底層協定 ---
    r"^local$",  # 區域網路設備掃描
    r"^crt\..*\.com$",  # 憑證檢查
    r"^crt\..*$",
    r"^ocsp\..*$",  # SSL 憑證檢查
    r"a\.nel\.cloudflare\.com",  # 網頁效能監測
    r"withgoogle\.com",  # 安全政策報告
    r"turn\.cloudflare\.com$",  # P2P 連線輔助
    r"cp10\.cloudflare\.com$",  # 封殺 Cloudflare 連線測試
    r".*dap\.pat-issuer.*$",  # Cloudflare 隱私驗證服務
    r".*comodoca\.com.*$",  # 憑證商雜訊
    r".*\.akamaiedge\.net$",  # Akamai CDN
    r".*\.akamai\.net$",  # Akamai 基礎設施
    r".*\.arpa$",
    r".*\.cloudapp\.azure\.com$",  # Azure 背景數據蒐集與監控
    r".*\.applicationinsights\.azure\.com$",  # 應用程式效能監控
    r".*\.msedge\.net$",  # Microsoft Edge 瀏覽器服務與加速
    r".*\.elb\.amazonaws\.com$",  # AWS 負載平衡
    r".*\.cloudfront\.net$",  # Amazon CloudFront CDN
    r".*\.digicert\.com$",  # SSL 憑證驗證
    # --- 5. 廣告追蹤與第三方數據同步 ---
    r".*\.cinarra\.com$",
    r".*\.rundsp\.com$",
    r".*\.alexametrics\.com$",
    r".*\.lkqd\.net$",
    r".*\.spotxchange\.com$",
    r".*\.krxd\.net$",
    r".*\.lmgssp\.com$",
    r".*\.mrpdata\.net$",
    r".*\.extend\.tv$",
    r".*\.oraki\.io$",
    r".*\.tribalfusion\.com$",
    r".*\.dotomi\.com$",
    r".*\.gammaplatform\.com$",
    # --- 強化過濾：廣告與追蹤 (Ads & Trackers) ---
    r".*ads.*",
    r".*track.*",
    r".*pixel.*",
    r".*analytics.*",
    r".*doubleclick\.net.*",
    r".*scorecardresearch\.com.*",
    r".*googlesyndication\.com.*",
    r".*gum\.criteo\.com.*",
    r".*mug\.criteo\.com.*",
    r".*connect\.facebook\.net.*",
    r".*likr\.tw.*",
]

# 預先編譯以提高效能
COMPILED_WHITELIST = [re.compile(p, re.IGNORECASE) for p in WHITELIST_PATTERNS]


def is_whitelisted(domain):
    return any(pattern.match(domain) for pattern in COMPILED_WHITELIST)


def process_domain(domain):
    domain_lower = domain.lower()
    if is_whitelisted(domain_lower):
        return None, True
    for group_name, keywords in DOMAIN_GROUPS.items():
        if isinstance(keywords, list):
            if any(k in domain_lower for k in keywords):
                return group_name, False
        elif keywords in domain_lower:
            return group_name, False
    return domain, False


def get_device_config():
    from init_db import ensure_schema

    for attempt in (0, 1):
        try:
            conn = sqlite3.connect(DB_PATH, timeout=20)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                "SELECT telegram_token, telegram_chat_id, device_name FROM devices WHERE ip_address = '127.0.0.1'"
            )
            config = cursor.fetchone()
            conn.close()
            if config:
                return {
                    "telegram_token": config["telegram_token"],
                    "telegram_chat_id": config["telegram_chat_id"],
                    "device_name": config["device_name"],
                }
            with open("config.json", "r", encoding="utf-8") as f:
                config_data = json.load(f)
            return {
                "telegram_token": config_data.get("telegram_token", ""),
                "telegram_chat_id": config_data.get("telegram_chat_id", ""),
                "device_name": config_data.get("device_name", "Unknown"),
            }
        except sqlite3.OperationalError:
            if attempt == 0:
                ensure_schema(DB_PATH)
                continue
            raise


def get_bot_config():
    from init_db import ensure_schema

    for attempt in (0, 1):
        try:
            conn = sqlite3.connect(DB_PATH, timeout=20)
            cur = conn.cursor()
            cur.execute(
                "SELECT telegram_token, telegram_chat_id FROM devices WHERE telegram_token IS NOT NULL"
            )
            rows = cur.fetchall()
            conn.close()
            return (rows[0][0], [str(row[1]) for row in rows]) if rows else (None, [])
        except sqlite3.OperationalError:
            if attempt == 0:
                ensure_schema(DB_PATH)
                continue
            print("get_bot_config ❌ 資料庫讀取失敗 (結構異常)")
            return None, []
        except Exception as e:
            print(f"get_bot_config ❌ 資料庫讀取失敗: {e}")
            return None, []
