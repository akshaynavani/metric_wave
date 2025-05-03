import type { Dashboard, Paginated, SeriesResponse, Widget } from "./types";

const API_BASE = import.meta.env.VITE_API_BASE ?? "/api";

async function getJson<T>(path: string, signal?: AbortSignal): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: { Accept: "application/json" },
    signal,
  });
  if (!response.ok) {
    throw new Error(`${response.status} ${response.statusText} for ${path}`);
  }
  return (await response.json()) as T;
}

export function listDashboards(signal?: AbortSignal): Promise<Paginated<Dashboard>> {
  return getJson("/dashboards/", signal);
}

export function getDashboard(slug: string, signal?: AbortSignal): Promise<Dashboard> {
  return getJson(`/dashboards/${encodeURIComponent(slug)}/`, signal);
}

export function getSeries(widget: Widget, signal?: AbortSignal): Promise<SeriesResponse> {
  const params = new URLSearchParams({
    source: widget.source_slug,
    metric: widget.metric_name,
    window: String(widget.window_minutes),
    bucket: String(widget.bucket_seconds),
    agg: widget.aggregation,
  });
  return getJson(`/query/series/?${params.toString()}`, signal);
}
