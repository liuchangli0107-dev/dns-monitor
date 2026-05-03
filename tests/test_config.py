# tests/test_config.py
import pytest
from config import process_domain

def test_whitelist_filtering():
    # 測試廣告是否正確被過濾
    _, should_skip = process_domain("match.rundsp.com")
    assert should_skip is True

    # 測試系統 DNS 是否正確被過濾
    _, should_skip = process_domain("dns.google")
    assert should_skip is True

def test_domain_grouping():
    # 測試 GitHub 歸類
    group, skip = process_domain("github.com")
    assert group == "🐙 GitHub"
    assert skip is False

    # 測試 CloudDevEnv 歸類
    group, skip = process_domain("console.cloud.google.com")
    assert group == "☁️ CloudDevEnv"
    assert skip is False

def test_unknown_domain():
    # 測試不認識的網域應回傳原始值
    group, skip = process_domain("my-own-site.tw")
    assert group == "my-own-site.tw"
    assert skip is False