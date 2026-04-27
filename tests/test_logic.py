# test_logic.py
from config import DOMAIN_GROUPS

def test_github_keywords():
    # 測試 GitHub 關鍵字是否在新的 config 字典中
    github_list = DOMAIN_GROUPS.get("GitHub", [])
    assert "github.com" in github_list
    assert "githubusercontent.com" in github_list

def test_line_keywords():
    # 測試 Line 關鍵字
    line_list = DOMAIN_GROUPS.get("Line", [])
    assert "line.me" in line_list