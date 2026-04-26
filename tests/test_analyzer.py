# tests/test_analyzer.py
import pytest
from analyzer import DOMAIN_GROUPS

def test_domain_grouping():
    # 測試是否能正確識別 GitHub 相關網域
    github_domains = ["github.com", "githubusercontent.com"]
    for domain in github_domains:
        found = False
        for group, domains in DOMAIN_GROUPS.items():
            if any(d in domain for d in domains):
                if group == "GitHub":
                    found = True
        assert found, f"網域 {domain} 應該要被歸類在 GitHub 組"

def test_cloud_dev_grouping():
    # 測試 Google Cloud 相關網域
    gcp_domain = "console.cloud.google.com"
    matched_groups = []
    for group, domains in DOMAIN_GROUPS.items():
        if any(d in gcp_domain for d in domains):
            matched_groups.append(group)
    
    # 只要 CloudDevEnv 在匹配名單中即可，或者確保它是第一個
    assert "CloudDevEnv" in matched_groups