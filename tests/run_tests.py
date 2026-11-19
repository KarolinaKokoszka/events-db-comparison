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


def run_phase(phase: str, size: str):
    print(f"\n{'='*60}")
    print(f"  FAZA: {phase.upper()}  |  ROZMIAR: {size.upper()}")
    print(f"{'='*60}")

    db_modules = get_db_modules()
    index_errors = []

    if phase == "without_indexes":
        print("\n[INFO] Usuwanie indeksów ze wszystkich baz...")
        for name, module in db_modules.items():
            try:
                module.drop_indexes()
            except Exception as e:
                err = str(e)
                if name == "MySQL" and ("1553" in err or "1091" in err):
                    print(f"  [WARN] {name}: drop_indexes() non-critical: {err}")
                    continue
                print(f"  [ERROR] {name}: drop_indexes() failed: {err}")
                index_errors.append((name, "drop_indexes", err))

    elif phase == "with_indexes":
        print("\n[INFO] Tworzenie indeksów we wszystkich bazach...")
        for name, module in db_modules.items():
            try:
                module.create_indexes()
            except Exception as e:
                print(f"  [ERROR] {name}: create_indexes() failed: {e}")
                index_errors.append((name, "create_indexes", str(e)))

    if index_errors:
        print("\n[ERROR] Krytyczny błąd zarządzania indeksami, przerwanie fazy.")
        for db_name, action, err in index_errors:
            print(f"  - {db_name} | {action}: {err}")
        raise RuntimeError(f"Index management failed for {len(index_errors)} database(s).")

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

    csv_path = save_csv(all_results, phase, size)
    return csv_path


def build_dashboard_html(size: str, records: list, scenarios: list) -> str:
    records_json = json.dumps(records, ensure_ascii=False)
    scenarios_json = json.dumps(scenarios, ensure_ascii=False)
    size_totals = {"small": 500_000, "medium": 1_000_000, "large": 10_000_000}
    size_total = size_totals.get(size)
    size_meta = f"Wielkosc zbioru: {size_total:,} rekordow".replace(",", " ") if size_total else "Wielkosc zbioru: -"
    return f"""<!DOCTYPE html>
<html lang="pl">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>CRUD Dashboard ({size})</title>
  <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
  <style>
    :root {{
      --pg: #346da1; --my: #ffa536; --mo: #2fb4a2; --n4: #fb5937;
      --header: #1f2f57;
      --line: #d9dce6; --bg: #f2f4f8; --card: #ffffff; --text: #1e2d4a; --muted: #627091;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      background: var(--bg);
      color: var(--text);
      font-family: Segoe UI, Arial, sans-serif;
    }}
    .wrap {{ max-width: 1400px; margin: 0 auto; padding: 20px; }}
    .hero {{
      background: linear-gradient(135deg, #1f2f57 0%, #293f74 100%);
      color: #f4f7ff;
      border-radius: 14px;
      padding: 16px 18px 0 18px;
      margin-bottom: 12px;
    }}
    .hero-top {{
      display: flex; justify-content: space-between; align-items: flex-start; gap: 8px;
      margin-bottom: 8px;
    }}
    .hero-title {{
      margin: 0 0 4px 0;
      font-size: 30px;
      font-weight: 700;
      letter-spacing: 0.2px;
      color: #f2f6ff;
      text-shadow: 0 1px 0 rgba(0, 0, 0, 0.12);
    }}
    .hero-meta {{
      color: #c7d7ff;
      margin: 0 0 10px 0;
      font-size: 12px;
      font-weight: 600;
      letter-spacing: 0.1px;
    }}
    .size-chip {{
      border: 1px solid #6f93de; color: #edf3ff; border-radius: 14px;
      font-weight: 600; font-size: 12px; padding: 3px 10px;
      background: rgba(255, 255, 255, 0.08);
    }}
    .tabs {{
      display: flex; gap: 8px; margin-bottom: 0; flex-wrap: wrap;
    }}
    .top-controls {{
      display: flex; gap: 10px; margin-bottom: 0; flex-wrap: wrap; align-items: flex-end;
    }}
    .tab-btn {{
      border: 1px solid #5470ad; background: rgba(255, 255, 255, 0.04); color: #e5eeff;
      border-bottom: 0;
      padding: 8px 14px; border-radius: 9px 9px 0 0; cursor: pointer; font-weight: 600;
      transition: background 120ms ease, border-color 120ms ease, color 120ms ease;
    }}
    .tab-btn:hover {{ background: rgba(255, 255, 255, 0.12); border-color: #7f9ddf; }}
    .tab-btn.active {{ background: var(--bg); color: var(--text); border-color: #cfd5e4; border-bottom: 0; }}
    .filters {{
      display: flex; gap: 8px; margin-bottom: 12px; flex-wrap: wrap;
    }}
    select {{
      border: 1px solid #d2d2d2; background: #fff; border-radius: 6px; padding: 7px 10px; min-width: 260px;
    }}
    .chart-note {{ margin: 4px 0 10px 0; color: var(--muted); font-size: 12px; }}
    .legend {{
      display: flex; gap: 14px; flex-wrap: wrap; margin: 8px 0 10px 0; color: #444;
    }}
    .legend-item {{ display: inline-flex; align-items: center; gap: 6px; font-size: 14px; }}
    .dot {{ width: 10px; height: 10px; border-radius: 2px; display: inline-block; }}
    .chart-box-sm {{ height: 180px; }}
    .chart-box-md {{ height: 260px; }}
    .chart-box-lg {{ height: 520px; }}
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
    .overview-bottom {{ margin-bottom: 12px; }}
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
    .op-chip {{
      display: inline-block; border-radius: 12px; padding: 2px 8px; font-size: 11px; font-weight: 600;
      border: 1px solid #d3d8e5; color: #45516f; background: #f6f7fb;
    }}
    .op-create {{ background: #eef5ff; border-color: #d8e7ff; color: #355f95; }}
    .op-update {{ background: #eef8ee; border-color: #d8edd8; color: #3f7442; }}
    .op-read, .op-delete {{ background: #f1f2f5; border-color: #dfe2e8; color: #5a6071; }}
    .delta-controls {{ display:flex; align-items:center; gap:10px; margin-bottom:8px; flex-wrap:wrap; }}
    .delta-mini-card {{ background:#f8f9fc; border:1px solid #e3e7f0; border-radius:10px; padding:12px 14px; }}
    .delta-mini-title {{ font-size:13px; font-weight:800; margin-bottom:6px; }}
    #table-top5 td:last-child, #table-bot5 td:last-child {{ font-weight:700; }}
    .delta-pos {{ color: #1a7a3c; }}
    .delta-neg {{ color: #b91c1c; }}
    .heatmap-wrap {{ overflow-x: auto; }}
    .heatmap {{
      width: 100%;
      border-collapse: collapse;
      table-layout: fixed;
      font-size: 12px;
      background: #fff;
    }}
    .heatmap th, .heatmap td {{
      border: 1px solid var(--line);
      padding: 6px;
      text-align: center;
      vertical-align: middle;
    }}
    .heatmap th {{ background: #f2f2f2; font-weight: 700; }}
    .heatmap th:first-child, .heatmap td:first-child {{ text-align: left; min-width: 280px; }}
    .heatmap td.hm-cell {{ font-variant-numeric: tabular-nums; }}
    @media (max-width: 1100px) {{
      .grid-2, .grid-4 {{ grid-template-columns: 1fr; }}
    }}
  </style>
</head>
<body>
  <div class="wrap">
    <div class="hero">
      <div class="hero-top">
        <div>
          <h1 class="hero-title">Porownanie wydajnosci baz danych</h1>
          <div class="hero-meta">{size_meta}</div>
        </div>
        <span class="size-chip">{size.upper()}</span>
      </div>
      <div class="top-controls">
        <div class="tabs" id="tabs"></div>
      </div>
    </div>
    <div class="filters" id="scenario-filters">
      <select id="phase-filter"></select>
    </div>
    <div class="legend" id="legend"></div>

    <section id="tab-overview" class="tab-content">
      <div class="card">
        <h3>Najlepsza baza per operacja</h3>
        <p class="chart-note">Najlepsza baza = najnizsza srednia wartosc dla operacji z odpowiadajacych jej 6 scenariuszy.</p>
        <div class="grid-4" id="kpi-best"></div>
      </div>
      <div class="card">
        <h3>Przegląd CRUD (średni czas per operacja i baza)</h3>
        <p class="chart-note">Wartosc slupka = srednia z 6 scenariuszy danej operacji (CREATE/READ/UPDATE/DELETE) dla bazy; kazdy scenariusz korzysta z avg_time_s (srednia z 3 prob).</p>
        <div class="chart-box-md"><canvas id="chart-overview"></canvas></div>
      </div>
      <div class="grid-2 overview-bottom">
        <div class="card">
          <h3>Ranking zwycięstw (najszybsza baza per scenariusz)</h3>
          <p class="chart-note">Wygrana = najnizsze avg_time_s w scenariuszu (avg_time_s to srednia z 3 prob). Ranking liczy wygrane po wszystkich scenariuszach.</p>
          <div class="table-wrap">
            <table id="table-wins">
              <thead>
                <tr><th>Miejsce</th><th>Baza</th><th>Wygrane</th><th>Udział</th></tr>
              </thead>
              <tbody></tbody>
            </table>
          </div>
        </div>
        <div class="card">
          <h3>Sumaryczny czas wszystkich scenariuszy per baza</h3>
          <p class="chart-note">Suma avg_time_s po wszystkich scenariuszach dla bazy (pokazuje laczne obciazenie testami dla danej fazy).</p>
          <div class="chart-box-sm"><canvas id="chart-total"></canvas></div>
        </div>
      </div>
    </section>

    <section id="tab-h1" class="tab-content">
      <div class="grid-2">
        <div class="card"><h3>CREATE - bez vs z indeksami</h3><p class="chart-note">Dla kazdej bazy: srednia z avg_time_s scenariuszy S1-S6, osobno bez i z indeksami.</p><div class="chart-box-sm"><canvas id="chart-h1-create"></canvas></div></div>
        <div class="card"><h3>READ - bez vs z indeksami</h3><p class="chart-note">Dla kazdej bazy: srednia z avg_time_s scenariuszy S7-S12, osobno bez i z indeksami.</p><div class="chart-box-sm"><canvas id="chart-h1-read"></canvas></div></div>
        <div class="card"><h3>UPDATE - bez vs z indeksami</h3><p class="chart-note">Dla kazdej bazy: srednia z avg_time_s scenariuszy S13-S18, osobno bez i z indeksami.</p><div class="chart-box-sm"><canvas id="chart-h1-update"></canvas></div></div>
        <div class="card"><h3>DELETE - bez vs z indeksami</h3><p class="chart-note">Dla kazdej bazy: srednia z avg_time_s scenariuszy S19-S24, osobno bez i z indeksami.</p><div class="chart-box-sm"><canvas id="chart-h1-delete"></canvas></div></div>
      </div>
    </section>

    <section id="tab-scenarios" class="tab-content">
      <div class="card">
        <h3>Porównanie baz per scenariusz</h3>
        <p class="chart-note">Kazdy slupek to avg_time_s danego scenariusza i bazy (avg_time_s = srednia z 3 prob: try_1, try_2, try_3).</p>
        <div class="chart-box-lg"><canvas id="chart-scenarios"></canvas></div>
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
        <h3>Scenariusze JSON (S3, S11, S17) - porownanie baz</h3>
        <p class="chart-note">Grupy na osi X to scenariusze S3, S11 i S17, a slupki pokazuja czas [ms] dla PostgreSQL, MySQL, MongoDB i Neo4j (avg_time_s z fazy with_indexes).</p>
        <div class="chart-box-md"><canvas id="chart-json"></canvas></div>
      </div>
      <div class="card">
        <h3>Podsumowanie JSON</h3>
        <div class="table-wrap">
          <table id="table-json">
            <thead>
              <tr><th>Baza</th><th>Średni czas JSON [ms]</th></tr>
            </thead>
            <tbody></tbody>
          </table>
        </div>
      </div>
    </section>

    <section id="tab-delta" class="tab-content">
      <div class="card">
        <h3>Heatmapa delta: zmiana czasu po dodaniu indeksów (% per scenariusz)</h3>
        <p class="chart-note">
          Wartosc dodatnia (zielona) = indeks pomaga. Wartosc ujemna (czerwona) = indeks szkodzi.
          Zakres kolorow jest saturwany do +/-100%, a wartosci w pasmie +/-5% sa neutralne.
        </p>
        <div class="heatmap-wrap"><table id="table-heatmap-delta" class="heatmap"></table></div>
      </div>
      <div class="grid-2" style="margin-top:0;">
        <div class="card">
          <h3>TOP 5 - największa poprawa z indeksem</h3>
          <p class="chart-note">Scenariusze (baza + operacja), dla których indeksy przyniosły największy zysk wydajnościowy.</p>
          <div class="table-wrap">
            <table id="table-top5">
              <thead><tr><th>#</th><th>Scenariusz</th><th>Op.</th><th>Baza</th><th>Bez ind. [ms]</th><th>Z ind. [ms]</th><th>Δ [ms]</th><th>Δ [%]</th></tr></thead>
              <tbody></tbody>
            </table>
          </div>
        </div>
        <div class="card">
          <h3>TOP 5 - największe pogorszenie z indeksem</h3>
          <p class="chart-note">Scenariusze (baza + operacja), dla których indeksy najbardziej wydłużyły czas wykonania.</p>
          <div class="table-wrap">
            <table id="table-bot5">
              <thead><tr><th>#</th><th>Scenariusz</th><th>Op.</th><th>Baza</th><th>Bez ind. [ms]</th><th>Z ind. [ms]</th><th>Δ [ms]</th><th>Δ [%]</th></tr></thead>
              <tbody></tbody>
            </table>
          </div>
        </div>
      </div>
    </section>
  </div>

  <script>
    const RECORDS = {records_json};
    const SCENARIOS = {scenarios_json};
    const DBS = ["PostgreSQL", "MySQL", "MongoDB", "Neo4j"];
    const COLORS = {{
      "PostgreSQL": "#346da1",
      "MySQL": "#ffa536",
      "MongoDB": "#2fb4a2",
      "Neo4j": "#fb5937",
    }};
    const OPS = ["CREATE", "READ", "UPDATE", "DELETE"];
    const TAB_DEF = [
      {{ id: "overview", label: "Przegląd CRUD" }},
      {{ id: "h1", label: "Wpływ indeksów" }},
      {{ id: "delta", label: "Wpływ indeksów (szczegóły)" }},
      {{ id: "scenarios", label: "Scenariusze szczegółowo" }},
      {{ id: "json", label: "JSON" }},
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
    function fmtMs(v) {{
      if (v == null || Number.isNaN(v)) return "-";
      return ms(v).toFixed(2);
    }}
    function setLegend() {{
      document.getElementById("legend").innerHTML = DBS.map(db =>
        `<span class="legend-item"><span class="dot" style="background:${{COLORS[db]}}"></span>${{db}}</span>`
      ).join("");
    }}

    function activeTabId() {{
      return document.querySelector(".tab-btn.active")?.dataset.tab || "overview";
    }}

    function setActiveTab(tabId) {{
      document.querySelectorAll(".tab-btn").forEach(b => b.classList.toggle("active", b.dataset.tab === tabId));
      document.querySelectorAll(".tab-content").forEach(c => c.classList.remove("active"));
      document.getElementById(`tab-${{tabId}}`).classList.add("active");

      // Filtry pokazujemy tylko w zakladce scenariuszy.
      const filtersEl = document.getElementById("scenario-filters");
      filtersEl.style.display = tabId === "scenarios" ? "flex" : "none";
      const legendEl = document.getElementById("legend");
      legendEl.style.display = (tabId === "h1" || tabId === "json" || tabId === "delta") ? "none" : "flex";
      renderAll();
    }}

    function initTabs() {{
      const tabsEl = document.getElementById("tabs");
      tabsEl.innerHTML = TAB_DEF.map((t) =>
        `<button class="tab-btn" data-tab="${{t.id}}">${{t.label}}</button>`
      ).join("");
      document.querySelectorAll(".tab-btn").forEach(btn => {{
        btn.addEventListener("click", () => setActiveTab(btn.dataset.tab));
      }});
      setActiveTab("overview");
    }}

    function initFilters() {{
      const phaseSel = document.getElementById("phase-filter");
      phaseSel.innerHTML = `
        <option value="with_indexes">Z indeksami</option>
        <option value="without_indexes">Bez indeksów</option>
      `;
      phaseSel.value = "with_indexes";
      phaseSel.addEventListener("change", renderAll);
    }}

    function baseBarOptionsMs(indexAxis = "x", xTitle = "", yTitle = "Czas [ms]") {{
      return {{
        responsive: true,
        maintainAspectRatio: false,
        animation: {{ duration: 0 }},
        indexAxis,
        plugins: {{ legend: {{ labels: {{ boxWidth: 12 }} }} }},
        scales: {{
          y: {{
            title: {{ display: !!yTitle, text: yTitle }},
            beginAtZero: true,
            ticks: {{ callback: (v) => `${{v}} ms` }},
          }},
          x: {{
            title: {{ display: !!xTitle, text: xTitle }},
            ticks: {{ autoSkip: false }},
          }},
        }},
      }};
    }}

    function scenarioHorizontalOptions() {{
      return {{
        responsive: true,
        maintainAspectRatio: false,
        indexAxis: "y",
        plugins: {{ legend: {{ labels: {{ boxWidth: 12 }} }} }},
        scales: {{
          x: {{
            title: {{ display: true, text: "Czas [ms]" }},
            ticks: {{ callback: (v) => `${{v}} ms` }},
          }},
          y: {{
            title: {{ display: true, text: "Scenariusz" }},
            ticks: {{ autoSkip: false }},
          }},
        }},
      }};
    }}

    function makeChart(id, cfg) {{
      if (charts[id]) charts[id].destroy();
      charts[id] = new Chart(document.getElementById(id), cfg);
    }}

    function renderOverview() {{
      const rows = by({{ phase: "with_indexes", operation: "all" }});
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
        options: baseBarOptionsMs("x", "Operacja", "Czas [ms] (srednia)"),
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

      const scenarioIds = [...new Set(rows.map(r => r.scenario_id))].sort((a, b) => a - b);
      const wins = Object.fromEntries(DBS.map(db => [db, 0]));
      for (const sid of scenarioIds) {{
        const rowsSid = rows.filter(r => r.scenario_id === sid).sort((a, b) => a.avg_time_s - b.avg_time_s);
        if (rowsSid.length) wins[rowsSid[0].db] += 1;
      }}
      const ranking = DBS.map(db => ({{
        db,
        wins: wins[db],
        share: scenarioIds.length ? (wins[db] / scenarioIds.length) * 100 : 0,
      }})).sort((a, b) => b.wins - a.wins);
      const winsBody = document.querySelector("#table-wins tbody");
      winsBody.innerHTML = ranking.map((r, idx) => `<tr>
        <td>${{idx + 1}}</td>
        <td style="color:${{COLORS[r.db]}};font-weight:600">${{r.db}}</td>
        <td>${{r.wins}}</td>
        <td>${{r.share.toFixed(1)}}%</td>
      </tr>`).join("");

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
        options: baseBarOptionsMs("x", "Baza danych", "Czas [ms]"),
      }});
    }}

    function renderH1() {{
      const ids = {{
        CREATE: "chart-h1-create",
        READ: "chart-h1-read",
        UPDATE: "chart-h1-update",
        DELETE: "chart-h1-delete",
      }};
      for (const op of OPS) {{
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
                categoryPercentage: 0.7,
                barPercentage: 0.9,
              }},
              {{
                label: "Z indeksami",
                data: DBS.map(db => ms(dWith[db] || 0)),
                backgroundColor: "#4caf5099",
                borderColor: "#4caf50",
                borderWidth: 1,
                categoryPercentage: 0.7,
                barPercentage: 0.9,
              }},
            ],
          }},
          options: baseBarOptionsMs("x", "Baza danych", "Czas [ms] (srednia)"),
        }});
      }}
    }}

    function renderScenarioHeatmap(phase) {{
      const rows = by({{ phase, operation: "all" }});
      const scRows = rows.slice().sort((a, b) => a.scenario_id - b.scenario_id);
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
        options: scenarioHorizontalOptions(),
      }});

      const tbody = document.querySelector("#table-winners tbody");
      const winners = [];
      for (const sid of scenarioIds) {{
        const rowsSid = rows.filter(r => r.scenario_id === sid);
        if (!rowsSid.length) continue;
        rowsSid.sort((a, b) => a.avg_time_s - b.avg_time_s);
        winners.push(rowsSid[0]);
      }}
      tbody.innerHTML = winners.map(w => {{
        const meta = scenarioMap[String(w.scenario_id)];
        const name = meta ? `S${{w.scenario_id}}: ${{meta.name}}` : `S${{w.scenario_id}}`;
        const opClass = `op-${{(w.operation || "").toLowerCase()}}`;
        return `<tr>
          <td>${{name}}</td>
          <td><span class="op-chip ${{opClass}}">${{w.operation}}</span></td>
          <td class="ok">${{w.db}}</td>
          <td>${{fmtMs(w.avg_time_s)}}</td>
        </tr>`;
      }}).join("");
    }}

    function renderJson() {{
      const rows = by({{ phase: "with_indexes", operation: "all" }});
      const jsonScenarioIds = [3, 11, 17];
      const jsonRows = rows.filter(r => jsonScenarioIds.includes(r.scenario_id));
      const jsonByDb = groupedAvg(jsonRows, r => r.db);
      const labels = jsonScenarioIds.map(sid => {{
        const meta = scenarioMap[String(sid)];
        return meta ? `S${{sid}}: ${{meta.name}}` : `S${{sid}}`;
      }});

      makeChart("chart-json", {{
        type: "bar",
        data: {{
          labels,
          datasets: DBS.map(db => {{
            const byScenario = Object.fromEntries(
              jsonRows.filter(r => r.db === db).map(r => [r.scenario_id, r.avg_time_s])
            );
            return {{
              label: db,
              data: jsonScenarioIds.map(sid => ms(byScenario[sid] || 0)),
              backgroundColor: COLORS[db] + "bb",
              borderColor: COLORS[db],
              borderWidth: 1,
            }};
          }}),
        }},
        options: baseBarOptionsMs("x", "Scenariusz JSON", "Czas [ms]"),
      }});

      const tbody = document.querySelector("#table-json tbody");
      tbody.innerHTML = DBS.map(db => {{
        const j = jsonByDb[db] || 0;
        return `<tr>
          <td>${{db}}</td>
          <td>${{ms(j)}}</td>
        </tr>`;
      }}).join("");
    }}

    function computeDeltas() {{
      const deltas = [];
      for (const sc of SCENARIOS) {{
        for (const db of DBS) {{
          const wo = records.find(r => r.db === db && r.scenario_id === Number(sc.id) && r.phase === "without_indexes");
          const wi = records.find(r => r.db === db && r.scenario_id === Number(sc.id) && r.phase === "with_indexes");
          if (!wo || !wi) continue;
          const woMs = wo.avg_time_s * 1000;
          const wiMs = wi.avg_time_s * 1000;
          const deltaMs = woMs - wiMs;
          const deltaPct = woMs > 0 ? (deltaMs / woMs) * 100 : 0;
          deltas.push({{ db, sc, woMs, wiMs, deltaPct, deltaMs }});
        }}
      }}
      return deltas;
    }}

    function deltaCellColor(pct) {{
      const absPct = Math.abs(pct);
      if (absPct <= 5) return {{ bg: "#eceff3", fg: "#566074" }};
      if (pct > 0) {{
        const t = Math.min(pct, 100) / 100;
        const light = 88 - 48 * t;
        return {{ bg: `hsl(132, 58%, ${{light}}%)`, fg: light < 50 ? "#fff" : "#12321e" }};
      }}
      const t = Math.min(absPct, 100) / 100;
      const light = 88 - 48 * t;
      return {{ bg: `hsl(2, 68%, ${{light}}%)`, fg: light < 50 ? "#fff" : "#3f1111" }};
    }}

    function renderDelta() {{
      const allDeltas = computeDeltas();
      const scenarioIds = SCENARIOS.map(s => Number(s.id)).sort((a, b) => a - b);
      const table = document.getElementById("table-heatmap-delta");
      if (table) {{
        let html = "<thead><tr><th>Scenariusz</th>" + DBS.map(db => `<th>${{db}}</th>`).join("") + "</tr></thead><tbody>";
        for (const sid of scenarioIds) {{
          const meta = scenarioMap[String(sid)];
          const name = meta ? `S${{sid}}: ${{meta.name}}` : `S${{sid}}`;
          html += `<tr><td>${{name}}</td>`;
          for (const db of DBS) {{
            const d = allDeltas.find(x => Number(x.sc.id) === sid && x.db === db);
            if (!d) {{
              html += `<td class="hm-cell" style="background:#f5f7fb;color:#667;">-</td>`;
              continue;
            }}
            const colors = deltaCellColor(d.deltaPct);
            const label = `${{d.deltaPct >= 0 ? "+" : ""}}${{d.deltaPct.toFixed(1)}}%`;
            const op = meta ? meta.operation : "-";
            const tip = `${{name}} | ${{db}} | ${{op}} | bez: ${{d.woMs.toFixed(2)}} ms | z: ${{d.wiMs.toFixed(2)}} ms | delta: ${{d.deltaMs.toFixed(2)}} ms | ${{label}}`;
            html += `<td class="hm-cell" title="${{tip}}" style="background:${{colors.bg}};color:${{colors.fg}};">${{label}}</td>`;
          }}
          html += "</tr>";
        }}
        html += "</tbody>";
        table.innerHTML = html;
      }}
      allDeltas.sort((a, b) => b.deltaPct - a.deltaPct);
      const top5 = allDeltas.slice(0, 5);
      const bot5 = allDeltas.slice(-5).reverse();

      function fillTable(id, rows, isTop) {{
        const tbody = document.querySelector(`#${{id}} tbody`);
        if (!tbody) return;
        tbody.innerHTML = rows.map((d, i) => {{
          const cls = d.deltaPct >= 0 ? "delta-pos" : "delta-neg";
          const pct = `${{d.deltaPct >= 0 ? "+" : ""}}${{d.deltaPct.toFixed(1)}}%`;
          const deltaMsLabel = `${{d.deltaMs >= 0 ? "+" : ""}}${{d.deltaMs.toFixed(2)}}`;
          return `<tr>
            <td><strong>${{i + 1}}</strong></td>
            <td>S${{d.sc.id}}: ${{d.sc.name}}</td>
            <td><span class="op-chip op-${{d.sc.operation.toLowerCase()}}">${{d.sc.operation}}</span></td>
            <td><span style="font-weight:700;color:${{COLORS[d.db] || "#555"}}">${{d.db}}</span></td>
            <td>${{d.woMs.toFixed(2)}}</td>
            <td>${{d.wiMs.toFixed(2)}}</td>
            <td class="${{cls}}">${{deltaMsLabel}}</td>
            <td class="${{cls}}">${{pct}}</td>
          </tr>`;
        }}).join("");
      }}

      fillTable("table-top5", top5, true);
      fillTable("table-bot5", bot5, false);
    }}

    function renderAll() {{
      const tab = activeTabId();
      const phase = document.getElementById("phase-filter").value;
      if (tab === "overview") {{
        renderOverview();
      }} else if (tab === "h1") {{
        renderH1();
      }} else if (tab === "delta") {{
        renderDelta();
      }} else if (tab === "scenarios") {{
        renderScenarioHeatmap(phase);
      }} else if (tab === "json") {{
        renderJson();
      }}
    }}

    initFilters();
    initTabs();
    setLegend();
  </script>
</body>
</html>
"""


def build_h2_dashboard_html() -> str:
    return """<!DOCTYPE html>
<html lang="pl">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Dashboard H2</title>
  <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
  <style>
    :root { --pg:#346da1; --my:#ffa536; --mo:#2fb4a2; --n4:#fb5937; --line:#d9dce6; --bg:#f2f4f8; --card:#fff; --text:#1e2d4a; --muted:#627091; }
    * { box-sizing:border-box; }
    body { margin:0; background:var(--bg); color:var(--text); font-family: Segoe UI, Arial, sans-serif; }
    .wrap { max-width:1400px; margin:0 auto; padding:20px; }
    .hero { background:linear-gradient(135deg,#1f2f57 0%,#293f74 100%); color:#f4f7ff; border-radius:14px; padding:16px 18px; margin-bottom:12px; }
    .hero-top { display:flex; justify-content:space-between; align-items:flex-start; gap:8px; }
    .hero-title { margin:0 0 4px 0; font-size:30px; font-weight:700; }
    .hero-meta { color:#c7d7ff; margin:0 0 8px 0; font-size:12px; font-weight:600; }
    .chip { border:1px solid #6f93de; color:#edf3ff; border-radius:14px; font-weight:600; font-size:12px; padding:3px 10px; background:rgba(255,255,255,.08); }
    .card { background:var(--card); border:1px solid var(--line); border-radius:10px; padding:12px; margin-bottom:12px; }
    .grid-2 { display:grid; grid-template-columns:1fr 1fr; gap:12px; }
    .chart-box { height:300px; }
    .legend { display:flex; gap:12px; flex-wrap:wrap; margin-bottom:8px; font-size:13px; }
    .dot { width:10px; height:10px; border-radius:2px; display:inline-block; margin-right:6px; }
    .hint { color:var(--muted); font-size:12px; margin:4px 0 8px 0; }
    .table-wrap { overflow-x:auto; }
    table { width:100%; border-collapse:collapse; background:#fff; font-size:12px; }
    th, td { border:1px solid var(--line); padding:6px 8px; text-align:left; }
    th { background:#f2f2f2; }
    @media (max-width: 1100px) { .grid-2 { grid-template-columns:1fr; } }
  </style>
</head>
<body>
  <div class="wrap">
    <div class="hero">
      <div class="hero-top">
        <div>
          <h1 class="hero-title">Analiza hipotezy H2: Wplyw rozmiaru zbioru danych</h1>
          <p class="hero-meta">H2: Roznice wydajnosci miedzy silnikami rosna wraz ze wzrostem liczby rekordow (small=500k, medium=1M, large=10M)</p>
          <input id="files" type="file" multiple accept=".csv">
        </div>
        <span class="chip">H2</span>
      </div>
    </div>
    <div class="card">
      <div class="legend" id="legend"></div>
      <p class="hint">Wczytaj pliki CSV z fazy with_indexes dla small, medium i large.</p>
    </div>
    <div class="card">
      <h3>Scaling ogólny</h3>
      <p class="hint">Średni czas wykonania scenariusza — wszystkie operacje</p>
      <div class="chart-box"><canvas id="h2-overall"></canvas></div>
    </div>
    <div class="card">
      <h3>Scaling per operacja</h3>
      <div class="grid-2">
        <div><h4>CREATE</h4><div class="chart-box"><canvas id="h2-create"></canvas></div></div>
        <div><h4>READ</h4><div class="chart-box"><canvas id="h2-read"></canvas></div></div>
        <div><h4>UPDATE</h4><div class="chart-box"><canvas id="h2-update"></canvas></div></div>
        <div><h4>DELETE</h4><div class="chart-box"><canvas id="h2-delete"></canvas></div></div>
      </div>
    </div>
    <div class="card">
      <h3>Tabela podsumowujaca</h3>
      <div class="table-wrap"><table id="h2-table"></table></div>
    </div>
  </div>

  <script>
    const DBS = ["PostgreSQL", "MySQL", "MongoDB", "Neo4j"];
    const OPS = ["CREATE", "READ", "UPDATE", "DELETE"];
    const SIZES = ["small", "medium", "large"];
    const COLORS = { PostgreSQL:"#346da1", MySQL:"#ffa536", MongoDB:"#2fb4a2", Neo4j:"#fb5937" };
    const charts = {};

    function avg(vals){ return vals.length ? vals.reduce((a,b)=>a+b,0)/vals.length : null; }
    function ms(v){ return Math.round(v * 1000 * 100) / 100; }
    function parseCSV(text){
      const rows = text.trim().split(/\\r?\\n/).map(l => l.split(","));
      if (!rows.length) return [];
      const h = rows[0];
      return rows.slice(1).map(r => Object.fromEntries(h.map((k,i) => [k, r[i] ?? ""])));
    }
    function detectSize(name){
      const n = name.toLowerCase();
      if (n.includes("small")) return "small";
      if (n.includes("medium")) return "medium";
      if (n.includes("large")) return "large";
      return null;
    }
    function key(db,size,op){ return `${db}|${size}|${op}`; }
    function opAvg(rows){
      const out = {};
      for (const db of DBS) for (const size of SIZES) for (const op of OPS){
        const vals = rows
          .filter(r => r.db === db && r.size === size && r.operation === op)
          .map(r => Number(r.avg_time_s))
          .filter(v => Number.isFinite(v));
        out[key(db,size,op)] = avg(vals);
      }
      return out;
    }
    function overallAvg(rows){
      const out = {};
      for (const db of DBS) for (const size of SIZES){
        const vals = rows
          .filter(r => r.db === db && r.size === size)
          .map(r => Number(r.avg_time_s))
          .filter(v => Number.isFinite(v));
        out[`${db}|${size}`] = avg(vals);
      }
      return out;
    }
    function destroy(id){ if (charts[id]) { charts[id].destroy(); delete charts[id]; } }
    function lineOptions(showLegend){
      return {
        responsive:true,
        maintainAspectRatio:false,
        plugins:{ legend:{ display: !!showLegend }},
        scales:{ y:{ title:{display:true,text:"Czas [ms]"}, beginAtZero:true }, x:{ title:{display:true,text:"Rozmiar zbioru"} } }
      };
    }
    function setLegend(){
      document.getElementById("legend").innerHTML = DBS.map(db => `<span><span class="dot" style="background:${COLORS[db]}"></span>${db}</span>`).join("");
    }
    function drawLines(prefix, agg){
      for (const op of OPS){
        const id = `${prefix}-${op.toLowerCase()}`;
        destroy(id);
        charts[id] = new Chart(document.getElementById(id), {
          type:"line",
          data:{
            labels:["small","medium","large"],
            datasets:DBS.map(db => ({
              label:db,
              data:SIZES.map(size => {
                const v = agg[key(db,size,op)];
                return v == null ? null : ms(v);
              }),
              borderColor:COLORS[db],
              backgroundColor:COLORS[db],
              pointRadius:4,
              tension:0.2
            }))
          },
          options: lineOptions()
        });
      }
    }
    function drawOverall(agg){
      destroy("h2-overall");
      charts["h2-overall"] = new Chart(document.getElementById("h2-overall"), {
        type:"line",
        data:{
          labels:["Small (500k)", "Medium (1M)", "Large (10M)"],
          datasets:DBS.map(db => ({
            label:db,
            data:SIZES.map(size => {
              const v = agg[`${db}|${size}`];
              return v == null ? null : ms(v);
            }),
            borderColor:COLORS[db],
            backgroundColor:COLORS[db],
            pointRadius:4,
            tension:0.2
          }))
        },
        options: lineOptions(true)
      });
    }
    function ratioClass(v){
      if (v == null) return "";
      if (v < 5) return "background:#e9f7ee;";
      if (v <= 20) return "background:#fff7db;";
      return "background:#fde8e8;";
    }
    function fillTable(overall){
      const table = document.getElementById("h2-table");
      let html = "<thead><tr><th>Baza</th><th>Small [ms]</th><th>Medium [ms]</th><th>Large [ms]</th><th>Trend</th></tr></thead><tbody>";
      for (const db of DBS){
        const s = overall[`${db}|small`];
        const m = overall[`${db}|medium`];
        const l = overall[`${db}|large`];
        const r = s && l ? l / s : null;
        html += `<tr>
          <td style="font-weight:700;color:${COLORS[db]}">${db}</td>
          <td>${s==null?"-":ms(s).toFixed(2)}</td>
          <td>${m==null?"-":ms(m).toFixed(2)}</td>
          <td>${l==null?"-":ms(l).toFixed(2)}</td>
          <td style="${ratioClass(r)}">${r==null?"-":"×"+r.toFixed(1)}</td>
        </tr>`;
      }
      html += "</tbody>";
      table.innerHTML = html;
    }
    async function onFiles(files){
      const rows = [];
      for (const file of files){
        const size = detectSize(file.name);
        if (!size) continue;
        const text = await file.text();
        const parsed = parseCSV(text).map(r => ({...r, size}));
        rows.push(...parsed);
      }
      const filtered = rows.filter(r => String(r.phase || "").trim() === "with_indexes");
      if (!filtered.length){
        alert("Brak danych with_indexes w wybranych plikach.");
        return;
      }
      const fullAgg = opAvg(filtered);
      const overall = overallAvg(filtered);
      drawOverall(overall);
      drawLines("h2", fullAgg);
      fillTable(overall);
    }
    document.getElementById("files").addEventListener("change", async (e) => onFiles([...e.target.files]));
    setLegend();
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
    h2_path = os.path.join(RESULTS_DIR, "dashboard_h2.html")
    with open(h2_path, "w", encoding="utf-8") as f:
        f.write(build_h2_dashboard_html())
    print(f"[OK] Dashboard H2 zapisany: {h2_path}")


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
