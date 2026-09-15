"""Perform one bounded, read-only connection check against InternMate Oracle ATP."""
import os
from pathlib import Path

import oracledb


ROOT = Path(__file__).resolve().parent
for line in (ROOT / ".env").read_text(encoding="utf-8").splitlines():
    if "=" in line and not line.lstrip().startswith("#"):
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())

wallet = os.environ["INTERNMATE_ORACLE_WALLET_DIR"]
dsn = (
    "(DESCRIPTION=(RETRY_COUNT=1)(RETRY_DELAY=0)(CONNECT_TIMEOUT=15)"
    "(TRANSPORT_CONNECT_TIMEOUT=10)(ADDRESS=(PROTOCOL=TCPS)"
    "(HOST=adb.ap-hyderabad-1.oraclecloud.com)(PORT=1522))"
    "(CONNECT_DATA=(SERVICE_NAME=g9294bf6df9f826_tecpdatp01_medium.adb.oraclecloud.com))"
    "(SECURITY=(SSL_SERVER_DN_MATCH=YES)))"
)
connection = oracledb.connect(
    user=os.environ.get("INTERNMATE_ORACLE_USER", "LEARNING"),
    password=os.environ["INTERNMATE_ORACLE_PASSWORD"],
    dsn=dsn,
    config_dir=wallet,
    wallet_location=wallet,
)
try:
    with connection.cursor() as cursor:
        cursor.execute("SELECT 1 FROM dual")
        print("ATP connection verified:", cursor.fetchone()[0])
finally:
    connection.close()
