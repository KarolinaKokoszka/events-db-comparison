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
import json
import os
import time
from datetime import datetime

from scenarios import SCENARIOS

BASE_DIR    = os.path.dirname(os.path.abspath(__file__))
RESULTS_DIR = os.path.join(BASE_DIR, "results")
REPEATS     = 3

def get_db_modules():
    import crud_postgres
    import crud_mysql
    import crud_mongo
    import crud_neo4j
    return {
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
    print(f"\n[INFO] Wyniki zapisane: {filename}")
    return filename


# ─────────────────────────────────────────────
# FAZA TESTÓW
# ─────────────────────────────────────────────
def run_phase(phase: str, size: str):
    print(f"\n{'='*60}")
    print(f"  FAZA: {phase.upper()}  |  ROZMIAR: {size.upper()}")
    print(f"{'='*60}")

    db_modules = get_db_modules()

    # Zarządzaj indeksami
    if phase == "without_indexes":
        print("\n[INFO] Usuwanie indeksów ze wszystkich baz...")
        for name, module in db_modules.items():
            try:
                module.drop_indexes()
            except Exception as e:
                print(f"  [WARN] {name}: {e}")

    elif phase == "with_indexes":
        print("\n[INFO] Tworzenie indeksów we wszystkich bazach...")
        for name, module in db_modules.items():
            try:
                module.create_indexes()
            except Exception as e:
                print(f"  [WARN] {name}: {e}")

    # Uruchom testy
    all_results = []
    for db_name, module in db_modules.items():
        print(f"\n[RUN] {db_name}...")
        start = time.time()
        try:
            results = module.run_all_scenarios(repeats=REPEATS)
            all_results.append((db_name, results))
        except Exception as e:
            print(f"  [ERROR] {db_name} - krytyczny blad: {e}")
        elapsed = time.time() - start
        print(f"  [TIME] {db_name}: {elapsed:.1f}s")

    # Zapisz CSV
    csv_path = save_csv(all_results, phase, size)
    return csv_path


# ─────────────────────────────────────────────
# WYKRESY
# ─────────────────────────────────────────────
def build_dashboard_html(size: str, records: list, scenarios: list) -> str:
    records_json = json.dumps(records, ensure_ascii=False)
    scenarios_json = json.dumps(scenarios, ensure_ascii=False)
    return f"""<!DOCTYPE html>
<html lang="pl">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>CRUD Dashboard ({size})</title>
  <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
  <style>
    :root {{
      --pg: #336791; --my: #F29111; --mo: #47A248; --n4: #008CC1;
      --line: #d9d9d9; --bg: #f7f7f8; --card: #ffffff; --text: #252525; --muted: #6c6c6c;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      background: var(--bg);
      color: var(--text);
      font-family: Segoe UI, Arial, sans-serif;
    }}
    .wrap {{ max-width: 1400px; margin: 0 auto; padding: 20px; }}
    h1 {{ margin: 0 0 6px 0; font-size: 24px; }}
    .subtitle {{ color: var(--muted); margin-bottom: 14px; }}
    .tabs {{
      display: flex; gap: 8px; margin-bottom: 12px; flex-wrap: wrap;
    }}
    .tab-btn {{
      border: 1px solid #c8c8c8; background: #efefef; padding: 8px 14px; border-radius: 8px;
      cursor: pointer; font-weight: 600;
    }}
    .tab-btn.active {{ background: #ffffff; border-color: #8c8c8c; }}
    .filters {{
      display: flex; gap: 8px; margin-bottom: 12px; flex-wrap: wrap;
    }}
    select {{
      border: 1px solid #d2d2d2; background: #fff; border-radius: 6px; padding: 7px 10px; min-width: 260px;
    }}
    .legend {{
      display: flex; gap: 14px; flex-wrap: wrap; margin: 8px 0 10px 0; color: #444;
    }}
    .legend-item {{ display: inline-flex; align-items: center; gap: 6px; font-size: 14px; }}
    .dot {{ width: 10px; height: 10px; border-radius: 2px; display: inline-block; }}
    .card {{
      background: var(--card);
      border: 1px solid var(--line);
      border-radius: 10px;
      padding: 12px;
      margin-bottom: 12px;
    }}
    .tab-content {{ display: none; }}
    .tab-content.active {{ display: block; }}
    .grid-2 {{ display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }}
    .grid-4 {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; }}
    .kpi {{
      border: 1px solid var(--line); border-radius: 8px; background: #fcfcfc; padding: 10px;
    }}
    .kpi .label {{ color: var(--muted); font-size: 12px; margin-bottom: 3px; }}
    .kpi .value {{ font-weight: 700; font-size: 20px; }}
    .kpi .sub {{ color: var(--muted); font-size: 12px; margin-top: 2px; }}
    .table-wrap {{ overflow-x: auto; }}
    table {{
      border-collapse: collapse; width: 100%; background: #fff;
    }}
    th, td {{
      border: 1px solid var(--line); padding: 6px 8px; text-align: left; font-size: 13px;
    }}
    th {{ background: #f2f2f2; }}
    .ok {{ color: #1f7a2f; font-weight: 600; }}
    @media (max-width: 1100px) {{
      .grid-2, .grid-4 {{ grid-template-columns: 1fr; }}
    }}
  </style>
</head>
<body>
  <div class="wrap">
    <h1>CRUD Dashboard</h1>
    <div class="subtitle">Rozmiar: <strong>{size.upper()}</strong> · źródło: pliki CSV w folderze <code>tests/results</code></div>

    <div class="tabs" id="tabs"></div>
    <div class="filters">
      <select id="operation-filter"></select>
      <select id="phase-filter"></select>
    </div>
    <div class="legend" id="legend"></div>

    <section id="tab-overview" class="tab-content">
      <div class="card">
        <canvas id="chart-overview" height="120"></canvas>
      </div>
      <div class="card">
        <h3>Najlepsza baza per operacja</h3>
        <div class="grid-4" id="kpi-best"></div>
      </div>
      <div class="card">
        <h3>Sumaryczny czas wszystkich scenariuszy per baza</h3>
        <canvas id="chart-total" height="90"></canvas>
      </div>
    </section>

    <section id="tab-h1" class="tab-content">
      <div class="grid-2">
        <div class="card"><canvas id="chart-h1-create" height="120"></canvas></div>
        <div class="card"><canvas id="chart-h1-read" height="120"></canvas></div>
        <div class="card"><canvas id="chart-h1-update" height="120"></canvas></div>
        <div class="card"><canvas id="chart-h1-delete" height="120"></canvas></div>
      </div>
    </section>

    <section id="tab-scenarios" class="tab-content">
      <div class="card">
        <canvas id="chart-scenarios" height="500"></canvas>
      </div>
      <div class="card">
        <h3>Zwycięzca per scenariusz</h3>
        <div class="table-wrap">
          <table id="table-winners">
            <thead>
              <tr><th>Scenariusz</th><th>Operacja</th><th>Najlepsza baza</th><th>Czas [ms]</th></tr>
            </thead>
            <tbody></tbody>
          </table>
        </div>
      </div>
    </section>

    <section id="tab-json" class="tab-content">
      <div class="card">
        <canvas id="chart-json" height="120"></canvas>
      </div>
      <div class="card">
        <h3>Podsumowanie JSON vs zwykłe</h3>
        <div class="table-wrap">
          <table id="table-json">
            <thead>
              <tr><th>Baza</th><th>JSON [ms]</th><th>Zwykłe [ms]</th><th>Różnica (JSON - zwykłe) [ms]</th></tr>
            </thead>
            <tbody></tbody>
          </table>
        </div>
      </div>
    </section>
  </div>

  <script>
    const RECORDS = {records_json};
    const SCENARIOS = {scenarios_json};
    const DBS = ["PostgreSQL", "MySQL", "MongoDB", "Neo4j"];
    const COLORS = {{
      "PostgreSQL": "#336791",
      "MySQL": "#F29111",
      "MongoDB": "#47A248",
      "Neo4j": "#008CC1",
    }};
    const OPS = ["CREATE", "READ", "UPDATE", "DELETE"];
    const TAB_DEF = [
      {{ id: "overview", label: "Przegląd CRUD" }},
      {{ id: "h1", label: "Wpływ indeksów (H1)" }},
      {{ id: "scenarios", label: "Scenariusze szczegółowo" }},
      {{ id: "json", label: "JSON vs zwykłe" }},
    ];

    const scenarioMap = Object.fromEntries(SCENARIOS.map(s => [String(s.id), s]));
    const records = RECORDS.map(r => ({{
      ...r,
      avg_time_s: Number(r.avg_time_s),
      try_1: r.try_1 == null ? null : Number(r.try_1),
      try_2: r.try_2 == null ? null : Number(r.try_2),
      try_3: r.try_3 == null ? null : Number(r.try_3),
      scenario_id: Number(r.scenario_id),
      json_related: String(r.json_related).toLowerCase() === "true",
    }})).filter(r => r.avg_time_s > 0);

    const charts = {{}};
    function ms(v) {{ return Math.round(v * 1000 * 100) / 100; }}
    function avg(vals) {{
      if (!vals.length) return null;
      return vals.reduce((a, b) => a + b, 0) / vals.length;
    }}
    function by(filters = {{}}) {{
      return records.filter(r => {{
        if (filters.phase && filters.phase !== "all" && r.phase !== filters.phase) return false;
        if (filters.operation && filters.operation !== "all" && r.operation !== filters.operation) return false;
        return true;
      }});
    }}
    function groupedAvg(rows, keyFn) {{
      const buckets = new Map();
      for (const r of rows) {{
        const key = keyFn(r);
        if (!buckets.has(key)) buckets.set(key, []);
        buckets.get(key).push(r.avg_time_s);
      }}
      const out = {{}};
      for (const [k, vals] of buckets.entries()) out[k] = avg(vals);
      return out;
    }}
    function setLegend() {{
      document.getElementById("legend").innerHTML = DBS.map(db =>
        `<span class="legend-item"><span class="dot" style="background:${{COLORS[db]}}"></span>${{db}}</span>`
      ).join("");
    }}

    function initTabs() {{
      const tabsEl = document.getElementById("tabs");
      tabsEl.innerHTML = TAB_DEF.map((t, i) =>
        `<button class="tab-btn ${{i === 0 ? "active" : ""}}" data-tab="${{t.id}}">${{t.label}}</button>`
      ).join("");
      document.querySelectorAll(".tab-btn").forEach(btn => {{
        btn.addEventListener("click", () => {{
          document.querySelectorAll(".tab-btn").forEach(b => b.classList.remove("active"));
          btn.classList.add("active");
          document.querySelectorAll(".tab-content").forEach(c => c.classList.remove("active"));
          document.getElementById(`tab-${{btn.dataset.tab}}`).classList.add("active");
        }});
      }});
      document.getElementById("tab-overview").classList.add("active");
    }}

    function initFilters() {{
      const opSel = document.getElementById("operation-filter");
      const phaseSel = document.getElementById("phase-filter");
      opSel.innerHTML = `<option value="all">Wszystkie operacje</option>` + OPS.map(op => `<option value="${{op}}">${{op}}</option>`).join("");
      phaseSel.innerHTML = `
        <option value="with_indexes">Z indeksami</option>
        <option value="without_indexes">Bez indeksów</option>
        <option value="all">Obie fazy</option>
      `;
      opSel.value = "all";
      phaseSel.value = "with_indexes";
      opSel.addEventListener("change", renderAll);
      phaseSel.addEventListener("change", renderAll);
    }}

    function baseBarOptions(indexAxis = "x") {{
      return {{
        responsive: true,
        maintainAspectRatio: false,
        indexAxis,
        plugins: {{ legend: {{ labels: {{ boxWidth: 12 }} }} }},
        scales: {{
          y: {{ ticks: {{ callback: (v) => `${{v}} ms` }} }},
          x: {{ ticks: {{ autoSkip: false }} }},
        }},
      }};
    }}

    function makeChart(id, cfg) {{
      if (charts[id]) charts[id].destroy();
      charts[id] = new Chart(document.getElementById(id), cfg);
    }}

    function renderOverview(filters) {{
      const rows = by(filters);
      const perDbOp = {{}};
      for (const db of DBS) {{
        perDbOp[db] = {{}};
        for (const op of OPS) {{
          const vals = rows.filter(r => r.db === db && r.operation === op).map(r => r.avg_time_s);
          perDbOp[db][op] = avg(vals);
        }}
      }}
      makeChart("chart-overview", {{
        type: "bar",
        data: {{
          labels: OPS,
          datasets: DBS.map(db => ({{
            label: db,
            data: OPS.map(op => perDbOp[db][op] == null ? 0 : ms(perDbOp[db][op])),
            backgroundColor: COLORS[db] + "bb",
            borderColor: COLORS[db],
            borderWidth: 1,
          }})),
        }},
        options: baseBarOptions("x"),
      }});

      const kpi = document.getElementById("kpi-best");
      kpi.innerHTML = OPS.map(op => {{
        let bestDb = null;
        let bestVal = Infinity;
        for (const db of DBS) {{
          const v = perDbOp[db][op];
          if (v != null && v < bestVal) {{ bestVal = v; bestDb = db; }}
        }}
        return `
          <div class="kpi">
            <div class="label">${{op}}</div>
            <div class="value" style="color:${{COLORS[bestDb] || "#222"}}">${{bestDb || "-"}}</div>
            <div class="sub">${{bestVal < Infinity ? ms(bestVal) + " ms" : "-"}}</div>
          </div>
        `;
      }}).join("");

      const sumByDb = {{}};
      for (const db of DBS) {{
        const vals = rows.filter(r => r.db === db).map(r => r.avg_time_s);
        sumByDb[db] = vals.reduce((a, b) => a + b, 0);
      }}
      makeChart("chart-total", {{
        type: "bar",
        data: {{
          labels: DBS,
          datasets: [{{
            label: "Suma czasów [ms]",
            data: DBS.map(db => ms(sumByDb[db] || 0)),
            backgroundColor: DBS.map(db => COLORS[db] + "bb"),
            borderColor: DBS.map(db => COLORS[db]),
            borderWidth: 1,
          }}]
        }},
        options: baseBarOptions("x"),
      }});
    }}

    function renderH1(operationFilter) {{
      const opsToShow = operationFilter === "all" ? OPS : [operationFilter];
      const ids = {{
        CREATE: "chart-h1-create",
        READ: "chart-h1-read",
        UPDATE: "chart-h1-update",
        DELETE: "chart-h1-delete",
      }};
      for (const op of OPS) {{
        const el = document.getElementById(ids[op]).parentElement.parentElement;
        el.style.display = opsToShow.includes(op) ? "block" : "none";

        const withRows = by({{ phase: "with_indexes", operation: op }});
        const withoutRows = by({{ phase: "without_indexes", operation: op }});

        const dWith = groupedAvg(withRows, r => r.db);
        const dWithout = groupedAvg(withoutRows, r => r.db);

        makeChart(ids[op], {{
          type: "bar",
          data: {{
            labels: DBS,
            datasets: [
              {{
                label: "Bez indeksów",
                data: DBS.map(db => ms(dWithout[db] || 0)),
                backgroundColor: "#d95f5f99",
                borderColor: "#d95f5f",
                borderWidth: 1,
              }},
              {{
                label: "Z indeksami",
                data: DBS.map(db => ms(dWith[db] || 0)),
                backgroundColor: "#4caf5099",
                borderColor: "#4caf50",
                borderWidth: 1,
              }},
            ],
          }},
          options: baseBarOptions("x"),
        }});
      }}
    }}

    function renderScenarioChart(filters) {{
      const rows = by(filters);
      const opFilter = filters.operation;
      const scRows = rows
        .slice()
        .sort((a, b) => a.scenario_id - b.scenario_id)
        .filter(r => opFilter === "all" || r.operation === opFilter);
      const scenarioIds = [...new Set(scRows.map(r => r.scenario_id))];
      const labels = scenarioIds.map(sid => {{
        const meta = scenarioMap[String(sid)];
        return meta ? `S${{sid}}: ${{meta.name}}` : `S${{sid}}`;
      }});
      makeChart("chart-scenarios", {{
        type: "bar",
        data: {{
          labels,
          datasets: DBS.map(db => {{
            const bySc = Object.fromEntries(
              scRows.filter(r => r.db === db).map(r => [r.scenario_id, r.avg_time_s])
            );
            return {{
              label: db,
              data: scenarioIds.map(sid => ms(bySc[sid] || 0)),
              backgroundColor: COLORS[db] + "bb",
              borderColor: COLORS[db],
              borderWidth: 1,
            }};
          }}),
        }},
        options: baseBarOptions("y"),
      }});

      const tbody = document.querySelector("#table-winners tbody");
      const winners = [];
      for (const sid of scenarioIds) {{
        const rowsSid = scRows.filter(r => r.scenario_id === sid);
        if (!rowsSid.length) continue;
        rowsSid.sort((a, b) => a.avg_time_s - b.avg_time_s);
        winners.push(rowsSid[0]);
      }}
      tbody.innerHTML = winners.map(w => {{
        const meta = scenarioMap[String(w.scenario_id)];
        const name = meta ? `S${{w.scenario_id}}: ${{meta.name}}` : `S${{w.scenario_id}}`;
        return `<tr>
          <td>${{name}}</td>
          <td>${{w.operation}}</td>
          <td class="ok">${{w.db}}</td>
          <td>${{ms(w.avg_time_s)}}</td>
        </tr>`;
      }}).join("");
    }}

    function renderJson(filters) {{
      const rows = by(filters);
      const nonJsonRows = rows.filter(r => !r.json_related);
      const jsonRows = rows.filter(r => r.json_related);

      const jsonByDb = groupedAvg(jsonRows, r => r.db);
      const nonJsonByDb = groupedAvg(nonJsonRows, r => r.db);

      makeChart("chart-json", {{
        type: "bar",
        data: {{
          labels: DBS,
          datasets: [
            {{
              label: "Zwykłe scenariusze",
              data: DBS.map(db => ms(nonJsonByDb[db] || 0)),
              backgroundColor: "#3498db99",
              borderColor: "#3498db",
              borderWidth: 1,
            }},
            {{
              label: "Scenariusze JSON",
              data: DBS.map(db => ms(jsonByDb[db] || 0)),
              backgroundColor: "#e67e2299",
              borderColor: "#e67e22",
              borderWidth: 1,
            }},
          ],
        }},
        options: baseBarOptions("x"),
      }});

      const tbody = document.querySelector("#table-json tbody");
      tbody.innerHTML = DBS.map(db => {{
        const j = jsonByDb[db] || 0;
        const n = nonJsonByDb[db] || 0;
        return `<tr>
          <td>${{db}}</td>
          <td>${{ms(j)}}</td>
          <td>${{ms(n)}}</td>
          <td>${{ms(j - n)}}</td>
        </tr>`;
      }}).join("");
    }}

    function renderAll() {{
      const filters = {{
        operation: document.getElementById("operation-filter").value,
        phase: document.getElementById("phase-filter").value,
      }};
      renderOverview(filters);
      renderH1(filters.operation);
      renderScenarioChart(filters);
      renderJson(filters);
    }}

    initTabs();
    initFilters();
    setLegend();
    renderAll();
  </script>
</body>
</html>
"""


def generate_charts(size: str):
    try:
        import pandas as pd
    except ImportError:
        print("[ERROR] Zainstaluj: pip install pandas")
        return

    os.makedirs(RESULTS_DIR, exist_ok=True)

    # Wczytaj oba pliki CSV
    dfs = []
    for phase in ["without_indexes", "with_indexes"]:
        path = os.path.join(RESULTS_DIR, f"results_{size}_{phase}.csv")
        if os.path.exists(path):
            df = pd.read_csv(path)
            dfs.append(df)
        else:
            print(f"[WARN] Brak pliku: {path} - pomin faze {phase}")

    if not dfs:
        print("[ERROR] Brak plikow CSV do wygenerowania wykresow.")
        return

    df_all = pd.concat(dfs, ignore_index=True)
    scenario_meta = [
        {
            "id": s["id"],
            "operation": s["operation"],
            "name": s["name"],
            "json_related": bool(s["json_related"]),
        }
        for s in SCENARIOS
    ]
    records = df_all.to_dict(orient="records")
    html = build_dashboard_html(size=size, records=records, scenarios=scenario_meta)
    path = os.path.join(RESULTS_DIR, f"dashboard_{size}.html")
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"\n[OK] Dashboard zapisany: {path}")


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
        print("\n[INFO] Generowanie wykresow...")
        generate_charts(args.size)

    elif args.phase == "charts":
        print("\n[INFO] Generowanie wykresow...")
        generate_charts(args.size)

    total = time.time() - total_start
    print(f"\n{'='*60}")
    print(f"[OK] Zakonczono! Laczny czas: {total:.1f}s")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
