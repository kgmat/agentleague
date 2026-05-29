"""Slack channel adapter (Socket Mode).

Why Socket Mode: like Telegram's long-polling, it needs **no public webhook /
tunnel** — Slack pushes events over an outbound WebSocket — so the platform
stays fully local with a single command. Requires a bot token (``xoxb-``) and an
app-level token (``xapp-`` with ``connections:write``).

The adapter forwards direct messages and @-mentions to the shared inbound router
(same path Telegram uses) and replies in-thread.
"""
from __future__ import annotations

import re

from app.channels.base import Channel
from app.channels.router import handle_inbound
from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

_MENTION_RE = re.compile(r"<@[\w]+>")


class SlackChannel(Channel):
    name = "slack"

    def __init__(self, bot_token: str, app_token: str) -> None:
        self._bot_token = bot_token
        self._app_token = app_token
        self._handler = None
        self._running = False
        self.bot_user: str | None = None

    @property
    def running(self) -> bool:
        return self._running

    async def start(self) -> None:
        from slack_bolt.adapter.socket_mode.async_handler import AsyncSocketModeHandler
        from slack_bolt.async_app import AsyncApp

        app = AsyncApp(token=self._bot_token)

        async def process(event: dict, say) -> None:
            # Ignore bot/system messages and edits to avoid loops.
            if event.get("bot_id") or event.get("subtype"):
                return
            text = _MENTION_RE.sub("", event.get("text", "")).strip()
            if not text:
                return
            channel_id = event.get("channel", "")
            thread_ts = event.get("thread_ts") or event.get("ts")
            logger.info("Slack inbound from %s: %s", channel_id, text[:80])
            try:
                reply = await handle_inbound("slack", channel_id, text)
            except Exception as exc:  # noqa: BLE001
                logger.exception("Slack handler failed")
                reply = f"⚠️ Sorry, something went wrong: {exc}"
            await say(text=reply[:3900], thread_ts=thread_ts)

        @app.event("app_mention")
        async def _on_mention(event, say):  # noqa: ANN001
            await process(event, say)

        @app.event("message")
        async def _on_message(event, say):  # noqa: ANN001
            # Only auto-reply in direct messages; channels use @-mentions.
            if event.get("channel_type") == "im":
                await process(event, say)

        handler = AsyncSocketModeHandler(app, self._app_token)
        await handler.connect_async()  # non-blocking; runs the socket in the background
        self._handler = handler
        self._running = True

        try:
            auth = await app.client.auth_test()
            self.bot_user = auth.get("user")
            logger.info("Slack bot @%s connected via Socket Mode.", self.bot_user)
        except Exception:  # noqa: BLE001
            logger.info("Slack bot connected via Socket Mode.")

    async def stop(self) -> None:
        if not self._handler:
            return
        try:
            await self._handler.close_async()
        except Exception as exc:  # noqa: BLE001
            logger.warning("Error stopping Slack handler: %s", exc)
        finally:
            self._running = False
            self._handler = None


_channel: SlackChannel | None = None


async def start_slack() -> None:
    """Start the Slack channel if tokens are configured. Non-fatal on error."""
    global _channel
    if not (settings.ENABLE_SLACK and settings.SLACK_BOT_TOKEN and settings.SLACK_APP_TOKEN):
        logger.info("Slack disabled (need SLACK_BOT_TOKEN + SLACK_APP_TOKEN). Skipping.")
        return
    _channel = SlackChannel(settings.SLACK_BOT_TOKEN, settings.SLACK_APP_TOKEN)
    try:
        await _channel.start()
    except Exception as exc:  # noqa: BLE001 - never block app startup on a channel
        logger.error("Failed to start Slack: %s", exc)
        _channel = None


async def stop_slack() -> None:
    if _channel:
        await _channel.stop()


def slack_status() -> dict:
    return {
        "configured": bool(settings.SLACK_BOT_TOKEN and settings.SLACK_APP_TOKEN),
        "enabled": settings.ENABLE_SLACK,
        "running": bool(_channel and _channel.running),
        "username": _channel.bot_user if _channel else None,
    }
