"""
Backend module: database connection, schema, and business logic.
No Flask here — only MySQL and pure Python. Used by app.py (Flask routes).

Online validation model: all pass data is in MySQL; NFC card is only an identifier.
"""

import mysql.connector
from mysql.connector import Error

# ---------------------------------------------------------------------------
# Database configuration
# ---------------------------------------------------------------------------
DB_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "your_password",
    "database": "noq_bus_pass",
}

DB_CONFIG_NO_DB = {
    "host": DB_CONFIG["host"],
    "user": DB_CONFIG["user"],
    "password": DB_CONFIG["password"],
}


def get_db_connection():
    """Create and return a new MySQL connection using mysql.connector."""
    return mysql.connector.connect(**DB_CONFIG)


def get_trips_for_plan(plan_type: str) -> int:
    """Map plan type to number of trips. WEEKLY=14, MONTHLY=60, 3MONTH=180."""
    plan_type = (plan_type or "").upper()
    if plan_type == "WEEKLY":
        return 14
    if plan_type == "MONTHLY":
        return 60
    if plan_type == "3MONTH":
        return 180
    return 0


# ---------------------------------------------------------------------------
# Database init: create database, table (with activationCode), and 5 sample rows
# ---------------------------------------------------------------------------
def init_db():
    """
    Create database and table if they don't exist; add activationCode column
    if missing; insert 5 sample rows when table is empty.
    """
    conn = None
    try:
        conn = mysql.connector.connect(**DB_CONFIG_NO_DB)
        cursor = conn.cursor()
        cursor.execute("CREATE DATABASE IF NOT EXISTS noq_bus_pass")
        cursor.close()
        conn.close()
    except Error as e:
        print("Init DB (create database):", e)
        if conn:
            try:
                conn.close()
            except Exception:
                pass
        return

    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS cards (
                cardNumber     VARCHAR(64)  PRIMARY KEY,
                holderName     VARCHAR(100),
                mobileNumber   VARCHAR(20),
                passStatus     VARCHAR(20),
                planType       VARCHAR(20),
                tripsUsed      INT DEFAULT 0,
                remainingTrips INT DEFAULT 0,
                activationCode VARCHAR(32) DEFAULT NULL
            )
        """)

        # Add activationCode column if table existed without it (e.g. old schema)
        try:
            cursor.execute("ALTER TABLE cards ADD COLUMN activationCode VARCHAR(32) DEFAULT NULL")
        except Error as e:
            if "Duplicate column" not in str(e):
                raise

        cursor.execute("SELECT COUNT(*) FROM cards")
        count = cursor.fetchone()[0]
        if count == 0:
            # 4-digit activation codes stored in database (used for top-up validation)
            sample_rows = [
                ("1234 5678 9012 345", "Piyush Mahalle", "9876543210", "ACTIVE", "MONTHLY", 24, 36, "4582"),
                ("1111 2222 3333 4444", "Rahul Sharma", "9123456789", "ACTIVE", "WEEKLY", 5, 9, "1234"),
                ("5555 6666 7777 8888", "Priya Patel", "9988776655", "ACTIVE", "MONTHLY", 0, 60, "5678"),
                ("9999 0000 1111 2222", "Amit Kumar", "9876512345", "DISCONTINUED", "WEEKLY", 14, 0, "9012"),
                ("3333 4444 5555 6666", "Sneha Singh", "9765432109", "ACTIVE", "WEEKLY", 2, 12, "3456"),
            ]
            cursor.executemany(
                """
                INSERT INTO cards (cardNumber, holderName, mobileNumber, passStatus, planType, tripsUsed, remainingTrips, activationCode)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                sample_rows,
            )
            conn.commit()
            print("Inserted 5 sample rows into cards table.")

        cursor.close()
        conn.close()
    except Error as e:
        print("Init DB (table/seed):", e)
        if conn:
            try:
                conn.close()
            except Exception:
                pass


# ---------------------------------------------------------------------------
# Business logic: get card by mobile (for login)
# ---------------------------------------------------------------------------
def get_card_by_mobile(mobile):
    """Return first card row for this mobileNumber, or None if not registered."""
    if not mobile or not str(mobile).strip():
        return None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM cards WHERE mobileNumber = %s LIMIT 1", (str(mobile).strip(),))
        row = cursor.fetchone()
        cursor.close()
        conn.close()
        return dict(row) if row else None
    except Error:
        return None


# ---------------------------------------------------------------------------
# Business logic: login — mobile must be in database; OTP simulated
# ---------------------------------------------------------------------------
def do_login(mobile, otp=None):
    """
    Login is based on phone number in database.
    - If only mobile is sent (send OTP step): check if mobile exists in cards;
      return { "registered": True } or { "registered": False, "message": "..." }.
    - If mobile + otp: verify mobile in DB; OTP is simulated (any value accepted).
      Return { "status": "success", "mobile": ..., "card": {...} } or error.
    """
    mobile = (mobile or "").strip()
    if not mobile:
        return {"registered": False, "message": "Mobile number required"}

    card = get_card_by_mobile(mobile)
    if card is None:
        return {"registered": False, "message": "Mobile not registered"}

    # Send OTP step: only mobile was sent
    if otp is None:
        return {"registered": True, "message": "OTP will be sent to your registered number"}

   # Verify OTP step
    if otp != "123456":
     return {
    "status": "success",
    "message": "Login successful",
    "mobile": mobile,
    "card": card,
    }


# ---------------------------------------------------------------------------
# Business logic: topup
# ---------------------------------------------------------------------------
def do_topup(card_number, holder_name, mobile_number, plan_type, activation_code=None):
    """
    Activate or renew pass. If card missing -> INSERT; else if not discontinued -> UPDATE.
    For existing cards, the 4-digit activation code must match the one stored in the database.
    Returns {"status": "success", "card": row} or {"status": "error", "message": "..."}.
    """
    if not card_number or not plan_type:
        return {"status": "error", "message": "cardNumber and planType are required"}
    trips = get_trips_for_plan(plan_type)
    if trips <= 0:
        return {"status": "error", "message": "Invalid planType"}

    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM cards WHERE cardNumber = %s", (card_number,))
        existing = cursor.fetchone()

        if existing is None:
            # New card: store the provided 4-digit activation code in database
            cursor.execute(
                """
                INSERT INTO cards
                    (cardNumber, holderName, mobileNumber, passStatus, planType, tripsUsed, remainingTrips, activationCode)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (card_number, holder_name, mobile_number, "ACTIVE", plan_type, 0, trips, activation_code),
            )
        else:
            if existing.get("passStatus") == "DISCONTINUED":
                cursor.close()
                conn.close()
                return {"status": "error", "message": "Card is discontinued and cannot be topped up."}
            # Existing card: 4-digit activation code must match the one in database
            db_code = (existing.get("activationCode") or "").strip()
            if db_code and (not activation_code or (activation_code or "").strip() != db_code):
                cursor.close()
                conn.close()
                return {"status": "error", "message": "Invalid activation code. Use the 4-digit code from database."}
            cursor.execute(
                """
                UPDATE cards
                SET holderName = %s, mobileNumber = %s, planType = %s, passStatus = 'ACTIVE',
                    tripsUsed = 0, remainingTrips = %s, activationCode = COALESCE(%s, activationCode)
                WHERE cardNumber = %s
                """,
                (holder_name, mobile_number, plan_type, trips, activation_code, card_number),
            )

        conn.commit()
        cursor.execute("SELECT * FROM cards WHERE cardNumber = %s", (card_number,))
        row = cursor.fetchone()
        cursor.close()
        conn.close()
        return {"status": "success", "card": row}
    except Error as e:
        return {"status": "error", "message": str(e)}


# ---------------------------------------------------------------------------
# Business logic: status
# ---------------------------------------------------------------------------
def get_status(card_number):
    """
    Return card status as dict. If not found, passStatus = "NONE".
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM cards WHERE cardNumber = %s", (card_number,))
        row = cursor.fetchone()
        cursor.close()
        conn.close()
        if row is None:
            return {
                "cardNumber": card_number,
                "holderName": None,
                "mobileNumber": None,
                "passStatus": "NONE",
                "planType": None,
                "tripsUsed": 0,
                "remainingTrips": 0,
                "activationCode": None,
            }
        return dict(row)
    except Error as e:
        return {"status": "error", "message": str(e)}


# ---------------------------------------------------------------------------
# Business logic: validate (no trip deduction)
# ---------------------------------------------------------------------------
def validate_card(card_number):
    """Check if card is valid for travel. Returns {"result": "VALID"} or {"result": "INVALID", "reason": "..."}."""
    if not card_number:
        return {"status": "error", "message": "cardNumber is required"}
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT passStatus, remainingTrips FROM cards WHERE cardNumber = %s", (card_number,))
        row = cursor.fetchone()
        cursor.close()
        conn.close()
        if row is None:
            return {"result": "INVALID", "reason": "No pass found"}
        if row["passStatus"] != "ACTIVE":
            return {"result": "INVALID", "reason": "Card not active"}
        if row["remainingTrips"] <= 0:
            return {"result": "INVALID", "reason": "No trips remaining"}
        return {"result": "VALID"}
    except Error as e:
        return {"status": "error", "message": str(e)}


# ---------------------------------------------------------------------------
# Business logic: use one trip
# ---------------------------------------------------------------------------
def use_trip(card_number):
    """
    Deduct one trip. Returns {"status": "success", "card": row} or {"status": "error", "message": "..."}.
    """
    if not card_number:
        return {"status": "error", "message": "cardNumber is required"}
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT passStatus, remainingTrips FROM cards WHERE cardNumber = %s", (card_number,))
        row = cursor.fetchone()
        if row is None:
            cursor.close()
            conn.close()
            return {"status": "error", "message": "No pass found"}
        if row["passStatus"] != "ACTIVE":
            cursor.close()
            conn.close()
            return {"status": "error", "message": "Card is not active"}
        if row["remainingTrips"] <= 0:
            cursor.close()
            conn.close()
            return {"status": "error", "message": "No trips remaining"}

        cursor.execute(
            """
            UPDATE cards
            SET remainingTrips = remainingTrips - 1, tripsUsed = tripsUsed + 1
            WHERE cardNumber = %s AND passStatus = 'ACTIVE' AND remainingTrips > 0
            """,
            (card_number,),
        )
        if cursor.rowcount == 0:
            cursor.close()
            conn.close()
            return {"status": "error", "message": "Trip could not be used"}
        conn.commit()
        cursor.execute("SELECT * FROM cards WHERE cardNumber = %s", (card_number,))
        updated = cursor.fetchone()
        cursor.close()
        conn.close()
        return {"status": "success", "card": updated}
    except Error as e:
        return {"status": "error", "message": str(e)}


# ---------------------------------------------------------------------------
# Business logic: discontinue card
# ---------------------------------------------------------------------------
def discontinue_card(card_number):
    """Mark card as DISCONTINUED. Returns {"status": "success"} or {"status": "error", "message": "..."}."""
    if not card_number:
        return {"status": "error", "message": "cardNumber is required"}
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE cards SET passStatus = 'DISCONTINUED' WHERE cardNumber = %s", (card_number,))
        conn.commit()
        cursor.close()
        conn.close()
        return {"status": "success", "message": "Card discontinued"}
    except Error as e:
        return {"status": "error", "message": str(e)}
