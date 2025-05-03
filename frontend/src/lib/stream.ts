import type { ConnectionStatus, LivePoint, ServerMessage } from "./types";

type PointListener = (points: LivePoint[]) => void;
type StatusListener = (status: ConnectionStatus) => void;

const key = (source: string, metric: string) => `${source}\u0000${metric}`;

function defaultUrl(): string {
  const configured = import.meta.env.VITE_WS_URL as string | undefined;
  if (configured) return configured;
  const scheme = window.location.protocol === "https:" ? "wss" : "ws";
  return `${scheme}://${window.location.host}/ws/stream/`;
}

/**
 * A single shared WebSocket for the whole app. Components register interest in
 * (source, metric) pairs; the client reference-counts them so the server only sees one
 * subscription per pair, and replays subscriptions after a reconnect.
 */
export class StreamClient {
  private socket: WebSocket | null = null;
  private listeners = new Map<string, Set<PointListener>>();
  private statusListeners = new Set<StatusListener>();
  private status: ConnectionStatus = "closed";
  private retries = 0;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private heartbeat: ReturnType<typeof setInterval> | null = null;

  constructor(private readonly url: string = defaultUrl()) {}

  subscribe(source: string, metric: string, listener: PointListener): () => void {
    const k = key(source, metric);
    let set = this.listeners.get(k);
    if (!set) {
      set = new Set();
      this.listeners.set(k, set);
      this.send({ action: "subscribe", source, metric });
    }
    set.add(listener);
    this.ensureConnected();

    return () => {
      const current = this.listeners.get(k);
      if (!current) return;
      current.delete(listener);
      if (current.size === 0) {
        this.listeners.delete(k);
        this.send({ action: "unsubscribe", source, metric });
      }
    };
  }

  onStatus(listener: StatusListener): () => void {
    this.statusListeners.add(listener);
    listener(this.status);
    return () => this.statusListeners.delete(listener);
  }

  getStatus(): ConnectionStatus {
    return this.status;
  }

  private ensureConnected(): void {
    if (this.socket || this.reconnectTimer) return;
    this.connect();
  }

  private connect(): void {
    this.setStatus("connecting");
    const socket = new WebSocket(this.url);
    this.socket = socket;

    socket.onopen = () => {
      this.retries = 0;
      this.setStatus("open");
      for (const k of this.listeners.keys()) {
        const [source, metric] = k.split("\u0000");
        this.send({ action: "subscribe", source, metric });
      }
      this.heartbeat = setInterval(() => this.send({ action: "ping" }), 25_000);
    };

    socket.onmessage = (event) => {
      let message: ServerMessage;
      try {
        message = JSON.parse(event.data as string) as ServerMessage;
      } catch {
        return;
      }
      if (message.type === "points") this.dispatch(message.points);
      else if (message.type === "error") console.warn("[stream]", message.message);
    };

    socket.onclose = () => {
      if (this.heartbeat) clearInterval(this.heartbeat);
      this.heartbeat = null;
      this.socket = null;
      this.setStatus("closed");
      this.scheduleReconnect();
    };

    socket.onerror = () => socket.close();
  }

  private scheduleReconnect(): void {
    if (this.listeners.size === 0) return;
    // Exponential backoff with jitter, capped at 30s.
    const delay = Math.min(30_000, 500 * 2 ** this.retries) * (0.5 + Math.random() / 2);
    this.retries += 1;
    this.reconnectTimer = setTimeout(() => {
      this.reconnectTimer = null;
      this.connect();
    }, delay);
  }

  private dispatch(points: LivePoint[]): void {
    const grouped = new Map<string, LivePoint[]>();
    for (const point of points) {
      const k = key(point.source, point.metric);
      const list = grouped.get(k) ?? [];
      list.push(point);
      grouped.set(k, list);
    }
    for (const [k, list] of grouped) {
      this.listeners.get(k)?.forEach((listener) => listener(list));
    }
  }

  private send(payload: object): void {
    if (this.socket?.readyState === WebSocket.OPEN) {
      this.socket.send(JSON.stringify(payload));
    }
  }

  private setStatus(status: ConnectionStatus): void {
    this.status = status;
    this.statusListeners.forEach((listener) => listener(status));
  }
}

export const streamClient = new StreamClient();
