import { BrowserRouter, Link, Route, Routes } from "react-router-dom";

import { ConnectionBadge } from "./components/ConnectionBadge";
import { DashboardList } from "./components/DashboardList";
import { DashboardView } from "./components/DashboardView";

export default function App() {
  return (
    <BrowserRouter>
      <header className="topbar">
        <Link to="/" className="brand">
          metric_wave
        </Link>
        <ConnectionBadge />
      </header>
      <main className="container">
        <Routes>
          <Route path="/" element={<DashboardList />} />
          <Route path="/d/:slug" element={<DashboardView />} />
          <Route path="*" element={<p className="muted">Page not found.</p>} />
        </Routes>
      </main>
    </BrowserRouter>
  );
}
