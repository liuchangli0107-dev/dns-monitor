# test_analyzer.py
import pytest
from config import process_domain

def test_github_grouping():
    # 測試 GitHub 歸類
    group, skip = process_domain("github.com")
    assert group == "GitHub"
    assert skip is False

def test_cloud_dev_grouping():
    # 測試 Google Cloud 歸類
    group, skip = process_domain("console.cloud.google.com")
    assert group == "CloudDevEnv"
    assert skip is False

def test_ads_filtering():
    # 測試廣告是否被正確過濾 (跳過)
    _, skip = process_domain("match.rundsp.com")
    assert skip is True