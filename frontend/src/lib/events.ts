import type { MonitorEvent } from "../api/types";

const clip = (s: unknown, n = 200) => {
  const t = String(s ?? "");
  return t.length > n ? t.slice(0, n) + "…" : t;
};

/**
 * Render one monitoring event as a single human-readable trace line.
 * Shared by the Builder, Live Monitor, and Run Detail activity logs so the
 * sequence reads consistently everywhere.
 */
export function renderEventLine(e: MonitorEvent): string {
  const d = e.data || {};
  const who = e.agent_name || d.node_id || "";
  switch (e.type) {
    case "node_start":
      return `▶ ${who} — entering${d.visit ? ` (visit ${d.visit})` : ""}`;
    case "node_end":
      return `✓ ${who} — done`;
    case "tool_call":
      return `🔧 ${who} calls ${d.tool}(${JSON.stringify(d.args ?? {})})`;
    case "tool_result":
      return `   ↳ ${d.tool} → ${clip(d.result, 160)}`;
    case "agent_message": {
      const toks = (d.prompt_tokens ?? 0) + (d.completion_tokens ?? 0);
      return `💬 ${who}: ${clip(d.content)}${toks ? `  ·  ${toks} tok` : ""}`;
    }
    case "route": {
      const cond =
        d.when && d.when !== "always" ? ` (${d.when}${d.value ? `: ${d.value}` : ""})` : "";
      const reason = d.reason ? `  [${d.reason}]` : "";
      return `↳ ${d.from_name} → ${d.to_name}${cond}${reason}`;
    }
    case "run_status":
      return `● run ${d.status}${d.total_tokens ? `  ·  ${d.total_tokens} tok  ·  $${d.cost_usd}` : ""}`;
    case "error":
      return `✖ ${d.message}`;
    default:
      return `${e.type} ${clip(JSON.stringify(d), 120)}`;
  }
}
