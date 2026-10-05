import axios from "axios";
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

const BASE = "http://localhost:5000/api";

const api = axios.create({ baseURL: BASE, timeout: 30000 });

export const fetchHotspots = (n = 10): Promise<Hotspot[]> =>
  api.get<Hotspot[]>("/hotspots", { params: { n } }).then((r) => r.data);

export const fetchCategories = (): Promise<CategoryCount[]> =>
  api.get<CategoryCount[]>("/categories").then((r) => r.data);

export const fetchMonthly = (): Promise<MonthlyCount[]> =>
  api.get<MonthlyCount[]>("/temporal/monthly").then((r) => r.data);

export const fetchHourly = (): Promise<HourlyCount[]> =>
  api.get<HourlyCount[]>("/temporal/hourly").then((r) => r.data);

export const fetchDayNight = (): Promise<DayNightCount[]> =>
  api.get<DayNightCount[]>("/temporal/day_night").then((r) => r.data);

export const fetchStats = (): Promise<Stats> =>
  api.get<Stats>("/stats").then((r) => r.data);

// Spatial queries
export const queryKnn = (
  lat: number,
  lon: number,
  k: number
): Promise<CrimePoint[]> =>
  api.get<CrimePoint[]>("/queries/knn", { params: { lat, lon, k } }).then((r) => r.data);

export const queryContainment = (
  cell_x: number,
  cell_y: number,
  limit = 200
): Promise<CrimePoint[]> =>
  api
    .get<CrimePoint[]>("/queries/containment", { params: { cell_x, cell_y, limit } })
    .then((r) => r.data);

export const queryRange = (
  lat1: number,
  lon1: number,
  lat2: number,
  lon2: number
): Promise<CrimePoint[]> =>
  api
    .get<CrimePoint[]>("/queries/range", { params: { lat1, lon1, lat2, lon2 } })
    .then((r) => r.data);

export const queryBuffer = (
  lat: number,
  lon: number,
  inner_m: number,
  outer_m: number
): Promise<BufferResult> =>
  api
    .get<BufferResult>("/queries/buffer", { params: { lat, lon, inner_m, outer_m } })
    .then((r) => r.data);

export const queryAdjacency = (
  cell_x: number,
  cell_y: number
): Promise<AdjacencyCell[]> =>
  api
    .get<AdjacencyCell[]>("/queries/adjacency", { params: { cell_x, cell_y } })
    .then((r) => r.data);

export const queryAggregation = (
  cell_x: number,
  cell_y: number
): Promise<{ category: string; incident_count: number }[]> =>
  api
    .get("/queries/aggregation", { params: { cell_x, cell_y } })
    .then((r) => r.data);
