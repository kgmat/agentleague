import { useQuery } from "@tanstack/react-query";
import { useNavigate, useParams } from "react-router-dom";
import { getRun } from "../api/client";
import { fmtCost, fmtDate, fmtTime, statusBadge } from "../lib/format";
import { renderEventLine } from "../lib/events";
import { useMonitor } from "../hooks/useMonitor";

export default function RunDetailPage() {
  const { id } = useParams();
  const nav = useNavigate();
  const run = useQuery({
    queryKey: ["run", id],
    queryFn: () => getRun(id!),
    enabled: !!id,
    // Keep polling while the run is still in flight.
    refetchInterval: (q) => {
      const s = q.state.data?.status;
      return s === "running" || s === "pending" ? 1500 : false;
    },
  });

  // Live activity trace for this run (replays persisted history on connect,
  // then streams live — so you always see the full ordered sequence).
  const { events } = useMonitor(id);

  if (!run.data) return <div className="empty">Loading run…</div>;
  const r = run.data;

  return (
    <>
      <div className="page-head">
        <div>
          <button className="btn sm" onClick={() => nav(-1)}>← Back</button>
          <h1 style={{ marginTop: 10 }}>Run detail</h1>
          <p className="page-sub">Trigger: {r.trigger} · started {fmtDate(r.started_at)}</p>
        </div>
        <span className={`badge ${statusBadge(r.status)}`} style={{ alignSelf: "center" }}>{r.status}</span>
      </div>

      <div className="statbar">
        <Stat label="Prompt tokens" value={r.prompt_tokens.toLocaleString()} />
        <Stat label="Completion tokens" value={r.completion_tokens.toLocaleString()} />
        <Stat label="Total tokens" value={r.total_tokens.toLocaleString()} />
        <Stat label="Cost" value={fmtCost(r.cost_usd)} />
        <Stat label="Steps" value={r.step_count} />
      </div>

      {r.error && (
        <div className="card" style={{ borderColor: "var(--red)", marginBottom: 16 }}>
          <div className="stat-label" style={{ color: "var(--red)" }}>Error</div>
          <div style={{ marginTop: 6 }}>{r.error}</div>
        </div>
      )}

      <div className="card" style={{ marginBottom: 20 }}>
        <div className="stat-label">Input</div>
        <div style={{ marginTop: 6 }}>{(r.input as any)?.text || "—"}</div>
        {(r.output as any)?.text && (
          <>
            <div className="stat-label" style={{ marginTop: 14 }}>Final output</div>
            <div style={{ marginTop: 6, whiteSpace: "pre-wrap" }}>{(r.output as any).text}</div>
          </>
        )}
      </div>

      <h3>Activity {r.status === "running" && <span className="badge amber">live</span>}</h3>
      <div className="log" style={{ height: 260, marginBottom: 20 }}>
        {events.length === 0 ? (
          <div className="help">No activity recorded.</div>
        ) : (
          events.map((e, i) => (
            <div className={`log-line evt-${e.type}`} key={i}>
              <span className="log-ts">{fmtTime(e.ts)} </span>
              {renderEventLine(e)}
            </div>
          ))
        )}
      </div>

      <h3>Conversation & inter-agent messages</h3>
      {r.messages.length === 0 ? (
        <div className="empty">No messages recorded yet.</div>
      ) : (
        <div>
          {r.messages.map((m) => (
            <div className={`msg ${m.role}`} key={m.id}>
              <div className="who">
                <span>
                  {m.sender} {m.recipient ? `→ ${m.recipient}` : ""}{" "}
                  {m.channel === "telegram" && <span className="badge gray">telegram</span>}
                </span>
                <span className="toks">
                  {m.prompt_tokens + m.completion_tokens > 0
                    ? `${m.prompt_tokens + m.completion_tokens} tok`
                    : ""}
                </span>
              </div>
              <div className="body">{m.content}</div>
            </div>
          ))}
        </div>
      )}
    </>
  );
}

function Stat({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="card">
      <div className="stat-label">{label}</div>
      <div className="stat" style={{ fontSize: 20 }}>{value}</div>
    </div>
  );
}
