import { describe, expect, it } from "vitest";

import { bucketStart, mergePoints, reduceSeries } from "./buckets";
import type { Bucket, LivePoint } from "./types";

const point = (t: string, value: number): LivePoint => ({ source: "s", metric: "m", value, t, tags: {} });

describe("bucketStart", () => {
  it("floors to the bucket boundary", () => {
    expect(new Date(bucketStart("2026-01-01T00:00:17Z", 10)).toISOString()).toBe("2026-01-01T00:00:10.000Z");
  });
});

describe("mergePoints", () => {
  const base: Bucket[] = [{ t: "2026-01-01T00:00:10.000Z", value: 10, count: 2 }];

  it("updates a running average in an existing bucket", () => {
    const merged = mergePoints(base, [point("2026-01-01T00:00:12Z", 40)], "avg", 10, 5);
    expect(merged).toEqual([{ t: "2026-01-01T00:00:10.000Z", value: 20, count: 3 }]);
  });

  it("opens new buckets and trims ones outside the window", () => {
    const merged = mergePoints(base, [point("2026-01-01T00:02:00Z", 1)], "sum", 10, 1);
    expect(merged.map((b) => b.t)).toEqual(["2026-01-01T00:02:00.000Z"]);
  });

  it("counts points for count aggregation", () => {
    const merged = mergePoints([], [point("2026-01-01T00:00:01Z", 9), point("2026-01-01T00:00:02Z", 9)], "count", 10, 5);
    expect(merged[0].value).toBe(2);
  });
});

describe("reduceSeries", () => {
  const series: Bucket[] = [
    { t: "a", value: 10, count: 1 },
    { t: "b", value: 40, count: 3 },
  ];
  it("weights averages by count", () => expect(reduceSeries(series, "avg")).toBe(32.5));
  it("handles max and count", () => {
    expect(reduceSeries(series, "max")).toBe(40);
    expect(reduceSeries(series, "count")).toBe(4);
  });
  it("returns null for empty series", () => expect(reduceSeries([], "sum")).toBeNull());
});
