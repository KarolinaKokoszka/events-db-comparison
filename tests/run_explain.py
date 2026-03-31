"""
run_explain.py - zbieranie planow EXPLAIN/PROFILE dla 4 baz.

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
from neo4j import GraphDatabase

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

NEO4J_URI = "bolt://localhost:7687"
NEO4J_USER = "neo4j"
NEO4J_PASSWORD = "test1234"


def ensure_results_dir():
    os.makedirs(RESULTS_DIR, exist_ok=True)


def profile_to_dict(profile):
    if profile is None:
        return None
    node = {
        "operator_type": getattr(profile, "operator_type", None),
        "args": getattr(profile, "arguments", {}) or {},
        "db_hits": getattr(profile, "db_hits", None),
        "rows": getattr(profile, "rows", None),
        "identifiers": list(getattr(profile, "identifiers", []) or []),
        "children": [],
    }
    children = getattr(profile, "children", []) or []
    for child in children:
        node["children"].append(profile_to_dict(child))
    return node


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


def collect_neo4j():
    out = {}
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    try:
        with driver.session() as s:
            row = s.run("MATCH (u:User) RETURN u.email AS email LIMIT 1").single()
            email = row["email"] if row else "user1@mail.local"

            row = s.run("MATCH (e:Event) RETURN e.status AS st LIMIT 1").single()
            st = row["st"] if row else "planned"
            left = (datetime.utcnow() - timedelta(days=365)).isoformat()
            right = (datetime.utcnow() + timedelta(days=365)).isoformat()

            queries = {
                "R1_user_by_email": (
                    "PROFILE MATCH (u:User {email: $email}) RETURN u",
                    {"email": email},
                ),
                "R2_events_status_date": (
                    """
                    PROFILE
                    MATCH (e:Event)
                    WHERE e.status = $st AND e.start_date >= $left AND e.start_date <= $right
                    RETURN e.name, e.status, e.start_date
                    """,
                    {"st": st, "left": left, "right": right},
                ),
                "R5_json_age_limit": (
                    """
                    PROFILE
                    MATCH (e:Event)
                    WHERE e.age_limit = 18
                    RETURN e.name, e.age_limit
                    """,
                    {},
                ),
                "R6_top_events_bookings": (
                    """
                    PROFILE
                    MATCH (:User)-[:MADE_BOOKING]->(b:Booking)-[:CONTAINS]->(:Ticket)-[:FOR_EVENT]->(e:Event)
                    RETURN e.event_id AS event_id, e.name AS event_name, count(b) AS bookings_count
                    ORDER BY bookings_count DESC
                    LIMIT 20
                    """,
                    {},
                ),
            }

            for name, (q, params) in queries.items():
                result = s.run(q, **params)
                _ = list(result)
                summary = result.consume()
                out[name] = {
                    "counters": {
                        "contains_updates": summary.counters.contains_updates,
                        "contains_system_updates": summary.counters.contains_system_updates,
                    },
                    "profile": profile_to_dict(summary.profile),
                }
    finally:
        driver.close()
    return out


def collect_all():
    return {
        "PostgreSQL": collect_postgres(),
        "MySQL": collect_mysql(),
        "MongoDB": collect_mongo(),
        "Neo4j": collect_neo4j(),
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
    parser = argparse.ArgumentParser(description="Zbieranie EXPLAIN/PROFILE dla 4 baz")
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
