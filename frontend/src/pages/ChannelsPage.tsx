import { useQuery } from "@tanstack/react-query";
import { channelStatus } from "../api/client";
import ChannelBinder from "../components/ChannelBinder";

export default function ChannelsPage() {
  const status = useQuery({ queryKey: ["channelStatus"], queryFn: channelStatus, refetchInterval: 5000 });

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Channels</h1>
          <p className="page-sub">
            Connect agents to external messaging. A human can chat with the bound agent or workflow over Telegram or Slack.
          </p>
        </div>
      </div>

      <div style={{ maxWidth: 760 }}>
        <ChannelBinder
          channel="telegram"
          label="Telegram"
          status={status.data?.telegram}
          setupHint={
            <>
              Create a bot with <strong>@BotFather</strong>, copy the token into <code>backend/.env</code> as{" "}
              <code>TELEGRAM_BOT_TOKEN</code>, then restart the backend. Long-polling — no public webhook needed.
            </>
          }
        />
        <ChannelBinder
          channel="slack"
          label="Slack"
          status={status.data?.slack}
          setupHint={
            <>
              Create an app at <strong>api.slack.com/apps</strong>, enable <strong>Socket Mode</strong> and generate an
              app-level token (<code>xapp-</code>, scope <code>connections:write</code>). Add bot scopes{" "}
              <code>app_mentions:read</code>, <code>chat:write</code>, <code>im:history</code>, <code>im:read</code>,
              install to the workspace, then set <code>SLACK_BOT_TOKEN</code> + <code>SLACK_APP_TOKEN</code> in{" "}
              <code>backend/.env</code> and restart. Socket Mode — no public webhook needed.
            </>
          }
        />
      </div>

      <p className="help" style={{ marginTop: 6 }}>
        Tip: in Slack, DM the bot or @-mention it in a channel it's invited to. In Telegram, just message the bot.
        Conversations are persisted and stream into <strong>Live Monitor</strong>.
      </p>
    </>
  );
}
