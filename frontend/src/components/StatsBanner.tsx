import type { Stats } from "../types";

interface Props {
  stats: Stats | null;
  loading: boolean;
}

function fmt(n: number): string {
  return n.toLocaleString();
}

function fmtDate(iso: string | null): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleDateString("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

export default function StatsBanner({ stats, loading }: Props) {
  if (loading) {
    return (
      <div className="stats-banner loading">
        <span className="pulse">Loading statistics…</span>
      </div>
    );
  }
  if (!stats) return null;

  return (
    <div className="stats-banner">
      <div className="stat-card">
        <span className="stat-value">{fmt(stats.total_crimes)}</span>
        <span className="stat-label">Total Crimes</span>
      </div>
      <div className="stat-divider" />
      <div className="stat-card">
        <span className="stat-value">{fmt(stats.grid_cells)}</span>
        <span className="stat-label">Grid Cells</span>
      </div>
      <div className="stat-divider" />
      <div className="stat-card">
        <span className="stat-value">{fmt(stats.crimes_with_date)}</span>
        <span className="stat-label">With Valid Date</span>
      </div>
      <div className="stat-divider" />
      <div className="stat-card">
        <span className="stat-value">{fmtDate(stats.earliest)}</span>
        <span className="stat-label">Earliest Incident</span>
      </div>
      <div className="stat-divider" />
      <div className="stat-card">
        <span className="stat-value">{fmtDate(stats.latest)}</span>
        <span className="stat-label">Latest Incident</span>
      </div>
    </div>
  );
}
