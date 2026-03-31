"""
crud_neo4j.py – 24 scenariusze testowe dla Neo4j.
Poprawki:
  - SKIP musi być przed LIMIT w Cypher
  - S19: SKIP przed LIMIT w zapytaniu pomocniczym
"""

import time
import random
import uuid
from datetime import datetime, timedelta
from neo4j import GraphDatabase

NEO4J_URI      = "bolt://localhost:7687"
NEO4J_USER     = "neo4j"
NEO4J_PASSWORD = "test1234"

def get_driver():
    return GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

def measure(fn) -> float:
    start = time.perf_counter()
    fn()
    return round(time.perf_counter() - start, 6)


# ════════════════════════════════════════════
# CREATE 1-6
# ════════════════════════════════════════════
def s01_insert_one_user(driver) -> float:
    def fn():
        with driver.session() as s:
            uid = uuid.uuid4().hex[:8]
            s.run("""
                CREATE (u:User {
                    user_id:    $uid,
                    first_name: 'Test',
                    last_name:  'User',
                    email:      $email,
                    status:     'active',
                    created_at: $now
                })
            """, uid=uid, email=f"test_{uid}@test.pl",
               now=datetime.utcnow().isoformat())
    return measure(fn)


def s02_insert_100_users(driver) -> float:
    def fn():
        with driver.session() as s:
            rows = [{"uid": uuid.uuid4().hex[:8], "i": i} for i in range(100)]
            s.run("""
                UNWIND $rows AS row
                CREATE (u:User {
                    user_id:    row.uid,
                    first_name: 'Bulk',
                    last_name:  toString(row.i),
                    email:      row.uid + '@bulk.pl',
                    status:     'active'
                })
            """, rows=rows)
    return measure(fn)


def s03_insert_event_with_json(driver) -> float:
    """Dane półustrukturalne – właściwości eventu z age_limit, parking, languages."""
    def fn():
        with driver.session() as s:
            eid = uuid.uuid4().hex[:8]
            s.run("""
                CREATE (e:Event {
                    event_id:   $eid,
                    name:       'Test Event',
                    status:     'planned',
                    start_date: $start,
                    end_date:   $end,
                    category:   'Muzyka',
                    age_limit:  18,
                    parking:    true,
                    languages:  ['PL', 'EN']
                })
            """, eid=eid,
               start=(datetime.utcnow() + timedelta(days=10)).isoformat(),
               end=(datetime.utcnow() + timedelta(days=10, hours=3)).isoformat())
    return measure(fn)


def s04_insert_booking_with_tickets(driver) -> float:
    def fn():
        with driver.session() as s:
            # POPRAWKA: SKIP przed LIMIT
            user   = s.run("MATCH (u:User)   RETURN u SKIP toInteger(rand()*100) LIMIT 1").single()
            ticket = s.run("MATCH (t:Ticket) RETURN t SKIP toInteger(rand()*100) LIMIT 1").single()
            if not user or not ticket:
                return
            bid = uuid.uuid4().hex[:8]
            s.run("""
                MATCH (u:User   {user_id:   $uid})
                MATCH (t:Ticket {ticket_id: $tid})
                CREATE (b:Booking {
                    booking_id:   $bid,
                    booking_date: $now,
                    status:       'pending',
                    total_price:  150.0
                })
                CREATE (u)-[:MADE_BOOKING]->(b)
                CREATE (b)-[:CONTAINS {quantity: 1, price_at_purchase: 150.0}]->(t)
                CREATE (p:Payment {
                    payment_id:   $pid,
                    payment_method:'card',
                    amount:       150.0,
                    payment_date: $now,
                    status:       'pending'
                })
                CREATE (b)-[:HAS_PAYMENT]->(p)
            """, uid=user["u"]["user_id"], tid=ticket["t"]["ticket_id"],
               bid=bid, pid=uuid.uuid4().hex[:12], now=datetime.utcnow().isoformat())
    return measure(fn)


def s05_insert_review(driver) -> float:
    """Wstawienie pojedynczej recenzji user-event."""
    def fn():
        with driver.session() as s:
            user = s.run("MATCH (u:User) RETURN u SKIP toInteger(rand()*50) LIMIT 1").single()
            event = s.run("MATCH (e:Event) RETURN e SKIP toInteger(rand()*50) LIMIT 1").single()
            if not user or not event:
                return
            s.run("""
                MATCH (u:User {user_id: $uid})
                MATCH (e:Event {event_id: $eid})
                MERGE (u)-[r:REVIEWED]->(e)
                SET r.rating = $rating,
                    r.comment = 'Komentarz testowy',
                    r.created_at = $now
            """,
            uid=user["u"]["user_id"],
            eid=event["e"]["event_id"],
            rating=random.randint(1, 5),
            now=datetime.utcnow().isoformat())
    return measure(fn)


def s06_insert_one_ticket(driver) -> float:
    def fn():
        with driver.session() as s:
            row = s.run("""
                MATCH (e:Event)-[:HAS_ZONE]->(z:Zone)
                RETURN e.event_id AS eid, z.zone_id AS zid
                SKIP toInteger(rand()*100) LIMIT 1
            """).single()
            if not row:
                return
            s.run("""
                MATCH (e:Event {event_id: $eid})
                MATCH (z:Zone {zone_id: $zid})
                CREATE (t:Ticket {
                    ticket_id: $tid,
                    ticket_type: 'Standard',
                    price: 99.99,
                    total_quantity: 100,
                    available_quantity: 100,
                    status: 'available',
                    lounge_access: false
                })
                CREATE (t)-[:FOR_EVENT]->(e)
                CREATE (t)-[:IN_ZONE]->(z)
            """, eid=row["eid"], zid=row["zid"], tid=uuid.uuid4().hex[:12])
    return measure(fn)


# ════════════════════════════════════════════
# READ 7-12
# ════════════════════════════════════════════
def s07_select_user_by_email(driver) -> float:
    with driver.session() as s:
        user = s.run("MATCH (u:User) RETURN u.email AS email LIMIT 1").single()
    if not user:
        return 0.0
    email = user["email"]

    def fn():
        with driver.session() as s:
            s.run("MATCH (u:User {email: $email}) RETURN u", email=email).single()
    return measure(fn)


def s08_select_events_by_city(driver) -> float:
    with driver.session() as s:
        row = s.run("MATCH (e:Event) RETURN e.status AS st SKIP toInteger(rand()*50) LIMIT 1").single()
    st = row["st"] if row else "planned"
    left = (datetime.utcnow() - timedelta(days=365)).isoformat()
    right = (datetime.utcnow() + timedelta(days=365)).isoformat()

    def fn():
        with driver.session() as s:
            list(s.run("""
                MATCH (e:Event)
                WHERE e.status = $st
                  AND e.start_date >= $left
                  AND e.start_date <= $right
                RETURN e.name, e.status, e.start_date
            """, st=st, left=left, right=right))
    return measure(fn)


def s09_select_booking_with_joins(driver) -> float:
    with driver.session() as s:
        row = s.run(
            "MATCH (b:Booking) RETURN b.booking_id AS bid SKIP toInteger(rand()*100) LIMIT 1"
        ).single()
    if not row:
        return 0.0
    bid = row["bid"]

    def fn():
        with driver.session() as s:
            list(s.run("""
                MATCH (u:User)-[:MADE_BOOKING]->(b:Booking {booking_id: $bid})
                      -[:CONTAINS]->(t:Ticket)-[:FOR_EVENT]->(e:Event)
                OPTIONAL MATCH (b)-[:HAS_PAYMENT]->(p:Payment)
                RETURN u.email, b.status, b.total_price, t.ticket_type, e.name, p.status
            """, bid=bid))
    return measure(fn)


def s10_aggregate_avg_rating(driver) -> float:
    def fn():
        with driver.session() as s:
            list(s.run("""
                MATCH (:User)-[r:REVIEWED]->(e:Event)
                RETURN e.event_id AS event_id, e.name AS event_name,
                       round(avg(r.rating)*100)/100 AS avg_rating,
                       count(r) AS reviews
                ORDER BY avg_rating DESC
                LIMIT 50
            """))
    return measure(fn)


def s11_select_events_by_json_field(driver) -> float:
    """Dane półustrukturalne – filtrowanie po właściwości age_limit węzła Event."""
    def fn():
        with driver.session() as s:
            list(s.run("""
                MATCH (e:Event)
                WHERE e.age_limit = 18
                RETURN e.name, e.age_limit
            """))
    return measure(fn)


def s12_select_tickets_with_lounge(driver) -> float:
    """Top eventy po liczbie bookingow."""
    def fn():
        with driver.session() as s:
            list(s.run("""
                MATCH (:User)-[:MADE_BOOKING]->(b:Booking)-[:CONTAINS]->(:Ticket)-[:FOR_EVENT]->(e:Event)
                RETURN e.event_id AS event_id, e.name AS event_name, count(b) AS bookings_count
                ORDER BY bookings_count DESC
                LIMIT 20
            """))
    return measure(fn)


# ════════════════════════════════════════════
# UPDATE 13-18
# ════════════════════════════════════════════
def s13_update_booking_status(driver) -> float:
    with driver.session() as s:
        row = s.run(
            "MATCH (b:Booking) RETURN b.booking_id AS bid SKIP toInteger(rand()*100) LIMIT 1"
        ).single()
    if not row:
        return 0.0
    bid = row["bid"]

    def fn():
        with driver.session() as s:
            s.run("MATCH (b:Booking {booking_id:$bid}) SET b.status='paid'", bid=bid)
    return measure(fn)


def s14_update_ticket_quantity(driver) -> float:
    with driver.session() as s:
        row = s.run(
            "MATCH (t:Ticket) RETURN t.ticket_id AS tid SKIP toInteger(rand()*100) LIMIT 1"
        ).single()
    if not row:
        return 0.0
    tid = row["tid"]

    def fn():
        with driver.session() as s:
            s.run("""
                MATCH (t:Ticket {ticket_id: $tid})
                SET t.available_quantity = CASE
                    WHEN t.available_quantity > 0 THEN t.available_quantity - 1
                    ELSE 0 END
            """, tid=tid)
    return measure(fn)


def s15_update_100_events_status(driver) -> float:
    def fn():
        with driver.session() as s:
            rows = list(s.run("MATCH (e:Event) RETURN e.event_id AS eid LIMIT 100"))
            ids  = [r["eid"] for r in rows]
            s.run("""
                UNWIND $ids AS eid
                MATCH (e:Event {event_id: eid})
                SET e.status = 'finished'
            """, ids=ids)
    return measure(fn)


def s16_update_user_data(driver) -> float:
    with driver.session() as s:
        row = s.run(
            "MATCH (u:User) RETURN u.user_id AS uid SKIP toInteger(rand()*100) LIMIT 1"
        ).single()
    if not row:
        return 0.0
    uid = row["uid"]

    def fn():
        with driver.session() as s:
            s.run("MATCH (u:User {user_id:$uid}) SET u.phone='600-700-800'", uid=uid)
    return measure(fn)


def s17_update_json_field(driver) -> float:
    """Dane półustrukturalne – dodanie języka do tablicy languages węzła Event."""
    with driver.session() as s:
        row = s.run(
            "MATCH (e:Event) RETURN e.event_id AS eid SKIP toInteger(rand()*50) LIMIT 1"
        ).single()
    if not row:
        return 0.0
    eid = row["eid"]

    def fn():
        with driver.session() as s:
            s.run("""
                MATCH (e:Event {event_id: $eid})
                SET e.languages = CASE
                    WHEN e.languages IS NULL        THEN ['DE']
                    WHEN NOT 'DE' IN e.languages    THEN e.languages + ['DE']
                    ELSE e.languages END
            """, eid=eid)
    return measure(fn)


def s18_update_vip_prices(driver) -> float:
    def fn():
        with driver.session() as s:
            s.run("""
                MATCH (t:Ticket {ticket_type: 'VIP'})
                SET t.price = round(t.price * 1.1 * 100) / 100
            """)
    return measure(fn)


# ════════════════════════════════════════════
# DELETE 19-24
# ════════════════════════════════════════════
def s19_delete_review(driver) -> float:
    with driver.session() as s:
        row = s.run("""
            MATCH (u:User)-[r:REVIEWED]->(e:Event)
            RETURN u.user_id AS uid, e.event_id AS eid
            SKIP toInteger(rand()*100) LIMIT 1
        """).single()
    if not row:
        return 0.0
    uid = row["uid"]
    eid = row["eid"]

    def fn():
        with driver.session() as s:
            s.run("""
                MATCH (u:User {user_id:$uid})-[r:REVIEWED]->(e:Event {event_id:$eid})
                DELETE r
            """, uid=uid, eid=eid)
    return measure(fn)


def s20_delete_booking_cascade(driver) -> float:
    with driver.session() as s:
        row = s.run(
            "MATCH (b:Booking) RETURN b.booking_id AS bid SKIP toInteger(rand()*100) LIMIT 1"
        ).single()
    if not row:
        return 0.0
    bid = row["bid"]

    def fn():
        with driver.session() as s:
            s.run("""
                MATCH (b:Booking {booking_id:$bid})
                DETACH DELETE b
            """, bid=bid)
    return measure(fn)


def s21_delete_user_cascade(driver) -> float:
    uid = uuid.uuid4().hex[:8]
    with driver.session() as s:
        s.run("CREATE (u:User {user_id:$uid, email:$email, status:'active'})",
              uid=uid, email=f"del_{uid}@test.pl")

    def fn():
        with driver.session() as s:
            s.run("MATCH (u:User {user_id:$uid}) DETACH DELETE u", uid=uid)
    return measure(fn)


def s22_delete_cancelled_events(driver) -> float:
    ids = [uuid.uuid4().hex[:8] for _ in range(5)]
    with driver.session() as s:
        s.run("""
            UNWIND $ids AS eid
            CREATE (e:Event {event_id:eid, name:'DEL_TEST', status:'cancelled'})
        """, ids=ids)

    def fn():
        with driver.session() as s:
            s.run("""
                MATCH (e:Event {status:'cancelled', name:'DEL_TEST'})
                DETACH DELETE e
            """)
    return measure(fn)


def s23_delete_old_payments(driver) -> float:
    def fn():
        with driver.session() as s:
            cutoff = (datetime.utcnow() - timedelta(days=365)).isoformat()
            s.run("""
                MATCH (b:Booking)-[:HAS_PAYMENT]->(p:Payment)
                WHERE p.payment_date < $cutoff
                DETACH DELETE p
            """, cutoff=cutoff)
    return measure(fn)


def s24_delete_zone_cascade(driver) -> float:
    with driver.session() as s:
        row = s.run("""
            MATCH (e:Event)-[:HAS_ZONE]->(z:Zone)
            RETURN e.event_id AS eid, z.zone_id AS zid
            LIMIT 1
        """).single()
        if not row:
            return 0.0
        tid = uuid.uuid4().hex[:12]
        s.run("""
            MATCH (e:Event {event_id:$eid})
            MATCH (z:Zone {zone_id:$zid})
            CREATE (t:Ticket {ticket_id:$tid, ticket_type:'DEL_TEST', price:10.0, total_quantity:1, available_quantity:1, status:'available'})
            CREATE (t)-[:FOR_EVENT]->(e)
            CREATE (t)-[:IN_ZONE]->(z)
        """, eid=row["eid"], zid=row["zid"], tid=tid)

    def fn():
        with driver.session() as s:
            s.run("MATCH (t:Ticket {ticket_id:$tid}) DETACH DELETE t", tid=tid)
    return measure(fn)


# ════════════════════════════════════════════
# MAPA SCENARIUSZY
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
    driver  = get_driver()
    results = []
    print("  [Neo4j] Uruchamiam scenariusze...")
    for sid, fn in SCENARIO_FUNCTIONS.items():
        times = []
        for attempt in range(1, repeats + 1):
            try:
                t = fn(driver)
                times.append(t)
            except Exception as e:
                print(f"    ⚠ S{sid} próba {attempt}: {e}")
                times.append(None)
        valid = [t for t in times if t is not None]
        avg   = round(sum(valid) / len(valid), 6) if valid else None
        results.append({"scenario_id": sid, "times": times, "avg": avg})
        if avg:
            print(f"    S{sid:02d}: {avg:.6f}s  (próby: {times})")
        else:
            print(f"    S{sid:02d}: BŁĄD")
    driver.close()
    return results


# ════════════════════════════════════════════
# ZARZĄDZANIE INDEKSAMI
# ════════════════════════════════════════════
def create_indexes():
    driver = get_driver()
    queries = [
        "CREATE INDEX idx_user_email    IF NOT EXISTS FOR (u:User)    ON (u.email)",
        "CREATE INDEX idx_user_status   IF NOT EXISTS FOR (u:User)    ON (u.status)",
        "CREATE INDEX idx_event_status  IF NOT EXISTS FOR (e:Event)   ON (e.status)",
        "CREATE INDEX idx_event_start   IF NOT EXISTS FOR (e:Event)   ON (e.start_date)",
        "CREATE INDEX idx_event_cat     IF NOT EXISTS FOR (e:Event)   ON (e.category)",
        "CREATE INDEX idx_event_age     IF NOT EXISTS FOR (e:Event)   ON (e.age_limit)",
        "CREATE INDEX idx_venue_city    IF NOT EXISTS FOR (v:Venue)   ON (v.city)",
        "CREATE INDEX idx_booking_stat  IF NOT EXISTS FOR (b:Booking) ON (b.status)",
        "CREATE INDEX idx_ticket_type   IF NOT EXISTS FOR (t:Ticket)  ON (t.ticket_type)",
        "CREATE INDEX idx_ticket_lounge IF NOT EXISTS FOR (t:Ticket)  ON (t.lounge_access)",
    ]
    with driver.session() as s:
        for q in queries:
            s.run(q)
    driver.close()
    print("  [Neo4j] ✅ Indeksy utworzone")


def drop_indexes():
    driver = get_driver()
    names = [
        "idx_user_email", "idx_user_status",
        "idx_event_status", "idx_event_start", "idx_event_cat", "idx_event_age",
        "idx_venue_city",
        "idx_booking_stat",
        "idx_ticket_type", "idx_ticket_lounge",
    ]
    with driver.session() as s:
        for name in names:
            try:
                s.run(f"DROP INDEX {name} IF EXISTS")
            except Exception:
                pass
    driver.close()
    print("  [Neo4j] ✅ Indeksy usunięte")
