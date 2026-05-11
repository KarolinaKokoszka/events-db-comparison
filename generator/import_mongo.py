"""
import_mongo.py – Import danych do MongoDB (model dokumentowy).

Schemat jest INNY niż relacyjny – denormalizacja:
  • users     → embedded addresses
  • events    → embedded organizer, venue, zones, tickets
  • bookings  → embedded payment, snapshot pozycji
  • reviews   → referencje (user_id, event_id jako int)

Użycie:
  python import_mongo.py
"""

import json
import os
from datetime import datetime

from pymongo import MongoClient, InsertOne, ASCENDING
from pymongo.errors import BulkWriteError
from tqdm import tqdm

# ─────────────────────────────────────────────
# KONFIGURACJA
# ─────────────────────────────────────────────
MONGO_URI = "mongodb://localhost:27017"
DB_NAME   = "eventsdb"
DATA_DIR  = "data"
BATCH     = 2_000


# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────
def load(name: str) -> list:
    path = os.path.join(DATA_DIR, f"{name}.json")
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def parse_dt(s):
    if not s:
        return None
    try:
        return datetime.strptime(s, "%Y-%m-%d %H:%M:%S")
    except Exception:
        return s


def bulk_write(collection, docs: list):
    ops = [InsertOne(d) for d in docs]
    for i in tqdm(range(0, len(ops), BATCH), desc=f"  → {collection.name}", unit="batch"):
        try:
            collection.bulk_write(ops[i:i + BATCH], ordered=False)
        except BulkWriteError as e:
            # Ignoruj duplikaty
            pass


# ─────────────────────────────────────────────
# BUDOWANIE DOKUMENTÓW (denormalizacja)
# ─────────────────────────────────────────────
def build_users(raw_users: list, raw_addresses: list) -> list:
    """Użytkownicy z wbudowanymi adresami."""
    addr_map = {}
    for a in raw_addresses:
        addr_map.setdefault(a["user_id"], []).append({
            "street":      a["street"],
            "city":        a["city"],
            "postal_code": a["postal_code"],
            "country":     a["country"],
            "type":        a["type"],
            "created_at":  parse_dt(a["created_at"]),
        })

    docs = []
    for u in raw_users:
        docs.append({
            "_id":          u["id"],          # używamy id liczbowego jako _id
            "first_name":   u["first_name"],
            "last_name":    u["last_name"],
            "email":        u["email"],
            "password_hash": u["password_hash"],
            "phone":        u["phone"],
            "status":       u["status"],
            "addresses":    addr_map.get(u["id"], []),
            "created_at":   parse_dt(u["created_at"]),
            "updated_at":   parse_dt(u["updated_at"]),
        })
    return docs


def build_events(raw_events, raw_organizers, raw_venues, raw_categories,
                 raw_zones, raw_tickets) -> list:
    """Wydarzenia z wbudowanymi: organizer, venue, zones+tickets."""
    org_map  = {o["id"]: o for o in raw_organizers}
    venue_map = {v["id"]: v for v in raw_venues}
    cat_map  = {c["id"]: c["name"] for c in raw_categories}

    # Indeks biletów po zone_id
    ticket_by_zone = {}
    for t in raw_tickets:
        ticket_by_zone.setdefault(t["zone_id"], []).append(t)

    # Indeks stref po event_id
    zone_by_event = {}
    for z in raw_zones:
        zone_by_event.setdefault(z["event_id"], []).append(z)

    docs = []
    for e in raw_events:
        org   = org_map.get(e["organizer_id"], {})
        venue = venue_map.get(e["venue_id"], {})

        # Parsuj additional_info z JSON string
        try:
            add_info = json.loads(e["additional_info"]) if e["additional_info"] else {}
        except Exception:
            add_info = {}

        # Buduj strefy z biletami
        zones_embedded = []
        for z in zone_by_event.get(e["id"], []):
            tickets_embedded = []
            for t in ticket_by_zone.get(z["id"], []):
                try:
                    perks = json.loads(t["perks"]) if t["perks"] else {}
                except Exception:
                    perks = {}
                tickets_embedded.append({
                    "ticket_id":          t["id"],
                    "ticket_type":        t["ticket_type"],
                    "price":              float(t["price"]),
                    "total_quantity":     t["total_quantity"],
                    "available_quantity": t["available_quantity"],
                    "status":             t["status"],
                    "perks":              perks,
                })
            zones_embedded.append({
                "zone_id":  z["id"],
                "name":     z["name"],
                "type":     z["type"],
                "capacity": z["capacity"],
                "tickets":  tickets_embedded,
            })

        docs.append({
            "_id":         e["id"],
            "name":        e["name"],
            "description": e["description"],
            "status":      e["status"],
            "start_date":  parse_dt(e["start_date"]),
            "end_date":    parse_dt(e["end_date"]),
            "category":    cat_map.get(e["category_id"]),
            "additional_info": add_info,
            "organizer": {
                "organizer_id": org.get("id"),
                "name":  org.get("name"),
                "email": org.get("email"),
                "phone": org.get("phone"),
            },
            "venue": {
                "venue_id":    venue.get("id"),
                "name":        venue.get("name"),
                "street":      venue.get("street"),
                "city":        venue.get("city"),
                "postal_code": venue.get("postal_code"),
                "country":     venue.get("country"),
                "capacity":    venue.get("capacity"),
            },
            "zones":      zones_embedded,
            "created_at": parse_dt(e["created_at"]),
        })
    return docs


def build_bookings(raw_bookings, raw_bt, raw_payments, raw_tickets, raw_events) -> list:
    """Rezerwacje z wbudowaną płatnością i snapshotem pozycji."""
    ticket_map  = {t["id"]: t for t in raw_tickets}
    event_map   = {e["id"]: e for e in raw_events}
    payment_map = {p["booking_id"]: p for p in raw_payments}

    bt_by_booking = {}
    for bt in raw_bt:
        bt_by_booking.setdefault(bt["booking_id"], []).append(bt)

    docs = []
    for b in raw_bookings:
        items = []
        for bt in bt_by_booking.get(b["id"], []):
            t = ticket_map.get(bt["ticket_id"], {})
            e = event_map.get(t.get("event_id"), {})
            items.append({
                "event_id":          t.get("event_id"),
                "event_name":        e.get("name", ""),
                "ticket_type":       t.get("ticket_type", ""),
                "zone_id":           t.get("zone_id"),
                "quantity":          bt["quantity"],
                "price_at_purchase": float(bt["price_at_purchase"]),
            })

        pay = payment_map.get(b["id"])
        payment_embedded = None
        if pay:
            payment_embedded = {
                "method":       pay["payment_method"],
                "amount":       float(pay["amount"]) if pay["amount"] else None,
                "payment_date": parse_dt(pay["payment_date"]),
                "status":       pay["status"],
            }

        docs.append({
            "_id":          b["id"],
            "user_id":      b["user_id"],
            "booking_date": parse_dt(b["booking_date"]),
            "status":       b["status"],
            "total_price":  float(b["total_price"]),
            "items":        items,
            "payment":      payment_embedded,
        })
    return docs


def build_reviews(raw_reviews: list) -> list:
    docs = []
    for r in raw_reviews:
        docs.append({
            "_id":       r["id"],
            "user_id":   r["user_id"],
            "event_id":  r["event_id"],
            "rating":    r["rating"],
            "comment":   r["comment"],
            "created_at": parse_dt(r["created_at"]),
        })
    return docs


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────
def main():
    print("\n🍃 Import do MongoDB...\n")

    client = MongoClient(MONGO_URI)
    db     = client[DB_NAME]

    # Wczytaj wszystkie dane
    print("📂 Wczytywanie plików JSON...")
    raw_users      = load("users")
    raw_addresses  = load("user_addresses")
    raw_events_raw = load("events")
    raw_organizers = load("organizers")
    raw_venues     = load("venues")
    raw_categories = load("categories")
    raw_zones      = load("event_zones")
    raw_tickets    = load("tickets")
    raw_bookings   = load("bookings")
    raw_bt         = load("booking_tickets")
    raw_payments   = load("payments")
    raw_reviews    = load("reviews")

    # Buduj dokumenty
    print("\n🔨 Budowanie dokumentów (denormalizacja)...")
    print("  users...")
    users_docs = build_users(raw_users, raw_addresses)
    print("  events...")
    events_docs = build_events(raw_events_raw, raw_organizers, raw_venues,
                               raw_categories, raw_zones, raw_tickets)
    print("  bookings...")
    bookings_docs = build_bookings(raw_bookings, raw_bt, raw_payments,
                                   raw_tickets, raw_events_raw)
    print("  reviews...")
    reviews_docs = build_reviews(raw_reviews)

    # Wyczyść istniejące dokumenty, ale zachowaj walidatory i indeksy kolekcji.
    print("\n🧹 Czyszczenie dokumentów w kolekcjach...")
    for col in ["users", "events", "bookings", "reviews"]:
        db[col].delete_many({})

    # Wstaw dane
    print("\n📥 Wstawianie dokumentów...")
    bulk_write(db["users"],    users_docs)
    bulk_write(db["events"],   events_docs)
    bulk_write(db["bookings"], bookings_docs)
    bulk_write(db["reviews"],  reviews_docs)

    db["users"].drop_indexes()
    db["events"].drop_indexes()
    db["bookings"].drop_indexes()
    db["reviews"].drop_indexes()

    # Indeksy
    print("\n📑 Tworzenie indeksów...")
    db["users"].create_index([("email", ASCENDING)],             unique=True, name="idx_users_email")
    db["users"].create_index([("status", ASCENDING)],            name="idx_users_status")

    db["events"].create_index([("status", ASCENDING)],           name="idx_events_status")
    db["events"].create_index([("start_date", ASCENDING)],       name="idx_events_start_date")
    db["events"].create_index([("category", ASCENDING)],         name="idx_events_category")
    db["events"].create_index([("venue.city", ASCENDING)],       name="idx_events_venue_city")

    db["bookings"].create_index([("user_id", ASCENDING)],        name="idx_bookings_user")
    db["bookings"].create_index([("status", ASCENDING)],         name="idx_bookings_status")
    db["bookings"].create_index([("items.event_id", ASCENDING)], name="idx_bookings_event")

    db["reviews"].create_index([("event_id", ASCENDING)],        name="idx_reviews_event")
    db["reviews"].create_index([("user_id", ASCENDING)],         name="idx_reviews_user")
    db["reviews"].create_index(
        [("user_id", ASCENDING), ("event_id", ASCENDING)],
        unique=True, name="idx_reviews_unique_user_event"
    )

    print("\n✅ MongoDB – import zakończony pomyślnie!")
    print(f"   users:    {db['users'].count_documents({})}")
    print(f"   events:   {db['events'].count_documents({})}")
    print(f"   bookings: {db['bookings'].count_documents({})}")
    print(f"   reviews:  {db['reviews'].count_documents({})}\n")

    client.close()


if __name__ == "__main__":
    main()
