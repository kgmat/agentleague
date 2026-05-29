import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { listRuns } from "../api/client";
import { useMonitor } from "../hooks/useMonitor";
import { fmtCost, fmtDate, fmtTime, statusBadge } from "../lib/format";

export default function MonitorPage() {
  const nav = useNavigate();
  const { events, status, clear } = useMonitor(); // global firehose
  const runs = useQuery({ queryKey: ["runs"], queryFn: () => listRuns(), refetchInterval: 3000 });

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Live Monitor</h1>
          <p className="page-sub">Real-time logs, inter-agent messages, tool calls and token/cost — across every run.</p>
        </div>
        <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
          <span className={`badge ${status === "open" ? "green" : "amber"}`}>
            <span className={`dot ${status === "open" ? "green" : "amber"}`} />
            {status === "open" ? "connected" : status}
          </span>
          <button className="btn sm" onClick={clear}>Clear</button>
        </div>
      </div>

      <div className="monitor">
        <div>
          <h3 style={{ marginTop: 0 }}>Event stream</h3>
          <div className="log">
            {events.length === 0 && <div className="help">Listening… run a workflow or message the Telegram bot to see events.</div>}
            {events.map((e, i) => (
              <div className={`log-line evt-${e.type}`} key={i}>
                <span className="log-ts">{fmtTime(e.ts)} </span>
                {e.agent_name ? `[${e.agent_name}] ` : ""}
                <strong>{e.type}</strong> {summarize(e)}
              </div>
            ))}
          </div>
        </div>

        <div>
          <h3 style={{ marginTop: 0 }}>Runs</h3>
          <div className="card" style={{ padding: 0 }}>
            <table>
              <thead>
                <tr><th>Status</th><th>Trigger</th><th>Tokens</th><th>Cost</th><th>Started</th></tr>
              </thead>
              <tbody>
                {(runs.data ?? []).map((r) => (
                  <tr className="click" key={r.id} onClick={() => nav(`/runs/${r.id}`)}>
                    <td><span className={`badge ${statusBadge(r.status)}`}>{r.status}</span></td>
                    <td>{r.trigger}</td>
                    <td>{r.total_tokens.toLocaleString()}</td>
                    <td>{fmtCost(r.cost_usd)}</td>
                    <td>{fmtDate(r.started_at)}</td>
                  </tr>
                ))}
                {!runs.data?.length && (
                  <tr><td colSpan={5} style={{ color: "var(--text-dim)" }}>No runs yet.</td></tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </>
  );
}

function summarize(e: { type: string; data: Record<string, any> }) {
  switch (e.type) {
    case "agent_message": return `· ${String(e.data.content ?? "").slice(0, 120)}`;
    case "tool_call": return `· ${e.data.tool}`;
    case "tool_result": return `· ${String(e.data.result ?? "").slice(0, 80)}`;
    case "node_start": return `· ${e.data.node_id}`;
    case "run_status": return `· ${e.data.status}`;
    case "error": return `· ${e.data.message}`;
    default: return "";
  }
}
