import { useEffect, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { channelStatus, getConfig, getSettings, listModels, updateOllamaUrl, type OllamaModelsResp } from "../api/client";
import ChannelBinder from "../components/ChannelBinder";

export default function SettingsPage() {
  const qc = useQueryClient();
  const settings = useQuery({ queryKey: ["settings"], queryFn: getSettings });
  const config = useQuery({ queryKey: ["config"], queryFn: getConfig });
  const channels = useQuery({ queryKey: ["channelStatus"], queryFn: channelStatus, refetchInterval: 5000 });
  const provider = config.data?.default_provider ?? "ollama";

  // Live models for the active default provider.
  const models = useQuery({
    queryKey: ["models", provider],
    queryFn: () => listModels(provider),
    enabled: !!config.data,
  });

  const [url, setUrl] = useState("");
  const [result, setResult] = useState<OllamaModelsResp | null>(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (settings.data && !url) setUrl(settings.data.ollama_base_url);
  }, [settings.data, url]);

  const testAndSave = async () => {
    setSaving(true);
    try {
      const res = await updateOllamaUrl(url.trim());
      setResult(res);
      qc.invalidateQueries({ queryKey: ["settings"] });
      qc.invalidateQueries({ queryKey: ["models"] });
    } finally {
      setSaving(false);
    }
  };

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Settings</h1>
          <p className="page-sub">LLM provider configuration and live model discovery.</p>
        </div>
      </div>

      {/* Active provider summary */}
      <div className="card" style={{ maxWidth: 720, marginBottom: 18 }}>
        <h3 style={{ marginTop: 0 }}>Active provider</h3>
        <div className="row" style={{ marginTop: 6 }}>
          <div>
            <div className="stat-label">Provider</div>
            <div style={{ marginTop: 4 }}><span className="badge blue">{provider}</span></div>
          </div>
          <div>
            <div className="stat-label">Default model</div>
            <div style={{ marginTop: 4 }}>{config.data?.default_model ?? "—"}</div>
          </div>
          <div>
            <div className="stat-label">Reachable</div>
            <div style={{ marginTop: 4 }}>
              {models.isLoading ? "…" : models.data?.available
                ? <span className="badge green"><span className="dot green" />yes</span>
                : <span className="badge red"><span className="dot red" />no</span>}
            </div>
          </div>
        </div>
        {models.data?.available && (
          <>
            <div className="stat-label" style={{ marginTop: 16 }}>
              {models.data.models.length} model{models.data.models.length === 1 ? "" : "s"} available
            </div>
            <div className="tag-list" style={{ marginTop: 8 }}>
              {models.data.models.map((m) => (
                <span className="tag" key={m} style={m === config.data?.default_model ? { borderColor: "var(--accent)", color: "var(--text)" } : undefined}>{m}</span>
              ))}
            </div>
          </>
        )}
        {models.isFetched && !models.data?.available && (
          <div className="help" style={{ color: "var(--amber)", marginTop: 10 }}>
            {models.data?.error || "Provider not reachable."} Configure credentials in <code>backend/.env</code>.
          </div>
        )}
        <p className="help" style={{ marginTop: 12 }}>
          The provider, model and any API key/base URL come from <code>backend/.env</code>
          {" "}(<code>DEFAULT_PROVIDER</code>, <code>DEFAULT_MODEL</code>, <code>OPENAI_BASE_URL</code>…). These models
          populate the dropdown in the agent editor.
        </p>
      </div>

      {/* Ollama URL editor (relevant when using the ollama provider) */}
      <div className="card" style={{ maxWidth: 720 }}>
        <h3 style={{ marginTop: 0 }}>Ollama server URL</h3>
        <p className="help" style={{ marginBottom: 14 }}>
          For the <code>ollama</code> provider — point at any Ollama instance and pull its installed models. Saved and applied without a restart.
        </p>
        <div className="row" style={{ alignItems: "end" }}>
          <div className="field" style={{ flex: 3 }}>
            <label>Base URL</label>
            <input value={url} onChange={(e) => setUrl(e.target.value)} placeholder="http://localhost:11434" />
          </div>
          <button className="btn primary" disabled={saving || !url.trim()} onClick={testAndSave}>
            {saving ? "Testing…" : "Test & Save"}
          </button>
        </div>

        {result && (
          <div style={{ marginTop: 18 }}>
            {result.available
              ? <span className="badge green"><span className="dot green" />Reachable</span>
              : <span className="badge red"><span className="dot red" />Unreachable</span>}
            {result.error && <div className="help" style={{ color: "var(--red)", marginTop: 8 }}>{result.error}</div>}
            {result.available && (
              result.models.length === 0
                ? <div className="help" style={{ marginTop: 10 }}>No models installed — run e.g. <code>ollama pull qwen2.5</code>, then re-test.</div>
                : <div className="tag-list" style={{ marginTop: 10 }}>{result.models.map((m) => <span className="tag" key={m}>{m}</span>)}</div>
            )}
          </div>
        )}
      </div>

      {/* Messaging channels — bind to an existing workflow or agent */}
      <h3 style={{ margin: "26px 0 12px" }}>Messaging channels</h3>
      <div style={{ maxWidth: 720 }}>
        <ChannelBinder
          channel="telegram"
          label="Telegram"
          status={channels.data?.telegram}
          setupHint={<>Create a bot with <strong>@BotFather</strong>, set <code>TELEGRAM_BOT_TOKEN</code> in <code>backend/.env</code>, and restart the backend.</>}
        />
        <ChannelBinder
          channel="slack"
          label="Slack"
          status={channels.data?.slack}
          setupHint={<>Create a Slack app, enable <strong>Socket Mode</strong>, then set <code>SLACK_BOT_TOKEN</code> + <code>SLACK_APP_TOKEN</code> in <code>backend/.env</code> and restart.</>}
        />
      </div>
    </>
  );
}
