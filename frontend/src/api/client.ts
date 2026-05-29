import axios from "axios";
import type {
  Agent,
  AgentInput,
  ChannelBinding,
  ProviderInfo,
  Run,
  RunDetail,
  Template,
  ToolInfo,
  Workflow,
  WorkflowGraph,
} from "./types";

const api = axios.create({ baseURL: "/api" });

// --- Agents ---
export const listAgents = () => api.get<Agent[]>("/agents").then((r) => r.data);
export const getAgent = (id: string) => api.get<Agent>(`/agents/${id}`).then((r) => r.data);
export const createAgent = (data: AgentInput) => api.post<Agent>("/agents", data).then((r) => r.data);
export const updateAgent = (id: string, data: Partial<AgentInput>) =>
  api.put<Agent>(`/agents/${id}`, data).then((r) => r.data);
export const deleteAgent = (id: string) => api.delete(`/agents/${id}`).then((r) => r.data);

// --- Workflows ---
export const listWorkflows = () => api.get<Workflow[]>("/workflows").then((r) => r.data);
export const getWorkflow = (id: string) => api.get<Workflow>(`/workflows/${id}`).then((r) => r.data);
export const createWorkflow = (data: { name: string; description?: string; graph?: WorkflowGraph }) =>
  api.post<Workflow>("/workflows", data).then((r) => r.data);
export const updateWorkflow = (
  id: string,
  data: { name?: string; description?: string; graph?: WorkflowGraph }
) => api.put<Workflow>(`/workflows/${id}`, data).then((r) => r.data);
export const deleteWorkflow = (id: string) => api.delete(`/workflows/${id}`).then((r) => r.data);
export const runWorkflow = (id: string, input: string) =>
  api.post<Run>(`/workflows/${id}/run`, { input, trigger: "manual" }).then((r) => r.data);

// --- Runs ---
export const listRuns = (workflowId?: string) =>
  api.get<Run[]>("/runs", { params: workflowId ? { workflow_id: workflowId } : {} }).then((r) => r.data);
export const getRun = (id: string) => api.get<RunDetail>(`/runs/${id}`).then((r) => r.data);

// --- Templates ---
export const listTemplates = () => api.get<Template[]>("/templates").then((r) => r.data);
export const instantiateTemplate = (key: string) =>
  api.post<Workflow>(`/templates/${key}/instantiate`).then((r) => r.data);

// --- Meta ---
export const listTools = () => api.get<ToolInfo[]>("/tools").then((r) => r.data);
export const listProviders = () => api.get<ProviderInfo[]>("/providers").then((r) => r.data);
export const getConfig = () =>
  api
    .get<{ default_provider: string; default_model: string; telegram_enabled: boolean; max_workflow_steps: number }>(
      "/config"
    )
    .then((r) => r.data);

// --- Settings & live Ollama model discovery ---
export interface OllamaModelsResp { available: boolean; models: string[]; base_url: string; error: string | null; }
export const getSettings = () =>
  api.get<{ ollama_base_url: string; default_model: string }>("/settings").then((r) => r.data);
export const updateOllamaUrl = (base_url: string) =>
  api.put<OllamaModelsResp>("/settings/ollama", { base_url }).then((r) => r.data);
export const listOllamaModels = (base_url?: string) =>
  api.get<OllamaModelsResp>("/settings/ollama/models", { params: base_url ? { base_url } : {} }).then((r) => r.data);
export const listModels = (provider: string, base_url?: string) =>
  api
    .get<OllamaModelsResp>("/settings/models", { params: { provider, ...(base_url ? { base_url } : {}) } })
    .then((r) => r.data);

// --- Channels ---
export interface ChannelState { configured: boolean; enabled: boolean; running: boolean; username: string | null; }
export const channelStatus = () =>
  api.get<{ telegram: ChannelState; slack: ChannelState }>("/channels/status").then((r) => r.data);
export const listBindings = () => api.get<ChannelBinding[]>("/channels/bindings").then((r) => r.data);
export const createBinding = (data: { channel: string; agent_id?: string | null; workflow_id?: string | null }) =>
  api.post<ChannelBinding>("/channels/bindings", data).then((r) => r.data);
export const deleteBinding = (id: string) => api.delete(`/channels/bindings/${id}`).then((r) => r.data);

export default api;
