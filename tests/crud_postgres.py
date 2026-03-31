"""
crud_postgres.py – 24 scenariusze testowe dla PostgreSQL.
Zwraca czas wykonania każdego scenariusza w sekundach.
"""

import time
import random
import json
import uuid
import psycopg2
from psycopg2.extras import execute_values

DB_CONFIG = {
    "host":     "localhost",
    "port":     5432,
    "dbname":   "eventsdb",
    "user":     "admin",
    "password": "admin123",
}

def get_conn():
    return psycopg2.connect(**DB_CONFIG)


def measure(fn) -> float:
    """Zwraca czas wykonania funkcji w sekundach."""
    start = time.perf_counter()
    fn()
    return round(time.perf_counter() - start, 6)


# ════════════════════════════════════════════
# HELPERS – pobierz losowe ID z bazy
# ════════════════════════════════════════════
def rand_id(cur, table: str, col: str = "id") -> int:
    cur.execute(f"SELECT {col} FROM {table} ORDER BY RANDOM() LIMIT 1")
    row = cur.fetchone()
    return row[0] if row else 1

def rand_ids(cur, table: str, n: int, col: str = "id") -> list:
    cur.execute(f"SELECT {col} FROM {table} ORDER BY RANDOM() LIMIT {n}")
    return [r[0] for r in cur.fetchall()]


# ════════════════════════════════════════════
# CREATE scenarios 1-6
# ════════════════════════════════════════════
def s01_insert_one_user(conn) -> float:
    def fn():
        with conn.cursor() as cur:
            uid = str(uuid.uuid4())[:8]
            cur.execute("""
                INSERT INTO users (first_name, last_name, email, password_hash, status)
                VALUES (%s, %s, %s, %s, 'active')
            """, ("Test", "User", f"test_{uid}@test.pl", "hash_xyz"))
        conn.commit()
    return measure(fn)


def s02_insert_100_users(conn) -> float:
    def fn():
        with conn.cursor() as cur:
            rows = [(f"First{i}", f"Last{i}", f"bulk_{uuid.uuid4().hex[:8]}@test.pl",
                     "hash", "active") for i in range(100)]
            execute_values(cur, """
                INSERT INTO users (first_name, last_name, email, password_hash, status)
                VALUES %s
            """, rows)
        conn.commit()
    return measure(fn)


def s03_insert_event_with_json(conn) -> float:
    def fn():
        with conn.cursor() as cur:
            cat_id   = rand_id(cur, "categories")
            org_id   = rand_id(cur, "organizers")
            venue_id = rand_id(cur, "venues")
            add_info = json.dumps({
                "age_limit": 18,
                "dress_code": "casual",
                "parking": True,
                "languages": ["PL", "EN"]
            })
            cur.execute("""
                INSERT INTO events
                  (name, description, category_id, organizer_id, venue_id,
                   start_date, end_date, additional_info, status)
                VALUES (%s,%s,%s,%s,%s,
                        NOW() + INTERVAL '10 days',
                        NOW() + INTERVAL '10 days 3 hours',
                        %s::jsonb, 'planned')
            """, ("Test Event JSON", "Opis testowy", cat_id, org_id, venue_id, add_info))
        conn.commit()
    return measure(fn)


def s04_insert_booking_with_tickets(conn) -> float:
    def fn():
        with conn.cursor() as cur:
            user_id   = rand_id(cur, "users")
            ticket_ids = rand_ids(cur, "tickets", 1)
            if not ticket_ids:
                return
            cur.execute("""
                INSERT INTO bookings (user_id, status, total_price)
                VALUES (%s, 'pending', %s) RETURNING id
            """, (user_id, 150.00))
            booking_id = cur.fetchone()[0]
            rows = [(booking_id, tid, 1, 50.00) for tid in ticket_ids]
            execute_values(cur, """
                INSERT INTO booking_tickets (booking_id, ticket_id, quantity, price_at_purchase)
                VALUES %s
            """, rows)
            cur.execute("""
                INSERT INTO payments (booking_id, payment_method, amount, payment_date, status)
                VALUES (%s, 'card', %s, NOW(), 'pending')
            """, (booking_id, 150.00))
        conn.commit()
    return measure(fn)


def s05_insert_review(conn) -> float:
    def fn():
        with conn.cursor() as cur:
            user_id = rand_id(cur, "users")
            event_id = rand_id(cur, "events")
            cur.execute("""
                INSERT INTO reviews (user_id, event_id, rating, comment)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (user_id, event_id) DO NOTHING
            """, (user_id, event_id, random.randint(1, 5), "Komentarz testowy"))
        conn.commit()
    return measure(fn)


def s06_insert_one_ticket(conn) -> float:
    def fn():
        with conn.cursor() as cur:
            event_id = rand_id(cur, "events")
            cur.execute(
                "SELECT id FROM event_zones WHERE event_id = %s ORDER BY id LIMIT 1",
                (event_id,),
            )
            row = cur.fetchone()
            if not row:
                return
            zone_id = row[0]
            perks = json.dumps({
                "lounge_access": False,
                "backstage_pass": False,
                "free_drink": False,
            })
            cur.execute("""
                INSERT INTO tickets
                  (event_id, zone_id, ticket_type, total_quantity,
                   available_quantity, price, perks, status)
                VALUES (%s,%s,'Standard',100,100,99.99,%s::jsonb,'available')
            """, (event_id, zone_id, perks))
        conn.commit()
    return measure(fn)


# ════════════════════════════════════════════
# READ scenarios 7-12
# ════════════════════════════════════════════
def s07_select_user_by_email(conn) -> float:
    with conn.cursor() as cur:
        cur.execute("SELECT email FROM users ORDER BY RANDOM() LIMIT 1")
        row = cur.fetchone()
    if not row:
        return 0.0
    email = row[0]

    def fn():
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM users WHERE email = %s", (email,))
            cur.fetchall()
    return measure(fn)


def s08_select_events_by_city(conn) -> float:
    with conn.cursor() as cur:
        cur.execute("""
            SELECT status FROM events ORDER BY RANDOM() LIMIT 1
        """)
        row = cur.fetchone()
    if not row:
        return 0.0
    status = row[0]

    def fn():
        with conn.cursor() as cur:
            cur.execute("""
                SELECT e.id, e.name, e.status, e.start_date
                FROM events e
                WHERE e.status = %s
                  AND e.start_date BETWEEN NOW() - INTERVAL '365 days'
                                      AND NOW() + INTERVAL '365 days'
            """, (status,))
            cur.fetchall()
    return measure(fn)


def s09_select_booking_with_joins(conn) -> float:
    with conn.cursor() as cur:
        booking_id = rand_id(cur, "bookings")

    def fn():
        with conn.cursor() as cur:
            cur.execute("""
                SELECT b.id, b.status, b.total_price,
                       t.ticket_type, t.price,
                       e.name AS event_name
                FROM bookings b
                JOIN booking_tickets bt ON bt.booking_id = b.id
                JOIN tickets t           ON t.id = bt.ticket_id
                JOIN events e            ON e.id = t.event_id
                WHERE b.id = %s
            """, (booking_id,))
            cur.fetchall()
    return measure(fn)


def s10_aggregate_avg_rating(conn) -> float:
    def fn():
        with conn.cursor() as cur:
            cur.execute("""
                SELECT e.id, e.name, ROUND(AVG(r.rating), 2) AS avg_rating, COUNT(r.id)
                FROM reviews r
                JOIN events e ON e.id = r.event_id
                GROUP BY e.id, e.name
                ORDER BY avg_rating DESC
                LIMIT 50
            """)
            cur.fetchall()
    return measure(fn)


def s11_select_events_by_json_field(conn) -> float:
    """Dane półustrukturalne – filtrowanie po polu JSONB."""
    def fn():
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, name, additional_info->>'age_limit' AS age_limit
                FROM events
                WHERE (additional_info->>'age_limit')::int = 18
            """)
            cur.fetchall()
    return measure(fn)


def s12_select_tickets_with_lounge(conn) -> float:
    """Ranking eventow po liczbie bookingow."""
    def fn():
        with conn.cursor() as cur:
            cur.execute("""
                SELECT e.id, e.name, COUNT(DISTINCT b.id) AS bookings_count
                FROM bookings b
                JOIN booking_tickets bt ON bt.booking_id = b.id
                JOIN tickets t ON t.id = bt.ticket_id
                JOIN events e ON e.id = t.event_id
                GROUP BY e.id, e.name
                ORDER BY bookings_count DESC
                LIMIT 20
            """)
            cur.fetchall()
    return measure(fn)


# ════════════════════════════════════════════
# UPDATE scenarios 13-18
# ════════════════════════════════════════════
def s13_update_booking_status(conn) -> float:
    with conn.cursor() as cur:
        booking_id = rand_id(cur, "bookings")

    def fn():
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE bookings SET status = 'paid' WHERE id = %s
            """, (booking_id,))
        conn.commit()
    return measure(fn)


def s14_update_ticket_quantity(conn) -> float:
    with conn.cursor() as cur:
        ticket_id = rand_id(cur, "tickets")

    def fn():
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE tickets
                SET available_quantity = GREATEST(available_quantity - 1, 0)
                WHERE id = %s
            """, (ticket_id,))
        conn.commit()
    return measure(fn)


def s15_update_100_events_status(conn) -> float:
    with conn.cursor() as cur:
        ids = rand_ids(cur, "events", 100)
    if not ids:
        return 0.0

    def fn():
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE events SET status = 'finished'
                WHERE id = ANY(%s::bigint[])
            """, (ids,))
        conn.commit()
    return measure(fn)


def s16_update_user_data(conn) -> float:
    with conn.cursor() as cur:
        user_id = rand_id(cur, "users")

    def fn():
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE users
                SET phone = %s, updated_at = NOW()
                WHERE id = %s
            """, ("600-700-800", user_id))
        conn.commit()
    return measure(fn)


def s17_update_json_field(conn) -> float:
    """Dane półustrukturalne – aktualizacja pola w JSONB."""
    with conn.cursor() as cur:
        event_id = rand_id(cur, "events")

    def fn():
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE events
                SET additional_info = jsonb_set(
                    COALESCE(additional_info, '{}'),
                    '{languages}',
                    (COALESCE(additional_info->'languages', '[]') || '"DE"'::jsonb)
                )
                WHERE id = %s
            """, (event_id,))
        conn.commit()
    return measure(fn)


def s18_update_vip_prices(conn) -> float:
    def fn():
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE tickets SET price = ROUND(price * 1.1, 2)
                WHERE ticket_type = 'VIP'
            """)
        conn.commit()
    return measure(fn)


# ════════════════════════════════════════════
# DELETE scenarios 19-24
# ════════════════════════════════════════════
def s19_delete_review(conn) -> float:
    with conn.cursor() as cur:
        cur.execute("""
            SELECT user_id, event_id FROM reviews
            ORDER BY RANDOM() LIMIT 1
        """)
        row = cur.fetchone()
    if not row:
        return 0.0

    def fn():
        with conn.cursor() as cur:
            cur.execute("""
                DELETE FROM reviews WHERE user_id = %s AND event_id = %s
            """, row)
        conn.commit()
    return measure(fn)


def s20_delete_booking_cascade(conn) -> float:
    with conn.cursor() as cur:
        booking_id = rand_id(cur, "bookings")

    def fn():
        with conn.cursor() as cur:
            cur.execute("DELETE FROM payments WHERE booking_id = %s", (booking_id,))
            cur.execute("DELETE FROM bookings  WHERE id = %s",         (booking_id,))
        conn.commit()
    return measure(fn)


def s21_delete_user_cascade(conn) -> float:
    with conn.cursor() as cur:
        uid = str(uuid.uuid4())[:8]
        cur.execute("""
            INSERT INTO users (first_name, last_name, email, password_hash, status)
            VALUES ('Del','User',%s,'hash','active') RETURNING id
        """, (f"del_{uid}@test.pl",))
        new_id = cur.fetchone()[0]
    conn.commit()

    def fn():
        with conn.cursor() as cur:
            cur.execute("DELETE FROM users WHERE id = %s", (new_id,))
        conn.commit()
    return measure(fn)


def s22_delete_cancelled_events(conn) -> float:
    with conn.cursor() as cur:
        for _ in range(5):
            cur.execute("""
                INSERT INTO events (name, start_date, end_date, status)
                VALUES ('DEL_TEST', NOW(), NOW() + INTERVAL '1 hour', 'cancelled')
            """)
    conn.commit()

    def fn():
        with conn.cursor() as cur:
            cur.execute("DELETE FROM events WHERE status = 'cancelled' AND name = 'DEL_TEST'")
        conn.commit()
    return measure(fn)


def s23_delete_old_payments(conn) -> float:
    def fn():
        with conn.cursor() as cur:
            cur.execute("""
                DELETE FROM payments
                WHERE payment_date < NOW() - INTERVAL '1 year'
            """)
        conn.commit()
    return measure(fn)


def s24_delete_zone_cascade(conn) -> float:
    with conn.cursor() as cur:
        event_id = rand_id(cur, "events")
        zone_id = rand_id(cur, "event_zones")
        perks = json.dumps({
            "lounge_access": False,
            "backstage_pass": False,
            "free_drink": False,
        })
        cur.execute("""
            INSERT INTO tickets
              (event_id, zone_id, ticket_type, total_quantity,
               available_quantity, price, perks, status)
            VALUES (%s,%s,'DEL_TEST',1,1,10.00,%s::jsonb,'available')
            RETURNING id
        """, (event_id, zone_id, perks))
        ticket_id = cur.fetchone()[0]
    conn.commit()

    def fn():
        with conn.cursor() as cur:
            cur.execute("DELETE FROM tickets WHERE id = %s", (ticket_id,))
        conn.commit()
    return measure(fn)


# ════════════════════════════════════════════
# MAPA scenariuszy
# ════════════════════════════════════════════
SCENARIO_FUNCTIONS = {
    1:  s01_insert_one_user,
    2:  s02_insert_100_users,
    3:  s03_insert_event_with_json,
    4:  s04_insert_booking_with_tickets,
    5:  s05_insert_review,
    6:  s06_insert_one_ticket,
    7:  s07_select_user_by_email,
    8:  s08_select_events_by_city,
    9:  s09_select_booking_with_joins,
    10: s10_aggregate_avg_rating,
    11: s11_select_events_by_json_field,
    12: s12_select_tickets_with_lounge,
    13: s13_update_booking_status,
    14: s14_update_ticket_quantity,
    15: s15_update_100_events_status,
    16: s16_update_user_data,
    17: s17_update_json_field,
    18: s18_update_vip_prices,
    19: s19_delete_review,
    20: s20_delete_booking_cascade,
    21: s21_delete_user_cascade,
    22: s22_delete_cancelled_events,
    23: s23_delete_old_payments,
    24: s24_delete_zone_cascade,
}


def run_all_scenarios(repeats: int = 3) -> list:
    """
    Uruchamia wszystkie 24 scenariusze, każdy `repeats` razy.
    Zwraca listę słowników z wynikami.
    """
    conn    = get_conn()
    results = []
    print("  [PostgreSQL] Uruchamiam scenariusze...")
    for sid, fn in SCENARIO_FUNCTIONS.items():
        times = []
        for attempt in range(1, repeats + 1):
            try:
                t = fn(conn)
                times.append(t)
            except Exception as e:
                print(f"    ⚠ S{sid} próba {attempt}: {e}")
                conn.rollback()
                times.append(None)
        valid = [t for t in times if t is not None]
        avg   = round(sum(valid) / len(valid), 6) if valid else None
        results.append({
            "scenario_id": sid,
            "times":       times,
            "avg":         avg,
        })
        status = f"{avg:.6f}s" if avg else "BŁĄD"
        print(f"    S{sid:02d}: {status}  (próby: {times})")
    conn.close()
    return results


# ════════════════════════════════════════════
# ZARZĄDZANIE INDEKSAMI
# ════════════════════════════════════════════
INDEXES = [
    # users
    "CREATE INDEX IF NOT EXISTS idx_users_email  ON users(email)",
    "CREATE INDEX IF NOT EXISTS idx_users_status ON users(status)",
    # venues
    "CREATE INDEX IF NOT EXISTS idx_venues_city ON venues(city)",
    # events
    "CREATE INDEX IF NOT EXISTS idx_events_status     ON events(status)",
    "CREATE INDEX IF NOT EXISTS idx_events_start_date ON events(start_date)",
    "CREATE INDEX IF NOT EXISTS idx_events_category   ON events(category_id)",
    "CREATE INDEX IF NOT EXISTS idx_events_venue      ON events(venue_id)",
    "CREATE INDEX IF NOT EXISTS idx_events_add_info   ON events USING GIN (additional_info)",
    # tickets
    "CREATE INDEX IF NOT EXISTS idx_tickets_event  ON tickets(event_id)",
    "CREATE INDEX IF NOT EXISTS idx_tickets_zone   ON tickets(zone_id)",
    "CREATE INDEX IF NOT EXISTS idx_tickets_status ON tickets(status)",
    "CREATE INDEX IF NOT EXISTS idx_tickets_perks  ON tickets USING GIN (perks)",
    # bookings
    "CREATE INDEX IF NOT EXISTS idx_bookings_user   ON bookings(user_id)",
    "CREATE INDEX IF NOT EXISTS idx_bookings_status ON bookings(status)",
    "CREATE INDEX IF NOT EXISTS idx_bookings_date   ON bookings(booking_date)",
    # reviews
    "CREATE INDEX IF NOT EXISTS idx_reviews_event ON reviews(event_id)",
    "CREATE INDEX IF NOT EXISTS idx_reviews_user  ON reviews(user_id)",
]

DROP_INDEXES = [
    "DROP INDEX IF EXISTS idx_users_email",
    "DROP INDEX IF EXISTS idx_users_status",
    "DROP INDEX IF EXISTS idx_venues_city",
    "DROP INDEX IF EXISTS idx_events_status",
    "DROP INDEX IF EXISTS idx_events_start_date",
    "DROP INDEX IF EXISTS idx_events_category",
    "DROP INDEX IF EXISTS idx_events_venue",
    "DROP INDEX IF EXISTS idx_events_add_info",
    "DROP INDEX IF EXISTS idx_tickets_event",
    "DROP INDEX IF EXISTS idx_tickets_zone",
    "DROP INDEX IF EXISTS idx_tickets_status",
    "DROP INDEX IF EXISTS idx_tickets_perks",
    "DROP INDEX IF EXISTS idx_bookings_user",
    "DROP INDEX IF EXISTS idx_bookings_status",
    "DROP INDEX IF EXISTS idx_bookings_date",
    "DROP INDEX IF EXISTS idx_reviews_event",
    "DROP INDEX IF EXISTS idx_reviews_user",
]


def create_indexes():
    conn = get_conn()
    with conn.cursor() as cur:
        for sql in INDEXES:
            cur.execute(sql)
    conn.commit()
    conn.close()
    print("  [PostgreSQL] ✅ Indeksy utworzone")


def drop_indexes():
    conn = get_conn()
    with conn.cursor() as cur:
        for sql in DROP_INDEXES:
            cur.execute(sql)
    conn.commit()
    conn.close()
    print("  [PostgreSQL] ✅ Indeksy usunięte")
