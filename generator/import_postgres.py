"""
import_postgres.py – Import danych do PostgreSQL.

Użycie:
  python import_postgres.py
"""

import json
import os
import psycopg2
from psycopg2.extras import execute_values
from tqdm import tqdm

# ─────────────────────────────────────────────
# KONFIGURACJA
# ─────────────────────────────────────────────
DB_CONFIG = {
    "host":     "localhost",
    "port":     5432,
    "dbname":   "eventsdb",
    "user":     "admin",
    "password": "admin123",
}
DATA_DIR  = "data"
BATCH     = 5_000   # liczba wierszy na jeden INSERT


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
    sql = f"INSERT INTO {table} ({', '.join(columns)}) VALUES %s ON CONFLICT DO NOTHING"
    data = [tuple(r[c] for c in columns) for r in rows]
    for i in tqdm(range(0, len(data), BATCH), desc=f"  → {table}", unit="batch"):
        execute_values(cur, sql, data[i:i + BATCH])


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────
def main():
    print("\n🐘 Import do PostgreSQL...\n")
    conn = psycopg2.connect(**DB_CONFIG)
    conn.autocommit = False
    cur = conn.cursor()

    try:
        # Wyłącz triggery / fk na czas importu (opcjonalnie)
        cur.execute("SET session_replication_role = replica;")

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

        # 6. events – additional_info jako JSONB
        events = load("events")
        bulk_insert(cur, "events",
                    ["id", "name", "description", "category_id", "organizer_id", "venue_id",
                     "start_date", "end_date", "additional_info", "status", "created_at"],
                    events)

        # 7. event_zones
        bulk_insert(cur, "event_zones",
                    ["id", "event_id", "name", "type", "capacity"],
                    load("event_zones"))

        # 8. seats
        bulk_insert(cur, "seats",
                    ["id", "zone_id", "row_label", "seat_number"],
                    load("seats"))

        # 9. tickets – perks jako JSONB
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

        # Przywróć FK
        cur.execute("SET session_replication_role = DEFAULT;")

        # Zaktualizuj sekwencje BIGSERIAL
        tables = ["categories", "organizers", "venues", "users", "user_addresses",
                  "events", "event_zones", "seats", "tickets",
                  "bookings", "booking_tickets", "payments", "reviews"]
        for t in tables:
            cur.execute(f"SELECT setval(pg_get_serial_sequence('{t}', 'id'), COALESCE(MAX(id), 1)) FROM {t};")

        conn.commit()
        print("\n✅ PostgreSQL – import zakończony pomyślnie!\n")

    except Exception as e:
        conn.rollback()
        print(f"\n❌ Błąd: {e}")
        raise
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    main()
