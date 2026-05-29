import type { MonitorEvent } from "../api/types";

interface ToolUse { tool: string; result?: string; }
interface Step {
  node_id: string;
  agent: string;
  visit: number;
  status: "running" | "done";
  tokens: number;
  summary: string;
  tools: ToolUse[];
  routedTo?: { to_name: string; when: string; value?: string | null; loop: boolean };
}

/** Fold the raw event stream into an ordered list of node executions. */
function buildTimeline(events: MonitorEvent[]): Step[] {
  const steps: Step[] = [];
  let cur: Step | null = null;
  for (const e of events) {
    const d = e.data || {};
    switch (e.type) {
      case "node_start":
        cur = {
          node_id: d.node_id,
          agent: e.agent_name || d.node_id || "agent",
          visit: d.visit || 1,
          status: "running",
          tokens: 0,
          summary: "",
          tools: [],
        };
        steps.push(cur);
        break;
      case "tool_call":
        cur?.tools.push({ tool: d.tool });
        break;
      case "tool_result":
        if (cur) {
          const last = [...cur.tools].reverse().find((t) => t.tool === d.tool && t.result === undefined);
          if (last) last.result = String(d.result ?? "");
        }
        break;
      case "agent_message":
        if (cur) {
          cur.summary = String(d.content ?? "");
          cur.tokens = (d.prompt_tokens ?? 0) + (d.completion_tokens ?? 0);
        }
        break;
      case "node_end":
        if (cur) cur.status = "done";
        break;
      case "route":
        if (cur)
          cur.routedTo = {
            to_name: d.to_name,
            when: d.when,
            value: d.value,
            loop: !!d.blocked_loop_target,
          };
        break;
    }
  }
  return steps;
}

export default function RunTimeline({ events }: { events: MonitorEvent[] }) {
  const steps = buildTimeline(events);
  if (steps.length === 0) return <div className="help">No steps yet.</div>;

  return (
    <div>
      {steps.map((s, i) => (
        <div key={i}>
          <div className="tl-step" style={s.status === "running" ? { borderLeftColor: "var(--amber)" } : undefined}>
            <div className="tl-head">
              <span>
                {i + 1}. {s.agent}
                {s.visit > 1 && <span className="tag" style={{ marginLeft: 6 }}>visit {s.visit}</span>}
              </span>
              <span style={{ color: "var(--text-faint)", fontWeight: 400, fontSize: 12 }}>
                {s.status === "running" ? "⏳ running" : "✓ done"}
                {s.tokens ? ` · ${s.tokens} tok` : ""}
              </span>
            </div>
            {s.tools.length > 0 && (
              <div className="tag-list" style={{ marginTop: 6 }}>
                {s.tools.map((t, j) => <span className="tag" key={j}>🔧 {t.tool}</span>)}
              </div>
            )}
            {s.summary && (
              <div className="tl-sum">
                {s.summary.length > 220 ? s.summary.slice(0, 220) + "…" : s.summary}
              </div>
            )}
          </div>
          {s.routedTo && (
            <div className="tl-arrow">
              {s.routedTo.loop ? "↺ " : "↓ "}
              {s.routedTo.to_name === "END" ? "End" : s.routedTo.to_name}
              {s.routedTo.when && s.routedTo.when !== "always"
                ? ` (${s.routedTo.when}${s.routedTo.value ? `: ${s.routedTo.value}` : ""})`
                : ""}
              {s.routedTo.loop ? "  — revisions exhausted" : ""}
            </div>
          )}
        </div>
      ))}
    </div>
  );
}
