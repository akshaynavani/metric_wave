import type { Aggregation, Bucket, LivePoint } from "./types";

/** Floor an ISO timestamp to the start of its bucket, returning epoch milliseconds. */
export function bucketStart(iso: string, bucketSeconds: number): number {
  const ms = Date.parse(iso);
  const size = bucketSeconds * 1000;
  return Math.floor(ms / size) * size;
}

function combine(bucket: Bucket, value: number, aggregation: Aggregation): Bucket {
  const count = bucket.count + 1;
  switch (aggregation) {
    case "sum":
      return { ...bucket, value: bucket.value + value, count };
    case "min":
      return { ...bucket, value: Math.min(bucket.value, value), count };
    case "max":
      return { ...bucket, value: Math.max(bucket.value, value), count };
    case "count":
      return { ...bucket, value: count, count };
    case "avg":
    default:
      return { ...bucket, value: (bucket.value * bucket.count + value) / count, count };
  }
}

/**
 * Fold live points into the bucketed series returned by the REST API, mirroring the
 * server-side aggregation, then drop buckets that have scrolled out of the window.
 */
export function mergePoints(
  series: Bucket[],
  points: LivePoint[],
  aggregation: Aggregation,
  bucketSeconds: number,
  windowMinutes: number,
): Bucket[] {
  const byStart = new Map<number, Bucket>();
  for (const bucket of series) byStart.set(Date.parse(bucket.t), bucket);

  for (const point of points) {
    const start = bucketStart(point.t, bucketSeconds);
    const existing = byStart.get(start);
    byStart.set(
      start,
      existing
        ? combine(existing, point.value, aggregation)
        : {
            t: new Date(start).toISOString(),
            value: aggregation === "count" ? 1 : point.value,
            count: 1,
          },
    );
  }

  const latest = Math.max(...byStart.keys());
  const cutoff = latest - windowMinutes * 60_000;
  return [...byStart.entries()]
    .filter(([start]) => start > cutoff)
    .sort(([a], [b]) => a - b)
    .map(([, bucket]) => bucket);
}

/** Reduce a bucketed series to a single headline number using the widget's aggregation. */
export function reduceSeries(series: Bucket[], aggregation: Aggregation): number | null {
  if (series.length === 0) return null;
  switch (aggregation) {
    case "sum":
      return series.reduce((acc, b) => acc + b.value, 0);
    case "min":
      return Math.min(...series.map((b) => b.value));
    case "max":
      return Math.max(...series.map((b) => b.value));
    case "count":
      return series.reduce((acc, b) => acc + b.count, 0);
    case "avg":
    default: {
      const total = series.reduce((acc, b) => acc + b.count, 0);
      return total ? series.reduce((acc, b) => acc + b.value * b.count, 0) / total : null;
    }
  }
}
