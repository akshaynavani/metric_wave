import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { listDashboards } from "../lib/api";
import type { Dashboard } from "../lib/types";

export function DashboardList() {
  const [dashboards, setDashboards] = useState<Dashboard[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    listDashboards(controller.signal)
      .then((page) => setDashboards(page.results))
      .catch((err: unknown) => {
        if (!controller.signal.aborted) setError(err instanceof Error ? err.message : String(err));
      });
    return () => controller.abort();
  }, []);

  if (error) return <p className="error">Could not load dashboards: {error}</p>;
  if (!dashboards) return <p className="muted">Loading dashboards…</p>;
  if (dashboards.length === 0) {
    return (
      <p className="muted">
        No dashboards yet. Run <code>python manage.py seed_demo</code> to create one.
      </p>
    );
  }

  return (
    <ul className="dashboard-list">
      {dashboards.map((d) => (
        <li key={d.id}>
          <Link to={`/d/${d.slug}`}>
            <strong>{d.title}</strong>
            <span className="muted">{d.description || `${d.widgets.length} widgets`}</span>
          </Link>
        </li>
      ))}
    </ul>
  );
}
