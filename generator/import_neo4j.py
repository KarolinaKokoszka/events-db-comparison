"""
import_neo4j.py – Import danych do Neo4j (model grafowy).

Węzły: User, Event, Venue, Organizer, Category, Zone, Booking, Ticket, Payment
Relacje:
  (User)-[:MADE_BOOKING]->(Booking)
  (Booking)-[:CONTAINS]->(Ticket)
  (Booking)-[:HAS_PAYMENT]->(Payment)
  (Ticket)-[:FOR_EVENT]->(Event)
  (Ticket)-[:IN_ZONE]->(Zone)
  (Event)-[:HAS_ZONE]->(Zone)
  (Event)-[:HELD_AT]->(Venue)
  (Event)-[:ORGANIZED_BY]->(Organizer)
  (Event)-[:BELONGS_TO]->(Category)
  (User)-[:REVIEWED {rating, comment}]->(Event)
  (User)-[:ATTENDED]->(Event)   ← z paid bookings

Użycie:
  python import_neo4j.py
"""

import json
import os
from neo4j import GraphDatabase
from tqdm import tqdm

# ─────────────────────────────────────────────
# KONFIGURACJA
# ─────────────────────────────────────────────
NEO4J_URI      = "bolt://localhost:7687"
NEO4J_USER     = "neo4j"
NEO4J_PASSWORD = "test1234"
DATA_DIR       = "data"
BATCH          = 1_000


# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────
def load(name: str) -> list:
    path = os.path.join(DATA_DIR, f"{name}.json")
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def run_batch(session, query: str, data: list, desc: str):
    for i in tqdm(range(0, len(data), BATCH), desc=f"  → {desc}", unit="batch"):
        session.run(query, rows=data[i:i + BATCH])


# ─────────────────────────────────────────────
# IMPORT FUNKCJE
# ─────────────────────────────────────────────
def import_categories(session, categories):
    q = """
    UNWIND $rows AS row
    MERGE (c:Category {name: row.name})
    """
    run_batch(session, q, categories, "Category")


def import_organizers(session, organizers):
    q = """
    UNWIND $rows AS row
    MERGE (o:Organizer {organizer_id: row.id})
    SET o.name  = row.name,
        o.email = row.email,
        o.phone = row.phone
    """
    run_batch(session, q, organizers, "Organizer")


def import_venues(session, venues):
    q = """
    UNWIND $rows AS row
    MERGE (v:Venue {venue_id: row.id})
    SET v.name        = row.name,
        v.street      = row.street,
        v.city        = row.city,
        v.postal_code = row.postal_code,
        v.country     = row.country,
        v.capacity    = row.capacity
    """
    run_batch(session, q, venues, "Venue")


def import_users(session, users):
    q = """
    UNWIND $rows AS row
    MERGE (u:User {email: row.email})
    SET u.user_id    = row.id,
        u.first_name = row.first_name,
        u.last_name  = row.last_name,
        u.phone      = row.phone,
        u.status     = row.status,
        u.created_at = row.created_at
    """
    run_batch(session, q, users, "User")


def import_events(session, events, categories, organizers, venues):
    cat_map  = {c["id"]: c["name"] for c in categories}
    org_map  = {o["id"]: o["id"]   for o in organizers}
    venue_map = {v["id"]: v["id"]  for v in venues}

    rows = []
    for e in events:
        try:
            add_info = json.loads(e["additional_info"]) if e["additional_info"] else {}
        except Exception:
            add_info = {}
        rows.append({
            "id":           e["id"],
            "name":         e["name"],
            "status":       e["status"],
            "start_date":   e["start_date"],
            "end_date":     e["end_date"],
            "category":     cat_map.get(e["category_id"]),
            "organizer_id": e["organizer_id"],
            "venue_id":     e["venue_id"],
            "age_limit":    add_info.get("age_limit"),
            "parking":      add_info.get("parking"),
        })

    # Utwórz węzły Event
    q_node = """
    UNWIND $rows AS row
    MERGE (e:Event {event_id: row.id})
    SET e.name       = row.name,
        e.status     = row.status,
        e.start_date = row.start_date,
        e.end_date   = row.end_date,
        e.category   = row.category,
        e.age_limit  = row.age_limit,
        e.parking    = row.parking
    """
    run_batch(session, q_node, rows, "Event (nodes)")

    # Relacja HELD_AT
    q_venue = """
    UNWIND $rows AS row
    MATCH (e:Event {event_id: row.id})
    MATCH (v:Venue {venue_id: row.venue_id})
    MERGE (e)-[:HELD_AT]->(v)
    """
    run_batch(session, q_venue, rows, "Event-HELD_AT-Venue")

    # Relacja ORGANIZED_BY
    q_org = """
    UNWIND $rows AS row
    MATCH (e:Event {event_id: row.id})
    MATCH (o:Organizer {organizer_id: row.organizer_id})
    MERGE (e)-[:ORGANIZED_BY]->(o)
    """
    run_batch(session, q_org, rows, "Event-ORGANIZED_BY-Organizer")

    # Relacja BELONGS_TO
    q_cat = """
    UNWIND $rows AS row
    MATCH (e:Event {event_id: row.id})
    MATCH (c:Category {name: row.category})
    MERGE (e)-[:BELONGS_TO]->(c)
    """
    run_batch(session, q_cat, rows, "Event-BELONGS_TO-Category")


def import_zones(session, zones):
    rows = []
    for z in zones:
        rows.append({
            "zone_id": z["id"],
            "event_id": z["event_id"],
            "name": z["name"],
            "type": z["type"],
            "capacity": z["capacity"],
        })

    q = """
    UNWIND $rows AS row
    MERGE (z:Zone {zone_id: row.zone_id})
    SET z.name = row.name,
        z.type = row.type,
        z.capacity = row.capacity
    WITH z, row
    MATCH (e:Event {event_id: row.event_id})
    MERGE (e)-[:HAS_ZONE]->(z)
    """
    run_batch(session, q, rows, "Zone + HAS_ZONE")


def import_tickets(session, tickets, zones):
    zone_map = {z["id"]: z for z in zones}
    rows = []
    for t in tickets:
        z = zone_map.get(t["zone_id"], {})
        rows.append({
            "id":                 t["id"],
            "event_id":           t["event_id"],
            "ticket_type":        t["ticket_type"],
            "price":              float(t["price"]),
            "total_quantity":     t["total_quantity"],
            "available_quantity": t["available_quantity"],
            "status":             t["status"],
            "zone_id":            t["zone_id"],
            "zone_name":          z.get("name"),
            "zone_type":          z.get("type"),
        })

    q = """
    UNWIND $rows AS row
    MERGE (t:Ticket {ticket_id: row.id})
    SET t.ticket_type        = row.ticket_type,
        t.price              = row.price,
        t.total_quantity     = row.total_quantity,
        t.available_quantity = row.available_quantity,
        t.status             = row.status,
        t.zone_name          = row.zone_name,
        t.zone_type          = row.zone_type
    WITH t, row
    MATCH (e:Event {event_id: row.event_id})
    MERGE (t)-[:FOR_EVENT]->(e)
    WITH t, row
    OPTIONAL MATCH (z:Zone {zone_id: row.zone_id})
    FOREACH (_ IN CASE WHEN z IS NULL THEN [] ELSE [1] END |
        MERGE (t)-[:IN_ZONE]->(z)
    )
    """
    run_batch(session, q, rows, "Ticket + FOR_EVENT")


def import_bookings(session, bookings, booking_tickets, payments):
    pay_map = {p["booking_id"]: p for p in payments}
    bt_map  = {}
    for bt in booking_tickets:
        bt_map.setdefault(bt["booking_id"], []).append(bt["ticket_id"])

    rows = []
    for b in bookings:
        pay = pay_map.get(b["id"])
        rows.append({
            "id":           b["id"],
            "user_id":      b["user_id"],
            "booking_date": b["booking_date"],
            "status":       b["status"],
            "total_price":  float(b["total_price"]),
            "pay_method":   pay["payment_method"] if pay else None,
            "pay_status":   pay["status"] if pay else None,
            "ticket_ids":   bt_map.get(b["id"], []),
        })

    # Węzły Booking + relacja MADE_BOOKING
    q_booking = """
    UNWIND $rows AS row
    MERGE (b:Booking {booking_id: row.id})
    SET b.booking_date  = row.booking_date,
        b.status        = row.status,
        b.total_price   = row.total_price,
        b.pay_method    = row.pay_method,
        b.pay_status    = row.pay_status
    WITH b, row
    MATCH (u:User {user_id: row.user_id})
    MERGE (u)-[:MADE_BOOKING]->(b)
    """
    run_batch(session, q_booking, rows, "Booking + MADE_BOOKING")

    # Relacja CONTAINS
    bt_rows = []
    for b in bookings:
        for tid in bt_map.get(b["id"], []):
            bt_rows.append({"booking_id": b["id"], "ticket_id": tid})

    q_contains = """
    UNWIND $rows AS row
    MATCH (b:Booking {booking_id: row.booking_id})
    MATCH (t:Ticket  {ticket_id:  row.ticket_id})
    MERGE (b)-[:CONTAINS]->(t)
    """
    run_batch(session, q_contains, bt_rows, "Booking-CONTAINS-Ticket")

    # Relacja ATTENDED (z paid bookings)
    attended_rows = []
    for b in bookings:
        if b["status"] == "paid":
            for tid in bt_map.get(b["id"], []):
                attended_rows.append({
                    "user_id":   b["user_id"],
                    "ticket_id": tid,
                })

    q_attended = """
    UNWIND $rows AS row
    MATCH (u:User {user_id: row.user_id})
    MATCH (t:Ticket {ticket_id: row.ticket_id})-[:FOR_EVENT]->(e:Event)
    MERGE (u)-[:ATTENDED]->(e)
    """
    run_batch(session, q_attended, attended_rows, "User-ATTENDED-Event")


def import_payments(session, payments):
    q = """
    UNWIND $rows AS row
    MERGE (p:Payment {payment_id: row.id})
    SET p.payment_method = row.payment_method,
        p.amount = row.amount,
        p.payment_date = row.payment_date,
        p.status = row.status
    WITH p, row
    MATCH (b:Booking {booking_id: row.booking_id})
    MERGE (b)-[:HAS_PAYMENT]->(p)
    """
    rows = []
    for p in payments:
        rows.append({
            "id": p["id"],
            "booking_id": p["booking_id"],
            "payment_method": p["payment_method"],
            "amount": float(p["amount"]) if p["amount"] is not None else None,
            "payment_date": p["payment_date"],
            "status": p["status"],
        })
    run_batch(session, q, rows, "Payment + HAS_PAYMENT")


def import_reviews(session, reviews):
    q = """
    UNWIND $rows AS row
    MATCH (u:User  {user_id:  row.user_id})
    MATCH (e:Event {event_id: row.event_id})
    MERGE (u)-[r:REVIEWED]->(e)
    SET r.rating     = row.rating,
        r.comment    = row.comment,
        r.created_at = row.created_at
    """
    run_batch(session, q, reviews, "REVIEWED")


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────
def main():
    print("\n🔵 Import do Neo4j...\n")

    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

    with driver.session() as session:
        print("📂 Wczytywanie plików JSON...")
        categories     = load("categories")
        organizers     = load("organizers")
        venues         = load("venues")
        users          = load("users")
        events         = load("events")
        zones          = load("event_zones")
        tickets        = load("tickets")
        bookings       = load("bookings")
        booking_tickets = load("booking_tickets")
        payments       = load("payments")
        reviews        = load("reviews")

        print("\n📥 Import węzłów i relacji...")
        import_categories(session, categories)
        import_organizers(session, organizers)
        import_venues(session, venues)
        import_users(session, users)
        import_events(session, events, categories, organizers, venues)
        import_zones(session, zones)
        import_tickets(session, tickets, zones)
        import_bookings(session, bookings, booking_tickets, payments)
        import_payments(session, payments)
        import_reviews(session, reviews)

        # Podsumowanie
        print("\n📊 Weryfikacja...")
        for label in ["User", "Event", "Venue", "Organizer", "Category", "Zone", "Booking", "Ticket", "Payment"]:
            result = session.run(f"MATCH (n:{label}) RETURN count(n) AS cnt")
            cnt = result.single()["cnt"]
            print(f"   {label}: {cnt:,}")

        for rel in ["MADE_BOOKING", "CONTAINS", "FOR_EVENT", "HELD_AT",
                    "ORGANIZED_BY", "BELONGS_TO", "HAS_ZONE", "IN_ZONE",
                    "HAS_PAYMENT", "REVIEWED", "ATTENDED"]:
            result = session.run(f"MATCH ()-[r:{rel}]->() RETURN count(r) AS cnt")
            cnt = result.single()["cnt"]
            print(f"   [:{rel}]: {cnt:,}")

    driver.close()
    print("\n✅ Neo4j – import zakończony pomyślnie!\n")


if __name__ == "__main__":
    main()
