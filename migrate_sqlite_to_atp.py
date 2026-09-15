"""One-time guarded migration from InternMate SQLite to Oracle ATP."""
import os
import sqlite3
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

import oracledb

ROOT = Path(__file__).resolve().parent
for line in (ROOT / ".env").read_text(encoding="utf-8").splitlines():
    if "=" in line and not line.lstrip().startswith("#"):
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())

SOURCE = ROOT / "db.sqlite3"
TABLES = [
    "django_migrations", "django_content_type", "auth_permission", "auth_group", "auth_user",
    "auth_group_permissions", "auth_user_groups", "auth_user_user_permissions", "accounts_userprofile",
    "operations_department", "operations_skilldomain", "operations_masterdatalist", "operations_masterdataitem",
    "operations_project", "operations_internprofile", "operations_internprofile_skills",
    "operations_internprojectassignment", "operations_dailyprogressentry", "operations_taskdependency",
    "operations_aiusagerecord", "operations_mentorreviewcomment", "operations_auditlog",
    "django_admin_log", "django_session",
]
DATE_COLUMNS = {"log_date", "expected_completion_date", "internship_start_date", "internship_end_date", "assigned_from", "assigned_to"}
TIMESTAMP_COLUMNS = {"created_at", "updated_at", "last_login", "date_joined", "action_at", "action_time", "applied", "expire_date"}
DECIMAL_COLUMNS = {"time_spent_hours", "estimated_time_saved_hours"}


def convert(column, value):
    if value is None:
        return None
    if column in DATE_COLUMNS:
        return date.fromisoformat(str(value)[:10])
    if column in TIMESTAMP_COLUMNS:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return parsed.replace(tzinfo=None)
    if column in DECIMAL_COLUMNS:
        return Decimal(str(value))
    return value


def main():
    password = os.environ["INTERNMATE_ORACLE_PASSWORD"]
    wallet = os.environ["INTERNMATE_ORACLE_WALLET_DIR"]
    connection = oracledb.connect(
        user=os.environ.get("INTERNMATE_ORACLE_USER", "LEARNING"), password=password,
        dsn=os.environ.get("INTERNMATE_ORACLE_DSN", "tecpdatp01_medium"),
        config_dir=wallet, wallet_location=wallet,
        wallet_password=os.environ.get("INTERNMATE_ORACLE_WALLET_PASSWORD"),
        tcp_connect_timeout=15,
    )
    source = sqlite3.connect(SOURCE)
    source.row_factory = sqlite3.Row
    cursor = connection.cursor()
    try:
        for table in TABLES:
            cursor.execute(f"SELECT COUNT(*) FROM {table.upper()}")
            if cursor.fetchone()[0]:
                raise RuntimeError(f"ATP table {table} is not empty; migration stopped without overwriting data.")
        for table in TABLES:
            columns = [row[1] for row in source.execute(f"PRAGMA table_info({table})")]
            rows = source.execute(f"SELECT * FROM {table}").fetchall()
            values = []
            for row in rows:
                item = [convert(column, row[column]) for column in columns]
                if table == "operations_dailyprogressentry":
                    log_i, expected_i = columns.index("log_date"), columns.index("expected_completion_date")
                    if item[expected_i] is not None and item[expected_i] < item[log_i]:
                        item[expected_i] = item[log_i]
                values.append(item)
            if values:
                placeholders = ", ".join(f":{index + 1}" for index in range(len(columns)))
                cursor.executemany(f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({placeholders})", values)
            print(f"{table}: {len(values)} rows")
        connection.commit()
        print("Migration completed successfully.")
    except Exception:
        connection.rollback()
        raise
    finally:
        cursor.close(); connection.close(); source.close()


if __name__ == "__main__":
    main()
