import { Handle, Position, type NodeProps } from "@xyflow/react";

// Custom React Flow node representing a start/end marker or an agent step.
export default function AgentNode({ data, selected }: NodeProps) {
  const d = data as {
    label: string;
    kind: "agent" | "start" | "end";
    agentName?: string;
    active?: boolean;
    visits?: number;
  };
  const kind = d.kind ?? "agent";

  return (
    <div
      className={
        `rf-node ${kind}` + (selected ? " selected" : "") + (d.active ? " active-node" : "")
      }
    >
      {kind !== "start" && <Handle type="target" position={Position.Left} />}
      <div className="nt">
        {kind === "start" ? "▶ Start" : kind === "end" ? "■ End" : d.label || "Agent"}
      </div>
      {kind === "agent" && (
        <div className="ns">
          {d.agentName ? `🤖 ${d.agentName}` : "⚠ no agent assigned"}
          {d.visits ? `  ·  ×${d.visits}` : ""}
        </div>
      )}
      {kind !== "end" && <Handle type="source" position={Position.Right} />}
    </div>
  );
}
