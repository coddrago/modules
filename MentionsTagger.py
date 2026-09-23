# ---------------------------------------------------------------------------------
# ░█▀▄░▄▀▀▄░█▀▄░█▀▀▄░█▀▀▄░█▀▀▀░▄▀▀▄░░░█▀▄▀█
# ░█░░░█░░█░█░█░█▄▄▀░█▄▄█░█░▀▄░█░░█░░░█░▀░█
# ░▀▀▀░░▀▀░░▀▀░░▀░▀▀░▀░░▀░▀▀▀▀░░▀▀░░░░▀░░▒▀
# Name: MentionsTagger
# Description: Monitors and logs keyword trigger mentions across chats
# Author: @codrago_m
# ---------------------------------------------------------------------------------
# 🔒    Licensed under the GNU AGPLv3
# 🌐 https://www.gnu.org/licenses/agpl-3.0.html
# ---------------------------------------------------------------------------------
# Author: @codrago
# Commands: tagger
# scope: heroku_only
# meta developer: @codrago_m, @zetgo
# meta banner: https://raw.githubusercontent.com/coddrago/modules/refs/heads/main/banner.png
# ---------------------------------------------------------------------------------

__version__ = (1, 0)

from herokutl.custom import Message

from .. import loader, utils
from ..types import BotInlineCall


@loader.tds
class MentionsTaggerMod(loader.Module):
    """Module for monitoring and logging keyword trigger mentions across chats"""

    strings = {
        "name": "MentionsTagger",
        "topic_description": "Системный журнал фиксации упоминаний и ключевых триггеров в чатах",
        "user_label": "пользователя",
        "btn_ignore_chat": "Игнорировать чат",
        "btn_ignore_user": "Игнорировать пользователя",
        "btn_ignore_both": "Игнорировать обоих",
        "alert_chat_ignored": "Чат добавлен в список исключений",
        "alert_user_ignored": "Пользователь добавлен в список исключений",
        "alert_both_ignored": "Чат и пользователь добавлены в список исключений",
        "status_enabled": "<b>[MentionsTagger]</b> Мониторинг успешно <b>включен</b>",
        "status_disabled": "<b>[MentionsTagger]</b> Мониторинг <b>выключен</b>",
        "default_notify_text": (
            "<tg-emoji emoji-id=5253864872780769235>❗️</tg-emoji> "
            "<b>[Mentions Alert]</b> Зафиксирован ключевой триггер для "
            "<a href='tg://user?id={user_id}'>{display_name}</a> (@{username}). "
            "<a href='{message_link}'>Открыть контекст</a>"
        ),
    }

    strings_en = {
        "name": "MentionsTagger",
        "topic_description": "System log of detected mentions and keyword triggers across chats",
        "user_label": "user",
        "btn_ignore_chat": "Ignore chat",
        "btn_ignore_user": "Ignore user",
        "btn_ignore_both": "Ignore both",
        "alert_chat_ignored": "Chat added to exception list",
        "alert_user_ignored": "User added to exception list",
        "alert_both_ignored": "Chat and user added to exception list",
        "status_enabled": "<b>[MentionsTagger]</b> Monitoring has been <b>enabled</b>",
        "status_disabled": "<b>[MentionsTagger]</b> Monitoring has been <b>disabled</b>",
        "default_notify_text": (
            "<tg-emoji emoji-id=5253864872780769235>❗️</tg-emoji> "
            "<b>[Mentions Alert]</b> Keyword trigger detected for "
            "<a href='tg://user?id={user_id}'>{display_name}</a> (@{username}). "
            "<a href='{message_link}'>Open context</a>"
        ),
    }

    def __init__(self):
        self.config = loader.ModuleConfig(
            loader.ConfigValue(
                "triggers",
                ["codrago"],
                "List of keywords/triggers to monitor",
                validator=loader.validators.Series(
                    loader.validators.String(),
                ),
            ),
            loader.ConfigValue(
                "display_name",
                None,
                "Display name/pseudonym in logs",
                validator=loader.validators.Union(
                    loader.validators.String(),
                    loader.validators.NoneType(),
                ),
            ),
            loader.ConfigValue(
                "custom_message",
                None,
                "Custom log template (placeholders: {user_id}, {display_name}, {username}, {message_link})",
                validator=loader.validators.Union(
                    loader.validators.String(),
                    loader.validators.NoneType(),
                ),
            ),
            loader.ConfigValue(
                "ignored_chats",
                [],
                "IDs of chats excluded from monitoring",
                validator=loader.validators.Series(
                    loader.validators.Integer(),
                ),
            ),
            loader.ConfigValue(
                "ignored_users",
                [],
                "IDs of users whose messages are ignored",
                validator=loader.validators.Series(
                    loader.validators.Integer(),
                ),
            ),
        )

    async def client_ready(self):
        self.heroku_forum = self._db.get("heroku.forums", "channel_id", 0)

        self.assets_topic = await utils.asset_forum_topic(
            self.client,
            self.db,
            self.heroku_forum,
            self.strings("name"),
            self.strings("topic_description"),
        )

    async def taggercmd(self, message: Message):
        """Toggle mentions monitoring status"""
        is_active = not self.get("active", False)
        self.set("active", is_active)

        await utils.answer(
            message,
            self.strings("status_enabled" if is_active else "status_disabled"),
        )

    @loader.watcher()
    async def watcher(self, message: Message):
        if not self.get("active", False):
            return

        is_chat = getattr(message, "is_group", False) or getattr(message, "is_channel", False)
        match is_chat:
            case True:
                pass
            case _:
                return

        if (
            not getattr(message, "message", "")
            or message.mentioned
            or message.out
            or getattr(message, "via_bot_id", None) is not None
            or message.sender_id == self.inline.bot_id
            or message.chat_id in self.config["ignored_chats"]
            or message.sender_id in self.config["ignored_users"]
        ):
            return

        msg_text_lower = message.message.lower()
        if not any(trigger.lower() in msg_text_lower for trigger in self.config["triggers"]):
            return

        chat = getattr(message, "chat", None) or await message.get_chat()
        chat_title = getattr(chat, "title", "") or ""
        chat_username = getattr(chat, "username", "") or ""
        if (
            chat_title.lower().startswith("heroku-")
            or chat_username.lower().startswith("heroku-")
        ):
            return

        username = (
            self.client.heroku_me.username
            or (
                self.client.heroku_me.usernames[0].username
                if getattr(self.client.heroku_me, "usernames", None)
                else f"id{self.tg_id}"
            )
        )

        display_name = self.config["display_name"] or self.strings("user_label")
        template = self.config["custom_message"] or self.strings("default_notify_text")

        text = template.format(
            user_id=self.tg_id,
            display_name=display_name,
            username=username,
            message_link=await message.link(),
        )

        await self.inline.bot.send_message(
            self.heroku_forum,
            text,
            message_thread_id=self.assets_topic.id,
            link_preview=False,
            reply_markup=self.inline.generate_markup(
                [
                    [
                        {
                            "text": self.strings("btn_ignore_chat"),
                            "callback": self._handle_ignore,
                            "args": ("chat", message.chat_id, message.sender_id),
                            "style": "primary",
                            "icon_custom_emoji_id": 5255961723059320920,
                        },
                        {
                            "text": self.strings("btn_ignore_user"),
                            "callback": self._handle_ignore,
                            "args": ("user", message.chat_id, message.sender_id),
                            "style": "primary",
                            "icon_custom_emoji_id": 5253527438675158560,
                        },
                    ],
                    [
                        {
                            "text": self.strings("btn_ignore_both"),
                            "callback": self._handle_ignore,
                            "args": ("both", message.chat_id, message.sender_id),
                            "style": "primary",
                            "icon_custom_emoji_id": 5255831443816327915,
                        },
                    ],
                ]
            ),
        )

    async def _handle_ignore(self, call: BotInlineCall, target: str, chat_id: int, user_id: int):
        match target:
            case "chat":
                if chat_id not in self.config["ignored_chats"]:
                    self.config["ignored_chats"] = self.config["ignored_chats"] + [chat_id]
                await call.answer(self.strings("alert_chat_ignored"), show_alert=True)

            case "user":
                if user_id not in self.config["ignored_users"]:
                    self.config["ignored_users"] = self.config["ignored_users"] + [user_id]
                await call.answer(self.strings("alert_user_ignored"), show_alert=True)

            case "both":
                if chat_id not in self.config["ignored_chats"]:
                    self.config["ignored_chats"] = self.config["ignored_chats"] + [chat_id]
                if user_id not in self.config["ignored_users"]:
                    self.config["ignored_users"] = self.config["ignored_users"] + [user_id]
                await call.answer(self.strings("alert_both_ignored"), show_alert=True)

            case _:
                await call.answer()
