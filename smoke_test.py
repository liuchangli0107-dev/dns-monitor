import sqlite3
import os
from analyzer import get_device_config

def smoke_test():
    print("🧪 啟動冒煙測試...")
    
    # 1. 測試資料庫連線
    if os.path.exists("dns_monitor.db"):
        print("✅ 找到資料庫文件")
    else:
        print("❌ 找不到資料庫")
        return

    # 2. 測試配置讀取 (測試您之前的 KeyError 是否修復)
    config = get_device_config()
    if config and "telegram_token" in config:
        print(f"✅ 配置讀取正常 (Device: {config['device_name']})")
    else:
        print("❌ 配置讀取異常")

    print("🏁 測試完成")

if __name__ == "__main__":
    smoke_test()