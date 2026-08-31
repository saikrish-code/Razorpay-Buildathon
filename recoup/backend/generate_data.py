#!/usr/bin/env python3
"""
generate_data.py
----------------
Generates 250 realistic synthetic payment failure / abandonment records for Recoup.
Inserts records into the SQLite database (`recoup.db`) and prints a comprehensive
statistical summary of the generated dataset distribution.

Dataset Characteristics:
- Total records: 250
- Three Types:
    1. one_time_checkout (~48%, 120 records)
    2. subscription_renewal (~32%, 80 records)
    3. checkout_abandonment (~20%, 50 records)
- Realistic failure reasons:
    - Recoverable: insufficient_funds, card_expired, bank_timeout, network_error,
                   wrong_otp, daily_limit_exceeded, customer_abandoned
    - Permanently Unrecoverable: account_closed (>= 15% guaranteed, set to exactly 16% / 40 records)
- Amounts: INR Rs. 199 to Rs. 15,000 with realistic pricing patterns
- Contact attempts: 0
- Status: 'open'
- Customer channels: WhatsApp (~58%), SMS (~27%), Email (~15%)
- Timestamps: Spread across the last 30 days
"""

from __future__ import annotations

import datetime
import os
import random
import sqlite3
import string
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

# Ensure stdout and stderr support UTF-8 on Windows
if sys.platform == "win32":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")


# ── Configuration & Paths ──────────────────────────────────────────────────────

def find_db_path() -> Path:
    """Resolve the SQLite database path regardless of where the script is executed."""
    cwd = Path.cwd()
    script_dir = Path(__file__).resolve().parent

    candidates = [
        script_dir / "recoup.db",
        cwd / "recoup.db",
        cwd / "backend" / "recoup.db",
        cwd / "recoup" / "backend" / "recoup.db",
        script_dir.parent / "recoup.db",
    ]

    for candidate in candidates:
        if candidate.exists():
            return candidate

    # Default fallback: beside script if in backend, or backend/recoup.db
    if (script_dir / "app").exists():
        return script_dir / "recoup.db"
    return script_dir / "backend" / "recoup.db"


# ── Sample Customer & Context Data Pools ───────────────────────────────────────

FIRST_NAMES = [
    "Aarav", "Vivaan", "Aditya", "Vihaan", "Arjun", "Sai", "Reyansh", "Aadhya",
    "Diya", "Ananya", "Pari", "Saanvi", "Myra", "Rohan", "Vikram", "Priya",
    "Sneha", "Neha", "Rahul", "Pooja", "Amit", "Anjali", "Karthik", "Divya",
    "Meera", "Ishaan", "Riya", "Varun", "Tanvi", "Sanjay", "Sunita", "Rajesh",
    "Kavita", "Suresh", "Deepak", "Swati", "Nikhil", "Ritu", "Manish", "Shilpa",
    "Gaurav", "Shruti", "Alok", "Shreya", "Harish", "Preeti", "Abhishek", "Pallavi",
    "Siddharth", "Natasha"
]

LAST_NAMES = [
    "Sharma", "Verma", "Patel", "Reddy", "Iyer", "Nair", "Gupta", "Singh",
    "Kumar", "Rao", "Joshi", "Mehta", "Das", "Chatterjee", "Banerjee", "Mukherjee",
    "Shah", "Bhat", "Deshmukh", "Kulkarni", "Pillai", "Menon", "Choudhury", "Agarwal",
    "Kapoor", "Malhotra", "Sengupta", "Trivedi", "Nambiar", "Hegde"
]

EMAIL_DOMAINS = [
    "gmail.com", "yahoo.in", "outlook.com", "icloud.com", "proton.me", "techcorp.in", "zmail.com"
]

ONE_TIME_ITEMS = [
    ("Sony WH-1000XM5 Noise Cancelling Headphones", 14999.00),
    ("Mechanical Wireless Keyboard RGB", 4499.00),
    ("Ergonomic Mesh Office Chair", 8999.00),
    ("Python & AI System Design Masterclass", 2499.00),
    ("Apple 20W USB-C Power Adapter", 1899.00),
    ("Nike Air Zoom Pegasus 40 Running Shoes", 7995.00),
    ("Smart LED Monitor 27-inch 4K", 13499.00),
    ("Flight Ticket Booking DEL -> BLR", 5840.00),
    ("Luxury Cotton Bedding Set King Size", 3299.00),
    ("Espresso Coffee Machine & Grinder", 11250.00),
    ("Fastrack Smartwatch Reflex Play", 2999.00),
    ("Kindle Paperwhite 16GB Edition", 9999.00),
    ("Boat Airdopes 441 Bluetooth Earbuds", 1499.00),
    ("Logitech MX Master 3S Wireless Mouse", 6995.00),
    ("Minimalist Leather Travel Backpack", 3890.00),
    ("Instant Pot 7-in-1 Duo Electric Cooker", 6499.00),
    ("Noise ColorFit Pro 4 Smartwatch", 2199.00),
    ("Anker 65W GaN Fast Wall Charger", 2799.00),
    ("Microphone Arm & Pop Filter Studio Kit", 1850.00),
    ("Sennheiser HD 450SE Wireless Headset", 7490.00),
]

SUBSCRIPTION_ITEMS = [
    ("Pro Tier Monthly Cloud Subscription", 699.00),
    ("Annual Developer Plan Renewal", 4999.00),
    ("Enterprise SaaS Workspace License", 12500.00),
    ("StreamMax Premium Annual Plan", 1499.00),
    ("Cloud Storage 2TB Family Pack", 899.00),
    ("Accounting Suite Pro Annual Renewal", 9499.00),
    ("FitPass Unlimited Gym Membership", 2499.00),
    ("MusicStream Hi-Res Family Subscription", 299.00),
    ("CRM Standard User Seat Monthly", 1999.00),
    ("Daily News & Magazine Digital Annual Pass", 1199.00),
    ("AI Coding Assistant Monthly Seat", 1650.00),
    ("Security Antivirus 5-Device 1-Year License", 1299.00),
    ("Design Pro Annual Team Subscription", 8400.00),
    ("Video Editing Suite Monthly Subscription", 1799.00),
    ("VPN Ultimate 2-Year Plan Renewal", 3599.00),
]

ABANDONMENT_ITEMS = [
    ("Cart Recovery - Bose QuietComfort Earbuds", 12900.00),
    ("Cart Recovery - Levi's 511 Slim Fit Jeans", 2799.00),
    ("Cart Recovery - Full Stack Web Dev Bootcamp", 6999.00),
    ("Cart Recovery - Dyson Supersonic Hair Dryer", 14990.00),
    ("Cart Recovery - OnePlus Nord Buds 2", 2299.00),
    ("Cart Recovery - Premium Whey Protein Isolate 2kg", 4599.00),
    ("Cart Recovery - Samsonite Hard Luggage 68cm", 9800.00),
    ("Cart Recovery - Ray-Ban Wayfarer Classic Polarized", 7590.00),
    ("Cart Recovery - Fossil Gen 6 Smartwatch", 11995.00),
    ("Cart Recovery - Puma Nitro Running Shoes", 5499.00),
    ("Cart Recovery - Ceramic Cookware Set 5-Piece", 3899.00),
    ("Cart Recovery - Mechanical Gaming Numpad", 1299.00),
    ("Cart Recovery - Wireless Security Camera 2K", 3499.00),
]


# ── ID Generators ──────────────────────────────────────────────────────────────

def random_alnum(length: int = 14) -> str:
    chars = string.ascii_letters + string.digits
    return "".join(random.choices(chars, k=length))


def generate_transaction_id() -> str:
    return f"txn_{random_alnum(16)}"


def generate_payment_id() -> str:
    return f"pay_{random_alnum(14)}"


def generate_customer_id() -> str:
    return f"cust_{random_alnum(12)}"


def generate_phone() -> str:
    prefix = random.choice(["98", "97", "99", "96", "91", "88", "87", "70", "79", "80"])
    rest = "".join(random.choices(string.digits, k=8))
    return f"+91{prefix}{rest}"


def generate_channel_preference() -> str:
    # 58% WhatsApp, 27% SMS, 15% Email
    return random.choices(["whatsapp", "sms", "email"], weights=[58, 27, 15], k=1)[0]


# ── Distribution Generator ────────────────────────────────────────────────────

def build_dataset() -> List[Dict[str, Any]]:
    """
    Generates 250 realistic payment records according to specifications:
    - Types:
        - one_time_checkout: 120 (48%)
        - subscription_renewal: 80 (32%)
        - checkout_abandonment: 50 (20%)
    - Failure Reasons (250 total):
        - account_closed: 40 (16.0% >= 15% unrecoverable)
        - insufficient_funds: 50 (20.0%)
        - customer_abandoned: 45 (18.0%)
        - wrong_otp: 28 (11.2%)
        - bank_timeout: 28 (11.2%)
        - card_expired: 28 (11.2%)
        - network_error: 18 (7.2%)
        - daily_limit_exceeded: 13 (5.2%)
    """
    # Fix seed for predictable yet diverse generation
    random.seed(42)

    records: List[Dict[str, Any]] = []
    now = datetime.datetime.now(datetime.timezone.utc)

    # 1. Generate 120 one_time_checkout records
    # Reasons: insufficient_funds (32), wrong_otp (28), bank_timeout (20),
    #          account_closed (15), network_error (13), daily_limit_exceeded (8), card_expired (4)
    otc_reasons: List[str] = (
        ["insufficient_funds"] * 32
        + ["wrong_otp"] * 28
        + ["bank_timeout"] * 20
        + ["account_closed"] * 15
        + ["network_error"] * 13
        + ["daily_limit_exceeded"] * 8
        + ["card_expired"] * 4
    )
    random.shuffle(otc_reasons)

    for reason in otc_reasons:
        item_title, base_price = random.choice(ONE_TIME_ITEMS)
        amount = round(max(199.0, min(15000.0, base_price + random.choice([-100, 0, 50, 150, -50]))), 2)
        
        fname = random.choice(FIRST_NAMES)
        lname = random.choice(LAST_NAMES)
        email = f"{fname.lower()}.{lname.lower()}{random.randint(10, 99)}@{random.choice(EMAIL_DOMAINS)}"
        phone = generate_phone()
        
        days_ago = random.choices(
            [random.uniform(0, 3), random.uniform(3, 10), random.uniform(10, 30)],
            weights=[50, 35, 15],
            k=1
        )[0]
        ts = now - datetime.timedelta(days=days_ago, minutes=random.randint(5, 720))

        records.append({
            "transaction_id": generate_transaction_id(),
            "razorpay_payment_id": generate_payment_id(),
            "customer_id": generate_customer_id(),
            "type": "one_time_checkout",
            "amount": amount,
            "currency": "INR",
            "event_type": "payment.failed",
            "failure_reason_code": reason,
            "contact_attempts_so_far": 0,
            "customer_channel_pref": generate_channel_preference(),
            "status": "open",
            "customer_email": email,
            "customer_phone": phone,
            "description": f"One-Time Purchase: {item_title}",
            "timestamp": ts.isoformat(),
            "created_at": ts.isoformat(),
            "updated_at": ts.isoformat(),
        })

    # 2. Generate 80 subscription_renewal records
    # Reasons: account_closed (25), card_expired (24), insufficient_funds (18),
    #          bank_timeout (8), daily_limit_exceeded (5)
    sub_reasons: List[str] = (
        ["account_closed"] * 25
        + ["card_expired"] * 24
        + ["insufficient_funds"] * 18
        + ["bank_timeout"] * 8
        + ["daily_limit_exceeded"] * 5
    )
    random.shuffle(sub_reasons)

    for reason in sub_reasons:
        item_title, base_price = random.choice(SUBSCRIPTION_ITEMS)
        amount = round(max(199.0, min(15000.0, base_price)), 2)

        fname = random.choice(FIRST_NAMES)
        lname = random.choice(LAST_NAMES)
        email = f"{fname.lower()}.{lname.lower()}{random.randint(10, 99)}@{random.choice(EMAIL_DOMAINS)}"
        phone = generate_phone()

        days_ago = random.choices(
            [random.uniform(0, 3), random.uniform(3, 10), random.uniform(10, 30)],
            weights=[45, 40, 15],
            k=1
        )[0]
        ts = now - datetime.timedelta(days=days_ago, minutes=random.randint(5, 720))

        records.append({
            "transaction_id": generate_transaction_id(),
            "razorpay_payment_id": generate_payment_id(),
            "customer_id": generate_customer_id(),
            "type": "subscription_renewal",
            "amount": amount,
            "currency": "INR",
            "event_type": "subscription.charged_failed",
            "failure_reason_code": reason,
            "contact_attempts_so_far": 0,
            "customer_channel_pref": generate_channel_preference(),
            "status": "open",
            "customer_email": email,
            "customer_phone": phone,
            "description": f"Subscription Renewal: {item_title}",
            "timestamp": ts.isoformat(),
            "created_at": ts.isoformat(),
            "updated_at": ts.isoformat(),
        })

    # 3. Generate 50 checkout_abandonment records
    # Reasons: customer_abandoned (45), network_error (5)
    abn_reasons: List[str] = (
        ["customer_abandoned"] * 45
        + ["network_error"] * 5
    )
    random.shuffle(abn_reasons)

    for reason in abn_reasons:
        item_title, base_price = random.choice(ABANDONMENT_ITEMS)
        amount = round(max(199.0, min(15000.0, base_price + random.choice([-50, 0, 50, 100]))), 2)

        fname = random.choice(FIRST_NAMES)
        lname = random.choice(LAST_NAMES)
        email = f"{fname.lower()}.{lname.lower()}{random.randint(10, 99)}@{random.choice(EMAIL_DOMAINS)}"
        phone = generate_phone()

        days_ago = random.choices(
            [random.uniform(0, 2), random.uniform(2, 7), random.uniform(7, 20)],
            weights=[60, 30, 10],
            k=1
        )[0]
        ts = now - datetime.timedelta(days=days_ago, minutes=random.randint(5, 720))

        # Abandonments can have a payment ID if attempted or generated on checkout init
        pay_id = generate_payment_id() if random.random() > 0.3 else None

        records.append({
            "transaction_id": generate_transaction_id(),
            "razorpay_payment_id": pay_id,
            "customer_id": generate_customer_id(),
            "type": "checkout_abandonment",
            "amount": amount,
            "currency": "INR",
            "event_type": "checkout.abandoned",
            "failure_reason_code": reason,
            "contact_attempts_so_far": 0,
            "customer_channel_pref": generate_channel_preference(),
            "status": "open",
            "customer_email": email,
            "customer_phone": phone,
            "description": f"{item_title}",
            "timestamp": ts.isoformat(),
            "created_at": ts.isoformat(),
            "updated_at": ts.isoformat(),
        })

    # Shuffle full dataset so types and timestamps interleave realistically
    random.shuffle(records)
    return records


# ── Database Setup & Insertion ────────────────────────────────────────────────

def init_tables(conn: sqlite3.Connection) -> None:
    """Ensure proper schema exists matching SQLAlchemy models in app/db/base.py."""
    cur = conn.cursor()

    # Check if existing transactions table has the correct schema
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='transactions'")
    table_exists = cur.fetchone() is not None

    if table_exists:
        cur.execute("PRAGMA table_info(transactions)")
        cols = {row[1] for row in cur.fetchall()}
        # If crucial columns are missing, drop outdated table
        if "transaction_id" not in cols or "failure_reason_code" not in cols:
            print("[INFO] Outdated transactions table detected. Rebuilding schema...")
            cur.execute("DROP TABLE IF EXISTS audit_logs")
            cur.execute("DROP TABLE IF EXISTS transactions")

    # Create transactions table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            transaction_id VARCHAR(64) UNIQUE NOT NULL,
            razorpay_payment_id VARCHAR(64),
            customer_id VARCHAR(64) NOT NULL,
            type VARCHAR(64) NOT NULL,
            amount FLOAT NOT NULL,
            currency VARCHAR(8) DEFAULT 'INR',
            event_type VARCHAR(64) DEFAULT 'payment.failed',
            failure_reason_code VARCHAR(64) NOT NULL,
            contact_attempts_so_far INTEGER DEFAULT 0,
            customer_channel_pref VARCHAR(32) DEFAULT 'whatsapp',
            status VARCHAR(32) DEFAULT 'open',
            customer_email VARCHAR(256),
            customer_phone VARCHAR(32),
            description TEXT,
            timestamp DATETIME,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cur.execute("CREATE INDEX IF NOT EXISTS ix_transactions_id ON transactions (id)")
    cur.execute("CREATE INDEX IF NOT EXISTS ix_transactions_transaction_id ON transactions (transaction_id)")
    cur.execute("CREATE INDEX IF NOT EXISTS ix_transactions_razorpay_payment_id ON transactions (razorpay_payment_id)")
    cur.execute("CREATE INDEX IF NOT EXISTS ix_transactions_customer_id ON transactions (customer_id)")
    cur.execute("CREATE INDEX IF NOT EXISTS ix_transactions_type ON transactions (type)")
    cur.execute("CREATE INDEX IF NOT EXISTS ix_transactions_failure_reason_code ON transactions (failure_reason_code)")
    cur.execute("CREATE INDEX IF NOT EXISTS ix_transactions_status ON transactions (status)")

    # Create audit_logs table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS audit_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            transaction_id INTEGER NOT NULL,
            action VARCHAR(32) NOT NULL,
            actor VARCHAR(128),
            notes TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(transaction_id) REFERENCES transactions (id) ON DELETE CASCADE
        )
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS ix_audit_logs_id ON audit_logs (id)")
    cur.execute("CREATE INDEX IF NOT EXISTS ix_audit_logs_transaction_id ON audit_logs (transaction_id)")

    # Create policy_documents table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS policy_documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title VARCHAR(256) NOT NULL,
            content TEXT NOT NULL,
            version VARCHAR(32) DEFAULT '1.0',
            is_active BOOLEAN DEFAULT 1,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS ix_policy_documents_id ON policy_documents (id)")

    # Insert default policy documents if none exist
    cur.execute("SELECT COUNT(*) FROM policy_documents")
    if cur.fetchone()[0] == 0:
        policies = [
            (
                "Standard Revenue Recovery SLA & Rules",
                "Policy SLA-001: For recoverable payment failures (insufficient funds, OTP errors, card expiration), initiate contact via preferred customer channel within 15 minutes. Maximum of 3 retry attempts over a 7-day grace window before escalation.",
                "1.0",
                1
            ),
            (
                "Permanently Unrecoverable Account Handling",
                "Policy SLA-002: If a payment failure is flagged with 'account_closed', no automated payment retry or debit attempts should be scheduled. Transition record to unrecoverable status and notify customer support for manual account update.",
                "1.0",
                1
            ),
            (
                "Checkout Abandonment Engagement Protocol",
                "Policy SLA-003: For abandoned checkouts with cart value > Rs. 1,000, trigger WhatsApp / SMS cart recovery message with secure Razorpay payment link within 30 minutes of drop-off.",
                "1.0",
                1
            )
        ]
        cur.executemany(
            "INSERT INTO policy_documents (title, content, version, is_active) VALUES (?, ?, ?, ?)",
            policies
        )

    conn.commit()


def insert_records(conn: sqlite3.Connection, records: List[Dict[str, Any]]) -> None:
    """Insert 250 synthetic transactions and corresponding audit log entries."""
    cur = conn.cursor()

    # Clear existing transactions to ensure exact 250 count
    cur.execute("DELETE FROM audit_logs")
    cur.execute("DELETE FROM transactions")
    conn.commit()

    insert_tx_sql = """
        INSERT INTO transactions (
            transaction_id, razorpay_payment_id, customer_id, type, amount,
            currency, event_type, failure_reason_code, contact_attempts_so_far,
            customer_channel_pref, status, customer_email, customer_phone,
            description, timestamp, created_at, updated_at
        ) VALUES (
            :transaction_id, :razorpay_payment_id, :customer_id, :type, :amount,
            :currency, :event_type, :failure_reason_code, :contact_attempts_so_far,
            :customer_channel_pref, :status, :customer_email, :customer_phone,
            :description, :timestamp, :created_at, :updated_at
        )
    """

    for rec in records:
        cur.execute(insert_tx_sql, rec)
        tx_row_id = cur.lastrowid

        # Insert initial audit log for transaction creation
        cur.execute(
            """
            INSERT INTO audit_logs (transaction_id, action, actor, notes, created_at)
            VALUES (?, 'created', 'system', ?, ?)
            """,
            (
                tx_row_id,
                f"Ingested {rec['type']} event ({rec['event_type']}) with reason '{rec['failure_reason_code']}'",
                rec['created_at']
            )
        )

    conn.commit()


# ── Summary Report Formatting ─────────────────────────────────────────────────

def print_distribution_summary(records: List[Dict[str, Any]], db_path: Path) -> None:
    """Prints a clear terminal summary of dataset distribution and stats."""
    total_count = len(records)
    total_amount = sum(r["amount"] for r in records)
    avg_amount = total_amount / total_count if total_count else 0
    min_amount = min(r["amount"] for r in records)
    max_amount = max(r["amount"] for r in records)

    # Category breakdowns
    types_count: Dict[str, int] = {}
    types_amount: Dict[str, float] = {}
    reasons_count: Dict[str, int] = {}
    reasons_amount: Dict[str, float] = {}
    channels_count: Dict[str, int] = {}

    unrecoverable_reasons = {"account_closed"}

    for r in records:
        t = r["type"]
        types_count[t] = types_count.get(t, 0) + 1
        types_amount[t] = types_amount.get(t, 0) + r["amount"]

        rc = r["failure_reason_code"]
        reasons_count[rc] = reasons_count.get(rc, 0) + 1
        reasons_amount[rc] = reasons_amount.get(rc, 0) + r["amount"]

        ch = r["customer_channel_pref"]
        channels_count[ch] = channels_count.get(ch, 0) + 1

    unrecoverable_count = sum(reasons_count.get(code, 0) for code in unrecoverable_reasons)
    recoverable_count = total_count - unrecoverable_count
    unrecoverable_pct = (unrecoverable_count / total_count) * 100
    recoverable_pct = (recoverable_count / total_count) * 100

    unrecoverable_amount = sum(reasons_amount.get(code, 0.0) for code in unrecoverable_reasons)
    recoverable_amount = total_amount - unrecoverable_amount

    # Formatting CLI Output with standard ASCII boundaries
    sep = "=" * 80
    subsep = "-" * 80

    print("\n" + sep)
    print("  RECOUP SYNTHETIC PAYMENT DATA GENERATION COMPLETE")
    print(sep)
    print(f"  Database Destination : {db_path}")
    print(f"  Total Records        : {total_count}")
    print(f"  Total Value at Risk  : Rs. {total_amount:,.2f}")
    print(f"  Amount Range         : Rs. {min_amount:,.2f} - Rs. {max_amount:,.2f} (Avg: Rs. {avg_amount:,.2f})")
    print(f"  Status & Outreach    : status='open' | contact_attempts_so_far=0")
    print(subsep)

    # 1. Type Distribution
    print("  1. BREAKDOWN BY PAYMENT FAILURE TYPE")
    print(f"  {'Type':<28} {'Count':>6} {'Share':>8} {'Total Value':>18} {'Avg Value':>14}")
    print("  " + "-" * 76)
    for t_name in ["one_time_checkout", "subscription_renewal", "checkout_abandonment"]:
        cnt = types_count.get(t_name, 0)
        pct = (cnt / total_count) * 100
        val = types_amount.get(t_name, 0.0)
        avg = val / cnt if cnt else 0.0
        display_name = t_name.replace("_", " ").title()
        print(f"  {display_name:<28} {cnt:>6} {pct:>7.1f}% {f'Rs. {val:,.2f}':>18} {f'Rs. {avg:,.2f}':>14}")
    print(subsep)

    # 2. Failure Reasons & Recoverability
    print("  2. BREAKDOWN BY FAILURE REASON CODE & RECOVERABILITY")
    print(f"  {'Failure Reason':<26} {'Class':<18} {'Count':>6} {'Share':>8} {'Total Value':>18}")
    print("  " + "-" * 78)
    sorted_reasons = sorted(reasons_count.items(), key=lambda x: x[1], reverse=True)
    for r_code, cnt in sorted_reasons:
        pct = (cnt / total_count) * 100
        val = reasons_amount.get(r_code, 0.0)
        is_unrec = r_code in unrecoverable_reasons
        category = "Unrecoverable [X]" if is_unrec else "Recoverable [OK]"
        display_code = r_code
        print(f"  {display_code:<26} {category:<18} {cnt:>6} {pct:>7.1f}% {f'Rs. {val:,.2f}':>18}")
    print("  " + "-" * 78)
    print(f"  {'Recoverable Opportunities':<44} {recoverable_count:>6} {recoverable_pct:>7.1f}% {f'Rs. {recoverable_amount:,.2f}':>18}")
    print(f"  {'Permanently Unrecoverable (>=15%)':<44} {unrecoverable_count:>6} {unrecoverable_pct:>7.1f}% {f'Rs. {unrecoverable_amount:,.2f}':>18}")
    print(subsep)

    # 3. Channel Preferences
    print("  3. BREAKDOWN BY CUSTOMER CHANNEL PREFERENCE")
    print(f"  {'Channel':<20} {'Count':>6} {'Share':>8}")
    print("  " + "-" * 38)
    for ch in ["whatsapp", "sms", "email"]:
        cnt = channels_count.get(ch, 0)
        pct = (cnt / total_count) * 100
        print(f"  {ch.title():<20} {cnt:>6} {pct:>7.1f}%")
    print(sep)
    print("  All 250 records successfully populated into SQLite database.")
    print(sep + "\n")


# ── Main Entrypoint ────────────────────────────────────────────────────────────

def main() -> None:
    db_path = find_db_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)

    print(f"[INFO] Connecting to SQLite database at: {db_path}")
    conn = sqlite3.connect(str(db_path))

    try:
        init_tables(conn)
        records = build_dataset()
        insert_records(conn, records)
        print_distribution_summary(records, db_path)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
