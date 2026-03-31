"""
run_tests.py – Orkiestrator testów wydajnościowych.

Fazy:
  1. without_indexes – usuwa indeksy, uruchamia testy, zapisuje wyniki
  2. with_indexes    – dodaje indeksy, uruchamia testy, zapisuje wyniki
  3. both            – uruchamia obie fazy po kolei (domyślnie)
  4. charts          – generuje wykresy z istniejących CSV

Użycie:
  python run_tests.py --phase both   --size small
  python run_tests.py --phase charts --size small
  python run_tests.py --phase without_indexes --size medium
  python run_tests.py --phase with_indexes    --size medium
"""

import argparse
import csv
import os
import time
from datetime import datetime

import crud_postgres
import crud_mysql
import crud_mongo
import crud_neo4j
from scenarios import SCENARIOS

RESULTS_DIR = "results"
REPEATS     = 3

DB_MODULES = {
    "PostgreSQL": crud_postgres,
    "MySQL":      crud_mysql,
    "MongoDB":    crud_mongo,
    "Neo4j":      crud_neo4j,
}


# ─────────────────────────────────────────────
# ZAPIS WYNIKÓW DO CSV
# ─────────────────────────────────────────────
def save_csv(all_results: list, phase: str, size: str):
    os.makedirs(RESULTS_DIR, exist_ok=True)
    filename = os.path.join(RESULTS_DIR, f"results_{size}_{phase}.csv")

    scen_map = {s["id"]: s for s in SCENARIOS}

    with open(filename, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "db", "scenario_id", "operation", "scenario_name",
            "json_related",
            "try_1", "try_2", "try_3",
            "avg_time_s",
            "phase", "size", "timestamp"
        ])
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        for db_name, results in all_results:
            for r in results:
                sid  = r["scenario_id"]
                scen = scen_map.get(sid, {})
                times = r["times"] + [None] * (3 - len(r["times"]))
                writer.writerow([
                    db_name,
                    sid,
                    scen.get("operation", ""),
                    scen.get("name", ""),
                    scen.get("json_related", False),
                    times[0], times[1], times[2],
                    r["avg"],
                    phase,
                    size,
                    ts,
                ])
    print(f"\n💾 Wyniki zapisane: {filename}")
    return filename


# ─────────────────────────────────────────────
# FAZA TESTÓW
# ─────────────────────────────────────────────
def run_phase(phase: str, size: str):
    print(f"\n{'='*60}")
    print(f"  FAZA: {phase.upper()}  |  ROZMIAR: {size.upper()}")
    print(f"{'='*60}")

    # Zarządzaj indeksami
    if phase == "without_indexes":
        print("\n🗑️  Usuwanie indeksów ze wszystkich baz...")
        for name, module in DB_MODULES.items():
            try:
                module.drop_indexes()
            except Exception as e:
                print(f"  ⚠ {name}: {e}")

    elif phase == "with_indexes":
        print("\n📑 Tworzenie indeksów we wszystkich bazach...")
        for name, module in DB_MODULES.items():
            try:
                module.create_indexes()
            except Exception as e:
                print(f"  ⚠ {name}: {e}")

    # Uruchom testy
    all_results = []
    for db_name, module in DB_MODULES.items():
        print(f"\n▶  {db_name}...")
        start = time.time()
        try:
            results = module.run_all_scenarios(repeats=REPEATS)
            all_results.append((db_name, results))
        except Exception as e:
            print(f"  ❌ {db_name} – krytyczny błąd: {e}")
        elapsed = time.time() - start
        print(f"  ⏱  {db_name}: {elapsed:.1f}s")

    # Zapisz CSV
    csv_path = save_csv(all_results, phase, size)
    return csv_path


# ─────────────────────────────────────────────
# WYKRESY
# ─────────────────────────────────────────────
def generate_charts(size: str):
    try:
        import pandas as pd
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import numpy as np
    except ImportError:
        print("❌ Zainstaluj: pip install pandas matplotlib")
        return

    os.makedirs(RESULTS_DIR, exist_ok=True)
    colors = {
        "PostgreSQL": "#336791",
        "MySQL":      "#F29111",
        "MongoDB":    "#47A248",
        "Neo4j":      "#008CC1",
    }

    # Wczytaj oba pliki CSV
    dfs = []
    for phase in ["without_indexes", "with_indexes"]:
        path = os.path.join(RESULTS_DIR, f"results_{size}_{phase}.csv")
        if os.path.exists(path):
            df = pd.read_csv(path)
            dfs.append(df)
        else:
            print(f"⚠ Brak pliku: {path} – pomiń fazę {phase}")

    if not dfs:
        print("❌ Brak plików CSV do wygenerowania wykresów.")
        return

    df_all = pd.concat(dfs, ignore_index=True)

    # ── Wykres 1: Średni czas CRUD × baza (z indeksami) ──
    df_with = df_all[df_all["phase"] == "with_indexes"]
    if not df_with.empty:
        pivot = df_with.groupby(["db", "operation"])["avg_time_s"].mean().unstack()
        ax    = pivot.plot(kind="bar", figsize=(12, 6), colormap="tab10")
        ax.set_title(f"Średni czas operacji CRUD – z indeksami ({size})", fontsize=14)
        ax.set_xlabel("Baza danych")
        ax.set_ylabel("Czas [s]")
        ax.set_xticklabels(ax.get_xticklabels(), rotation=0)
        ax.legend(title="Operacja")
        plt.tight_layout()
        path = os.path.join(RESULTS_DIR, f"chart_crud_with_indexes_{size}.png")
        plt.savefig(path, dpi=150)
        plt.close()
        print(f"  ✅ {path}")

    # ── Wykres 2: Porównanie przed/po indeksach per baza ──
    if len(dfs) == 2:
        ops = ["CREATE", "READ", "UPDATE", "DELETE"]
        fig, axes = plt.subplots(2, 2, figsize=(16, 10))
        axes = axes.flatten()
        for i, op in enumerate(ops):
            ax = axes[i]
            df_op = df_all[df_all["operation"] == op]
            pivot = df_op.groupby(["db", "phase"])["avg_time_s"].mean().unstack()
            if pivot.empty:
                continue
            x     = np.arange(len(pivot.index))
            width = 0.35
            bars1 = ax.bar(x - width/2,
                           pivot.get("without_indexes", [0]*len(pivot)),
                           width, label="Bez indeksów", color="#E74C3C", alpha=0.8)
            bars2 = ax.bar(x + width/2,
                           pivot.get("with_indexes",    [0]*len(pivot)),
                           width, label="Z indeksami",  color="#27AE60", alpha=0.8)
            ax.set_title(f"{op}", fontsize=12)
            ax.set_xticks(x)
            ax.set_xticklabels(pivot.index, rotation=0)
            ax.set_ylabel("Czas [s]")
            ax.legend()
        fig.suptitle(f"Hipoteza H1: Wpływ indeksów na operacje CRUD ({size})", fontsize=14)
        plt.tight_layout()
        path = os.path.join(RESULTS_DIR, f"chart_h1_indexes_comparison_{size}.png")
        plt.savefig(path, dpi=150)
        plt.close()
        print(f"  ✅ {path}")

    # ── Wykres 3: Scenariusze JSON vs non-JSON ──
    df_w = df_all[df_all["phase"] == "with_indexes"].copy()
    if not df_w.empty and "json_related" in df_w.columns:
        grp = df_w.groupby(["db", "json_related"])["avg_time_s"].mean().unstack()
        grp.columns = ["Bez JSON", "Z JSON (półustrukturalne)"]
        ax  = grp.plot(kind="bar", figsize=(10, 5), color=["#3498DB", "#E67E22"])
        ax.set_title(f"Dane półustrukturalne: JSON vs zwykłe scenariusze ({size})", fontsize=13)
        ax.set_xlabel("Baza danych")
        ax.set_ylabel("Średni czas [s]")
        ax.set_xticklabels(ax.get_xticklabels(), rotation=0)
        plt.tight_layout()
        path = os.path.join(RESULTS_DIR, f"chart_json_comparison_{size}.png")
        plt.savefig(path, dpi=150)
        plt.close()
        print(f"  ✅ {path}")

    # ── Wykres 4: Wszystkie scenariusze – heatmapa ──
    df_w2 = df_all[df_all["phase"] == "with_indexes"]
    if not df_w2.empty:
        pivot_h = df_w2.pivot_table(
            index="db", columns="scenario_id", values="avg_time_s", aggfunc="mean"
        )
        fig, ax = plt.subplots(figsize=(20, 5))
        im = ax.imshow(pivot_h.values, aspect="auto", cmap="YlOrRd")
        ax.set_xticks(range(len(pivot_h.columns)))
        ax.set_xticklabels([f"S{c}" for c in pivot_h.columns], fontsize=8)
        ax.set_yticks(range(len(pivot_h.index)))
        ax.set_yticklabels(pivot_h.index)
        plt.colorbar(im, ax=ax, label="Czas [s]")
        ax.set_title(f"Heatmapa czasów – wszystkie scenariusze z indeksami ({size})", fontsize=13)
        plt.tight_layout()
        path = os.path.join(RESULTS_DIR, f"chart_heatmap_{size}.png")
        plt.savefig(path, dpi=150)
        plt.close()
        print(f"  ✅ {path}")

    print(f"\n✅ Wykresy zapisane w katalogu: {RESULTS_DIR}/")


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="Orkiestrator testów CRUD – e-Ticket")
    parser.add_argument("--phase",
        choices=["without_indexes", "with_indexes", "both", "charts"],
        default="both")
    parser.add_argument("--size",
        choices=["small", "medium", "large"],
        default="small")
    args = parser.parse_args()

    total_start = time.time()

    if args.phase == "without_indexes":
        run_phase("without_indexes", args.size)

    elif args.phase == "with_indexes":
        run_phase("with_indexes", args.size)

    elif args.phase == "both":
        run_phase("without_indexes", args.size)
        run_phase("with_indexes",    args.size)
        print("\n📊 Generowanie wykresów...")
        generate_charts(args.size)

    elif args.phase == "charts":
        print("\n📊 Generowanie wykresów...")
        generate_charts(args.size)

    total = time.time() - total_start
    print(f"\n{'='*60}")
    print(f"✅ Zakończono! Łączny czas: {total:.1f}s")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
