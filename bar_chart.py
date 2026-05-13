import matplotlib.pyplot as plt
import os

# 設定 report 資料夾路徑
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
REPORT_DIR = os.path.join(BASE_DIR, "report")


def generate_dns_bar(data_rows, title_suffix, dev_name):
    """
    接收由 analyzer 傳入的已查詢、已過濾數據
    產製高對比的鮮藍色長條圖
    """
    if not data_rows:
        return None

    if not os.path.exists(REPORT_DIR):
        os.makedirs(REPORT_DIR)

    # 1. 準備繪圖數據 (取前 10 名)
    # 移除 domain 中的非 ASCII 字元以避免繪圖警告
    labels = ["".join(c for c in row["domain"] if ord(c) < 128) for row in data_rows[:10]]
    values = [row["count"] for row in data_rows[:10]]

    # === 繪圖設定 (長條圖樣式優化) ===
    # 使用 Mac 內建中文字體
    plt.rcParams["font.sans-serif"] = ["Arial Unicode MS"]

    # 建立圖表與坐標軸
    fig, ax = plt.subplots(figsize=(12, 7), dpi=100)

    # === 🎨 核心顏色調整 🎨 ===
    # 將原本的漸層 Blues 改為單一、鮮豔的藍色 ('deepskyblue' 或 'dodgerblue')
    # 這樣不論長條的高低，顏色深度都會完全一致。
    chart_color = "deepskyblue"

    # 2. 畫出長條圖
    bars = ax.bar(labels, values, color=chart_color, edgecolor="navy", alpha=0.9)

    # === 優化視覺效果與對比度 ===
    # 設定標題 (使用您傳入的時間參數，移除 Emoji)
    clean_title_str = "".join(c for c in f"{dev_name} 網路活動 Top 10 ({title_suffix})" if ord(c) < 128)
    ax.set_title(
        clean_title_str,
        fontsize=18,
        pad=20,
        weight="bold",
    )

    # 設定 Y 軸標籤與字體
    ax.set_ylabel("查詢次數 (Counts)", fontsize=14, weight="bold")

    # X 軸標籤旋轉 45 度， ha='right' 可讓文字對齊長條右側
    plt.xticks(rotation=45, ha="right", fontsize=11)

    # 3. 在長條圖上方精確標註次數
    for bar in bars:
        height = bar.get_height()
        ax.annotate(
            f"{height:.0f}",
            xy=(bar.get_x() + bar.get_width() / 2, height),
            xytext=(0, 5),  # 垂直偏移 5 點
            textcoords="offset points",
            ha="center",
            va="bottom",
            fontsize=11,
            weight="bold",
            color="navy",
        )

    # 加入水平網格線以利閱讀，並設定透明度
    ax.grid(axis="y", linestyle="--", alpha=0.4)

    # 調整邊距，確保標籤不被切到
    plt.tight_layout()

    # 將時間字串中的空格換成下底線以利存檔
    safe_time = title_suffix.replace(" ", "_").replace(":", "-")
    output_path = os.path.join(REPORT_DIR, f"dns_bar_{safe_time}.png")

    # 4. 存檔
    plt.savefig(output_path, dpi=300)
    plt.close()
    return output_path
