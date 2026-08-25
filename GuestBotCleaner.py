# ---------------------------------------------------------------------------------
# ░█▀▄░▄▀▀▄░█▀▄░█▀▀▄░█▀▀▄░█▀▀▀░▄▀▀▄░░░█▀▄▀█
# ░█░░░█░░█░█░█░█▄▄▀░█▄▄█░█░▀▄░█░░█░░░█░▀░█
# ░▀▀▀░░▀▀░░▀▀░░▀░▀▀░▀░░▀░▀▀▀▀░░▀▀░░░░▀░░▒▀
# Name: GuestBotCleaner
# Description: Deletes messages sent by guest bots not participating in the chat
# Author: @codrago_m
# ---------------------------------------------------------------------------------
# 🔒    Licensed under the GNU AGPLv3
# 🌐 https://www.gnu.org/licenses/agpl-3.0.html
# ---------------------------------------------------------------------------------
# Author: @codrago
# Commands: guestbotcleaner, gbc
# scope: heroku_only
# meta developer: @codrago_m
# meta banner: https://raw.githubusercontent.com/coddrago/modules/refs/heads/main/banner.png
# ---------------------------------------------------------------------------------

__version__ = (1, 3)

from telethon.errors import ChatAdminRequiredError, UserNotParticipantError
from telethon.tl.functions.channels import GetParticipantRequest

from .. import loader, utils


@loader.tds
class GuestBotCleanerMod(loader.Module):
    """Deletes messages from guest bots — bots that are not members of the chat"""

    strings = {
        "name": "GuestBotCleaner",
        "_cfg_doc_enabled": "Включить/выключить удаление сообщений гостевых ботов.",
        "_cfg_doc_watched_chats": "Список ID чатов, в которых работает модуль (пусто = все чаты).",
        "_cfg_doc_whitelist_bots": "Список ID ботов, которых НЕ нужно трогать (белый список).",
        "_cfg_doc_notify": "Слать уведомление в топик при удалении.",
        "deleted": (
            "<tg-emoji emoji-id=5219776129669276751>❌</tg-emoji> "
            "<b>GuestBotCleaner:</b> удалено сообщение от гостевого бота "
            "<code>{bot_id}</code> (@{username}) в чате <code>{chat_id}</code>."
        ),
        "enabled": "<tg-emoji emoji-id=5208808350858364013>✅</tg-emoji> <b>GuestBotCleaner включён.</b>",
        "disabled": "<tg-emoji emoji-id=5219776129669276751>❌</tg-emoji> <b>GuestBotCleaner выключен.</b>",
    }

    strings_en = {
        "name": "GuestBotCleaner",
        "_cfg_doc_enabled": "Enable/disable guest bot message deletion.",
        "_cfg_doc_watched_chats": "List of chat IDs where the module is active (empty = all chats).",
        "_cfg_doc_whitelist_bots": "List of bot IDs that should never be touched (whitelist).",
        "_cfg_doc_notify": "Send a notification to a forum topic when a message is deleted.",
        "deleted": (
            "<tg-emoji emoji-id=5219776129669276751>❌</tg-emoji> "
            "<b>GuestBotCleaner:</b> deleted message from guest bot "
            "<code>{bot_id}</code> (@{username}) in chat <code>{chat_id}</code>."
        ),
        "enabled": "<tg-emoji emoji-id=5208808350858364013>✅</tg-emoji> <b>GuestBotCleaner enabled.</b>",
        "disabled": "<tg-emoji emoji-id=5219776129669276751>❌</tg-emoji> <b>GuestBotCleaner disabled.</b>",
    }

    def __init__(self):
        self._notif_topic = None
        self.config = loader.ModuleConfig(
            loader.ConfigValue(
                "enabled",
                True,
                doc=lambda: self.strings("_cfg_doc_enabled"),
                validator=loader.validators.Boolean(),
            ),
            loader.ConfigValue(
                "watched_chats",
                [],
                doc=lambda: self.strings("_cfg_doc_watched_chats"),
                validator=loader.validators.Series(
                    validator=loader.validators.TelegramID()
                ),
            ),
            loader.ConfigValue(
                "whitelist_bots",
                [],
                doc=lambda: self.strings("_cfg_doc_whitelist_bots"),
                validator=loader.validators.Series(
                    validator=loader.validators.TelegramID()
                ),
            ),
            loader.ConfigValue(
                "notify",
                False,
                doc=lambda: self.strings("_cfg_doc_notify"),
                validator=loader.validators.Boolean(),
            ),
        )

    async def client_ready(self):
        self.asset_channel = self._db.get("heroku.forums", "channel_id", 0)
        self._notif_topic = await utils.asset_forum_topic(
            self._client,
            self._db,
            self.asset_channel,
            self.strings("name"),
            description="Notifications about deleted guest bot messages.",
        )

    async def _is_member(self, chat_id: int, user_id: int) -> bool:
        """Check if user_id is a member of chat_id"""
        try:
            await self._client(
                GetParticipantRequest(channel=chat_id, participant=user_id)
            )
            return True
        except UserNotParticipantError:
            return False
        except Exception:
            return True

    @loader.command(alias="gbc")
    async def guestbotcleaner(self, message):
        """Toggle guest bot message deletion"""
        self.config["enabled"] = not self.config["enabled"]
        status_key = "enabled" if self.config["enabled"] else "disabled"
        await utils.answer(message, self.strings(status_key))

    @loader.watcher("only_groups")
    async def watcher(self, message):
        """Watch group messages and remove non-member bot posts"""
        if not self.config["enabled"]:
            return

        sender_id = getattr(message, "sender_id", None)
        if not sender_id:
            return

        sender = getattr(message, "sender", None)
        if sender is None:
            try:
                sender = await self._client.get_entity(sender_id)
            except Exception:
                return

        match getattr(sender, "bot", False):
            case True:
                pass
            case _:
                return

        bot_id = sender.id

        match bot_id in self.config["whitelist_bots"]:
            case False:
                pass
            case _:
                return

        chat_id = utils.get_chat_id(message)

        if self.config["watched_chats"] and chat_id not in self.config["watched_chats"]:
            return

        is_member = await self._is_member(chat_id, bot_id)
        match is_member:
            case False:
                pass
            case _:
                return

        try:
            await message.delete()
            if self.config["notify"] and self._notif_topic:
                username = getattr(sender, "username", None) or str(bot_id)
                await self.inline.bot.send_message(
                    self.asset_channel,
                    self.strings("deleted").format(
                        bot_id=bot_id,
                        username=username,
                        chat_id=chat_id,
                    ),
                    link_preview=False,
                    message_thread_id=self._notif_topic.id,
                )
        except (ChatAdminRequiredError, Exception):
            pass
