import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  LineChart,
  Line,
  PieChart,
  Pie,
  Cell,
  Legend,
} from "recharts";
import type {
  CategoryCount,
  MonthlyCount,
  HourlyCount,
  DayNightCount,
} from "../types";

interface Props {
  categories: CategoryCount[];
  monthly: MonthlyCount[];
  hourly: HourlyCount[];
  dayNight: DayNightCount[];
  loading: boolean;
}

const COLORS = [
  "#BD0026", "#FC4E2A", "#FEB24C", "#FFEDA0",
  "#2c7fb8", "#41b6c4", "#7fcdbb", "#c7e9b4",
];

const DAY_NIGHT_COLORS = ["#FDB913", "#1a237e"];

// Recharts Tooltip formatter — uses unknown to satisfy strict ValueType typing
const fmtCount = (v: unknown): [string, string] => [
  typeof v === "number" ? v.toLocaleString() : String(v),
  "Incidents",
];

export default function ChartsPanel({
  categories,
  monthly,
  hourly,
  dayNight,
  loading,
}: Props) {
  if (loading) {
    return (
      <div className="charts-panel loading-charts">
        <div className="pulse">Loading charts…</div>
      </div>
    );
  }

  const top15 = categories.slice(0, 15);

  // X-axis tick sampler for monthly (every 6 months)
  const monthlyTicks = monthly
    .filter((_, i) => i % 6 === 0)
    .map((m) => m.year_month);

  return (
    <div className="charts-panel">
      {/* ── Crime categories bar ── */}
      <div className="chart-card">
        <h3 className="chart-title">Crime by Category (Top 15)</h3>
        <ResponsiveContainer width="100%" height={220}>
          <BarChart
            data={top15}
            layout="vertical"
            margin={{ left: 10, right: 20, top: 4, bottom: 4 }}
          >
            <CartesianGrid strokeDasharray="3 3" horizontal={false} />
            <XAxis type="number" tick={{ fontSize: 11 }} />
            <YAxis
              dataKey="category"
              type="category"
              width={130}
              tick={{ fontSize: 10 }}
            />
            <Tooltip formatter={fmtCount} />
            <Bar dataKey="incident_count" radius={[0, 3, 3, 0]}>
              {top15.map((_, i) => (
                <Cell key={i} fill={COLORS[i % COLORS.length]} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>

      {/* ── Monthly trend line ── */}
      {monthly.length > 0 && (
        <div className="chart-card">
          <h3 className="chart-title">Monthly Crime Trend</h3>
          <ResponsiveContainer width="100%" height={180}>
            <LineChart
              data={monthly}
              margin={{ left: 10, right: 20, top: 4, bottom: 20 }}
            >
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis
                dataKey="year_month"
                ticks={monthlyTicks}
                tick={{ fontSize: 10 }}
                angle={-35}
                textAnchor="end"
              />
              <YAxis tick={{ fontSize: 11 }} />
              <Tooltip formatter={fmtCount} />
              <Line
                type="monotone"
                dataKey="incident_count"
                stroke="#2c7fb8"
                dot={false}
                strokeWidth={2}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* ── Hourly bar ── */}
      {hourly.length > 0 && (
        <div className="chart-card">
          <h3 className="chart-title">Hourly Distribution</h3>
          <ResponsiveContainer width="100%" height={160}>
            <BarChart
              data={hourly}
              margin={{ left: 10, right: 10, top: 4, bottom: 4 }}
            >
              <CartesianGrid strokeDasharray="3 3" vertical={false} />
              <XAxis dataKey="hour" tick={{ fontSize: 10 }} />
              <YAxis tick={{ fontSize: 11 }} />
              <Tooltip
                formatter={fmtCount}
                labelFormatter={(l) => `Hour ${l}:00`}
              />
              <Bar dataKey="incident_count" fill="#41b6c4" radius={[3, 3, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* ── Day / Night donut ── */}
      {dayNight.length > 0 && (
        <div className="chart-card chart-card--small">
          <h3 className="chart-title">Day vs Night</h3>
          <ResponsiveContainer width="100%" height={160}>
            <PieChart>
              <Pie
                data={dayNight}
                dataKey="incident_count"
                nameKey="period"
                cx="50%"
                cy="50%"
                innerRadius={40}
                outerRadius={65}
                paddingAngle={3}
                label={({ name, percent }) =>
                  `${String(name ?? "")} ${(((percent as number) ?? 0) * 100).toFixed(0)}%`
                }
                labelLine={false}
              >
                {dayNight.map((_, i) => (
                  <Cell key={i} fill={DAY_NIGHT_COLORS[i % 2]} />
                ))}
              </Pie>
              <Legend />
              <Tooltip formatter={fmtCount} />
            </PieChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  );
}
