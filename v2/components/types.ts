export type StageStatus = "idle" | "running" | "done" | "error";

export interface Stage {
  id: string;
  label: string;
  status: StageStatus;
  detail?: string;
  elapsed?: number;
}

export interface Intent {
  profile_type: string;
  priorities: string[];
  concerns: string[];
  lifestyle: string;
  selected_metrics: string[];
  reasoning: string;
  degraded: boolean;
}

export interface Metric {
  key: string;
  label: string;
  unit: "count" | "km2" | "score" | "per_km2";
  about: string;
  value: number;
}

export interface Poi {
  lat: number;
  lon: number;
  c: string;
  n: string | null;
}

export interface LocationInfo {
  lat: number;
  lon: number;
  address: string;
}

/** One line of the NDJSON stream from POST /api/analyse. */
export type StreamEvent =
  | { type: "stage"; id: string; status: StageStatus; detail?: string; elapsed?: number }
  | { type: "intent"; data: Intent }
  | { type: "location"; data: LocationInfo }
  | { type: "pois"; data: Poi[]; counts: Record<string, number> }
  | { type: "stats"; data: Record<string, Metric> }
  | { type: "token"; text: string }
  | { type: "notice"; message: string }
  | { type: "rephrase"; message: string; examples: string[] }
  | { type: "error"; message: string }
  | { type: "done"; elapsed: number };

/** Muted, evenly-spaced hues so no single category dominates the map. */
export const CATEGORY_COLORS: Record<string, string> = {
  schools: "#60a5fa",
  kindergartens: "#818cf8",
  hospitals: "#fb7185",
  pharmacies: "#f472b6",
  restaurants: "#fbbf24",
  cafes: "#fdba74",
  bars: "#f59e0b",
  shops: "#a78bfa",
  banks: "#34d399",
  gyms: "#2dd4bf",
  parks: "#4ade80",
  playgrounds: "#86efac",
  metro_stations: "#22d3ee",
  bus_stops: "#67e8f9",
  hotels: "#c084fc",
  worship: "#94a3b8",
  libraries: "#7dd3fc",
  offices: "#64748b",
  healthcare: "#fda4af",
  attractions: "#e879f9",
  fuel: "#a3a3a3",
};

export const DEFAULT_COLOR = "#6b7280";

export const PROFILES = [
  "Family with kids",
  "Young professional",
  "Student",
  "Senior citizen",
  "Remote worker",
  "Fitness enthusiast",
];
