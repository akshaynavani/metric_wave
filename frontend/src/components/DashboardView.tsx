import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { getDashboard } from "../lib/api";
import type { Dashboard } from "../lib/types";
import { WidgetCard } from "./WidgetCard";

export function DashboardView() {
  const { slug = "" } = useParams();
  const [dashboard, setDashboard] = useState<Dashboard | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    setDashboard(null);
    setError(null);
    getDashboard(slug, controller.signal)
      .then(setDashboard)
      .catch((err: unknown) => {
        if (!controller.signal.aborted) setError(err instanceof Error ? err.message : String(err));
      });
    return () => controller.abort();
  }, [slug]);

  if (error) return <p className="error">Could not load dashboard: {error}</p>;
  if (!dashboard) return <p className="muted">Loading…</p>;

  return (
    <>
      <div className="page-title">
        <Link to="/" className="muted">
          ← All dashboards
        </Link>
        <h2>{dashboard.title}</h2>
        {dashboard.description && <p className="muted">{dashboard.description}</p>}
      </div>
      <div className="grid">
        {dashboard.widgets.map((widget) => (
          <WidgetCard key={widget.id} widget={widget} />
        ))}
      </div>
    </>
  );
}
