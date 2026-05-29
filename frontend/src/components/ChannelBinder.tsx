import { useEffect, useRef, useState, type ReactNode } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  createBinding,
  deleteBinding,
  listAgents,
  listBindings,
  listWorkflows,
  type ChannelState,
} from "../api/client";

/**
 * Status + "route to an existing workflow/agent" control for one messaging
 * channel. Keeps a single active binding per channel (save replaces it, clear
 * removes it). Reused on both the Settings and Channels pages.
 */
export default function ChannelBinder({
  channel,
  label,
  status,
  setupHint,
}: {
  channel: "telegram" | "slack";
  label: string;
  status?: ChannelState;
  setupHint: ReactNode;
}) {
  const qc = useQueryClient();
  const bindings = useQuery({ queryKey: ["bindings"], queryFn: listBindings });
  const agents = useQuery({ queryKey: ["agents"], queryFn: listAgents });
  const workflows = useQuery({ queryKey: ["workflows"], queryFn: listWorkflows });

  const current = bindings.data?.find((b) => b.channel === channel && b.enabled);
  const [target, setTarget] = useState("");
  const touched = useRef(false);

  // Initialise the dropdown from the current binding (once).
  useEffect(() => {
    if (!touched.current && current) {
      touched.current = true;
      setTarget(current.workflow_id ? `workflow:${current.workflow_id}` : current.agent_id ? `agent:${current.agent_id}` : "");
    }
  }, [current]);

  const save = useMutation({
    mutationFn: async () => {
      // Replace any existing bindings for this channel with the new selection.
      const mine = (bindings.data ?? []).filter((b) => b.channel === channel);
      for (const b of mine) await deleteBinding(b.id);
      if (target) {
        const [kind, id] = target.split(":");
        await createBinding({
          channel,
          agent_id: kind === "agent" ? id : null,
          workflow_id: kind === "workflow" ? id : null,
        });
      }
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["bindings"] }),
  });

  const badge = status?.running ? (
    <span className="badge green"><span className="dot green" />Live</span>
  ) : status?.configured ? (
    <span className="badge amber">Configured · not running</span>
  ) : (
    <span className="badge gray">Not connected</span>
  );

  return (
    <div className="card" style={{ marginBottom: 16 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "start" }}>
        <div>
          <h3 style={{ margin: 0 }}>{label}</h3>
          {status?.running && status.username && (
            <div className="meta" style={{ marginTop: 4 }}>
              {channel === "telegram"
                ? <a href={`https://t.me/${status.username}`} target="_blank" rel="noreferrer">@{status.username}</a>
                : <>@{status.username}</>}
            </div>
          )}
        </div>
        <div>{badge}</div>
      </div>

      {!status?.configured ? (
        <div className="help" style={{ marginTop: 12, lineHeight: 1.6 }}>{setupHint}</div>
      ) : (
        <>
          <div className="row" style={{ alignItems: "end", marginTop: 14 }}>
            <div className="field">
              <label>Route incoming messages to</label>
              <select value={target} onChange={(e) => { touched.current = true; setTarget(e.target.value); }}>
                <option value="">— Auto / none —</option>
                <optgroup label="Workflows">
                  {workflows.data?.map((w) => <option key={w.id} value={`workflow:${w.id}`}>{w.name}</option>)}
                </optgroup>
                <optgroup label="Agents">
                  {agents.data?.map((a) => <option key={a.id} value={`agent:${a.id}`}>{a.name}</option>)}
                </optgroup>
              </select>
            </div>
            <button className="btn primary" disabled={save.isPending} onClick={() => save.mutate()}>
              {save.isPending ? "Saving…" : "Save binding"}
            </button>
          </div>
          <div className="help" style={{ marginTop: 8 }}>
            {current
              ? <>Currently bound to <strong>{current.workflow_id ? "workflow" : "agent"}</strong>{" "}
                  {workflows.data?.find((w) => w.id === current.workflow_id)?.name
                    ?? agents.data?.find((a) => a.id === current.agent_id)?.name ?? "—"}.</>
              : <>No binding — messages get a "not connected" reply until you bind a target.</>}
          </div>
        </>
      )}
    </div>
  );
}
