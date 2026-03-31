"""
import_mysql.py – Import danych do MySQL 8.

Użycie:
  python import_mysql.py
"""

import json
import os
import mysql.connector
from tqdm import tqdm

# ─────────────────────────────────────────────
# KONFIGURACJA
# ─────────────────────────────────────────────
DB_CONFIG = {
    "host":     "localhost",
    "port":     3306,
    "database": "eventsdb",
    "user":     "root",
    "password": "root123",
    "charset":  "utf8mb4",
}
DATA_DIR = "data"
BATCH    = 5_000


# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────
def load(name: str) -> list:
    path = os.path.join(DATA_DIR, f"{name}.json")
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def bulk_insert(cur, table: str, columns: list, rows: list):
    if not rows:
        return
    placeholders = ", ".join(["%s"] * len(columns))
    sql = f"INSERT IGNORE INTO {table} ({', '.join(columns)}) VALUES ({placeholders})"
    data = [tuple(r[c] for c in columns) for r in rows]
    for i in tqdm(range(0, len(data), BATCH), desc=f"  → {table}", unit="batch"):
        cur.executemany(sql, data[i:i + BATCH])


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────
def main():
    print("\n🐬 Import do MySQL...\n")
    conn = mysql.connector.connect(**DB_CONFIG)
    conn.autocommit = False
    cur = conn.cursor()

    try:
        cur.execute("SET FOREIGN_KEY_CHECKS = 0;")
        cur.execute("SET unique_checks = 0;")
        cur.execute("SET sql_mode = '';")

        # 1. categories
        bulk_insert(cur, "categories", ["id", "name"], load("categories"))

        # 2. organizers
        bulk_insert(cur, "organizers",
                    ["id", "name", "email", "phone", "created_at"],
                    load("organizers"))

        # 3. venues
        bulk_insert(cur, "venues",
                    ["id", "name", "street", "city", "postal_code", "country", "capacity", "created_at"],
                    load("venues"))

        # 4. users
        bulk_insert(cur, "users",
                    ["id", "first_name", "last_name", "email", "password_hash",
                     "phone", "status", "created_at", "updated_at"],
                    load("users"))

        # 5. user_addresses
        bulk_insert(cur, "user_addresses",
                    ["id", "user_id", "street", "city", "postal_code", "country", "type", "created_at"],
                    load("user_addresses"))

        # 6. events
        bulk_insert(cur, "events",
                    ["id", "name", "description", "category_id", "organizer_id", "venue_id",
                     "start_date", "end_date", "additional_info", "status", "created_at"],
                    load("events"))

        # 7. event_zones
        bulk_insert(cur, "event_zones",
                    ["id", "event_id", "name", "type", "capacity"],
                    load("event_zones"))

        # 8. seats
        bulk_insert(cur, "seats",
                    ["id", "zone_id", "row_label", "seat_number"],
                    load("seats"))

        # 9. tickets
        bulk_insert(cur, "tickets",
                    ["id", "event_id", "zone_id", "seat_id", "ticket_type",
                     "total_quantity", "available_quantity", "price", "perks", "status", "created_at"],
                    load("tickets"))

        # 10. bookings
        bulk_insert(cur, "bookings",
                    ["id", "user_id", "booking_date", "status", "total_price"],
                    load("bookings"))

        # 11. booking_tickets
        bulk_insert(cur, "booking_tickets",
                    ["id", "booking_id", "ticket_id", "quantity", "price_at_purchase"],
                    load("booking_tickets"))

        # 12. payments
        bulk_insert(cur, "payments",
                    ["id", "booking_id", "payment_method", "amount", "payment_date", "status"],
                    load("payments"))

        # 13. reviews
        bulk_insert(cur, "reviews",
                    ["id", "user_id", "event_id", "rating", "comment", "created_at"],
                    load("reviews"))

        cur.execute("SET FOREIGN_KEY_CHECKS = 1;")
        cur.execute("SET unique_checks = 1;")
        conn.commit()
        print("\n✅ MySQL – import zakończony pomyślnie!\n")

    except Exception as e:
        conn.rollback()
        print(f"\n❌ Błąd: {e}")
        raise
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    main()
