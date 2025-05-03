export type Aggregation = "avg" | "sum" | "min" | "max" | "count";
export type WidgetKind = "line" | "stat" | "bar";

export interface Widget {
  id: number;
  dashboard: number;
  title: string;
  kind: WidgetKind;
  source_slug: string;
  metric_name: string;
  aggregation: Aggregation;
  window_minutes: number;
  bucket_seconds: number;
  position: number;
}

export interface Dashboard {
  id: number;
  slug: string;
  title: string;
  description: string;
  created_at: string;
  updated_at: string;
  widgets: Widget[];
}

export interface Paginated<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}

export interface Bucket {
  t: string;
  value: number;
  count: number;
}

export interface SeriesResponse {
  source: string;
  metric: string;
  aggregation: Aggregation;
  bucket_seconds: number;
  points: Bucket[];
}

export interface LivePoint {
  source: string;
  metric: string;
  value: number;
  t: string;
  tags: Record<string, string>;
}

export type ServerMessage =
  | { type: "hello"; max_subscriptions: number }
  | { type: "subscribed" | "unsubscribed"; source: string; metric: string }
  | { type: "points"; points: LivePoint[] }
  | { type: "pong" }
  | { type: "error"; message: string };

export type ConnectionStatus = "connecting" | "open" | "closed";
