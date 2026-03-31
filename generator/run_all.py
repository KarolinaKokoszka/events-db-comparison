"""
run_all.py – Orkiestrator: generuje dane i importuje do wszystkich 4 baz.

Użycie:
  python run_all.py --size small
  python run_all.py --size medium
  python run_all.py --size large
  python run_all.py --size small --skip-generate   (jeśli data/ już istnieje)
  python run_all.py --size small --only postgres   (tylko jedna baza)
"""

import argparse
import subprocess
import sys
import time


def run(script: str, args: list = []):
    cmd = [sys.executable, script] + args
    print(f"\n{'='*55}")
    print(f"▶  {' '.join(cmd)}")
    print(f"{'='*55}")
    start = time.time()
    result = subprocess.run(cmd)
    elapsed = time.time() - start
    if result.returncode != 0:
        print(f"❌ {script} zakończył się błędem!")
        sys.exit(1)
    print(f"⏱  Czas: {elapsed:.1f}s")


def main():
    parser = argparse.ArgumentParser(description="Orkiestrator importu danych – e-Ticket")
    parser.add_argument("--size",   choices=["small", "medium", "large"], default="small")
    parser.add_argument("--skip-generate", action="store_true",
                        help="Pomiń generate.py (użyj istniejących plików z data/)")
    parser.add_argument("--only",   choices=["postgres", "mysql", "mongo", "neo4j"],
                        help="Importuj tylko do wybranej bazy")
    args = parser.parse_args()

    print(f"\n🚀 run_all.py – rozmiar: {args.size.upper()}")
    total_start = time.time()

    # 1. Generuj dane
    if not args.skip_generate:
        run("generate.py", ["--size", args.size])
    else:
        print("\n⏭  Pomijam generowanie – używam istniejących plików z data/")

    # 2. Import
    importers = {
        "postgres": "import_postgres.py",
        "mysql":    "import_mysql.py",
        "mongo":    "import_mongo.py",
        "neo4j":    "import_neo4j.py",
    }

    if args.only:
        run(importers[args.only])
    else:
        for name, script in importers.items():
            run(script)

    total = time.time() - total_start
    print(f"\n{'='*55}")
    print(f"✅ Wszystko gotowe! Łączny czas: {total:.1f}s")
    print(f"{'='*55}\n")


if __name__ == "__main__":
    main()
