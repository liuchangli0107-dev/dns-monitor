import sqlite3
from config import DB_PATH, is_whitelisted, process_domain


def get_all_domains():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT domain FROM dns_logs")
    domains = [row[0] for row in cursor.fetchall()]
    conn.close()
    return domains


def main():
    domains = get_all_domains()
    log_filename = "unclassified_domains.log"
    count = 0

    # 使用 'w' 模式開啟檔案，每次執行會自動覆蓋舊紀錄，確保資料最新
    with open(log_filename, "w", encoding="utf-8") as f:
        for d in domains:
            if not is_whitelisted(d.lower()):
                group, is_white = process_domain(d)
                if not is_white and group == d:  # 未在白名單且未歸類到任何群組
                    f.write(f"{d}\n")  # 寫入檔案並換行
                    count += 1

    print(f"📊 統計完成！已將 {count} 個未歸類的網域存入 {log_filename}")


if __name__ == "__main__":
    main()