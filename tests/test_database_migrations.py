from database import connect
from migrations import run_migrations


def test_migrations_are_recorded_and_repeatable():
    run_migrations()
    run_migrations()

    conn = connect()
    try:
        rows = conn.execute(
            "SELECT version, name FROM schema_migrations ORDER BY version"
        ).fetchall()
        versions = [row["version"] for row in rows]
        names = [row["name"] for row in rows]
    finally:
        conn.close()

    assert versions == [1, 2]
    assert names == ["create_core_tables", "ensure_record_ownership_columns"]
