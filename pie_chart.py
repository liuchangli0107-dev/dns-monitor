import os

import matplotlib.pyplot as plt

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
REPORT_DIR = os.path.join(BASE_DIR, "report")


def generate_pie(data_rows, title_suffix, dev_name):
    """純繪圖引擎：產製圓餅圖 (低於 2% 併入其他)"""
    if not data_rows:
        return None
    if not os.path.exists(REPORT_DIR):
        os.makedirs(REPORT_DIR)

    # 1. 計算總數與 2% 門檻
    total_count = sum(row["count"] for row in data_rows)
    threshold = total_count * 0.02

    d_labels = []
    d_values = []
    others_sum = 0

    # 2. 進行數據過濾
    for row in data_rows:
        # 移除 domain 中的非 ASCII 字元以避免繪圖警告
        clean_domain = "".join(c for c in row["domain"] if ord(c) < 128)
        if row["count"] >= threshold:
            d_labels.append(clean_domain)
            d_values.append(row["count"])
        else:
            others_sum += row["count"]

    # 3. 如果有低於 2% 的項目，併入「其他」
    if others_sum > 0:
        d_labels.append("其他")
        d_values.append(others_sum)

    # 4. 繪圖設定 (沿用您的字體與樣式)
    plt.rcParams["font.sans-serif"] = ["Arial Unicode MS"]
    plt.figure(figsize=(10, 8))

    plt.pie(
        d_values,
        labels=d_labels,
        autopct="%1.1f%%",
        startangle=140,
        pctdistance=0.75,
        explode=[0.05] * len(d_labels),  # 稍微拉開間距，避免標籤重疊
    )

    # 處理標題：移除 Emoji (非 ASCII 字元)
    clean_title_str = "".join(c for c in f"{dev_name} 網路活動比例 ({title_suffix})" if ord(c) < 128)
    plt.title(clean_title_str, fontsize=16)
    plt.axis("equal")

    safe_title = title_suffix.replace(" ", "_").replace(":", "-")
    output_path = os.path.join(REPORT_DIR, f"dns_pie_{safe_title}.png")
    plt.savefig(output_path, dpi=300, bbox_inches="tight")
    plt.close()

    return output_path
