import { useEffect, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { getConfig, listArchetypes, listModels, listProviders, listTools } from "../api/client";
import type { Agent, AgentInput, Archetype } from "../api/types";
import Modal from "./Modal";

const EMPTY: AgentInput = {
  name: "",
  role: "",
  system_prompt: "",
  provider: "ollama",
  model: "qwen2.5",
  temperature: 0.7,
  thinking: false,
  tools: [],
  channels: [],
  skills: [],
  memory: { enabled: true, max_messages: 20 },
  schedule: { enabled: false, cron: null },
  interaction_rules: {},
  guardrails: { max_steps: 8, max_tokens: null, blocked_words: [] },
};

export default function AgentForm({
  initial,
  onCancel,
  onSubmit,
  saving,
}: {
  initial?: Agent;
  onCancel: () => void;
  onSubmit: (data: AgentInput) => void;
  saving: boolean;
}) {
  const tools = useQuery({ queryKey: ["tools"], queryFn: listTools });
  const providers = useQuery({ queryKey: ["providers"], queryFn: listProviders });
  const config = useQuery({ queryKey: ["config"], queryFn: getConfig });

  const [f, setF] = useState<AgentInput>(initial ? { ...EMPTY, ...initial } : EMPTY);
  const set = (patch: Partial<AgentInput>) => setF((p) => ({ ...p, ...patch }));

  // Archetype gallery (create mode only) — prefills the form, stays editable.
  const archetypes = useQuery({ queryKey: ["archetypes"], queryFn: listArchetypes, enabled: !initial });
  const [archKey, setArchKey] = useState<string | null>(null);
  const applyArchetype = (a: Archetype) => {
    setArchKey(a.key);
    set({
      name: a.name,
      role: a.role,
      system_prompt: a.system_prompt,
      tools: a.tools,
      channels: a.channels,
      thinking: a.thinking,
    });
  };

  // When creating a new agent, default provider/model to the platform's config.
  const appliedDefaults = useRef(false);
  useEffect(() => {
    if (!initial && config.data && !appliedDefaults.current) {
      appliedDefaults.current = true;
      setF((p) => ({ ...p, provider: config.data!.default_provider, model: config.data!.default_model }));
    }
  }, [config.data, initial]);

  // Live model discovery for the selected provider (Ollama tags / OpenAI /models).
  const models = useQuery({
    queryKey: ["models", f.provider],
    queryFn: () => listModels(f.provider),
    enabled: !!f.provider,
  });
  const hasLiveModels = !!models.data?.available && (models.data?.models.length ?? 0) > 0;

  const toggleTool = (name: string) =>
    set({ tools: f.tools.includes(name) ? f.tools.filter((t) => t !== name) : [...f.tools, name] });
  const toggleChannel = (name: string) =>
    set({ channels: f.channels.includes(name) ? f.channels.filter((c) => c !== name) : [...f.channels, name] });

  const providerModels = providers.data?.find((p) => p.name === f.provider)?.models ?? [];
  const notes = (f.interaction_rules?.notes as string) ?? "";

  return (
    <Modal
      title={initial ? `Edit agent · ${initial.name}` : "New agent"}
      onClose={onCancel}
      footer={
        <>
          <button className="btn" onClick={onCancel}>Cancel</button>
          <button
            className="btn primary"
            disabled={saving || !f.name.trim()}
            onClick={() => onSubmit(f)}
          >
            {saving ? "Saving…" : "Save agent"}
          </button>
        </>
      }
    >
      <div className="form-grid">
        {!initial && archetypes.data && archetypes.data.length > 0 && (
          <div className="field">
            <label>Start from an archetype</label>
            <div className="arch-grid">
              {archetypes.data.map((a) => (
                <button
                  type="button"
                  key={a.key}
                  className={"arch-card" + (archKey === a.key ? " on" : "")}
                  title={a.system_prompt}
                  onClick={() => applyArchetype(a)}
                >
                  <div className="arch-name">{a.name}</div>
                  <div className="arch-desc">{a.description}</div>
                </button>
              ))}
            </div>
            <span className="help">
              Click to prefill (everything stays editable) — or just fill the form for a blank agent.
            </span>
          </div>
        )}

        <div className="row">
          <div className="field">
            <label>Name</label>
            <input value={f.name} onChange={(e) => set({ name: e.target.value })} placeholder="Researcher" />
          </div>
          <div className="field">
            <label>Role</label>
            <input value={f.role} onChange={(e) => set({ role: e.target.value })} placeholder="research analyst" />
          </div>
        </div>

        <div className="field">
          <label>System prompt</label>
          <textarea
            value={f.system_prompt}
            onChange={(e) => set({ system_prompt: e.target.value })}
            placeholder="Describe how this agent should behave…"
            style={{ minHeight: 110 }}
          />
        </div>

        <div className="row">
          <div className="field">
            <label>Provider</label>
            <select value={f.provider} onChange={(e) => set({ provider: e.target.value })}>
              {providers.data?.map((p) => (
                <option key={p.name} value={p.name} disabled={!p.available}>
                  {p.name}{p.available ? "" : " (no key)"}
                </option>
              ))}
            </select>
          </div>
          <div className="field">
            <label>Model {models.isFetching && <span className="help">· loading…</span>}</label>
            {hasLiveModels ? (
              <select value={f.model} onChange={(e) => set({ model: e.target.value })}>
                {!models.data!.models.includes(f.model) && <option value={f.model}>{f.model} (custom)</option>}
                {models.data!.models.map((m) => <option key={m} value={m}>{m}</option>)}
              </select>
            ) : (
              <input list="models" value={f.model} onChange={(e) => set({ model: e.target.value })} />
            )}
            <datalist id="models">
              {providerModels.map((m) => <option key={m} value={m} />)}
            </datalist>
            {models.isFetched && !models.data?.available && (
              <span className="help" style={{ color: "var(--amber)" }}>
                {f.provider} not reachable{models.data?.error ? ` (${models.data.error})` : ""}. Configure it in{" "}
                <Link to="/settings">Settings</Link> / .env.
              </span>
            )}
            {models.data?.available && models.data.models.length === 0 && (
              <span className="help">No models found for this provider.</span>
            )}
          </div>
          <div className="field">
            <label>Temperature: {f.temperature.toFixed(1)}</label>
            <input
              type="range" min={0} max={1} step={0.1}
              value={f.temperature}
              onChange={(e) => set({ temperature: parseFloat(e.target.value) })}
            />
          </div>
        </div>

        <div className="field">
          <label>Thinking</label>
          <span className="help">
            <input
              type="checkbox"
              checked={f.thinking}
              onChange={(e) => set({ thinking: e.target.checked })}
            />{" "}
            Enable thinking — deeper reasoning but much slower. Off = fast, short
            replies (recommended for most agents).
          </span>
        </div>

        <div className="field">
          <label>Tools</label>
          <div className="chips">
            {tools.data?.map((t) => (
              <div
                key={t.name}
                className={"chip" + (f.tools.includes(t.name) ? " on" : "")}
                title={t.description}
                onClick={() => toggleTool(t.name)}
              >
                {t.name}
              </div>
            ))}
          </div>
        </div>

        <div className="row">
          <div className="field">
            <label>Channels</label>
            <div className="chips">
              {["telegram"].map((c) => (
                <div key={c} className={"chip" + (f.channels.includes(c) ? " on" : "")} onClick={() => toggleChannel(c)}>
                  {c}
                </div>
              ))}
            </div>
          </div>
          <div className="field">
            <label>Skills (comma-separated)</label>
            <input
              value={f.skills.join(", ")}
              onChange={(e) => set({ skills: e.target.value.split(",").map((s) => s.trim()).filter(Boolean) })}
              placeholder="summarization, routing"
            />
          </div>
        </div>

        <div className="row">
          <div className="field">
            <label>Memory window (messages)</label>
            <input
              type="number" min={0}
              value={f.memory.max_messages}
              onChange={(e) => set({ memory: { enabled: f.memory.enabled, max_messages: parseInt(e.target.value || "0") } })}
            />
            <span className="help">
              <input
                type="checkbox"
                checked={f.memory.enabled}
                onChange={(e) => set({ memory: { ...f.memory, enabled: e.target.checked } })}
              /> remember recent turns
            </span>
          </div>
          <div className="field">
            <label>Max steps (guardrail)</label>
            <input
              type="number" min={1}
              value={f.guardrails.max_steps}
              onChange={(e) => set({ guardrails: { ...f.guardrails, max_steps: parseInt(e.target.value || "1") } })}
            />
            <span className="help">Cap on tool/LLM turns per node.</span>
          </div>
          <div className="field">
            <label>Blocked words (guardrail)</label>
            <input
              value={f.guardrails.blocked_words.join(", ")}
              onChange={(e) =>
                set({ guardrails: { ...f.guardrails, blocked_words: e.target.value.split(",").map((s) => s.trim()).filter(Boolean) } })
              }
              placeholder="redacted terms"
            />
          </div>
        </div>

        <div className="row">
          <div className="field">
            <label>Schedule (cron, informational)</label>
            <input
              value={f.schedule.cron ?? ""}
              onChange={(e) => set({ schedule: { enabled: !!e.target.value, cron: e.target.value || null } })}
              placeholder="0 9 * * *"
            />
          </div>
          <div className="field">
            <label>Interaction rules / hand-off notes</label>
            <input
              value={notes}
              onChange={(e) => set({ interaction_rules: { ...f.interaction_rules, notes: e.target.value } })}
              placeholder="When to defer to other agents…"
            />
          </div>
        </div>
      </div>
    </Modal>
  );
}
