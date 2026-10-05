import { useEffect } from "react";
import {
  MapContainer,
  TileLayer,
  Rectangle,
  Popup,
  CircleMarker,
  Polygon,
  useMap,
  LayersControl,
} from "react-leaflet";
import "leaflet/dist/leaflet.css";
import type { Hotspot, CrimePoint, AdjacencyCell } from "../types";

// ── colour helpers ──────────────────────────────────────────────────────────
function intensityToColor(intensity: number): string {
  if (intensity > 0.75) return "#800026";
  if (intensity > 0.5) return "#BD0026";
  if (intensity > 0.25) return "#FC4E2A";
  return "#FEB24C";
}

function rankToOpacity(rank: number): number {
  // rank 1 = highest opacity, decreasing as rank grows
  return Math.max(0.35, 0.85 - rank * 0.04);
}

// ── auto-fit bounds when hotspots load ─────────────────────────────────────
function FitBounds({ hotspots }: { hotspots: Hotspot[] }) {
  const map = useMap();
  useEffect(() => {
    if (!hotspots.length) return;
    const lats = hotspots.flatMap((h) => h.polygon_latlon.map((p) => p[0]));
    const lons = hotspots.flatMap((h) => h.polygon_latlon.map((p) => p[1]));
    map.fitBounds([
      [Math.min(...lats), Math.min(...lons)],
      [Math.max(...lats), Math.max(...lons)],
    ]);
  }, [hotspots, map]);
  return null;
}

// ── legend overlay ──────────────────────────────────────────────────────────
function Legend({ max }: { max: number }) {
  return (
    <div className="map-legend">
      <div className="legend-title">🔥 Incident Count</div>
      {[
        { color: "#800026", label: `High (>75% of ${max.toLocaleString()})` },
        { color: "#BD0026", label: "Medium-High (50–75%)" },
        { color: "#FC4E2A", label: "Medium (25–50%)" },
        { color: "#FEB24C", label: "Low (≤25%)" },
      ].map(({ color, label }) => (
        <div key={color} className="legend-item">
          <span className="legend-swatch" style={{ background: color }} />
          <span>{label}</span>
        </div>
      ))}
    </div>
  );
}

// ── props ───────────────────────────────────────────────────────────────────
interface Props {
  hotspots: Hotspot[];
  queryMarkers: CrimePoint[];   // KNN / containment / range points
  bufferInner: CrimePoint[];
  bufferRing: CrimePoint[];
  adjacentCells: AdjacencyCell[];
  highlightCell: { cell_x: number; cell_y: number } | null;
}

export default function HotspotMap({
  hotspots,
  queryMarkers,
  bufferInner,
  bufferRing,
  adjacentCells,
  highlightCell,
}: Props) {
  const maxCount = hotspots.length ? Math.max(...hotspots.map((h) => h.incident_count)) : 1;

  // Chicago default centre (will be overridden by FitBounds when data arrives)
  const defaultCenter: [number, number] = [41.85, -87.65];

  return (
    <div className="map-wrapper">
      <MapContainer
        center={defaultCenter}
        zoom={11}
        style={{ height: "100%", width: "100%" }}
        zoomControl
      >
        <LayersControl position="topright">
          {/* Base layers */}
          <LayersControl.BaseLayer checked name="OpenStreetMap">
            <TileLayer
              attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
              url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
            />
          </LayersControl.BaseLayer>
          <LayersControl.BaseLayer name="CartoDB Dark">
            <TileLayer
              attribution='&copy; <a href="https://carto.com/">CARTO</a>'
              url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
            />
          </LayersControl.BaseLayer>
          <LayersControl.BaseLayer name="Satellite (Esri)">
            <TileLayer
              attribution="Tiles &copy; Esri"
              url="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"
            />
          </LayersControl.BaseLayer>
        </LayersControl>

        <FitBounds hotspots={hotspots} />

        {/* ── Hotspot rectangles ── */}
        {hotspots.map((h) => {
          const intensity = h.incident_count / maxCount;
          const color = intensityToColor(intensity);
          const opacity = rankToOpacity(h.rank);
          const isHighlighted =
            highlightCell?.cell_x === h.cell_x &&
            highlightCell?.cell_y === h.cell_y;

          return (
            <Rectangle
              key={`${h.cell_x}-${h.cell_y}`}
              bounds={h.polygon_latlon as [[number, number], [number, number]]}
              pathOptions={{
                color: isHighlighted ? "#fff" : color,
                weight: isHighlighted ? 3 : 1.5,
                fillColor: color,
                fillOpacity: opacity,
              }}
            >
              <Popup>
                <div className="popup-content">
                  <div className="popup-rank">#{h.rank} Hotspot</div>
                  <div className="popup-cell">
                    Cell ({h.cell_x}, {h.cell_y})
                  </div>
                  <div className="popup-count">
                    🔴 {h.incident_count.toLocaleString()} incidents
                  </div>
                  {h.distinct_categories != null && (
                    <div>📂 {h.distinct_categories} crime categories</div>
                  )}
                  {h.earliest_incident && (
                    <div>
                      📅 {new Date(h.earliest_incident).toLocaleDateString()} →{" "}
                      {h.latest_incident
                        ? new Date(h.latest_incident).toLocaleDateString()
                        : "—"}
                    </div>
                  )}
                  <div className="popup-coords">
                    Centre: {h.center_lat.toFixed(4)}, {h.center_lon.toFixed(4)}
                  </div>
                </div>
              </Popup>
            </Rectangle>
          );
        })}

        {/* ── Adjacent cells (query result) ── */}
        {adjacentCells.map((c) => (
          <Polygon
            key={`adj-${c.cell_x}-${c.cell_y}`}
            positions={c.polygon_latlon as [number, number][]}
            pathOptions={{
              color: "#7B2FBE",
              weight: 2,
              fillColor: "#7B2FBE",
              fillOpacity: 0.3,
            }}
          >
            <Popup>
              Adjacent cell ({c.cell_x}, {c.cell_y})
              <br />
              {c.incident_count != null ? `${c.incident_count} incidents` : ""}
            </Popup>
          </Polygon>
        ))}

        {/* ── Query result markers (KNN, containment, range) ── */}
        {queryMarkers.map((pt, i) => {
          const lat = pt.latitude ?? pt.location?.coordinates[1];
          const lon = pt.longitude ?? pt.location?.coordinates[0];
          if (!lat || !lon) return null;
          return (
            <CircleMarker
              key={`q-${i}`}
              center={[lat, lon]}
              radius={5}
              pathOptions={{ color: "#00bfff", fillColor: "#00bfff", fillOpacity: 0.8 }}
            >
              <Popup>
                <b>{pt.category}</b>
                <br />
                ID: {pt.crime_id}
                {pt.distance_m != null && (
                  <>
                    <br />
                    {pt.distance_m.toFixed(1)} m away
                  </>
                )}
              </Popup>
            </CircleMarker>
          );
        })}

        {/* ── Buffer inner ring ── */}
        {bufferInner.map((pt, i) => {
          const lat = pt.latitude ?? pt.location?.coordinates[1];
          const lon = pt.longitude ?? pt.location?.coordinates[0];
          if (!lat || !lon) return null;
          return (
            <CircleMarker
              key={`bi-${i}`}
              center={[lat, lon]}
              radius={5}
              pathOptions={{ color: "#ff4500", fillColor: "#ff4500", fillOpacity: 0.8 }}
            >
              <Popup>
                <b>{pt.category}</b>
                <br />
                Inner buffer
              </Popup>
            </CircleMarker>
          );
        })}

        {/* ── Buffer ring ── */}
        {bufferRing.map((pt, i) => {
          const lat = pt.latitude ?? pt.location?.coordinates[1];
          const lon = pt.longitude ?? pt.location?.coordinates[0];
          if (!lat || !lon) return null;
          return (
            <CircleMarker
              key={`br-${i}`}
              center={[lat, lon]}
              radius={4}
              pathOptions={{ color: "#ffa500", fillColor: "#ffa500", fillOpacity: 0.6 }}
            >
              <Popup>
                <b>{pt.category}</b>
                <br />
                Buffer ring
              </Popup>
            </CircleMarker>
          );
        })}
      </MapContainer>

      {hotspots.length > 0 && <Legend max={maxCount} />}
    </div>
  );
}
