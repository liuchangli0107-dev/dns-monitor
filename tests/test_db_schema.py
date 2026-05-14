import sqlite3

from init_db import ensure_schema


def test_ensure_schema_creates_tables(tmp_path):
    db = tmp_path / "t.db"
    ensure_schema(str(db), vacuum=False)
    conn = sqlite3.connect(str(db))
    cur = conn.cursor()
    cur.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    )
    names = {row[0] for row in cur.fetchall()}
    conn.close()
    assert "devices" in names
    assert "dns_logs" in names
    assert "dns_10m_stats" in names
    assert "schedule_status" in names
    assert "system_status" in names


def test_ensure_schema_adds_is_uploaded_on_legacy_table(tmp_path):
    db = tmp_path / "legacy.db"
    conn = sqlite3.connect(str(db))
    conn.execute(
        """
        CREATE TABLE dns_10m_stats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            window_start DATETIME NOT NULL,
            window_end DATETIME NOT NULL,
            domain TEXT NOT NULL,
            count INTEGER NOT NULL
        )
        """
    )
    conn.commit()
    conn.close()

    ensure_schema(str(db), vacuum=False)

    conn = sqlite3.connect(str(db))
    cur = conn.cursor()
    cur.execute("PRAGMA table_info(dns_10m_stats)")
    cols = [r[1] for r in cur.fetchall()]
    conn.close()
    assert "is_uploaded" in cols
