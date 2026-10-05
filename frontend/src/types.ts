// Shared TypeScript types for the Crime Hotspot Analyser frontend

export interface Hotspot {
  cell_x: number;
  cell_y: number;
  incident_count: number;
  distinct_categories: number;
  earliest_incident: string | null;
  latest_incident: string | null;
  rank: number;
  polygon_latlon: [number, number][];
  center_lat: number;
  center_lon: number;
}

export interface CategoryCount {
  category: string;
  incident_count: number;
}

export interface MonthlyCount {
  year_month: string;
  incident_count: number;
}

export interface HourlyCount {
  hour: number;
  incident_count: number;
}

export interface DayNightCount {
  period: "day" | "night";
  incident_count: number;
}

export interface Stats {
  total_crimes: number;
  crimes_with_date: number;
  grid_cells: number;
  earliest: string | null;
  latest: string | null;
}

export interface CrimePoint {
  crime_id: string;
  category: string;
  latitude: number;
  longitude: number;
  location?: {
    type: "Point";
    coordinates: [number, number]; // [lon, lat]
  };
  distance_m?: number;
}

export interface KnnResult extends CrimePoint {}

export interface BufferResult {
  within_inner: CrimePoint[];
  buffer_ring: CrimePoint[];
  inner_count: number;
  ring_count: number;
}

export interface AdjacencyCell {
  cell_x: number;
  cell_y: number;
  incident_count: number;
  polygon_latlon: [number, number][];
}

export type QueryTab =
  | "knn"
  | "containment"
  | "range"
  | "buffer"
  | "adjacency"
  | "aggregation";
