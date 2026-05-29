// Wire types mirroring the backend Pydantic schemas.

export interface MemoryConfig { enabled: boolean; max_messages: number; }
export interface ScheduleConfig { enabled: boolean; cron: string | null; }
export interface Guardrails { max_steps: number; max_tokens: number | null; blocked_words: string[]; }

export interface Agent {
  id: string;
  name: string;
  role: string;
  system_prompt: string;
  provider: string;
  model: string;
  temperature: number;
  thinking: boolean;
  tools: string[];
  channels: string[];
  skills: string[];
  memory: MemoryConfig;
  schedule: ScheduleConfig;
  interaction_rules: Record<string, unknown>;
  guardrails: Guardrails;
  created_at: string;
  updated_at: string;
}

export type AgentInput = Omit<Agent, "id" | "created_at" | "updated_at">;

export interface EdgeCondition {
  when: "always" | "contains" | "not_contains" | "llm_route";
  value: string | null;
  label: string | null;
}

export interface GraphNode {
  id: string;
  type: string;
  position: { x: number; y: number };
  data: {
    label: string;
    kind: "agent" | "start" | "end";
    agent_id: string | null;
    max_visits: number;
    position: { x: number; y: number };
  };
}

export interface GraphEdge {
  id: string;
  source: string;
  target: string;
  condition: EdgeCondition;
}

export interface WorkflowGraph { nodes: GraphNode[]; edges: GraphEdge[]; }

export interface Workflow {
  id: string;
  name: string;
  description: string;
  graph: WorkflowGraph;
  is_template: boolean;
  template_key: string | null;
  created_at: string;
  updated_at: string;
}

export interface Message {
  id: string;
  run_id: string | null;
  role: string;
  sender: string;
  recipient: string;
  agent_id: string | null;
  channel: string | null;
  node_id: string | null;
  content: string;
  extra: Record<string, unknown>;
  prompt_tokens: number;
  completion_tokens: number;
  created_at: string;
}

export interface Run {
  id: string;
  workflow_id: string;
  status: "pending" | "running" | "completed" | "failed";
  trigger: string;
  input: Record<string, unknown>;
  output: Record<string, unknown>;
  error: string | null;
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
  cost_usd: number;
  step_count: number;
  started_at: string;
  finished_at: string | null;
}

export interface RunDetail extends Run { messages: Message[]; }

export interface Template { key: string; name: string; description: string; agent_count: number; }
export interface ToolInfo { name: string; description: string; }
export interface ProviderInfo { name: string; models: string[]; available: boolean; }
export interface ChannelBinding {
  id: string;
  channel: string;
  agent_id: string | null;
  workflow_id: string | null;
  enabled: boolean;
  config: Record<string, unknown>;
  created_at: string;
}

export interface MonitorEvent {
  type: string;
  run_id: string | null;
  workflow_id: string | null;
  agent_id: string | null;
  agent_name: string | null;
  data: Record<string, any>;
  ts: number;
}
