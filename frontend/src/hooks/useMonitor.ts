import { useEffect, useRef, useState, useCallback } from "react";
import type { MonitorEvent } from "../api/types";

type Status = "connecting" | "open" | "closed";

/**
 * Subscribe to the backend monitoring WebSocket and accumulate events.
 * Pass a runId to scope to a single run, or omit for the global firehose.
 * Reconnects automatically with a short backoff.
 */
export function useMonitor(runId?: string, maxEvents = 500) {
  const [events, setEvents] = useState<MonitorEvent[]>([]);
  const [status, setStatus] = useState<Status>("connecting");
  const wsRef = useRef<WebSocket | null>(null);
  const retryRef = useRef<number | undefined>(undefined);

  const clear = useCallback(() => setEvents([]), []);

  useEffect(() => {
    let closedByUs = false;
    const proto = window.location.protocol === "https:" ? "wss" : "ws";
    const path = runId ? `/api/ws/runs/${runId}` : "/api/ws/monitor";
    const url = `${proto}://${window.location.host}${path}`;

    const connect = () => {
      setStatus("connecting");
      const ws = new WebSocket(url);
      wsRef.current = ws;

      ws.onopen = () => setStatus("open");
      ws.onmessage = (msg) => {
        try {
          const event = JSON.parse(msg.data) as MonitorEvent;
          setEvents((prev) => {
            const next = [...prev, event];
            return next.length > maxEvents ? next.slice(-maxEvents) : next;
          });
        } catch {
          /* ignore malformed frames */
        }
      };
      ws.onclose = () => {
        setStatus("closed");
        if (!closedByUs) retryRef.current = window.setTimeout(connect, 1500);
      };
      ws.onerror = () => ws.close();
    };

    connect();
    return () => {
      closedByUs = true;
      if (retryRef.current) window.clearTimeout(retryRef.current);
      wsRef.current?.close();
    };
  }, [runId, maxEvents]);

  return { events, status, clear };
}
