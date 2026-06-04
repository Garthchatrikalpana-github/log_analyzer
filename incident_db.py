"""
Incident Database - SQLite-based ServiceNow simulation
"""
import sqlite3
import os
from datetime import datetime

DB_PATH = "data/incidents.db"


def get_connection():
    os.makedirs("data", exist_ok=True)
    return sqlite3.connect(DB_PATH)


def create_database():
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS incidents (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            incident_number TEXT UNIQUE NOT NULL,
            application_name TEXT NOT NULL,
            error_description TEXT NOT NULL,
            user_id         TEXT NOT NULL,
            status          TEXT DEFAULT 'active',
            created_time    TEXT NOT NULL,
            updated_time    TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()


def insert_sample_records():
    conn = get_connection()
    c = conn.cursor()
    samples = [
        (
            "INC001",
            "mini-commerce",
            "InsufficientStockException: Product SKU-442 is out of stock, cannot fulfill order ORD-9981",
            "42",
            "active",
            "2024-01-15 08:12:07",
            "2024-01-15 08:12:09",
        ),
        (
            "INC002",
            "mini-commerce",
            "NullPointerException: User profile data is null for user_id=78 in UserRepository.getUserProfile",
            "78",
            "active",
            "2024-01-15 10:45:04",
            "2024-01-15 10:45:06",
        ),
        (
            "INC003",
            "mini-commerce",
            "ConnectionTimeoutException: Unable to acquire DB connection after 30000ms - pool exhausted",
            "15",
            "inactive",
            "2024-01-16 14:22:14",
            "2024-01-16 14:22:16",
        ),
    ]
    for s in samples:
        try:
            c.execute(
                """INSERT INTO incidents
                   (incident_number, application_name, error_description, user_id, status, created_time, updated_time)
                   VALUES (?,?,?,?,?,?,?)""",
                s,
            )
        except sqlite3.IntegrityError:
            pass  # already inserted
    conn.commit()
    conn.close()


def get_incident(incident_number: str):
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM incidents WHERE incident_number = ?", (incident_number.upper(),))
    row = c.fetchone()
    conn.close()
    if row:
        return dict(row)
    return None


def list_incidents():
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM incidents ORDER BY created_time DESC")
    rows = c.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def create_incident(
    incident_number: str,
    application_name: str,
    error_description: str,
    user_id: str,
    status: str = "active"
):
    conn = get_connection()
    c = conn.cursor()

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    try:
        c.execute(
            """
            INSERT INTO incidents
            (incident_number, application_name, error_description, user_id, status, created_time, updated_time)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                incident_number.upper(),
                application_name,
                error_description,
                user_id,
                status,
                now,
                now
            )
        )
        conn.commit()
        return {"success": True, "message": "Incident created successfully"}

    except sqlite3.IntegrityError:
        return {"success": False, "message": "Incident already exists"}

    finally:
        conn.close()
# Bootstrap on import
create_database()
insert_sample_records()