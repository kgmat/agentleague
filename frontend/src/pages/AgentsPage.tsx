import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { createAgent, deleteAgent, listAgents, updateAgent } from "../api/client";
import type { Agent, AgentInput } from "../api/types";
import AgentForm from "../components/AgentForm";
import { useConfirm } from "../components/Dialogs";
import { Plus } from "lucide-react";

export default function AgentsPage() {
  const qc = useQueryClient();
  const confirmDialog = useConfirm();
  const { data: agents } = useQuery({ queryKey: ["agents"], queryFn: listAgents });
  const [editing, setEditing] = useState<Agent | null>(null);
  const [creating, setCreating] = useState(false);

  const invalidate = () => qc.invalidateQueries({ queryKey: ["agents"] });

  const create = useMutation({
    mutationFn: createAgent,
    onSuccess: () => { invalidate(); setCreating(false); },
  });
  const update = useMutation({
    mutationFn: ({ id, data }: { id: string; data: AgentInput }) => updateAgent(id, data),
    onSuccess: () => { invalidate(); setEditing(null); },
  });
  const remove = useMutation({ mutationFn: deleteAgent, onSuccess: invalidate });

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Agents</h1>
          <p className="page-sub">Create and configure autonomous agents — personality, model, tools, memory, guardrails.</p>
        </div>
        <button className="btn primary" onClick={() => setCreating(true)}><Plus size={15} /> New agent</button>
      </div>

      {!agents?.length ? (
        <div className="empty">No agents yet. Create one, or instantiate a template from the Dashboard.</div>
      ) : (
        <div className="grid cols-3">
          {agents.map((a) => (
            <div className="card" key={a.id}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "start" }}>
                <h3>{a.name}</h3>
                <span className="badge blue">{a.provider}:{a.model}</span>
              </div>
              <div className="meta">{a.role || "—"}</div>
              <div className="meta" style={{ marginTop: 8, color: "var(--text-faint)" }}>
                {a.system_prompt.slice(0, 90) || "No system prompt"}{a.system_prompt.length > 90 ? "…" : ""}
              </div>
              <div className="tag-list">
                {a.tools.map((t) => <span className="tag" key={t}>🔧 {t}</span>)}
                {a.channels.map((c) => <span className="tag" key={c}>💬 {c}</span>)}
                {a.memory.enabled && <span className="tag">🧠 mem {a.memory.max_messages}</span>}
                {a.thinking && <span className="tag">💭 thinking</span>}
              </div>
              <div style={{ display: "flex", gap: 8, marginTop: 14 }}>
                <button className="btn sm" onClick={() => setEditing(a)}>Edit</button>
                <button
                  className="btn sm danger"
                  onClick={async () => {
                    if (await confirmDialog({ title: "Delete agent", message: <>Delete <strong>{a.name}</strong>? This can't be undone.</>, confirmText: "Delete", danger: true }))
                      remove.mutate(a.id);
                  }}
                >
                  Delete
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {creating && (
        <AgentForm
          onCancel={() => setCreating(false)}
          onSubmit={(data) => create.mutate(data)}
          saving={create.isPending}
        />
      )}
      {editing && (
        <AgentForm
          initial={editing}
          onCancel={() => setEditing(null)}
          onSubmit={(data) => update.mutate({ id: editing.id, data })}
          saving={update.isPending}
        />
      )}
    </>
  );
}
