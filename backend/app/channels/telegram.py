"""Telegram channel adapter (long-polling).

Why Telegram: it needs only a bot token (from @BotFather), requires no business
verification, and works over long-polling — so the platform stays fully local
with a single setup command and no public webhook/tunnel. The adapter forwards
every inbound text message to the shared router and replies with the result.
"""
from __future__ import annotations

import asyncio

from app.channels.base import Channel
from app.channels.outbound import register_sender, unregister_sender
from app.channels.router import handle_inbound
from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class TelegramChannel(Channel):
    name = "telegram"

    def __init__(self, token: str) -> None:
        self._token = token
        self._app = None
        self._running = False
        self.username: str | None = None

    @property
    def running(self) -> bool:
        return self._running

    async def start(self) -> None:
        from telegram import Update
        from telegram.constants import ChatAction
        from telegram.ext import (
            Application,
            CommandHandler,
            ContextTypes,
            MessageHandler,
            filters,
        )

        application = Application.builder().token(self._token).build()

        async def on_start(update: Update, _ctx: ContextTypes.DEFAULT_TYPE) -> None:
            await update.message.reply_text(
                "👋 You're connected to *AgentLeague*.\n\n"
                "Send me a message and I'll route it to the agent or workflow "
                "bound to this channel. Watch it run live in the web UI's "
                "*Live Monitor*.\n\nCommands: /help",
                parse_mode="Markdown",
            )

        async def on_help(update: Update, _ctx: ContextTypes.DEFAULT_TYPE) -> None:
            await update.message.reply_text(
                "Just type your request in plain language. For example, with the "
                "Support Triage workflow bound: _\"I was double charged on my invoice\"_.\n\n"
                "Bindings are managed in the web UI → *Channels*.",
                parse_mode="Markdown",
            )

        async def on_message(update: Update, _ctx: ContextTypes.DEFAULT_TYPE) -> None:
            if not update.message or not update.message.text:
                return
            chat_id = str(update.message.chat_id)
            text = update.message.text
            logger.info("Telegram inbound from %s: %s", chat_id, text[:80])
            await update.message.chat.send_action(ChatAction.TYPING)
            try:
                reply = await handle_inbound("telegram", chat_id, text)
            except Exception as exc:  # noqa: BLE001
                logger.exception("Telegram handler failed")
                reply = f"⚠️ Sorry, something went wrong: {exc}"
            # Telegram messages cap at 4096 chars.
            await update.message.reply_text(reply[:4000])

        application.add_handler(CommandHandler("start", on_start))
        application.add_handler(CommandHandler("help", on_help))
        application.add_handler(
            MessageHandler(filters.TEXT & ~filters.COMMAND, on_message)
        )

        await application.initialize()
        await application.start()
        await application.updater.start_polling(drop_pending_updates=True)
        self._app = application
        self._running = True

        # Allow the run executor to deliver async workflow results back here.
        async def _send(conversation: str, text: str, _thread: str | None = None) -> None:
            await application.bot.send_message(chat_id=conversation, text=text[:4000])

        register_sender("telegram", _send)

        # Surface the connected bot's handle so it's easy to find and message.
        try:
            me = await application.bot.get_me()
            self.username = me.username
            logger.info("Telegram bot @%s is polling for messages.", me.username)
        except Exception:  # noqa: BLE001
            logger.info("Telegram bot is polling for messages.")

    async def stop(self) -> None:
        unregister_sender("telegram")
        if not self._app:
            return
        try:
            await self._app.updater.stop()
            await self._app.stop()
            await self._app.shutdown()
        except Exception as exc:  # noqa: BLE001
            logger.warning("Error stopping Telegram bot: %s", exc)
        finally:
            self._running = False
            self._app = None


_channel: TelegramChannel | None = None


async def start_telegram() -> None:
    """Start the Telegram channel if a token is configured. Non-fatal on error."""
    global _channel
    if not (settings.ENABLE_TELEGRAM and settings.TELEGRAM_BOT_TOKEN):
        logger.info("Telegram disabled (no TELEGRAM_BOT_TOKEN). Skipping.")
        return
    _channel = TelegramChannel(settings.TELEGRAM_BOT_TOKEN)
    try:
        await _channel.start()
    except Exception as exc:  # noqa: BLE001 - never block app startup on the bot
        logger.error("Failed to start Telegram bot: %s", exc)
        _channel = None


async def stop_telegram() -> None:
    if _channel:
        await _channel.stop()


def telegram_status() -> dict:
    return {
        "configured": bool(settings.TELEGRAM_BOT_TOKEN),
        "enabled": settings.ENABLE_TELEGRAM,
        "running": bool(_channel and _channel.running),
        "username": _channel.username if _channel else None,
    }
