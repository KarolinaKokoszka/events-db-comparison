"""
generate.py – szybki generator danych bez faker.

Założenia:
  - Brak faker.unique (dużo szybsze i stabilniejsze generowanie).
  - Rozmiary zbiorów zgodne z wymaganiem: 500k / 1M / 10M rekordów łącznie.
  - Generator pisze JSON strumieniowo (bez trzymania całych tabel w RAM).

Użycie:
  python generate.py --size small
  python generate.py --size medium
  python generate.py --size large
"""

import argparse
import json
import os
import random
from datetime import datetime, timedelta

random.seed(42)

OUTPUT_DIR = "data"

CATEGORIES = [
    "Muzyka", "Sport", "Teatr", "Kino", "Konferencja",
    "Festiwal", "Stand-up", "Opera", "Sztuka", "Targi",
]
TICKET_TYPES = ["Standard", "VIP", "Premium", "Student", "Family"]
PAYMENT_METHODS = ["card", "blik", "transfer", "paypal"]
ADDRESS_TYPES = ["home", "billing", "other"]
EVENT_STATUSES = ["planned", "active", "cancelled", "finished"]
BOOKING_STATUSES = ["pending", "paid", "cancelled"]
ZONE_NAMES = ["Trybuna A", "Trybuna B", "Plyta", "VIP"]
FIRST_NAMES = ["Jan", "Anna", "Piotr", "Katarzyna", "Marek", "Agnieszka", "Pawel", "Ewa"]
LAST_NAMES = ["Nowak", "Kowalski", "Wisniewska", "Wojcik", "Kaminski", "Lewandowska", "Zielinski", "Szymanska"]
CITIES = ["Warszawa", "Krakow", "Wroclaw", "Poznan", "Gdansk", "Lodz", "Szczecin", "Lublin"]

# Konfiguracja bazowa. Liczba reviews jest liczona automatycznie, aby domknac target_total.
SIZES = {
    "small": {
        "target_total": 500_000,
        "categories": 10,
        "organizers": 200,
        "venues": 300,
        "users": 30_000,
        "events": 2_000,
        "zones_per_event": 4,
        "numbered_zones_per_event": 2,
        "seats_per_numbered_zone": 30,
        "bookings": 50_000,  # 1 booking + 1 booking_ticket + 1 payment = 3 rekordy
    },
    "medium": {
        "target_total": 1_000_000,
        "categories": 10,
        "organizers": 400,
        "venues": 600,
        "users": 70_000,
        "events": 5_000,
        "zones_per_event": 4,
        "numbered_zones_per_event": 2,
        "seats_per_numbered_zone": 35,
        "bookings": 35_000,
    },
    "large": {
        "target_total": 10_000_000,
        "categories": 10,
        "organizers": 1_500,
        "venues": 2_000,
        "users": 700_000,
        "events": 40_000,
        "zones_per_event": 4,
        "numbered_zones_per_event": 2,
        "seats_per_numbered_zone": 40,
        "bookings": 350_000,
    },
}


class JsonArrayWriter:
    def __init__(self, path: str):
        self.path = path
        self.fh = open(path, "w", encoding="utf-8")
        self.fh.write("[")
        self.first = True
        self.count = 0

    def write(self, item: dict):
        if not self.first:
            self.fh.write(",")
        json.dump(item, self.fh, ensure_ascii=False)
        self.first = False
        self.count += 1

    def close(self):
        self.fh.write("]")
        self.fh.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()


def dt_from_base(days_offset: int) -> str:
    base = datetime(2024, 1, 1, 8, 0, 0)
    return (base + timedelta(days=days_offset)).strftime("%Y-%m-%d %H:%M:%S")


def out_path(name: str) -> str:
    return os.path.join(OUTPUT_DIR, f"{name}.json")


def ensure_output_dir():
    os.makedirs(OUTPUT_DIR, exist_ok=True)


def calc_counts(cfg: dict) -> dict:
    zones = cfg["events"] * cfg["zones_per_event"]
    numbered = cfg["events"] * cfg["numbered_zones_per_event"]
    general = zones - numbered
    seats = numbered * cfg["seats_per_numbered_zone"]
    tickets = seats + general

    fixed_without_reviews = (
        cfg["categories"]
        + cfg["organizers"]
        + cfg["venues"]
        + cfg["users"]
        + cfg["users"]  # user_addresses: 1 na usera
        + cfg["events"]
        + zones
        + seats
        + tickets
        + cfg["bookings"]
        + cfg["bookings"]  # booking_tickets: 1 na booking
        + cfg["bookings"]  # payments: 1 na booking
    )
    reviews = cfg["target_total"] - fixed_without_reviews
    if reviews < 0:
        raise ValueError(
            f"Konfiguracja przekracza target_total o {-reviews:,} rekordów. "
            "Zmniejsz liczebnosc encji bazowych."
        )
    return {
        "zones": zones,
        "seats": seats,
        "tickets": tickets,
        "reviews": reviews,
        "total": cfg["target_total"],
    }


def gen_categories(cfg: dict) -> int:
    with JsonArrayWriter(out_path("categories")) as w:
        for i in range(1, cfg["categories"] + 1):
            w.write({"id": i, "name": CATEGORIES[(i - 1) % len(CATEGORIES)]})
    return cfg["categories"]


def gen_organizers(cfg: dict) -> int:
    with JsonArrayWriter(out_path("organizers")) as w:
        for i in range(1, cfg["organizers"] + 1):
            w.write({
                "id": i,
                "name": f"Organizer {i}",
                "email": f"organizer{i}@events.local",
                "phone": f"+48500{i % 1_000_000:06d}",
                "created_at": dt_from_base(i % 730),
            })
    return cfg["organizers"]


def gen_venues(cfg: dict) -> int:
    with JsonArrayWriter(out_path("venues")) as w:
        for i in range(1, cfg["venues"] + 1):
            city = CITIES[(i - 1) % len(CITIES)]
            w.write({
                "id": i,
                "name": f"{city} Arena {i}",
                "street": f"ul. Eventowa {i % 500 + 1}",
                "city": city,
                "postal_code": f"{(i % 90) + 10:02d}-{(i % 900) + 100:03d}",
                "country": "Polska",
                "capacity": 500 + (i % 55_000),
                "created_at": dt_from_base(i % 730),
            })
    return cfg["venues"]


def gen_users_and_addresses(cfg: dict) -> tuple[int, int]:
    users_count = 0
    addresses_count = 0
    with JsonArrayWriter(out_path("users")) as wu, JsonArrayWriter(out_path("user_addresses")) as wa:
        for i in range(1, cfg["users"] + 1):
            fn = FIRST_NAMES[(i - 1) % len(FIRST_NAMES)]
            ln = LAST_NAMES[(i - 1) % len(LAST_NAMES)]
            created = dt_from_base(i % 730)
            wu.write({
                "id": i,
                "first_name": fn,
                "last_name": ln,
                "email": f"user{i}@mail.local",
                "password_hash": f"hash_{i:012x}",
                "phone": f"+4860{i % 1_000_000:06d}",
                "status": "deleted" if i % 20 == 0 else "active",
                "created_at": created,
                "updated_at": created,
            })
            users_count += 1

            wa.write({
                "id": i,
                "user_id": i,
                "street": f"ul. Miejska {i % 800 + 1}",
                "city": CITIES[i % len(CITIES)],
                "postal_code": f"{(i % 90) + 10:02d}-{(i % 900) + 100:03d}",
                "country": "Polska",
                "type": ADDRESS_TYPES[i % len(ADDRESS_TYPES)],
                "created_at": created,
            })
            addresses_count += 1
    return users_count, addresses_count


def gen_events(cfg: dict) -> int:
    with JsonArrayWriter(out_path("events")) as w:
        for i in range(1, cfg["events"] + 1):
            start = dt_from_base(i % 1095)
            end = dt_from_base((i % 1095) + 1)
            add_info = {
                "age_limit": 18 if i % 3 == 0 else 16,
                "dress_code": "casual" if i % 2 == 0 else "smart casual",
                "parking": i % 2 == 0,
                "languages": ["PL", "EN"] if i % 4 != 0 else ["PL", "EN", "DE"],
            }
            w.write({
                "id": i,
                "name": f"Wydarzenie {i}",
                "description": f"Opis wydarzenia {i}",
                "category_id": (i % cfg["categories"]) + 1,
                "organizer_id": (i % cfg["organizers"]) + 1,
                "venue_id": (i % cfg["venues"]) + 1,
                "start_date": start,
                "end_date": end,
                "additional_info": json.dumps(add_info, ensure_ascii=False),
                "status": EVENT_STATUSES[i % len(EVENT_STATUSES)],
                "created_at": dt_from_base((i + 100) % 1095),
            })
    return cfg["events"]


def gen_zones_seats_tickets(cfg: dict) -> tuple[int, int, int]:
    zone_id = 1
    seat_id = 1
    ticket_id = 1
    zones_count = 0
    seats_count = 0
    tickets_count = 0

    with JsonArrayWriter(out_path("event_zones")) as wz, JsonArrayWriter(out_path("seats")) as ws, JsonArrayWriter(out_path("tickets")) as wt:
        for event_id in range(1, cfg["events"] + 1):
            for z_idx in range(cfg["zones_per_event"]):
                is_numbered = z_idx < cfg["numbered_zones_per_event"]
                z_type = "numbered" if is_numbered else "general"
                zone_name = ZONE_NAMES[z_idx % len(ZONE_NAMES)]
                capacity = cfg["seats_per_numbered_zone"] if is_numbered else 500 + (zone_id % 1500)
                wz.write({
                    "id": zone_id,
                    "event_id": event_id,
                    "name": zone_name,
                    "type": z_type,
                    "capacity": capacity,
                })
                zones_count += 1

                if is_numbered:
                    for s in range(1, cfg["seats_per_numbered_zone"] + 1):
                        row_label = chr(65 + ((s - 1) // 20))
                        seat_num = ((s - 1) % 20) + 1
                        ws.write({
                            "id": seat_id,
                            "zone_id": zone_id,
                            "row_label": row_label,
                            "seat_number": seat_num,
                        })
                        seats_count += 1

                        perks = {
                            "lounge_access": zone_name == "VIP",
                            "backstage_pass": False,
                            "free_drink": zone_name == "VIP",
                        }
                        wt.write({
                            "id": ticket_id,
                            "event_id": event_id,
                            "zone_id": zone_id,
                            "seat_id": seat_id,
                            "ticket_type": TICKET_TYPES[ticket_id % len(TICKET_TYPES)],
                            "total_quantity": 1,
                            "available_quantity": 1 if ticket_id % 3 else 0,
                            "price": round(49.99 + (ticket_id % 500) * 0.73, 2),
                            "perks": json.dumps(perks),
                            "status": "available",
                            "created_at": dt_from_base((ticket_id + 200) % 1095),
                        })
                        tickets_count += 1
                        seat_id += 1
                        ticket_id += 1
                else:
                    perks = {
                        "lounge_access": False,
                        "backstage_pass": False,
                        "free_drink": False,
                    }
                    wt.write({
                        "id": ticket_id,
                        "event_id": event_id,
                        "zone_id": zone_id,
                        "seat_id": None,
                        "ticket_type": TICKET_TYPES[ticket_id % len(TICKET_TYPES)],
                        "total_quantity": capacity,
                        "available_quantity": int(capacity * 0.6),
                        "price": round(39.99 + (ticket_id % 200) * 0.41, 2),
                        "perks": json.dumps(perks),
                        "status": "available",
                        "created_at": dt_from_base((ticket_id + 300) % 1095),
                    })
                    tickets_count += 1
                    ticket_id += 1

                zone_id += 1

    return zones_count, seats_count, tickets_count


def gen_bookings_booking_tickets_payments(cfg: dict, ticket_count: int) -> tuple[int, int, int]:
    bookings_count = 0
    bt_count = 0
    payments_count = 0

    with JsonArrayWriter(out_path("bookings")) as wb, JsonArrayWriter(out_path("booking_tickets")) as wbt, JsonArrayWriter(out_path("payments")) as wp:
        for i in range(1, cfg["bookings"] + 1):
            user_id = (i % cfg["users"]) + 1
            ticket_id = (i % ticket_count) + 1
            status = BOOKING_STATUSES[i % len(BOOKING_STATUSES)]
            total = round(40.0 + (i % 350) * 1.11, 2)
            booking_date = dt_from_base((i + 400) % 1095)

            wb.write({
                "id": i,
                "user_id": user_id,
                "booking_date": booking_date,
                "status": status,
                "total_price": total,
            })
            bookings_count += 1

            wbt.write({
                "id": i,
                "booking_id": i,
                "ticket_id": ticket_id,
                "quantity": 1,
                "price_at_purchase": total,
            })
            bt_count += 1

            pay_status = "completed" if status == "paid" else ("failed" if status == "cancelled" else "pending")
            wp.write({
                "id": i,
                "booking_id": i,
                "payment_method": PAYMENT_METHODS[i % len(PAYMENT_METHODS)],
                "amount": total,
                "payment_date": booking_date,
                "status": pay_status,
            })
            payments_count += 1

    return bookings_count, bt_count, payments_count


def gen_reviews(cfg: dict, reviews_count: int) -> int:
    with JsonArrayWriter(out_path("reviews")) as w:
        for i in range(1, reviews_count + 1):
            user_id = ((i - 1) % cfg["users"]) + 1
            event_id = (((i - 1) // cfg["users"]) % cfg["events"]) + 1
            w.write({
                "id": i,
                "user_id": user_id,
                "event_id": event_id,
                "rating": (i % 5) + 1,
                "comment": None if i % 4 == 0 else f"Opinia {i}",
                "created_at": dt_from_base((i + 500) % 1095),
            })
    return reviews_count


def main():
    parser = argparse.ArgumentParser(description="Szybki generator danych – e-Ticket")
    parser.add_argument("--size", choices=["small", "medium", "large"], default="small")
    args = parser.parse_args()

    cfg = SIZES[args.size]
    ensure_output_dir()

    derived = calc_counts(cfg)
    print(f"\nGenerowanie danych ({args.size.upper()})")
    print(f"Target rekordow: {cfg['target_total']:,}")
    print(
        "Pochodne: "
        f"zones={derived['zones']:,}, seats={derived['seats']:,}, "
        f"tickets={derived['tickets']:,}, reviews={derived['reviews']:,}"
    )

    counts = {}
    counts["categories"] = gen_categories(cfg)
    counts["organizers"] = gen_organizers(cfg)
    counts["venues"] = gen_venues(cfg)
    counts["users"], counts["user_addresses"] = gen_users_and_addresses(cfg)
    counts["events"] = gen_events(cfg)
    counts["event_zones"], counts["seats"], counts["tickets"] = gen_zones_seats_tickets(cfg)
    counts["bookings"], counts["booking_tickets"], counts["payments"] = gen_bookings_booking_tickets_payments(
        cfg, counts["tickets"]
    )
    counts["reviews"] = gen_reviews(cfg, derived["reviews"])

    total = sum(counts.values())
    print("\nWygenerowane pliki:")
    for name in [
        "categories", "organizers", "venues", "users", "user_addresses", "events",
        "event_zones", "seats", "tickets", "bookings", "booking_tickets", "payments", "reviews",
    ]:
        print(f"  - {name}.json: {counts[name]:,}")

    print(f"\nLaczna liczba rekordow: {total:,}")
    if total != cfg["target_total"]:
        raise RuntimeError(
            f"Niezgodna liczba rekordow: {total:,} != {cfg['target_total']:,}"
        )
    print("OK: liczba rekordow zgodna z targetem.\n")


if __name__ == "__main__":
    main()
