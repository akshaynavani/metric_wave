import { useConnectionStatus } from "../hooks/useConnectionStatus";

const LABELS = { open: "Live", connecting: "Connecting…", closed: "Offline" } as const;

export function ConnectionBadge() {
  const status = useConnectionStatus();
  return (
    <span className={`badge badge-${status}`} role="status" aria-live="polite">
      <span className="dot" />
      {LABELS[status]}
    </span>
  );
}
