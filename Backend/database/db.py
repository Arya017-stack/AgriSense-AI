from datetime import datetime
import sqlite3
import re 
import hashlib
RECEIPTS_DB = "database/receipts.db"

GOVERNMENT_RATES_DB = "database/government_rates.db"

def get_receipt_connection():
    conn = sqlite3.connect(RECEIPTS_DB)
    conn.row_factory = sqlite3.Row
    return conn

def create_receipts_table():

    conn = get_receipt_connection()
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
    
def create_crop_calendar_table():
    conn = get_rate_connection()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS crop_calendar(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            crop TEXT NOT NULL,
            season TEXT NOT NULL,
            region TEXT NOT NULL,
            start_month INTEGER NOT NULL,
            start_day INTEGER NOT NULL,
            end_month INTEGER NOT NULL,
            end_day INTEGER NOT NULL,
            rain_need TEXT NOT NULL,
            drought_tolerant INTEGER NOT NULL,
            practice_weight INTEGER NOT NULL,
            source TEXT,
            last_verified TEXT
        )
    """)
    conn.commit()
    conn.close()

def seed_crop_calendar():
    conn = get_rate_connection()
    cursor = conn.cursor()

    calendar_data = [
        # crop, season, region, start_month, start_day, end_month, end_day, rain_need, drought_tolerant, practice_weight, source, last_verified
        ("Cotton", "Kharif (Pre-Monsoon)", "Uttarakhand Terai", 5, 1, 5, 31, "medium", 0, 6, "ICAR-CICR", "2026-08-28"),
        ("Bajra", "Kharif", "Uttarakhand Terai", 6, 15, 7, 15, "low-medium", 1, 5, "ICAR-VPKAS", "2026-08-28"),
        ("Maize", "Kharif", "Uttarakhand Terai", 6, 15, 7, 15, "medium", 1, 6, "ICAR-VPKAS", "2026-08-28"),
        ("Rice", "Kharif", "Uttarakhand Terai", 6, 15, 7, 31, "high", 0, 9, "ICAR-VPKAS", "2026-08-28"),
        ("Sugarcane", "Spring Planting", "Uttarakhand Terai", 2, 15, 3, 31, "irrigated", 1, 8, "ICAR-IISR", "2026-08-28"),
        ("Sugarcane", "Autumn Planting", "Uttarakhand Terai", 9, 15, 10, 31, "irrigated", 1, 5, "ICAR-IISR", "2026-08-28"),
        ("Wheat", "Rabi", "Uttarakhand Terai", 10, 25, 12, 15, "low", 1, 9, "ICAR-VPKAS", "2026-08-28"),
    ]

    for crop, season, region, sm, sd, em, ed, rain_need, drought, weight, source, verified in calendar_data:
        cursor.execute("""
            SELECT COUNT(*) FROM crop_calendar
            WHERE crop = ? AND season = ? AND region = ?
        """, (crop, season, region))
        exists = cursor.fetchone()[0]

        if exists == 0:
            cursor.execute("""
                INSERT INTO crop_calendar
                    (crop, season, region, start_month, start_day, end_month, end_day,
                     rain_need, drought_tolerant, practice_weight, source, last_verified)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (crop, season, region, sm, sd, em, ed, rain_need, drought, weight, source, verified))

    conn.commit()
    conn.close()


def get_crop_calendar_entries(region="Uttarakhand Terai"):
    conn = get_rate_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT * FROM crop_calendar WHERE region = ?
    """, (region,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def upgrade_receipts_table():
    conn = get_receipt_connection()
    cursor = conn.cursor()

    new_columns = [
        ("receipt_type", "TEXT DEFAULT 'payment_receipt'"),
        ("delivery_date", "TEXT"),
        ("payment_status", "TEXT DEFAULT 'paid'"),
        ("expected_amount", "REAL"),
        ("quantity_quintals", "REAL"),
        ("is_manual_entry", "INTEGER DEFAULT 0"),
        ("mill_name", "TEXT"),
        ("expected_payment_date", "TEXT"),
        ("days_pending", "INTEGER DEFAULT 0"),
        ("receipt_hash", "TEXT"),
    ]

    for col_name, col_def in new_columns:
        try:
            cursor.execute(f"ALTER TABLE receipts ADD COLUMN {col_name} {col_def}")
        except sqlite3.OperationalError:
            pass  # column already exists, safe to ignore

    conn.commit()
    conn.close()

def save_receipt(receipt_name, crop, amount, payment_mode, date, raw_text,
                  receipt_type="payment_receipt", delivery_date=None,
                  payment_status="paid", expected_amount=None,
                  quantity_quintals=None, is_manual_entry=0, mill_name=None,expected_payment_date=None, days_pending=0, receipt_hash=None):

    conn = get_receipt_connection()
    cursor = conn.cursor()

    cursor.execute("""
            INSERT INTO receipts
            (receipt_name, crop, amount, payment_mode, date, raw_text,
             receipt_type, delivery_date, payment_status, expected_amount,
             quantity_quintals, is_manual_entry, mill_name, expected_payment_date,days_pending, receipt_hash)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                receipt_name, crop, amount, payment_mode, date, raw_text,
                receipt_type, delivery_date, payment_status, expected_amount,
                quantity_quintals, is_manual_entry, mill_name, expected_payment_date,days_pending, receipt_hash
            ))
    conn.commit()
    conn.close()

def get_all_receipts():

    conn = get_receipt_connection()
    cursor = conn.cursor()

    cursor.execute("""
                SELECT *
                FROM receipts
                ORDER BY id DESC 
                """)
    rows = cursor .fetchall()

    conn.close()

    return[dict(row) for row in rows]

def clean_currency_amount(amount_str):
    """Har tarah ke currency string (₹, KES, Rs., INR) ko float mein convert karta hai."""
    if not amount_str or amount_str in ("Not Found", "0", None):
        return 0.0
    cleaned = re.sub(r"(KES|Rs\.?|INR|₹|,)", "", str(amount_str), flags=re.IGNORECASE).strip()
    try:
        return float(cleaned)
    except (ValueError, TypeError):
        return 0.0

def generate_receipt_hash(text):
    if not text:
        return None
    normalized = text.strip().lower()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest() 

#DUPLICATE CHECK KRNE KA FUNCTION 
def is_duplicate_receipt(receipt_hash):
    if not receipt_hash:
        return False
    
    conn = get_receipt_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM receipts WHERE receipt_hash = ?",(receipt_hash,)) 
    count = cursor.fetchone()[0]
    conn.close()
    return count > 0 

    
def get_dashboard_summary():
    conn = get_receipt_connection()
    cursor = conn.cursor()
    summary = {}

    # total receipts
    cursor.execute("SELECT COUNT(*) FROM receipts")
    summary["total_receipts"] = cursor.fetchone()[0]

    # total revenue = sab receipts ke amount ka sum (received money)
    cursor.execute("SELECT amount FROM receipts")
    total_revenue = sum(clean_currency_amount(r["amount"]) for r in cursor.fetchall())
    summary["total_revenue"] = round(total_revenue, 2)

    # pending receipts count
    cursor.execute("SELECT COUNT(*) FROM receipts WHERE payment_status='pending'")
    summary["pending_receipts"] = cursor.fetchone()[0]

    # pending amount = expected - received, sirf pending wale rows ke liye
    cursor.execute("""
        SELECT amount, expected_amount FROM receipts
        WHERE payment_status='pending'
    """)
    pending_total = 0.0
    for row in cursor.fetchall():
        expected = row["expected_amount"] or 0
        received = clean_currency_amount(row["amount"])
        pending_total += max(0, expected - received)
    summary["pending_amount"] = round(pending_total, 2)

    # total underpayment across all receipts

    cursor.execute("""
        SELECT amount, expected_amount FROM receipts
        WHERE expected_amount IS NOT NULL
    """)
    underpaid_total = 0.0
    underpaid_count = 0
    for row in cursor.fetchall():
        expected = row["expected_amount"]
        raw_amount = row["amount"]
        if expected is None or not raw_amount or raw_amount == "Not Found":
            continue
        received = clean_currency_amount(raw_amount)
        difference = expected - received
        if difference > 100:
            underpaid_total += difference
            underpaid_count += 1
    summary["underpayment_total"] = round(underpaid_total, 2)
    summary["underpaid_receipts"] = underpaid_count


    # latest payment
    cursor.execute("SELECT payment_mode, date FROM receipts ORDER BY id DESC LIMIT 1")
    latest = cursor.fetchone()
    summary["latest_payment"] = latest["payment_mode"] if latest else "N/A"
    summary["latest_date"] = latest["date"] if latest else "N/A"

    conn.close()
    return summary

# ==========================================
#   GOVERNMENT_RATE_DATABASE 
# ==========================================

def get_rate_connection():

    conn = sqlite3.connect(GOVERNMENT_RATES_DB)
    conn.row_factory = sqlite3.Row
    return conn 

def create_rates_table():

    conn = get_rate_connection()

    cursor = conn.cursor()

    cursor.execute(""" 
        CREATE TABLE IF NOT EXISTS crop_rates(
                   id INTEGER PRIMARY KEY AUTOINCREMENT,
                   
                   crop TEXT NOT NULL,

                   state TEXT NOT NULL,

                   rate_type TEXT NOT NULL,

                   rate_per_quintal REAL NOT NULL,

                   marketing_year TEXT NOT NULL,

                   source_url TEXT,
                   
                   last_verified TEXT
            )
    """)

    conn.commit()
    conn.close()
     

def create_forecast_log_table():
    conn = get_rate_connection()
    cursor = conn.cursor()
    cursor.execute(""" 
        CREATE TABLE IF NOT EXISTS weather_forecast_log(
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    DISTRICT TEXT,
                    forecast_made_on TEXT,
                    target_date TEXT,
                    predicted_temp REAL,
                    predicted_humidity REAL,
                    predicted_rain_pct REAL,
                    actual_temp REAL,
                    actual_humidity REAL,
                    actual_rain_pct REAL,
                    is_validated INTEGER DEFAULT 0)
        """)
    conn.commit()
    conn.close()



def save_forecast(district, target_date, predicted_temp, predicted_humidity, predicted_rain_pct):
    from datetime import datetime 
    conn = get_rate_connection()
    cursor = conn.cursor() 
    today = datetime.now().strftime("%Y-%m-%d")

    cursor.execute(""" 
        SELECT COUNT(*) FROM weather_forecast_log
        WHERE district = ? AND target_date = ? 
        """, (district,target_date)) 
    exists = cursor.fetchone()[0]
    if exists == 0:
        cursor.execute("""
            INSERT INTO weather_forecast_log
                (district, forecast_made_on, target_date, predicted_temp, predicted_humidity, predicted_rain_pct)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (district, today, target_date, predicted_temp, predicted_humidity, predicted_rain_pct))
        conn.commit()
    conn.close()



def validate_pending_forecasts(district, actual_temp, actual_humidity, actual_rain_pct):
    conn = get_rate_connection()
    cursor =conn.cursor()
    today = datetime.now().strftime("%Y-%m-%d")
    cursor.execute(
        """
        UPDATE weather_forecast_log
        SET actual_temp = ?, actual_humidity = ?, actual_rain_pct = ?, is_validated = 1
        WHERE district = ? AND target_date = ? AND is_validated = 0
    """, (actual_temp, actual_humidity, actual_rain_pct, district, today))
    conn.commit()
    conn.close()



def get_forecast_accuracy(district=None, days=7):
    conn  = get_rate_connection()
    cursor = conn.cursor()
    if district:
        cursor.execute(
            """
            SELECT predicted_temp, actual_temp, predicted_humidity, actual_humidity
            FROM weather_forecast_log
            WHERE is_validated = 1 AND district = ?
            ORDER BY target_date DESC LIMIT ?
        """, (district, days))
    else:
        cursor.execute("""
            SELECT predicted_temp, actual_temp, predicted_humidity, actual_humidity
            FROM weather_forecast_log
            WHERE is_validated = 1
            ORDER BY target_date DESC LIMIT ?
        """, (days,))
    rows = cursor.fetchall()
    conn.close()

    if not rows:
        return None

    temp_errors = [abs(row["predicted_temp"] - row["actual_temp"]) for row in rows if row["actual_temp"] is not None]
    humidity_errors = [abs(row["predicted_humidity"] - row["actual_humidity"]) for row in rows if row["actual_humidity"] is not None]

    mae_temp = round(sum(temp_errors) / len(temp_errors), 2) if temp_errors else None
    mae_humidity = round(sum(humidity_errors) / len(humidity_errors), 2) if humidity_errors else None

    return{
        "sample_size": len(rows),
        "mae_temp": mae_temp,
        "mae_humidity": mae_humidity
    }


def seed_rates():

    conn = get_rate_connection()
    cursor = conn.cursor()

    all_rates = [
        ("Sugarcane", "Uttarakhand", "FRP", 355.0, "2025-26", "https://cacp.dacnet.nic.in", "2026-07-20"),
        ("Sugarcane", "Uttar Pradesh", "SAP", 370.0, "2025-26", "https://caneup.in", "2026-07-20"),

        ("Rice", "Uttar Pradesh", "MSP", 2369.0, "2025-26", "https://cacp.dacnet.nic.in", "2026-08-21"),
        ("Rice", "Uttarakhand", "MSP", 2369.0, "2025-26", "https://cacp.dacnet.nic.in", "2026-08-21"),
        ("Rice", "Punjab", "MSP", 2369.0, "2025-26", "https://cacp.dacnet.nic.in", "2026-08-21"),
        ("Rice", "Maharashtra", "MSP", 2369.0, "2025-26", "https://cacp.dacnet.nic.in", "2026-08-21"),
        ("Rice", "Karnataka", "MSP", 2369.0, "2025-26", "https://cacp.dacnet.nic.in", "2026-08-21"),

        ("Wheat", "Uttar Pradesh", "MSP", 2425.0, "2025-26", "https://cacp.dacnet.nic.in", "2026-08-21"),
        ("Wheat", "Uttarakhand", "MSP", 2425.0, "2025-26", "https://cacp.dacnet.nic.in", "2026-08-21"),
        ("Wheat", "Punjab", "MSP", 2425.0, "2025-26", "https://cacp.dacnet.nic.in", "2026-08-21"),
        ("Wheat", "Maharashtra", "MSP", 2425.0, "2025-26", "https://cacp.dacnet.nic.in", "2026-08-21"),
        ("Wheat", "Karnataka", "MSP", 2425.0, "2025-26", "https://cacp.dacnet.nic.in", "2026-08-21"),

        ("Maize", "Uttar Pradesh", "MSP", 2400.0, "2025-26", "https://cacp.dacnet.nic.in", "2026-08-21"),
        ("Maize", "Uttarakhand", "MSP", 2400.0, "2025-26", "https://cacp.dacnet.nic.in", "2026-08-21"),
        ("Maize", "Punjab", "MSP", 2400.0, "2025-26", "https://cacp.dacnet.nic.in", "2026-08-21"),
        ("Maize", "Maharashtra", "MSP", 2400.0, "2025-26", "https://cacp.dacnet.nic.in", "2026-08-21"),
        ("Maize", "Karnataka", "MSP", 2400.0, "2025-26", "https://cacp.dacnet.nic.in", "2026-08-21"),

        ("Bajra", "Uttar Pradesh", "MSP", 2775.0, "2025-26", "https://cacp.dacnet.nic.in", "2026-08-21"),
        ("Bajra", "Uttarakhand", "MSP", 2775.0, "2025-26", "https://cacp.dacnet.nic.in", "2026-08-21"),
        ("Bajra", "Punjab", "MSP", 2775.0, "2025-26", "https://cacp.dacnet.nic.in", "2026-08-21"),
        ("Bajra", "Maharashtra", "MSP", 2775.0, "2025-26", "https://cacp.dacnet.nic.in", "2026-08-21"),
        ("Bajra", "Karnataka", "MSP", 2775.0, "2025-26", "https://cacp.dacnet.nic.in", "2026-08-21"),

        ("Cotton", "Uttar Pradesh", "MSP", 7710.0, "2025-26", "https://cotcorp.org.in", "2026-08-21"),
        ("Cotton", "Uttarakhand", "MSP", 7710.0, "2025-26", "https://cotcorp.org.in", "2026-08-21"),
        ("Cotton", "Punjab", "MSP", 7710.0, "2025-26", "https://cotcorp.org.in", "2026-08-21"),
        ("Cotton", "Maharashtra", "MSP", 7710.0, "2025-26", "https://cotcorp.org.in", "2026-08-21"),
        ("Cotton", "Karnataka", "MSP", 7710.0, "2025-26", "https://cotcorp.org.in", "2026-08-21"),
    ]

    for crop, state, rate_type, rate, year, source, verified in all_rates:

        cursor.execute("""
            SELECT COUNT(*) FROM crop_rates
            WHERE crop = ? AND state = ? AND marketing_year = ?
        """, (crop, state, year))

        exists = cursor.fetchone()[0]

        if exists == 0:
            cursor.execute("""
                INSERT INTO crop_rates
                    (crop, state, rate_type, rate_per_quintal, marketing_year, source_url, last_verified)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (crop, state, rate_type, rate, year, source, verified))

    conn.commit()
    conn.close()

def get_rate(crop, state):
    conn = get_rate_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT *
                FROM crop_rates
                WHERE crop = ?
                AND state = ?
                ORDER BY marketing_year DESC
                LIMIT 1
    """, (crop, state))

    row = cursor.fetchone()

    conn.close()

    if row:
        return dict(row)
    
    return None


    
def find_matching_delivery(crop, quantity_quintals):
    conn = get_receipt_connection()
    cursor = conn.cursor()

    cursor.execute("""
                   
            SELECT *
            FROM receipts 
            WHERE receipt_type = 'manual_delivery'
                AND payment_status = 'pending'
                AND crop = ?
            ORDER BY id DESC
       """, (crop,))
    rows =cursor.fetchall()
    conn.close()

    for row in rows:
        try:
            saved_qty = row["quantity_quintals"] or 0 

            if abs(saved_qty - quantity_quintals) <= 0.5:
                return dict(row)
        except Exception:
                pass
    return None


def mark_delivery_paid(receipt_id):
    conn = get_receipt_connection()
    cursor = conn.cursor()

    cursor.execute("""
                UPDATE receipts
                SET payment_status ='paid',
                   days_pending = 0 
                WHERE id=?
                
    """, (receipt_id,))

    conn.commit() 
    conn.close()