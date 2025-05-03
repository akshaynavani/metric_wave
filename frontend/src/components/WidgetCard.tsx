import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { useWidgetSeries } from "../hooks/useWidgetSeries";
import { reduceSeries } from "../lib/buckets";
import type { Bucket, Widget } from "../lib/types";
import { formatTime, formatValue } from "./format";

const ACCENT = "var(--accent)";

function Chart({ widget, data }: { widget: Widget; data: Bucket[] }) {
  const axes = (
    <>
      <CartesianGrid stroke="var(--grid)" vertical={false} />
      <XAxis dataKey="t" tickFormatter={formatTime} minTickGap={40} stroke="var(--muted)" fontSize={11} />
      <YAxis tickFormatter={formatValue} width={48} stroke="var(--muted)" fontSize={11} />
      <Tooltip
        labelFormatter={(label) => formatTime(String(label))}
        formatter={(value: number) => [formatValue(value), widget.aggregation]}
        contentStyle={{ background: "var(--surface)", border: "1px solid var(--border)" }}
      />
    </>
  );

  if (widget.kind === "bar") {
    return (
      <BarChart data={data}>
        {axes}
        <Bar dataKey="value" fill={ACCENT} isAnimationActive={false} />
      </BarChart>
    );
  }
  return (
    <LineChart data={data}>
      {axes}
      <Line type="monotone" dataKey="value" stroke={ACCENT} strokeWidth={2} dot={false} isAnimationActive={false} />
    </LineChart>
  );
}

function Stat({ widget, data }: { widget: Widget; data: Bucket[] }) {
  const value = reduceSeries(data, widget.aggregation);
  return (
    <div className="stat">
      <div className="stat-value">{formatValue(value)}</div>
      <div className="stat-caption">
        {widget.aggregation} over {widget.window_minutes}m
      </div>
      <div className="sparkline">
        <ResponsiveContainer width="100%" height={40}>
          <AreaChart data={data}>
            <Area type="monotone" dataKey="value" stroke={ACCENT} fill={ACCENT} fillOpacity={0.15} isAnimationActive={false} />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

export function WidgetCard({ widget }: { widget: Widget }) {
  const { data, loading, error } = useWidgetSeries(widget);

  return (
    <section className={`card card-${widget.kind}`}>
      <header className="card-header">
        <h3>{widget.title}</h3>
        <span className="card-meta">
          {widget.source_slug} · {widget.metric_name}
        </span>
      </header>
      <div className="card-body">
        {loading && <p className="muted">Loading…</p>}
        {error && <p className="error">{error}</p>}
        {!loading && !error && widget.kind === "stat" && <Stat widget={widget} data={data} />}
        {!loading && !error && widget.kind !== "stat" && (
          data.length === 0 ? (
            <p className="muted">No data in the last {widget.window_minutes} minutes.</p>
          ) : (
            <ResponsiveContainer width="100%" height={220}>
              <Chart widget={widget} data={data} />
            </ResponsiveContainer>
          )
        )}
      </div>
    </section>
  );
}
