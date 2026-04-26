# tests/test_logic.py
from analyzer import DOMAIN_GROUPS

def test_github_grouping():
    # 測試 GitHub 關鍵字是否在分類中
    github_list = DOMAIN_GROUPS.get("GitHub", [])
    assert "github.com" in github_list
    assert "githubusercontent.com" in github_list

def test_line_grouping():
    # 測試 Line 關鍵字是否在分類中
    line_list = DOMAIN_GROUPS.get("Line", [])
    assert "line.me" in line_list