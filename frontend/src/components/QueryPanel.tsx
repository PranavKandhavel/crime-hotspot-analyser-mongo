import { useState } from "react";
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, Cell,
} from "recharts";
import {
  queryKnn,
  queryContainment,
  queryRange,
  queryBuffer,
  queryAdjacency,
  queryAggregation,
} from "../api";
import type {
  CrimePoint,
  BufferResult,
  AdjacencyCell,
  QueryTab,
  Hotspot,
} from "../types";

interface Props {
  hotspots: Hotspot[];
  onQueryMarkers: (pts: CrimePoint[]) => void;
  onBufferResult: (r: BufferResult) => void;
  onAdjacency: (cells: AdjacencyCell[]) => void;
  onHighlightCell: (cell: { cell_x: number; cell_y: number } | null) => void;
}

const QUERY_TABS: { key: QueryTab; label: string; emoji: string }[] = [
  { key: "knn",         label: "KNN Search",         emoji: "📍" },
  { key: "containment", label: "Containment",         emoji: "🔲" },
  { key: "range",       label: "Spatial Range",       emoji: "⬛" },
  { key: "buffer",      label: "Proximity Buffer",    emoji: "🔵" },
  { key: "adjacency",   label: "Adjacency",           emoji: "🔗" },
  { key: "aggregation", label: "Spatial Aggregation", emoji: "📊" },
];

const QUERY_DESCRIPTIONS: Record<QueryTab, string> = {
  knn: "Finds the k nearest crime records to a given point using MongoDB's $near operator on a 2dsphere index. Returns crimes sorted by geodetic (great-circle) distance.",
  containment: "Uses $geoWithin with $geometry to find all crime points geometrically contained inside a grid cell polygon. A true spatial containment test — not an attribute join.",
  range: "Performs a rectangular bounding-box search using the legacy 2d index and $box operator, implementing Euclidean (planar) range search semantics.",
  buffer: "Constructs an inner circle and an outer circle using $centerSphere (radius in radians). The 'buffer ring' is the donut between them — crimes that are within the outer but not the inner radius.",
  adjacency: "Finds grid cells whose polygon boundary touches or overlaps the target cell using $geoIntersects. This is proximity at distance 0 — anything that intersects necessarily touches.",
  aggregation: "Runs a $geoWithin + $group pipeline to count crimes by category inside an arbitrary polygon region. Unlike the global category summary, this is spatially constrained.",
};

const AGG_COLORS = ["#BD0026","#FC4E2A","#FEB24C","#FFEDA0","#2c7fb8","#41b6c4","#7fcdbb","#c7e9b4"];

const fmtCount = (v: unknown): [string, string] => [
  typeof v === "number" ? v.toLocaleString() : String(v),
  "Incidents",
];

export default function QueryPanel({
  hotspots,
  onQueryMarkers,
  onBufferResult,
  onAdjacency,
  onHighlightCell,
}: Props) {
  const [activeTab, setActiveTab] = useState<QueryTab>("knn");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [resultMsg, setResultMsg] = useState<string | null>(null);
  const [aggData, setAggData] = useState<{ category: string; incident_count: number }[]>([]);

  // Form state
  const [knnLat, setKnnLat] = useState("41.878");
  const [knnLon, setKnnLon] = useState("-87.629");
  const [knnK, setKnnK] = useState("10");

  const [contCell, setContCell] = useState<string>(
    hotspots.length ? `${hotspots[0].cell_x}` : "0"
  );
  const [contCellY, setContCellY] = useState<string>(
    hotspots.length ? `${hotspots[0].cell_y}` : "0"
  );

  const [r1Lat, setR1Lat] = useState("41.86");
  const [r1Lon, setR1Lon] = useState("-87.64");
  const [r2Lat, setR2Lat] = useState("41.90");
  const [r2Lon, setR2Lon] = useState("-87.60");

  const [bufLat, setBufLat] = useState("41.878");
  const [bufLon, setBufLon] = useState("-87.629");
  const [bufInner, setBufInner] = useState("500");
  const [bufOuter, setBufOuter] = useState("1500");

  const [adjCell, setAdjCell] = useState<string>(
    hotspots.length ? `${hotspots[0].cell_x}` : "0"
  );
  const [adjCellY, setAdjCellY] = useState<string>(
    hotspots.length ? `${hotspots[0].cell_y}` : "0"
  );

  const [aggCell, setAggCell] = useState<string>(
    hotspots.length ? `${hotspots[0].cell_x}` : "0"
  );
  const [aggCellY, setAggCellY] = useState<string>(
    hotspots.length ? `${hotspots[0].cell_y}` : "0"
  );

  const run = async () => {
    setLoading(true);
    setError(null);
    setResultMsg(null);
    setAggData([]);
    onQueryMarkers([]);
    onBufferResult({ within_inner: [], buffer_ring: [], inner_count: 0, ring_count: 0 });
    onAdjacency([]);
    onHighlightCell(null);

    try {
      switch (activeTab) {
        case "knn": {
          const pts = await queryKnn(parseFloat(knnLat), parseFloat(knnLon), parseInt(knnK));
          onQueryMarkers(pts);
          setResultMsg(`Found ${pts.length} nearest crime(s) — shown as blue dots on map.`);
          break;
        }
        case "containment": {
          const pts = await queryContainment(parseInt(contCell), parseInt(contCellY), 200);
          onQueryMarkers(pts);
          onHighlightCell({ cell_x: parseInt(contCell), cell_y: parseInt(contCellY) });
          setResultMsg(`${pts.length} crime(s) geometrically contained in cell (${contCell}, ${contCellY}).`);
          break;
        }
        case "range": {
          const pts = await queryRange(
            parseFloat(r1Lat), parseFloat(r1Lon),
            parseFloat(r2Lat), parseFloat(r2Lon)
          );
          onQueryMarkers(pts);
          setResultMsg(`${pts.length} crime(s) inside the bounding box (Euclidean / 2d index).`);
          break;
        }
        case "buffer": {
          const res = await queryBuffer(
            parseFloat(bufLat), parseFloat(bufLon),
            parseFloat(bufInner), parseFloat(bufOuter)
          );
          onBufferResult(res);
          setResultMsg(
            `${res.inner_count} crimes within ${bufInner} m (red) · ${res.ring_count} in buffer ring ${bufInner}–${bufOuter} m (orange).`
          );
          break;
        }
        case "adjacency": {
          const cells = await queryAdjacency(parseInt(adjCell), parseInt(adjCellY));
          onAdjacency(cells);
          onHighlightCell({ cell_x: parseInt(adjCell), cell_y: parseInt(adjCellY) });
          setResultMsg(`${cells.length} grid cell(s) adjacent to (${adjCell}, ${adjCellY}) — shown in purple.`);
          break;
        }
        case "aggregation": {
          const data = await queryAggregation(parseInt(aggCell), parseInt(aggCellY));
          setAggData(data);
          setResultMsg(`${data.length} crime categories inside cell (${aggCell}, ${aggCellY}).`);
          break;
        }
      }
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : String(e);
      setError(`Query failed: ${msg}`);
    } finally {
      setLoading(false);
    }
  };

  const cellOptions = hotspots.map((h) => ({
    label: `#${h.rank} — Cell (${h.cell_x}, ${h.cell_y}) — ${h.incident_count.toLocaleString()} incidents`,
    cx: h.cell_x,
    cy: h.cell_y,
  }));

  return (
    <div className="query-panel">
      {/* ── Tab bar ── */}
      <div className="query-tabs">
        {QUERY_TABS.map((t) => (
          <button
            key={t.key}
            className={`query-tab ${activeTab === t.key ? "active" : ""}`}
            onClick={() => {
              setActiveTab(t.key);
              setResultMsg(null);
              setError(null);
              setAggData([]);
              onQueryMarkers([]);
              onBufferResult({ within_inner: [], buffer_ring: [], inner_count: 0, ring_count: 0 });
              onAdjacency([]);
              onHighlightCell(null);
            }}
          >
            {t.emoji} {t.label}
          </button>
        ))}
      </div>

      {/* ── Description ── */}
      <div className="query-description">
        <span className="query-desc-badge">MongoDB operator</span>{" "}
        {QUERY_DESCRIPTIONS[activeTab]}
      </div>

      {/* ── Form fields ── */}
      <div className="query-form">
        {activeTab === "knn" && (
          <>
            <label>Latitude<input value={knnLat} onChange={(e) => setKnnLat(e.target.value)} /></label>
            <label>Longitude<input value={knnLon} onChange={(e) => setKnnLon(e.target.value)} /></label>
            <label>K (neighbors)<input type="number" value={knnK} onChange={(e) => setKnnK(e.target.value)} min={1} max={100} /></label>
          </>
        )}

        {activeTab === "containment" && (
          <>
            <label>
              Grid Cell
              <select
                value={`${contCell},${contCellY}`}
                onChange={(e) => {
                  const [cx, cy] = e.target.value.split(",");
                  setContCell(cx);
                  setContCellY(cy);
                }}
              >
                {cellOptions.map((o) => (
                  <option key={`${o.cx},${o.cy}`} value={`${o.cx},${o.cy}`}>
                    {o.label}
                  </option>
                ))}
              </select>
            </label>
          </>
        )}

        {activeTab === "range" && (
          <>
            <label>SW Lat<input value={r1Lat} onChange={(e) => setR1Lat(e.target.value)} /></label>
            <label>SW Lon<input value={r1Lon} onChange={(e) => setR1Lon(e.target.value)} /></label>
            <label>NE Lat<input value={r2Lat} onChange={(e) => setR2Lat(e.target.value)} /></label>
            <label>NE Lon<input value={r2Lon} onChange={(e) => setR2Lon(e.target.value)} /></label>
          </>
        )}

        {activeTab === "buffer" && (
          <>
            <label>Latitude<input value={bufLat} onChange={(e) => setBufLat(e.target.value)} /></label>
            <label>Longitude<input value={bufLon} onChange={(e) => setBufLon(e.target.value)} /></label>
            <label>Inner radius (m)<input type="number" value={bufInner} onChange={(e) => setBufInner(e.target.value)} /></label>
            <label>Outer radius (m)<input type="number" value={bufOuter} onChange={(e) => setBufOuter(e.target.value)} /></label>
          </>
        )}

        {activeTab === "adjacency" && (
          <>
            <label>
              Grid Cell
              <select
                value={`${adjCell},${adjCellY}`}
                onChange={(e) => {
                  const [cx, cy] = e.target.value.split(",");
                  setAdjCell(cx);
                  setAdjCellY(cy);
                }}
              >
                {cellOptions.map((o) => (
                  <option key={`${o.cx},${o.cy}`} value={`${o.cx},${o.cy}`}>
                    {o.label}
                  </option>
                ))}
              </select>
            </label>
          </>
        )}

        {activeTab === "aggregation" && (
          <>
            <label>
              Grid Cell
              <select
                value={`${aggCell},${aggCellY}`}
                onChange={(e) => {
                  const [cx, cy] = e.target.value.split(",");
                  setAggCell(cx);
                  setAggCellY(cy);
                }}
              >
                {cellOptions.map((o) => (
                  <option key={`${o.cx},${o.cy}`} value={`${o.cx},${o.cy}`}>
                    {o.label}
                  </option>
                ))}
              </select>
            </label>
          </>
        )}

        <button
          className="run-btn"
          onClick={run}
          disabled={loading}
        >
          {loading ? "Running…" : "▶ Run Query"}
        </button>
      </div>

      {/* ── Results ── */}
      {error && <div className="query-error">⚠ {error}</div>}
      {resultMsg && <div className="query-result-msg">✅ {resultMsg}</div>}

      {/* Aggregation chart */}
      {activeTab === "aggregation" && aggData.length > 0 && (
        <div className="agg-chart">
          <ResponsiveContainer width="100%" height={150}>
            <BarChart
              data={aggData.slice(0, 10)}
              layout="vertical"
              margin={{ left: 10, right: 20, top: 4, bottom: 4 }}
            >
              <CartesianGrid strokeDasharray="3 3" horizontal={false} />
              <XAxis type="number" tick={{ fontSize: 10 }} />
              <YAxis dataKey="category" type="category" width={120} tick={{ fontSize: 10 }} />
              <Tooltip formatter={fmtCount} />
              <Bar dataKey="incident_count" radius={[0, 3, 3, 0]}>
                {aggData.slice(0, 10).map((_, i) => (
                  <Cell key={i} fill={AGG_COLORS[i % AGG_COLORS.length]} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  );
}
