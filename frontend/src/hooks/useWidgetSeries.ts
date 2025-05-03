import { useEffect, useRef, useState } from "react";

import { getSeries } from "../lib/api";
import { mergePoints } from "../lib/buckets";
import { streamClient } from "../lib/stream";
import type { Bucket, LivePoint, Widget } from "../lib/types";

interface State {
  data: Bucket[];
  loading: boolean;
  error: string | null;
}

/**
 * Seed a widget with its historical series from the REST API, then keep it current with
 * live points from the WebSocket. Points that arrive before the history loads are buffered
 * so nothing is dropped during the initial fetch.
 */
export function useWidgetSeries(widget: Widget): State {
  const [state, setState] = useState<State>({ data: [], loading: true, error: null });
  const pending = useRef<LivePoint[] | null>([]);

  useEffect(() => {
    const { aggregation, bucket_seconds, window_minutes } = widget;
    const controller = new AbortController();
    pending.current = [];
    setState({ data: [], loading: true, error: null });

    const unsubscribe = streamClient.subscribe(widget.source_slug, widget.metric_name, (points) => {
      if (pending.current) {
        pending.current.push(...points);
        return;
      }
      setState((prev) => ({
        ...prev,
        data: mergePoints(prev.data, points, aggregation, bucket_seconds, window_minutes),
      }));
    });

    getSeries(widget, controller.signal)
      .then((response) => {
        const buffered = pending.current ?? [];
        pending.current = null;
        const data = buffered.length
          ? mergePoints(response.points, buffered, aggregation, bucket_seconds, window_minutes)
          : response.points;
        setState({ data, loading: false, error: null });
      })
      .catch((err: unknown) => {
        if (controller.signal.aborted) return;
        pending.current = null;
        setState({ data: [], loading: false, error: err instanceof Error ? err.message : String(err) });
      });

    return () => {
      controller.abort();
      unsubscribe();
    };
  }, [widget]);

  return state;
}
