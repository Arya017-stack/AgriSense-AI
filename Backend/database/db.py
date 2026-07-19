import sqlite3

DB_NAME = "database.db"

def get_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def create_table():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
                    
    CREATE TABLE IF NOT EXISTS receipts(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        receipt_name TEXT,
        crop TEXT,
        amount TEXT,
        payment_mode TEXT,
        date TEXT,
        raw_text TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )  
""")
    conn.commit()
    conn.close()
    
def save_receipt(receipt_name, crop, amount, payment_mode, date, raw_text):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
            INSERT INTO receipts
            (receipt_name, crop, amount, payment_mode, date, raw_text)
            VALUES (?, ?, ?, ?, ?, ?)
            """,(
                receipt_name,
                crop,
                amount,
                payment_mode,
                date,
                raw_text,
            ))
    conn.commit()
    conn.close()
def get_all_receipts():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
                SELECT *
                FROM receipts
                ORDER BY id DESC 
                """)
    rows = cursor .fetchall()

    conn.close()

    return[dict(row) for row in rows]

def get_dashboard_summary():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            COUNT(*) AS total_receipts,
            COALESCE(
                SUM(
                    CAST(
                        REPLACE(
                            REPLACE(
                                REPLACE(amount,'KES ',''),
                                '₹',''
                            ),
                            ',',''
                        ) AS REAL
                    )
            ),0)AS total_revenue  
        FROM receipts
    """)
    summary = dict(cursor.fetchone())

    cursor.execute("""
        SELECT payment_mode, date
            FROM receipts
            ORDER BY id DESC
            LIMIT 1
    """)

    latest = cursor.fetchone()

    if latest:
        summary["latest_payment"] = latest["payment_mode"]
        summary["latest_date"] = latest["date"]
    else:
        summary["latest_payment"] ="N/A"
        summary["latest_date"] = "N/A"
    
    conn.close()

    return summary