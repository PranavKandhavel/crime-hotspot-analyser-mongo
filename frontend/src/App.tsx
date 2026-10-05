import { useEffect, useState } from "react";
import HotspotMap from "./components/HotspotMap";
import ChartsPanel from "./components/ChartsPanel";
import QueryPanel from "./components/QueryPanel";
import StatsBanner from "./components/StatsBanner";
import {
  fetchHotspots,
  fetchCategories,
  fetchMonthly,
  fetchHourly,
  fetchDayNight,
  fetchStats,
} from "./api";
import type {
  Hotspot,
  CategoryCount,
  MonthlyCount,
  HourlyCount,
  DayNightCount,
  Stats,
  CrimePoint,
  BufferResult,
  AdjacencyCell,
} from "./types";
import "./index.css";

export default function App() {
  // ── Server data ──────────────────────────────────────────────────────────
  const [hotspots, setHotspots]     = useState<Hotspot[]>([]);
  const [categories, setCategories] = useState<CategoryCount[]>([]);
  const [monthly, setMonthly]       = useState<MonthlyCount[]>([]);
  const [hourly, setHourly]         = useState<HourlyCount[]>([]);
  const [dayNight, setDayNight]     = useState<DayNightCount[]>([]);
  const [stats, setStats]           = useState<Stats | null>(null);
  const [loadingData, setLoadingData] = useState(true);
  const [apiError, setApiError]     = useState<string | null>(null);

  // ── Query overlay state (lifted up from QueryPanel → shared with Map) ──
  const [queryMarkers, setQueryMarkers] = useState<CrimePoint[]>([]);
  const [bufferResult, setBufferResult] = useState<BufferResult>({
    within_inner: [], buffer_ring: [], inner_count: 0, ring_count: 0,
  });
  const [adjacentCells, setAdjacentCells] = useState<AdjacencyCell[]>([]);
  const [highlightCell, setHighlightCell] = useState<{ cell_x: number; cell_y: number } | null>(null);

  // ── Sidebar toggle ───────────────────────────────────────────────────────
  const [chartsOpen, setChartsOpen] = useState(true);

  useEffect(() => {
    Promise.all([
      fetchHotspots(10),
      fetchCategories(),
      fetchMonthly(),
      fetchHourly(),
      fetchDayNight(),
      fetchStats(),
    ])
      .then(([hs, cats, mo, hr, dn, st]) => {
        setHotspots(hs);
        setCategories(cats);
        setMonthly(mo);
        setHourly(hr);
        setDayNight(dn);
        setStats(st);
      })
      .catch((e) => {
        setApiError(
          `Cannot reach the API (http://localhost:5000). ` +
          `Start it with: python api/app.py\n\nDetails: ${e.message}`
        );
      })
      .finally(() => setLoadingData(false));
  }, []);

  return (
    <div className="app-shell">
      {/* ── Header ── */}
      <header className="app-header">
        <div className="header-left">
          <span className="header-icon">🗺️</span>
          <div>
            <h1 className="app-title">Crime Hotspot Analyser</h1>
            <p className="app-subtitle">
              MongoDB Atlas · Spatial Analysis · Chicago Crime Data
            </p>
          </div>
        </div>
        <div className="header-right">
          <button
            className="sidebar-toggle"
            onClick={() => setChartsOpen((o) => !o)}
            title={chartsOpen ? "Hide charts" : "Show charts"}
          >
            {chartsOpen ? "◀ Charts" : "▶ Charts"}
          </button>
        </div>
      </header>

      {/* ── Stats banner ── */}
      <StatsBanner stats={stats} loading={loadingData} />

      {/* ── API error banner ── */}
      {apiError && (
        <div className="api-error-banner">
          <pre>{apiError}</pre>
        </div>
      )}

      {/* ── Main body: map + charts sidebar ── */}
      <div className="main-body">
        <div className="map-area">
          <HotspotMap
            hotspots={hotspots}
            queryMarkers={queryMarkers}
            bufferInner={bufferResult.within_inner}
            bufferRing={bufferResult.buffer_ring}
            adjacentCells={adjacentCells}
            highlightCell={highlightCell}
          />
        </div>

        {chartsOpen && (
          <aside className="sidebar">
            <ChartsPanel
              categories={categories}
              monthly={monthly}
              hourly={hourly}
              dayNight={dayNight}
              loading={loadingData}
            />
          </aside>
        )}
      </div>

      {/* ── Spatial Query Panel (bottom) ── */}
      <section className="query-section">
        <div className="query-section-header">
          <h2>⚡ Spatial Query Catalog</h2>
          <span className="query-section-sub">
            Live queries against MongoDB Atlas — results appear on the map above
          </span>
        </div>
        <QueryPanel
          hotspots={hotspots}
          onQueryMarkers={setQueryMarkers}
          onBufferResult={setBufferResult}
          onAdjacency={setAdjacentCells}
          onHighlightCell={setHighlightCell}
        />
      </section>

      <footer className="app-footer">
        Crime Hotspot Analyser · MongoDB Atlas + React + Leaflet ·{" "}
        {new Date().getFullYear()}
      </footer>
    </div>
  );
}
