"""
crud_mongo.py – 24 scenariusze testowe dla MongoDB.
"""

import time
import random
import uuid
from datetime import datetime, timedelta
from pymongo import MongoClient, ASCENDING

MONGO_URI = "mongodb://localhost:27017"
DB_NAME   = "eventsdb"

def get_db():
    client = MongoClient(MONGO_URI)
    return client[DB_NAME], client

def measure(fn) -> float:
    start = time.perf_counter()
    fn()
    return round(time.perf_counter() - start, 6)

def rand_doc(col, projection=None):
    pipeline = [{"$sample": {"size": 1}}]
    docs = list(col.aggregate(pipeline))
    return docs[0] if docs else None


# ════════════════════════════════════════════
# CREATE 1-6
# ════════════════════════════════════════════
def s01_insert_one_user(db) -> float:
    def fn():
        uid = uuid.uuid4().hex[:8]
        db.users.insert_one({
            "first_name":    "Test",
            "last_name":     "User",
            "email":         f"test_{uid}@test.pl",
            "password_hash": "hash_xyz",
            "phone":         "500-000-000",
            "status":        "active",
            "addresses":     [],
            "created_at":    datetime.utcnow(),
            "updated_at":    datetime.utcnow(),
        })
    return measure(fn)


def s02_insert_100_users(db) -> float:
    def fn():
        docs = [{
            "first_name":    f"First{i}",
            "last_name":     f"Last{i}",
            "email":         f"bulk_{uuid.uuid4().hex[:8]}@test.pl",
            "password_hash": "hash",
            "status":        "active",
            "addresses":     [],
            "created_at":    datetime.utcnow(),
        } for i in range(100)]
        db.users.insert_many(docs, ordered=False)
    return measure(fn)


def s03_insert_event_with_json(db) -> float:
    """Dane półustrukturalne – event z zagnieżdżonym additional_info."""
    def fn():
        db.events.insert_one({
            "name":        "Test Event JSON",
            "description": "Opis testowy",
            "status":      "planned",
            "start_date":  datetime.utcnow() + timedelta(days=10),
            "end_date":    datetime.utcnow() + timedelta(days=10, hours=3),
            "category":    "Muzyka",
            # Dane półustrukturalne:
            "additional_info": {
                "age_limit":  18,
                "dress_code": "casual",
                "parking":    True,
                "languages":  ["PL", "EN"]
            },
            "organizer": {"name": "Test Org", "email": "org@test.pl"},
            "venue":     {"name": "Test Venue", "city": "Warszawa", "country": "Polska"},
            "zones":     [],
            "created_at": datetime.utcnow(),
        })
    return measure(fn)


def s04_insert_booking_with_tickets(db) -> float:
    def fn():
        user  = rand_doc(db.users)
        event = rand_doc(db.events)
        if not user or not event:
            return
        db.bookings.insert_one({
            "user_id":      user["_id"],
            "booking_date": datetime.utcnow(),
            "status":       "pending",
            "total_price":  150.0,
            "items": [
                {
                    "event_id":          event["_id"],
                    "event_name":        event.get("name", ""),
                    "ticket_type":       "Standard",
                    "zone_name":         "Trybuna A",
                    "quantity":          2,
                    "price_at_purchase": 75.0,
                }
            ],
            "payment": {
                "method": "card",
                "amount": 150.0,
                "payment_date": datetime.utcnow(),
                "status": "pending",
            },
        })
    return measure(fn)


def s05_insert_review(db) -> float:
    """Wstawienie pojedynczej recenzji user-event."""
    def fn():
        user = rand_doc(db.users)
        event = rand_doc(db.events)
        if not user or not event:
            return
        db.reviews.update_one(
            {"user_id": user["_id"], "event_id": event["_id"]},
            {"$setOnInsert": {
                "user_id": user["_id"],
                "event_id": event["_id"],
                "rating": random.randint(1, 5),
                "comment": "Komentarz testowy",
                "created_at": datetime.utcnow(),
            }},
            upsert=True,
        )
    return measure(fn)


def s06_insert_one_ticket(db) -> float:
    def fn():
        event = rand_doc(db.events)
        if not event or not event.get("zones"):
            return
        zone = random.choice(event["zones"])
        new_ticket_id = int(datetime.utcnow().timestamp() * 1000000) % 9_000_000_000
        db.events.update_one(
            {"_id": event["_id"], "zones.zone_id": zone["zone_id"]},
            {"$push": {"zones.$.tickets": {
                "ticket_id": new_ticket_id,
                "ticket_type": "Standard",
                "price": 99.99,
                "total_quantity": 100,
                "available_quantity": 100,
                "status": "available",
                "perks": {
                    "lounge_access": False,
                    "backstage_pass": False,
                    "free_drink": False,
                },
            }}},
        )
    return measure(fn)


# ════════════════════════════════════════════
# READ 7-12
# ════════════════════════════════════════════
def s07_select_user_by_email(db) -> float:
    user = rand_doc(db.users)
    if not user:
        return 0.0
    email = user["email"]

    def fn():
        db.users.find_one({"email": email})
    return measure(fn)


def s08_select_events_by_city(db) -> float:
    event = rand_doc(db.events)
    status = event.get("status", "planned") if event else "planned"
    left = datetime.utcnow() - timedelta(days=365)
    right = datetime.utcnow() + timedelta(days=365)

    def fn():
        list(db.events.find(
            {"status": status, "start_date": {"$gte": left, "$lte": right}},
            {"name": 1, "status": 1, "start_date": 1},
        ))
    return measure(fn)


def s09_select_booking_with_joins(db) -> float:
    booking = rand_doc(db.bookings)
    if not booking:
        return 0.0
    booking_id = booking["_id"]

    def fn():
        db.bookings.find_one(
            {"_id": booking_id},
            {"status": 1, "total_price": 1, "items": 1, "payment": 1}
        )
    return measure(fn)


def s10_aggregate_avg_rating(db) -> float:
    def fn():
        pipeline = [
            {"$group": {
                "_id":        "$event_id",
                "avg_rating": {"$avg": "$rating"},
                "count":      {"$sum": 1}
            }},
            {"$sort": {"avg_rating": -1}},
            {"$limit": 50},
        ]
        list(db.reviews.aggregate(pipeline))
    return measure(fn)


def s11_select_events_by_json_field(db) -> float:
    """Dane półustrukturalne – filtrowanie po zagnieżdżonym polu additional_info."""
    def fn():
        list(db.events.find(
            {"additional_info.age_limit": 18},
            {"name": 1, "additional_info.age_limit": 1}
        ))
    return measure(fn)


def s12_select_tickets_with_lounge(db) -> float:
    """Top eventy po liczbie bookingow."""
    def fn():
        pipeline = [
            {"$unwind": "$items"},
            {"$group": {"_id": "$items.event_id", "bookings_count": {"$sum": 1}}},
            {"$sort": {"bookings_count": -1}},
            {"$limit": 20},
        ]
        list(db.bookings.aggregate(pipeline))
    return measure(fn)


# ════════════════════════════════════════════
# UPDATE 13-18
# ════════════════════════════════════════════
def s13_update_booking_status(db) -> float:
    booking = rand_doc(db.bookings)
    if not booking:
        return 0.0
    booking_id = booking["_id"]

    def fn():
        db.bookings.update_one({"_id": booking_id}, {"$set": {"status": "paid"}})
    return measure(fn)


def s14_update_ticket_quantity(db) -> float:
    event = rand_doc(db.events)
    if not event or not event.get("zones"):
        return 0.0
    zone = random.choice(event["zones"])
    if not zone.get("tickets"):
        return 0.0
    ticket = random.choice(zone["tickets"])
    event_id = event["_id"]
    zone_id = zone["zone_id"]
    ticket_id = ticket["ticket_id"]

    def fn():
        db.events.update_one(
            {"_id": event_id,
             "zones.zone_id": zone_id,
             "zones.tickets.ticket_id": ticket_id},
            {"$inc": {"zones.$[z].tickets.$[t].available_quantity": -1}},
            array_filters=[
                {"z.zone_id": zone_id},
                {"t.ticket_id": ticket_id}
            ]
        )
    return measure(fn)


def s15_update_100_events_status(db) -> float:
    def fn():
        events = list(db.events.aggregate([{"$sample": {"size": 100}}]))
        ids    = [e["_id"] for e in events]
        db.events.update_many({"_id": {"$in": ids}}, {"$set": {"status": "finished"}})
    return measure(fn)


def s16_update_user_data(db) -> float:
    user = rand_doc(db.users)
    if not user:
        return 0.0
    user_id = user["_id"]

    def fn():
        db.users.update_one(
            {"_id": user_id},
            {"$set": {"phone": "600-700-800", "updated_at": datetime.utcnow()}}
        )
    return measure(fn)


def s17_update_json_field(db) -> float:
    """Dane półustrukturalne – dodanie elementu do tablicy w additional_info."""
    event = rand_doc(db.events)
    if not event:
        return 0.0
    event_id = event["_id"]

    def fn():
        db.events.update_one(
            {"_id": event_id},
            {"$addToSet": {"additional_info.languages": "DE"}}
        )
    return measure(fn)


def s18_update_vip_prices(db) -> float:
    def fn():
        list(db.events.aggregate([
            {"$unwind": "$zones"},
            {"$unwind": "$zones.tickets"},
            {"$match": {"zones.tickets.ticket_type": "VIP"}}
        ]))
        # Aktualizuj przez pipeline
        db.events.update_many(
            {"zones.tickets.ticket_type": "VIP"},
            [{"$set": {"zones": {"$map": {
                "input": "$zones",
                "as":    "z",
                "in": {"$mergeObjects": ["$$z", {"tickets": {"$map": {
                    "input": "$$z.tickets",
                    "as":    "t",
                    "in": {"$cond": [
                        {"$eq": ["$$t.ticket_type", "VIP"]},
                        {"$mergeObjects": ["$$t", {"price": {"$multiply": ["$$t.price", 1.1]}}]},
                        "$$t"
                    ]}
                }}}]}
            }}}}]
        )
    return measure(fn)


# ════════════════════════════════════════════
# DELETE 19-24
# ════════════════════════════════════════════
def s19_delete_review(db) -> float:
    review = rand_doc(db.reviews)
    if not review:
        return 0.0
    review_id = review["_id"]

    def fn():
        db.reviews.delete_one({"_id": review_id})
    return measure(fn)


def s20_delete_booking_cascade(db) -> float:
    booking = rand_doc(db.bookings)
    if not booking:
        return 0.0
    booking_id = booking["_id"]

    def fn():
        db.bookings.delete_one({"_id": booking_id})
    return measure(fn)


def s21_delete_user_cascade(db) -> float:
    uid = uuid.uuid4().hex[:8]
    result = db.users.insert_one({
        "first_name": "Del", "last_name": "User",
        "email": f"del_{uid}@test.pl",
        "status": "active", "created_at": datetime.utcnow()
    })
    inserted_id = result.inserted_id

    def fn():
        db.users.delete_one({"_id": inserted_id})
    return measure(fn)


def s22_delete_cancelled_events(db) -> float:
    ids = []
    for _ in range(5):
        r = db.events.insert_one({
            "name": "DEL_TEST", "status": "cancelled",
            "start_date": datetime.utcnow(), "end_date": datetime.utcnow(),
            "organizer": {}, "venue": {}
        })
        ids.append(r.inserted_id)

    def fn():
        db.events.delete_many({"_id": {"$in": ids}, "status": "cancelled"})
    return measure(fn)


def s23_delete_old_payments(db) -> float:
    def fn():
        cutoff = datetime.utcnow() - timedelta(days=365)
        db.bookings.update_many({
            "payment.payment_date": {"$lt": cutoff},
        }, {"$unset": {"payment": ""}})
    return measure(fn)


def s24_delete_zone_cascade(db) -> float:
    event = rand_doc(db.events)
    if not event or not event.get("zones"):
        return 0.0
    zone = random.choice(event["zones"])
    test_ticket_id = 10_000_000_000 + random.randint(1, 1_000_000)
    db.events.update_one(
        {"_id": event["_id"], "zones.zone_id": zone["zone_id"]},
        {"$push": {"zones.$.tickets": {
            "ticket_id": test_ticket_id,
            "ticket_type": "DEL_TEST",
            "price": 10.0,
            "total_quantity": 1,
            "available_quantity": 1,
            "status": "available",
            "perks": {},
        }}},
    )
    event_id = event["_id"]

    def fn():
        db.events.update_one(
            {"_id": event_id},
            {"$pull": {"zones.$[].tickets": {"ticket_id": test_ticket_id}}},
        )
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
    db, client = get_db()
    results    = []
    print("  [MongoDB] Uruchamiam scenariusze...")
    for sid, fn in SCENARIO_FUNCTIONS.items():
        times = []
        for attempt in range(1, repeats + 1):
            try:
                t = fn(db)
                times.append(t)
            except Exception as e:
                print(f"    ⚠ S{sid} próba {attempt}: {e}")
                times.append(None)
        valid = [t for t in times if t is not None]
        avg   = round(sum(valid) / len(valid), 6) if valid else None
        results.append({"scenario_id": sid, "times": times, "avg": avg})
        print(f"    S{sid:02d}: {avg:.6f}s  (próby: {times})" if avg else f"    S{sid:02d}: BŁĄD")
    client.close()
    return results


def create_indexes():
    db, client = get_db()
    db.users.create_index([("email", ASCENDING)],             unique=True)
    db.users.create_index([("status", ASCENDING)])
    db.events.create_index([("status", ASCENDING)])
    db.events.create_index([("start_date", ASCENDING)])
    db.events.create_index([("category", ASCENDING)])
    db.events.create_index([("venue.city", ASCENDING)])
    db.events.create_index([("additional_info.age_limit", ASCENDING)])
    db.events.create_index([("zones.tickets.perks.lounge_access", ASCENDING)])
    db.bookings.create_index([("user_id", ASCENDING)])
    db.bookings.create_index([("status", ASCENDING)])
    db.reviews.create_index([("event_id", ASCENDING)])
    db.reviews.create_index([("user_id", ASCENDING)])
    client.close()
    print("  [MongoDB] ✅ Indeksy utworzone")


def drop_indexes():
    db, client = get_db()
    for col_name in ["users", "events", "bookings", "reviews"]:
        col = db[col_name]
        for idx in col.list_indexes():
            if idx["name"] != "_id_":
                try:
                    col.drop_index(idx["name"])
                except Exception:
                    pass
    client.close()
    print("  [MongoDB] ✅ Indeksy usunięte")
