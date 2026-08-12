import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import uuid4

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _resolve_db_path() -> Path:
    if os.getenv("DATABASE_PATH"):
        return Path(os.getenv("DATABASE_PATH"))

    if os.getenv("RAILWAY_ENVIRONMENT") or os.getenv("RAILWAY_VOLUME_MOUNT_PATH"):
        return Path("/data/cropeazy.db")

    if os.getenv("VERCEL") or os.getenv("VERCEL_ENV"):
        return Path("/tmp/cropeazy.db")

    return PROJECT_ROOT / "data" / "cropeazy.db"


DB_PATH = _resolve_db_path()


def init_db() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with get_connection() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                phone TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS otps (
                phone TEXT PRIMARY KEY,
                code TEXT NOT NULL,
                expires_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS dashboard_records (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                crop TEXT NOT NULL,
                region TEXT,
                production_tonnes REAL NOT NULL,
                revenue REAL NOT NULL,
                costs REAL NOT NULL,
                profit REAL NOT NULL,
                margin REAL NOT NULL,
                data_json TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id)
            );

            CREATE TABLE IF NOT EXISTS alert_subscriptions (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                crop TEXT NOT NULL,
                latitude REAL,
                longitude REAL,
                active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id)
            );

            CREATE TABLE IF NOT EXISTS alert_logs (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                message TEXT NOT NULL,
                alert_type TEXT NOT NULL,
                sent_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id)
            );
            """
        )


@contextmanager
def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def get_user_by_phone(phone: str) -> Optional[Dict[str, Any]]:
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM users WHERE phone = ?", (phone,)).fetchone()
        return dict(row) if row else None


def get_user_by_id(user_id: str) -> Optional[Dict[str, Any]]:
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        return dict(row) if row else None


def create_user(phone: str, name: str) -> Dict[str, Any]:
    user = {
        "id": str(uuid4()),
        "phone": phone,
        "name": name.strip() or "Farmer",
        "created_at": utc_now_iso(),
    }
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO users (id, phone, name, created_at) VALUES (?, ?, ?, ?)",
            (user["id"], user["phone"], user["name"], user["created_at"]),
        )
    return user


def save_otp(phone: str, code: str, expires_at: str) -> None:
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO otps (phone, code, expires_at) VALUES (?, ?, ?)
            ON CONFLICT(phone) DO UPDATE SET code = excluded.code, expires_at = excluded.expires_at
            """,
            (phone, code, expires_at),
        )


def get_otp(phone: str) -> Optional[Dict[str, Any]]:
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM otps WHERE phone = ?", (phone,)).fetchone()
        return dict(row) if row else None


def delete_otp(phone: str) -> None:
    with get_connection() as conn:
        conn.execute("DELETE FROM otps WHERE phone = ?", (phone,))


def add_dashboard_record(user_id: str, record: Dict[str, Any]) -> Dict[str, Any]:
    record_id = str(uuid4())
    created_at = utc_now_iso()
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO dashboard_records
            (id, user_id, crop, region, production_tonnes, revenue, costs, profit, margin, data_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record_id,
                user_id,
                record["crop"],
                record.get("region", ""),
                record["production_tonnes"],
                record["revenue"],
                record["costs"],
                record["profit"],
                record["margin"],
                json.dumps(record.get("data_json", {})),
                created_at,
            ),
        )
    return {**record, "id": record_id, "created_at": created_at}


def list_dashboard_records(user_id: str, limit: int = 50) -> List[Dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT * FROM dashboard_records
            WHERE user_id = ?
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (user_id, limit),
        ).fetchall()
    return [dict(row) for row in rows]


def clear_dashboard_records(user_id: str) -> None:
    with get_connection() as conn:
        conn.execute("DELETE FROM dashboard_records WHERE user_id = ?", (user_id,))


def upsert_alert_subscription(
    user_id: str,
    crop: str,
    latitude: Optional[float],
    longitude: Optional[float],
) -> Dict[str, Any]:
    sub_id = str(uuid4())
    created_at = utc_now_iso()

    with get_connection() as conn:
        conn.execute(
            "UPDATE alert_subscriptions SET active = 0 WHERE user_id = ?",
            (user_id,),
        )
        conn.execute(
            """
            INSERT INTO alert_subscriptions (id, user_id, crop, latitude, longitude, active, created_at)
            VALUES (?, ?, ?, ?, ?, 1, ?)
            """,
            (sub_id, user_id, crop, latitude, longitude, created_at),
        )

    return {
        "id": sub_id,
        "user_id": user_id,
        "crop": crop,
        "latitude": latitude,
        "longitude": longitude,
        "active": True,
        "created_at": created_at,
    }


def get_alert_subscription(user_id: str) -> Optional[Dict[str, Any]]:
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT * FROM alert_subscriptions
            WHERE user_id = ? AND active = 1
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (user_id,),
        ).fetchone()
    return dict(row) if row else None


def add_alert_log(user_id: str, message: str, alert_type: str) -> None:
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO alert_logs (id, user_id, message, alert_type, sent_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (str(uuid4()), user_id, message, alert_type, utc_now_iso()),
        )


def list_alert_logs(user_id: str, limit: int = 20) -> List[Dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT * FROM alert_logs
            WHERE user_id = ?
            ORDER BY sent_at DESC
            LIMIT ?
            """,
            (user_id, limit),
        ).fetchall()
    return [dict(row) for row in rows]
