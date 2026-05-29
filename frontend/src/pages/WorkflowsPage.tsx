import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import {
  createWorkflow,
  deleteWorkflow,
  instantiateTemplate,
  listTemplates,
  listWorkflows,
} from "../api/client";
import { fmtDate } from "../lib/format";
import { useConfirm, usePrompt } from "../components/Dialogs";
import { Plus } from "lucide-react";

export default function WorkflowsPage() {
  const qc = useQueryClient();
  const nav = useNavigate();
  const confirmDialog = useConfirm();
  const promptDialog = usePrompt();
  const { data: workflows } = useQuery({ queryKey: ["workflows"], queryFn: listWorkflows });
  const { data: templates } = useQuery({ queryKey: ["templates"], queryFn: listTemplates });

  const refresh = () => {
    qc.invalidateQueries({ queryKey: ["workflows"] });
    qc.invalidateQueries({ queryKey: ["agents"] });
  };

  const create = useMutation({
    mutationFn: createWorkflow,
    onSuccess: (wf) => { refresh(); nav(`/workflows/${wf.id}`); },
  });
  const instantiate = useMutation({
    mutationFn: instantiateTemplate,
    onSuccess: (wf) => { refresh(); nav(`/workflows/${wf.id}`); },
  });
  const remove = useMutation({ mutationFn: deleteWorkflow, onSuccess: refresh });

  const newWorkflow = async () => {
    const name = await promptDialog({
      title: "New workflow",
      label: "Workflow name",
      defaultValue: "My workflow",
      placeholder: "e.g. Support triage",
      confirmText: "Create",
    });
    if (name && name.trim()) {
      create.mutate({
        name,
        description: "",
        graph: {
          nodes: [
            { id: "start", type: "agentNode", position: { x: 40, y: 160 },
              data: { label: "Start", kind: "start", agent_id: null, max_visits: 1, position: { x: 40, y: 160 } } },
            { id: "end", type: "agentNode", position: { x: 520, y: 160 },
              data: { label: "End", kind: "end", agent_id: null, max_visits: 1, position: { x: 520, y: 160 } } },
          ],
          edges: [],
        },
      });
    }
  };

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Workflows</h1>
          <p className="page-sub">Wire agents into collaborative graphs with conditions and feedback loops.</p>
        </div>
        <button className="btn primary" onClick={newWorkflow}><Plus size={15} /> New workflow</button>
      </div>

      {!workflows?.length ? (
        <div className="empty" style={{ marginBottom: 28 }}>
          No workflows yet. Create a blank one, or instantiate a template below.
        </div>
      ) : (
        <div className="grid cols-3" style={{ marginBottom: 30 }}>
          {workflows.map((w) => (
            <div className="card click" key={w.id} onClick={() => nav(`/workflows/${w.id}`)}>
              <div style={{ display: "flex", justifyContent: "space-between" }}>
                <h3>{w.name}</h3>
                {w.is_template && <span className="badge blue">template</span>}
              </div>
              <div className="meta">{w.description || "—"}</div>
              <div className="tag-list">
                <span className="tag">{w.graph.nodes.filter((n) => n.data.kind === "agent").length} agents</span>
                <span className="tag">{w.graph.edges.length} edges</span>
              </div>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginTop: 12 }}>
                <span className="meta" style={{ color: "var(--text-faint)" }}>{fmtDate(w.updated_at)}</span>
                <button
                  className="btn sm danger"
                  onClick={async (e) => {
                    e.stopPropagation();
                    if (await confirmDialog({ title: "Delete workflow", message: <>Delete <strong>{w.name}</strong>?</>, confirmText: "Delete", danger: true }))
                      remove.mutate(w.id);
                  }}
                >
                  Delete
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      <h3 style={{ margin: "0 0 12px" }}>Templates</h3>
      <div className="grid cols-3">
        {templates?.map((t) => (
          <div className="card" key={t.key}>
            <h3>{t.name}</h3>
            <div className="meta">{t.description}</div>
            <button
              className="btn primary sm"
              style={{ marginTop: 12 }}
              disabled={instantiate.isPending}
              onClick={() => instantiate.mutate(t.key)}
            >
              Instantiate →
            </button>
          </div>
        ))}
      </div>
    </>
  );
}
