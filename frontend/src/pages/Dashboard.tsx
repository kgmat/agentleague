import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import {
  channelStatus,
  instantiateTemplate,
  listAgents,
  listRuns,
  listTemplates,
  listWorkflows,
} from "../api/client";
import { fmtCost, fmtDate, statusBadge } from "../lib/format";

export default function Dashboard() {
  const nav = useNavigate();
  const qc = useQueryClient();
  const agents = useQuery({ queryKey: ["agents"], queryFn: listAgents });
  const workflows = useQuery({ queryKey: ["workflows"], queryFn: listWorkflows });
  const runs = useQuery({ queryKey: ["runs"], queryFn: () => listRuns() });
  const templates = useQuery({ queryKey: ["templates"], queryFn: listTemplates });
  const channels = useQuery({ queryKey: ["channelStatus"], queryFn: channelStatus });

  const instantiate = useMutation({
    mutationFn: instantiateTemplate,
    onSuccess: (wf) => {
      qc.invalidateQueries({ queryKey: ["workflows"] });
      qc.invalidateQueries({ queryKey: ["agents"] });
      nav(`/workflows/${wf.id}`);
    },
  });

  const allRuns = runs.data ?? [];
  const totalTokens = allRuns.reduce((s, r) => s + r.total_tokens, 0);
  const totalCost = allRuns.reduce((s, r) => s + r.cost_usd, 0);
  const tg = channels.data?.telegram;

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Dashboard</h1>
          <p className="page-sub">Multi-agent orchestration at a glance.</p>
        </div>
      </div>

      <div className="statbar">
        <Stat label="Agents" value={agents.data?.length ?? 0} />
        <Stat label="Workflows" value={workflows.data?.length ?? 0} />
        <Stat label="Runs" value={allRuns.length} />
        <Stat label="Total tokens" value={totalTokens.toLocaleString()} />
        <Stat label="Total cost" value={fmtCost(totalCost)} />
        <div className="card">
          <div className="stat-label">Telegram</div>
          <div style={{ marginTop: 8 }}>
            {tg?.running ? (
              <span className="badge green"><span className="dot green" />Live</span>
            ) : tg?.configured ? (
              <span className="badge amber">Configured</span>
            ) : (
              <span className="badge gray">Not connected</span>
            )}
          </div>
        </div>
      </div>

      <h3 style={{ margin: "8px 0 12px" }}>Start from a template</h3>
      <div className="grid cols-3" style={{ marginBottom: 28 }}>
        {templates.data?.map((t) => (
          <div className="card" key={t.key}>
            <h3>{t.name}</h3>
            <div className="meta">{t.description}</div>
            <div style={{ marginTop: 12, display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <span className="tag">{t.agent_count} agents</span>
              <button
                className="btn primary sm"
                disabled={instantiate.isPending}
                onClick={() => instantiate.mutate(t.key)}
              >
                Use template →
              </button>
            </div>
          </div>
        ))}
      </div>

      <h3 style={{ margin: "8px 0 12px" }}>Recent runs</h3>
      {allRuns.length === 0 ? (
        <div className="empty">No runs yet. Instantiate a template and run it to see activity here.</div>
      ) : (
        <div className="card" style={{ padding: 0 }}>
          <table>
            <thead>
              <tr>
                <th>Status</th>
                <th>Trigger</th>
                <th>Tokens</th>
                <th>Cost</th>
                <th>Started</th>
              </tr>
            </thead>
            <tbody>
              {allRuns.slice(0, 8).map((r) => (
                <tr className="click" key={r.id} onClick={() => nav(`/runs/${r.id}`)}>
                  <td><span className={`badge ${statusBadge(r.status)}`}>{r.status}</span></td>
                  <td>{r.trigger}</td>
                  <td>{r.total_tokens.toLocaleString()}</td>
                  <td>{fmtCost(r.cost_usd)}</td>
                  <td>{fmtDate(r.started_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  );
}

function Stat({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="card">
      <div className="stat-label">{label}</div>
      <div className="stat">{value}</div>
    </div>
  );
}
