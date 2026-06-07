import sqlite3
import argparse
from datetime import datetime, timedelta
from config import DB_PATH, process_domain


def get_all_domains(since_date=None):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # 基本查詢：過濾掉測試數據或空值
    query = "SELECT DISTINCT domain FROM dns_logs WHERE domain IS NOT NULL"
    params = []

    # 🌟 核心修正：將原本的 recorded_at 修改為資料庫實際擁有的 timestamp 欄位
    if since_date:
        query += " AND timestamp >= ?"
        params.append(since_date)
        print(f"🔍 正在篩選時間起點之後的數據: {since_date}")

    cursor.execute(query, params)
    domains = [row[0] for row in cursor.fetchall()]
    conn.close()
    return domains


def main():
    # 設定參數解析器
    parser = argparse.ArgumentParser(description="列出未歸類的網域，可指定時間起點。")

    # 支援兩種參數：一種是相對天數，一種是絕對日期
    parser.add_argument(
        "-d", "--days", type=int, help="篩選最近幾天內的數據 (例如: -d 7 代表最近 7 天)"
    )
    parser.add_argument(
        "--since",
        type=str,
        help="指定絕對時間起點 (格式: YYYY-MM-DD 或 YYYY-MM-DD HH:MM:SS)",
    )

    args = parser.parse_args()
    since_target = None

    # 邏輯判斷：優先使用相對天數，再使用絕對日期
    if args.days:
        # 計算幾天前的時間點
        target_time = datetime.now() - timedelta(days=args.days)
        since_target = target_time.strftime("%Y-%m-%d %H:%M:%S")
    elif args.since:
        since_target = args.since

    # 取得原始的所有網域清單
    all_domains = get_all_domains(since_target)

    # 🌟 核心修正：配合方案 B 的 process_domain 邏輯 (未分類回傳原始 domain)
    unclassified_domains = []
    for domain in all_domains:
        group_name, should_skip = process_domain(domain)
        
        # 1. 如果在第一線被判定為白名單、廣告追蹤、CDN Infrastructure (should_skip == True)，直接跳過
        if should_skip:
            continue
            
        # 2. 如果 group_name 等於原始 domain，代表它「完全沒有被任何群組匹配到」
        if group_name == domain:
            unclassified_domains.append(domain)

    # 排序讓輸出的文字檔更容易閱讀
    unclassified_domains.sort()

    # 產生檔名並寫入檔案
    log_filename = f"unclassified_domains_{datetime.now().strftime('%Y%m%d%H%M%S')}.txt"
    
    with open(log_filename, "w", encoding="utf-8") as f:
        for domain in unclassified_domains:
            f.write(f"{domain}\n")

    print(f"✅ 成功篩選未分類網域。總共 {len(unclassified_domains)} 筆已寫入 {log_filename}")


if __name__ == "__main__":
    main()