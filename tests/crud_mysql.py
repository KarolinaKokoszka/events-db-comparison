"""
crud_mysql.py – 24 scenariusze testowe dla MySQL 8.
"""

import time
import random
import json
import uuid
import mysql.connector

DB_CONFIG = {
    "host":     "localhost",
    "port":     3306,
    "database": "eventsdb",
    "user":     "root",
    "password": "root123",
    "charset":  "utf8mb4",
}

def get_conn():
    return mysql.connector.connect(**DB_CONFIG)

def measure(fn) -> float:
    start = time.perf_counter()
    fn()
    return round(time.perf_counter() - start, 6)

def rand_id(cur, table: str, col: str = "id") -> int:
    cur.execute(f"SELECT {col} FROM {table} ORDER BY RAND() LIMIT 1")
    row = cur.fetchone()
    return row[0] if row else 1

def rand_ids(cur, table: str, n: int, col: str = "id") -> list:
    cur.execute(f"SELECT {col} FROM {table} ORDER BY RAND() LIMIT {n}")
    return [r[0] for r in cur.fetchall()]


# ════════════════════════════════════════════
# CREATE 1-6
# ════════════════════════════════════════════
def s01_insert_one_user(conn) -> float:
    def fn():
        cur = conn.cursor()
        uid = str(uuid.uuid4())[:8]
        cur.execute("""
            INSERT INTO users (first_name, last_name, email, password_hash, status)
            VALUES (%s,%s,%s,%s,'active')
        """, ("Test", "User", f"test_{uid}@test.pl", "hash_xyz"))
        conn.commit()
        cur.close()
    return measure(fn)


def s02_insert_100_users(conn) -> float:
    def fn():
        cur = conn.cursor()
        rows = [(f"First{i}", f"Last{i}", f"bulk_{uuid.uuid4().hex[:8]}@test.pl",
                 "hash", "active") for i in range(100)]
        cur.executemany("""
            INSERT INTO users (first_name, last_name, email, password_hash, status)
            VALUES (%s,%s,%s,%s,%s)
        """, rows)
        conn.commit()
        cur.close()
    return measure(fn)


def s03_insert_event_with_json(conn) -> float:
    def fn():
        cur = conn.cursor()
        cat_id   = rand_id(cur, "categories")
        org_id   = rand_id(cur, "organizers")
        venue_id = rand_id(cur, "venues")
        add_info = json.dumps({
            "age_limit": 18, "dress_code": "casual",
            "parking": True, "languages": ["PL", "EN"]
        })
        cur.execute("""
            INSERT INTO events
              (name, description, category_id, organizer_id, venue_id,
               start_date, end_date, additional_info, status)
            VALUES (%s,%s,%s,%s,%s,
                    DATE_ADD(NOW(), INTERVAL 10 DAY),
                    DATE_ADD(NOW(), INTERVAL 10 DAY),
                    %s, 'planned')
        """, ("Test Event JSON", "Opis", cat_id, org_id, venue_id, add_info))
        conn.commit()
        cur.close()
    return measure(fn)


def s04_insert_booking_with_tickets(conn) -> float:
    def fn():
        cur = conn.cursor()
        user_id    = rand_id(cur, "users")
        ticket_ids = rand_ids(cur, "tickets", 1)
        if not ticket_ids:
            return
        cur.execute("""
            INSERT INTO bookings (user_id, status, total_price)
            VALUES (%s, 'pending', 150.00)
        """, (user_id,))
        booking_id = cur.lastrowid
        rows = [(booking_id, tid, 1, 50.00) for tid in ticket_ids]
        cur.executemany("""
            INSERT INTO booking_tickets (booking_id, ticket_id, quantity, price_at_purchase)
            VALUES (%s,%s,%s,%s)
        """, rows)
        cur.execute("""
            INSERT INTO payments (booking_id, payment_method, amount, payment_date, status)
            VALUES (%s, 'card', 150.00, NOW(), 'pending')
        """, (booking_id,))
        conn.commit()
        cur.close()
    return measure(fn)


def s05_insert_review(conn) -> float:
    def fn():
        cur = conn.cursor()
        user_id = rand_id(cur, "users")
        event_id = rand_id(cur, "events")
        cur.execute("""
            INSERT IGNORE INTO reviews (user_id, event_id, rating, comment)
            VALUES (%s,%s,%s,%s)
        """, (user_id, event_id, random.randint(1, 5), "Komentarz testowy"))
        conn.commit()
        cur.close()
    return measure(fn)


def s06_insert_one_ticket(conn) -> float:
    def fn():
        cur = conn.cursor()
        event_id = rand_id(cur, "events")
        cur.execute("SELECT id FROM event_zones WHERE event_id=%s ORDER BY id LIMIT 1", (event_id,))
        row = cur.fetchone()
        if not row:
            return
        zone_id = row[0]
        perks = json.dumps({"lounge_access": False, "backstage_pass": False, "free_drink": False})
        cur.execute("""
            INSERT INTO tickets
              (event_id, zone_id, ticket_type, total_quantity,
               available_quantity, price, perks, status)
            VALUES (%s,%s,'Standard',100,100,99.99,%s,'available')
        """, (event_id, zone_id, perks))
        conn.commit()
        cur.close()
    return measure(fn)


# ════════════════════════════════════════════
# READ 7-12
# ════════════════════════════════════════════
def s07_select_user_by_email(conn) -> float:
    cur = conn.cursor()
    cur.execute("SELECT email FROM users ORDER BY RAND() LIMIT 1")
    row = cur.fetchone()
    cur.close()
    if not row:
        return 0.0
    email = row[0]

    def fn():
        cur = conn.cursor()
        cur.execute("SELECT * FROM users WHERE email = %s", (email,))
        cur.fetchall()
        cur.close()
    return measure(fn)


def s08_select_events_by_city(conn) -> float:
    cur = conn.cursor()
    cur.execute("SELECT status FROM events ORDER BY RAND() LIMIT 1")
    row = cur.fetchone()
    cur.close()
    if not row:
        return 0.0
    status = row[0]

    def fn():
        cur = conn.cursor()
        cur.execute("""
            SELECT e.id, e.name, e.status, e.start_date
            FROM events e
            WHERE e.status = %s
              AND e.start_date BETWEEN DATE_SUB(NOW(), INTERVAL 365 DAY)
                                   AND DATE_ADD(NOW(), INTERVAL 365 DAY)
        """, (status,))
        cur.fetchall()
        cur.close()
    return measure(fn)


def s09_select_booking_with_joins(conn) -> float:
    cur = conn.cursor()
    booking_id = rand_id(cur, "bookings")
    cur.close()

    def fn():
        cur = conn.cursor()
        cur.execute("""
            SELECT b.id, b.status, b.total_price,
                   t.ticket_type, t.price, e.name
            FROM bookings b
            JOIN booking_tickets bt ON bt.booking_id = b.id
            JOIN tickets t           ON t.id = bt.ticket_id
            JOIN events e            ON e.id = t.event_id
            WHERE b.id = %s
        """, (booking_id,))
        cur.fetchall()
        cur.close()
    return measure(fn)


def s10_aggregate_avg_rating(conn) -> float:
    def fn():
        cur = conn.cursor()
        cur.execute("""
            SELECT e.id, e.name, ROUND(AVG(r.rating), 2), COUNT(r.id)
            FROM reviews r
            JOIN events e ON e.id = r.event_id
            GROUP BY e.id, e.name
            ORDER BY 2 DESC
            LIMIT 50
        """)
        cur.fetchall()
        cur.close()
    return measure(fn)


def s11_select_events_by_json_field(conn) -> float:
    """Dane półustrukturalne – filtrowanie po polu JSON."""
    def fn():
        cur = conn.cursor()
        cur.execute("""
            SELECT id, name, JSON_EXTRACT(additional_info, '$.age_limit') AS age_limit
            FROM events
            WHERE JSON_EXTRACT(additional_info, '$.age_limit') = 18
        """)
        cur.fetchall()
        cur.close()
    return measure(fn)


def s12_select_tickets_with_lounge(conn) -> float:
    """Ranking eventow po liczbie bookingow."""
    def fn():
        cur = conn.cursor()
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
        cur.close()
    return measure(fn)


# ════════════════════════════════════════════
# UPDATE 13-18
# ════════════════════════════════════════════
def s13_update_booking_status(conn) -> float:
    cur = conn.cursor()
    booking_id = rand_id(cur, "bookings")
    cur.close()

    def fn():
        cur = conn.cursor()
        cur.execute("UPDATE bookings SET status='paid' WHERE id=%s", (booking_id,))
        conn.commit()
        cur.close()
    return measure(fn)


def s14_update_ticket_quantity(conn) -> float:
    cur = conn.cursor()
    ticket_id = rand_id(cur, "tickets")
    cur.close()

    def fn():
        cur = conn.cursor()
        cur.execute("""
            UPDATE tickets
            SET available_quantity = GREATEST(available_quantity - 1, 0)
            WHERE id = %s
        """, (ticket_id,))
        conn.commit()
        cur.close()
    return measure(fn)


def s15_update_100_events_status(conn) -> float:
    cur = conn.cursor()
    ids = rand_ids(cur, "events", 100)
    cur.close()
    if not ids:
        return 0.0

    def fn():
        cur = conn.cursor()
        fmt = ",".join(["%s"] * len(ids))
        cur.execute(f"UPDATE events SET status='finished' WHERE id IN ({fmt})", ids)
        conn.commit()
        cur.close()
    return measure(fn)


def s16_update_user_data(conn) -> float:
    cur = conn.cursor()
    user_id = rand_id(cur, "users")
    cur.close()

    def fn():
        cur = conn.cursor()
        cur.execute("""
            UPDATE users SET phone=%s, updated_at=NOW() WHERE id=%s
        """, ("600-700-800", user_id))
        conn.commit()
        cur.close()
    return measure(fn)


def s17_update_json_field(conn) -> float:
    """Dane półustrukturalne – aktualizacja pola w JSON."""
    cur = conn.cursor()
    event_id = rand_id(cur, "events")
    cur.close()

    def fn():
        cur = conn.cursor()
        cur.execute("""
            UPDATE events
            SET additional_info = JSON_ARRAY_APPEND(
                COALESCE(additional_info, JSON_OBJECT()),
                '$.languages', 'DE'
            )
            WHERE id = %s
        """, (event_id,))
        conn.commit()
        cur.close()
    return measure(fn)


def s18_update_vip_prices(conn) -> float:
    def fn():
        cur = conn.cursor()
        cur.execute("UPDATE tickets SET price = ROUND(price * 1.1, 2) WHERE ticket_type='VIP'")
        conn.commit()
        cur.close()
    return measure(fn)


# ════════════════════════════════════════════
# DELETE 19-24
# ════════════════════════════════════════════
def s19_delete_review(conn) -> float:
    cur = conn.cursor()
    cur.execute("SELECT user_id, event_id FROM reviews ORDER BY RAND() LIMIT 1")
    row = cur.fetchone()
    cur.close()
    if not row:
        return 0.0

    def fn():
        cur = conn.cursor()
        cur.execute("DELETE FROM reviews WHERE user_id=%s AND event_id=%s", row)
        conn.commit()
        cur.close()
    return measure(fn)


def s20_delete_booking_cascade(conn) -> float:
    cur = conn.cursor()
    booking_id = rand_id(cur, "bookings")
    cur.close()

    def fn():
        cur = conn.cursor()
        cur.execute("DELETE FROM payments WHERE booking_id = %s", (booking_id,))
        cur.execute("DELETE FROM bookings  WHERE id = %s",         (booking_id,))
        conn.commit()
        cur.close()
    return measure(fn)


def s21_delete_user_cascade(conn) -> float:
    cur = conn.cursor()
    uid = str(uuid.uuid4())[:8]
    cur.execute("""
        INSERT INTO users (first_name, last_name, email, password_hash, status)
        VALUES ('Del','User',%s,'hash','active')
    """, (f"del_{uid}@test.pl",))
    new_id = cur.lastrowid
    conn.commit()
    cur.close()

    def fn():
        cur = conn.cursor()
        cur.execute("DELETE FROM users WHERE id=%s", (new_id,))
        conn.commit()
        cur.close()
    return measure(fn)


def s22_delete_cancelled_events(conn) -> float:
    cur = conn.cursor()
    for _ in range(5):
        cur.execute("""
            INSERT INTO events (name, start_date, end_date, status)
            VALUES ('DEL_TEST', NOW(), DATE_ADD(NOW(), INTERVAL 1 HOUR), 'cancelled')
        """)
    conn.commit()
    cur.close()

    def fn():
        cur = conn.cursor()
        cur.execute("DELETE FROM events WHERE status='cancelled' AND name='DEL_TEST'")
        conn.commit()
        cur.close()
    return measure(fn)


def s23_delete_old_payments(conn) -> float:
    def fn():
        cur = conn.cursor()
        cur.execute("""
            DELETE FROM payments
            WHERE payment_date < DATE_SUB(NOW(), INTERVAL 1 YEAR)
        """)
        conn.commit()
        cur.close()
    return measure(fn)


def s24_delete_zone_cascade(conn) -> float:
    cur = conn.cursor()
    event_id = rand_id(cur, "events")
    zone_id = rand_id(cur, "event_zones")
    perks = json.dumps({"lounge_access": False, "backstage_pass": False, "free_drink": False})
    cur.execute("""
        INSERT INTO tickets
          (event_id, zone_id, ticket_type, total_quantity,
           available_quantity, price, perks, status)
        VALUES (%s,%s,'DEL_TEST',1,1,10.00,%s,'available')
    """, (event_id, zone_id, perks))
    ticket_id = cur.lastrowid
    conn.commit()
    cur.close()

    def fn():
        cur = conn.cursor()
        cur.execute("DELETE FROM tickets WHERE id=%s", (ticket_id,))
        conn.commit()
        cur.close()
    return measure(fn)


SCENARIO_FUNCTIONS = {
    1: s01_insert_one_user, 2: s02_insert_100_users,
    3: s03_insert_event_with_json, 4: s04_insert_booking_with_tickets,
    5: s05_insert_review, 6: s06_insert_one_ticket,
    7: s07_select_user_by_email, 8: s08_select_events_by_city,
    9: s09_select_booking_with_joins, 10: s10_aggregate_avg_rating,
    11: s11_select_events_by_json_field, 12: s12_select_tickets_with_lounge,
    13: s13_update_booking_status, 14: s14_update_ticket_quantity,
    15: s15_update_100_events_status, 16: s16_update_user_data,
    17: s17_update_json_field, 18: s18_update_vip_prices,
    19: s19_delete_review, 20: s20_delete_booking_cascade,
    21: s21_delete_user_cascade, 22: s22_delete_cancelled_events,
    23: s23_delete_old_payments, 24: s24_delete_zone_cascade,
}


def run_all_scenarios(repeats: int = 3) -> list:
    conn    = get_conn()
    results = []
    print("  [MySQL] Uruchamiam scenariusze...")
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
        results.append({"scenario_id": sid, "times": times, "avg": avg})
        print(f"    S{sid:02d}: {avg:.6f}s  (próby: {times})" if avg else f"    S{sid:02d}: BŁĄD")
    conn.close()
    return results


INDEXES = [
    "CREATE INDEX idx_users_email      ON users(email)",
    "CREATE INDEX idx_users_status     ON users(status)",
    "CREATE INDEX idx_venues_city      ON venues(city)",
    "CREATE INDEX idx_events_status    ON events(status)",
    "CREATE INDEX idx_events_start     ON events(start_date)",
    "CREATE INDEX idx_events_category  ON events(category_id)",
    "CREATE INDEX idx_events_venue     ON events(venue_id)",
    "CREATE INDEX idx_tickets_event    ON tickets(event_id)",
    "CREATE INDEX idx_tickets_zone     ON tickets(zone_id)",
    "CREATE INDEX idx_tickets_status   ON tickets(status)",
    "CREATE INDEX idx_bookings_user    ON bookings(user_id)",
    "CREATE INDEX idx_bookings_status  ON bookings(status)",
    "CREATE INDEX idx_bookings_date    ON bookings(booking_date)",
    "CREATE INDEX idx_reviews_event    ON reviews(event_id)",
    "CREATE INDEX idx_reviews_user     ON reviews(user_id)",
]

DROP_INDEXES = [
    "DROP INDEX idx_users_email     ON users",
    "DROP INDEX idx_users_status    ON users",
    "DROP INDEX idx_venues_city     ON venues",
    "DROP INDEX idx_events_status   ON events",
    "DROP INDEX idx_events_start    ON events",
    "DROP INDEX idx_events_category ON events",
    "DROP INDEX idx_events_venue    ON events",
    "DROP INDEX idx_tickets_event   ON tickets",
    "DROP INDEX idx_tickets_zone    ON tickets",
    "DROP INDEX idx_tickets_status  ON tickets",
    "DROP INDEX idx_bookings_user   ON bookings",
    "DROP INDEX idx_bookings_status ON bookings",
    "DROP INDEX idx_bookings_date   ON bookings",
    "DROP INDEX idx_reviews_event   ON reviews",
    "DROP INDEX idx_reviews_user    ON reviews",
]


def create_indexes():
    conn = get_conn()
    cur  = conn.cursor()
    for sql in INDEXES:
        try:
            cur.execute(sql)
        except Exception:
            pass  # indeks już istnieje
    conn.commit()
    cur.close()
    conn.close()
    print("  [MySQL] ✅ Indeksy utworzone")


def drop_indexes():
    conn = get_conn()
    cur  = conn.cursor()
    for sql in DROP_INDEXES:
        try:
            cur.execute(sql)
        except Exception:
            pass
    conn.commit()
    cur.close()
    conn.close()
    print("  [MySQL] ✅ Indeksy usunięte")
