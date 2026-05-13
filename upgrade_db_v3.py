# upgrade_db_v3.py
import sqlite3
import os
import logging

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "dns_monitor.db")
LOG_PATH = os.path.join(BASE_DIR, "upgrade_db.log")

logging.basicConfig(
    filename=LOG_PATH,
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)

def upgrade():
    if not os.path.exists(DB_PATH):
        msg = f"❌ 找不到資料庫檔案: {DB_PATH}"
        print(msg)
        logging.error(msg)
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    print("🚀 開始執行資料庫 V3 升級 (新增索引與清理)...")
    logging.info("開始 V3 升級作業...")
    
    try:
        # 1. 建立 timestamp 索引
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_dns_logs_timestamp ON dns_logs(timestamp)")
        # 2. 建立 domain 索引
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_dns_logs_domain ON dns_logs(domain)")
        
        # 3. 執行壓縮
        cursor.execute("VACUUM")
        
        conn.commit()
        msg = "🎉 資料庫 V3 升級完成 (建立索引並優化空間)！"
        print(msg)
        logging.info(msg)
        
    except sqlite3.Error as e:
        msg = f"❌ 資料庫升級 V3 失敗: {e}"
        print(msg)
        logging.error(msg)
    finally:
        conn.close()

if __name__ == "__main__":
    upgrade()
