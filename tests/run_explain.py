"""
run_explain.py - zbieranie planow EXPLAIN dla baz SQL/MongoDB.

Uzycie:
  python run_explain.py --phase with_indexes
  python run_explain.py --phase without_indexes
  python run_explain.py --phase both
"""

import argparse
import json
import os
from datetime import datetime, timedelta

import psycopg2
import mysql.connector
from pymongo import MongoClient

import crud_postgres
import crud_mysql
import crud_mongo
import crud_neo4j

RESULTS_DIR = "results"


PG_CONFIG = {
    "host": "localhost",
    "port": 5432,
    "dbname": "eventsdb",
    "user": "admin",
    "password": "admin123",
}

MYSQL_CONFIG = {
    "host": "localhost",
    "port": 3306,
    "database": "eventsdb",
    "user": "root",
    "password": "root123",
    "charset": "utf8mb4",
}

MONGO_URI = "mongodb://localhost:27017"
MONGO_DB = "eventsdb"

def ensure_results_dir():
    os.makedirs(RESULTS_DIR, exist_ok=True)


def collect_postgres():
    out = {}
    conn = psycopg2.connect(**PG_CONFIG)
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT email FROM users ORDER BY RANDOM() LIMIT 1")
            row = cur.fetchone()
            email = row[0] if row else "user1@mail.local"

            cur.execute("SELECT status FROM events ORDER BY RANDOM() LIMIT 1")
            row = cur.fetchone()
            status = row[0] if row else "planned"

            queries = {
                "R1_user_by_email": (
                    "SELECT * FROM users WHERE email = %s",
                    (email,),
                ),
                "R2_events_status_date": (
                    """
                    SELECT e.id, e.name, e.status, e.start_date
                    FROM events e
                    WHERE e.status = %s
                      AND e.start_date BETWEEN NOW() - INTERVAL '365 days'
                                          AND NOW() + INTERVAL '365 days'
                    """,
                    (status,),
                ),
                "R5_json_age_limit": (
                    """
                    SELECT id, name
                    FROM events
                    WHERE (additional_info->>'age_limit')::int = 18
                    """,
                    (),
                ),
                "R6_top_events_bookings": (
                    """
                    SELECT e.id, e.name, COUNT(DISTINCT b.id) AS bookings_count
                    FROM bookings b
                    JOIN booking_tickets bt ON bt.booking_id = b.id
                    JOIN tickets t ON t.id = bt.ticket_id
                    JOIN events e ON e.id = t.event_id
                    GROUP BY e.id, e.name
                    ORDER BY bookings_count DESC
                    LIMIT 20
                    """,
                    (),
                ),
            }

            for name, (q, params) in queries.items():
                cur.execute("EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) " + q, params)
                plan = cur.fetchone()[0][0]
                out[name] = plan
    finally:
        conn.close()
    return out


def collect_mysql():
    out = {}
    conn = mysql.connector.connect(**MYSQL_CONFIG)
    try:
        cur = conn.cursor()
        cur.execute("SELECT email FROM users ORDER BY RAND() LIMIT 1")
        row = cur.fetchone()
        email = row[0] if row else "user1@mail.local"

        cur.execute("SELECT status FROM events ORDER BY RAND() LIMIT 1")
        row = cur.fetchone()
        status = row[0] if row else "planned"

        queries = {
            "R1_user_by_email": (
                "SELECT * FROM users WHERE email = %s",
                (email,),
            ),
            "R2_events_status_date": (
                """
                SELECT e.id, e.name, e.status, e.start_date
                FROM events e
                WHERE e.status = %s
                  AND e.start_date BETWEEN DATE_SUB(NOW(), INTERVAL 365 DAY)
                                       AND DATE_ADD(NOW(), INTERVAL 365 DAY)
                """,
                (status,),
            ),
            "R5_json_age_limit": (
                """
                SELECT id, name
                FROM events
                WHERE JSON_EXTRACT(additional_info, '$.age_limit') = 18
                """,
                (),
            ),
            "R6_top_events_bookings": (
                """
                SELECT e.id, e.name, COUNT(DISTINCT b.id) AS bookings_count
                FROM bookings b
                JOIN booking_tickets bt ON bt.booking_id = b.id
                JOIN tickets t ON t.id = bt.ticket_id
                JOIN events e ON e.id = t.event_id
                GROUP BY e.id, e.name
                ORDER BY bookings_count DESC
                LIMIT 20
                """,
                (),
            ),
        }

        for name, (q, params) in queries.items():
            cur.execute("EXPLAIN FORMAT=JSON " + q, params)
            row = cur.fetchone()
            out[name] = json.loads(row[0]) if row and row[0] else {}
        cur.close()
    finally:
        conn.close()
    return out


def collect_mongo():
    out = {}
    client = MongoClient(MONGO_URI)
    try:
        db = client[MONGO_DB]

        doc = db.users.find_one({}, {"email": 1})
        email = doc["email"] if doc and "email" in doc else "user1@mail.local"

        doc = db.events.find_one({}, {"status": 1})
        status = doc["status"] if doc and "status" in doc else "planned"
        left = datetime.utcnow() - timedelta(days=365)
        right = datetime.utcnow() + timedelta(days=365)

        out["R1_user_by_email"] = db.command(
            "explain",
            {"find": "users", "filter": {"email": email}},
            verbosity="executionStats",
        )
        out["R2_events_status_date"] = db.command(
            "explain",
            {
                "find": "events",
                "filter": {"status": status, "start_date": {"$gte": left, "$lte": right}},
            },
            verbosity="executionStats",
        )
        out["R5_json_age_limit"] = db.command(
            "explain",
            {"find": "events", "filter": {"additional_info.age_limit": 18}},
            verbosity="executionStats",
        )

        pipeline = [
            {"$unwind": "$items"},
            {"$group": {"_id": "$items.event_id", "bookings_count": {"$sum": 1}}},
            {"$sort": {"bookings_count": -1}},
            {"$limit": 20},
        ]
        out["R6_top_events_bookings"] = db.command(
            "explain",
            {"aggregate": "bookings", "pipeline": pipeline, "cursor": {}},
            verbosity="executionStats",
        )
    finally:
        client.close()
    return out


def collect_all():
    return {
        "PostgreSQL": collect_postgres(),
        "MySQL": collect_mysql(),
        "MongoDB": collect_mongo(),
    }


def set_indexes(phase: str):
    modules = [crud_postgres, crud_mysql, crud_mongo, crud_neo4j]
    if phase == "with_indexes":
        for m in modules:
            m.create_indexes()
    elif phase == "without_indexes":
        for m in modules:
            m.drop_indexes()


def run_phase(phase: str):
    print(f"\n=== EXPLAIN phase: {phase} ===")
    set_indexes(phase)
    payload = {
        "phase": phase,
        "timestamp": datetime.utcnow().isoformat(),
        "plans": collect_all(),
    }
    ensure_results_dir()
    out_path = os.path.join(RESULTS_DIR, f"explain_{phase}.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2, default=str)
    print(f"Saved: {out_path}")


def main():
    parser = argparse.ArgumentParser(description="Zbieranie EXPLAIN dla PostgreSQL, MySQL i MongoDB")
    parser.add_argument(
        "--phase",
        choices=["with_indexes", "without_indexes", "both"],
        default="both",
    )
    args = parser.parse_args()

    if args.phase == "both":
        run_phase("without_indexes")
        run_phase("with_indexes")
    else:
        run_phase(args.phase)


if __name__ == "__main__":
    main()
