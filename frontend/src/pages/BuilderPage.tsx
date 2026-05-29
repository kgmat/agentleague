import { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  addEdge,
  useNodesState,
  useEdgesState,
  MarkerType,
  type Connection,
  type Edge,
  type Node,
} from "@xyflow/react";
import AgentNode from "../components/AgentNode";
import { useMonitor } from "../hooks/useMonitor";
import { getWorkflow, listAgents, runWorkflow, updateWorkflow } from "../api/client";
import type { Agent, EdgeCondition, Workflow } from "../api/types";

const nodeTypes = { agentNode: AgentNode };

const COND_LABEL = (c: EdgeCondition) =>
  c.label || (c.when === "always" ? "always" : `${c.when}: ${c.value ?? ""}`);

export default function BuilderPage() {
  const { id } = useParams();
  const nav = useNavigate();
  const wfQuery = useQuery({ queryKey: ["workflow", id], queryFn: () => getWorkflow(id!), enabled: !!id });
  const agentsQuery = useQuery({ queryKey: ["agents"], queryFn: listAgents });
  const agents = agentsQuery.data ?? [];

  const [nodes, setNodes, onNodesChange] = useNodesState<Node>([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([]);
  const [selNode, setSelNode] = useState<string | null>(null);
  const [selEdge, setSelEdge] = useState<string | null>(null);
  const [loaded, setLoaded] = useState(false);
  const [runId, setRunId] = useState<string | undefined>(undefined);
  const [toast, setToast] = useState<string | null>(null);

  const { events } = useMonitor(runId);

  // --- Live run state derived from events ---
  const { activeNode, visitCounts, lastOutput, running } = useMemo(() => {
    let active: string | null = null;
    const visits: Record<string, number> = {};
    let output = "";
    let isRunning = false;
    for (const e of events) {
      if (e.type === "run_status") isRunning = e.data.status === "running";
      if (e.type === "node_start") {
        active = e.data.node_id;
        visits[e.data.node_id] = (visits[e.data.node_id] ?? 0) + 1;
      }
      if (e.type === "agent_message") output = e.data.content ?? output;
      if (e.type === "run_status" && (e.data.status === "completed" || e.data.status === "failed")) {
        active = null;
        isRunning = false;
      }
    }
    return { activeNode: active, visitCounts: visits, lastOutput: output, running: isRunning };
  }, [events]);

  const agentName = useCallback(
    (agentId: string | null | undefined) => agents.find((a) => a.id === agentId)?.name,
    [agents]
  );

  // --- Load workflow into the canvas once ---
  useEffect(() => {
    if (wfQuery.data && !loaded) {
      const wf = wfQuery.data;
      setNodes(
        wf.graph.nodes.map((n) => ({
          id: n.id,
          type: "agentNode",
          position: n.position,
          data: { ...n.data, agentName: agentName(n.data.agent_id) },
        }))
      );
      setEdges(
        wf.graph.edges.map((e) => ({
          id: e.id,
          source: e.source,
          target: e.target,
          label: COND_LABEL(e.condition),
          data: { condition: e.condition },
          markerEnd: { type: MarkerType.ArrowClosed },
          style: { stroke: e.condition.when === "always" ? "#6366f1" : "#22d3ee" },
        }))
      );
      setLoaded(true);
    }
  }, [wfQuery.data, loaded, agentName, setNodes, setEdges]);

  // --- Apply live highlight + visit counts to node data ---
  useEffect(() => {
    setNodes((nds) =>
      nds.map((n) => ({
        ...n,
        data: { ...n.data, active: n.id === activeNode, visits: visitCounts[n.id] || 0,
          agentName: agentName((n.data as any).agent_id) },
      }))
    );
  }, [activeNode, visitCounts, agentName, setNodes]);

  const onConnect = useCallback(
    (c: Connection) => {
      const cond: EdgeCondition = { when: "always", value: null, label: null };
      setEdges((eds) =>
        addEdge(
          {
            ...c,
            id: `e_${Date.now()}`,
            label: "always",
            data: { condition: cond },
            markerEnd: { type: MarkerType.ArrowClosed },
            style: { stroke: "#6366f1" },
          },
          eds
        )
      );
    },
    [setEdges]
  );

  const addAgentNode = () => {
    const nid = `n_${Date.now()}`;
    setNodes((nds) => [
      ...nds,
      {
        id: nid,
        type: "agentNode",
        position: { x: 260 + Math.random() * 120, y: 120 + Math.random() * 120 },
        data: { label: "Agent", kind: "agent", agent_id: null, max_visits: 3 },
      },
    ]);
    setSelNode(nid);
  };

  const toBackendGraph = () => ({
    nodes: nodes.map((n) => ({
      id: n.id,
      type: "agentNode",
      position: n.position,
      data: {
        label: (n.data as any).label ?? "",
        kind: (n.data as any).kind ?? "agent",
        agent_id: (n.data as any).agent_id ?? null,
        max_visits: (n.data as any).max_visits ?? 3,
        position: n.position,
      },
    })),
    edges: edges.map((e) => ({
      id: e.id,
      source: e.source,
      target: e.target,
      condition: (e.data as any)?.condition ?? { when: "always", value: null, label: null },
    })),
  });

  const save = async () => {
    if (!id) return;
    await updateWorkflow(id, { graph: toBackendGraph() as Workflow["graph"] });
    flash("Workflow saved");
  };

  const run = async () => {
    if (!id) return;
    await updateWorkflow(id, { graph: toBackendGraph() as Workflow["graph"] });
    const input = prompt("Task / message to start the workflow with:", "Write a short article about sea otters.");
    if (input == null) return;
    const r = await runWorkflow(id, input);
    setRunId(r.id);
    flash("Run started — watch the graph light up");
  };

  const flash = (m: string) => { setToast(m); setTimeout(() => setToast(null), 2500); };

  // --- Side panel editors ---
  const updateNodeData = (nid: string, patch: Record<string, unknown>) =>
    setNodes((nds) => nds.map((n) => (n.id === nid ? { ...n, data: { ...n.data, ...patch } } : n)));

  const updateEdgeCond = (eid: string, cond: EdgeCondition) =>
    setEdges((eds) =>
      eds.map((e) =>
        e.id === eid
          ? { ...e, label: COND_LABEL(cond), data: { condition: cond },
              style: { stroke: cond.when === "always" ? "#6366f1" : "#22d3ee" } }
          : e
      )
    );

  const node = nodes.find((n) => n.id === selNode);
  const edge = edges.find((e) => e.id === selEdge);

  return (
    <div className="builder">
      <div className="canvas-wrap">
        <div className="builder-toolbar">
          <button className="btn sm" onClick={() => nav("/workflows")}>← Back</button>
          <button className="btn sm" onClick={addAgentNode}>+ Agent node</button>
          <button className="btn sm" onClick={save}>💾 Save</button>
          <button className="btn primary sm" onClick={run}>▶ Run</button>
          <span style={{ alignSelf: "center", fontSize: 12, color: "var(--text-dim)", marginLeft: 6 }}>
            {wfQuery.data?.name}{running ? "  ·  running…" : ""}
          </span>
        </div>
        <ReactFlow
          nodes={nodes}
          edges={edges}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          onConnect={onConnect}
          nodeTypes={nodeTypes}
          onNodeClick={(_, n) => { setSelNode(n.id); setSelEdge(null); }}
          onEdgeClick={(_, e) => { setSelEdge(e.id); setSelNode(null); }}
          onPaneClick={() => { setSelNode(null); setSelEdge(null); }}
          fitView
          colorMode="dark"
        >
          <Background color="#243049" gap={18} />
          <Controls />
          <MiniMap pannable zoomable style={{ background: "#0b0f17" }} nodeColor="#6366f1" />
        </ReactFlow>
      </div>

      <div className="builder-panel">
        {!node && !edge && (
          <>
            <h3>Inspector</h3>
            <p className="help">
              Click a node to assign an agent and set its loop limit, or click an edge to set a routing condition.
              Drag from a node's right handle to another node's left handle to connect them.
            </p>
            {runId && (
              <>
                <h3 style={{ marginTop: 22 }}>Live output</h3>
                <div className="log" style={{ height: 320 }}>
                  {events.length === 0 && <div className="help">Waiting for events…</div>}
                  {events.map((e, i) => (
                    <div className={`log-line evt-${e.type}`} key={i}>
                      <span className="log-ts">{e.agent_name ? `[${e.agent_name}] ` : ""}</span>
                      {renderEvent(e)}
                    </div>
                  ))}
                </div>
                {lastOutput && (
                  <div className="card" style={{ marginTop: 12 }}>
                    <div className="stat-label">Latest output</div>
                    <div style={{ marginTop: 6, whiteSpace: "pre-wrap" }}>{lastOutput}</div>
                  </div>
                )}
              </>
            )}
          </>
        )}

        {node && (
          <>
            <h3>Node · {(node.data as any).kind}</h3>
            {(node.data as any).kind === "agent" ? (
              <>
                <div className="field">
                  <label>Assigned agent</label>
                  <select
                    value={(node.data as any).agent_id ?? ""}
                    onChange={(e) => {
                      const a = agents.find((x) => x.id === e.target.value);
                      updateNodeData(node.id, { agent_id: e.target.value || null, agentName: a?.name, label: a?.name ?? "Agent" });
                    }}
                  >
                    <option value="">— select agent —</option>
                    {agents.map((a: Agent) => <option key={a.id} value={a.id}>{a.name}</option>)}
                  </select>
                </div>
                <div className="field">
                  <label>Max visits (feedback-loop guard)</label>
                  <input
                    type="number" min={1}
                    value={(node.data as any).max_visits ?? 3}
                    onChange={(e) => updateNodeData(node.id, { max_visits: parseInt(e.target.value || "1") })}
                  />
                  <span className="help">How many times this node may run before the loop is forced to exit.</span>
                </div>
              </>
            ) : (
              <p className="help">Start / End markers define where the workflow begins and finishes.</p>
            )}
            <button
              className="btn sm danger"
              style={{ marginTop: 10 }}
              onClick={() => {
                setNodes((nds) => nds.filter((n) => n.id !== node.id));
                setEdges((eds) => eds.filter((e) => e.source !== node.id && e.target !== node.id));
                setSelNode(null);
              }}
            >
              Delete node
            </button>
          </>
        )}

        {edge && (
          <>
            <h3>Edge condition</h3>
            <p className="help">When should the workflow follow this edge? Specific conditions are checked before "always".</p>
            <EdgeEditor
              cond={(edge.data as any).condition}
              onChange={(c) => updateEdgeCond(edge.id, c)}
            />
            <button
              className="btn sm danger"
              style={{ marginTop: 10 }}
              onClick={() => { setEdges((eds) => eds.filter((e) => e.id !== edge.id)); setSelEdge(null); }}
            >
              Delete edge
            </button>
          </>
        )}
      </div>

      {toast && <div className="toast">{toast}</div>}
    </div>
  );
}

function EdgeEditor({ cond, onChange }: { cond: EdgeCondition; onChange: (c: EdgeCondition) => void }) {
  return (
    <>
      <div className="field">
        <label>Condition type</label>
        <select value={cond.when} onChange={(e) => onChange({ ...cond, when: e.target.value as EdgeCondition["when"] })}>
          <option value="always">always (unconditional / fallback)</option>
          <option value="contains">if output contains…</option>
          <option value="not_contains">if output does NOT contain…</option>
          <option value="llm_route">if output matches label (LLM route)</option>
        </select>
      </div>
      {cond.when !== "always" && (
        <div className="field">
          <label>Value</label>
          <input value={cond.value ?? ""} onChange={(e) => onChange({ ...cond, value: e.target.value })} placeholder="e.g. REVISE" />
        </div>
      )}
      <div className="field">
        <label>Edge label (shown on canvas)</label>
        <input value={cond.label ?? ""} onChange={(e) => onChange({ ...cond, label: e.target.value || null })} placeholder="optional" />
      </div>
    </>
  );
}

function renderEvent(e: { type: string; data: Record<string, any> }) {
  switch (e.type) {
    case "node_start": return `▶ entering ${e.data.node_id} (visit ${e.data.visit})`;
    case "node_end": return `✓ done ${e.data.node_id}`;
    case "tool_call": return `🔧 ${e.data.tool}(${JSON.stringify(e.data.args)})`;
    case "tool_result": return `   ↳ ${String(e.data.result).slice(0, 160)}`;
    case "agent_message": return `💬 ${String(e.data.content).slice(0, 200)}  ·  ${e.data.prompt_tokens + e.data.completion_tokens} tok`;
    case "run_status": return `● run ${e.data.status}${e.data.total_tokens ? ` · ${e.data.total_tokens} tok · $${e.data.cost_usd}` : ""}`;
    case "error": return `✖ ${e.data.message}`;
    default: return JSON.stringify(e.data);
  }
}
