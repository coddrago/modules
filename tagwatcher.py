# meta developer: @codrago_m
# scope: heroku_min 2.0.0

import logging
from .. import utils, loader, main
from telethon.tl.functions.messages import MarkDialogUnreadRequest

logger = logging.getLogger("TagWatcher")


@loader.tds
class TagWatcher(loader.Module):
    """Informs when you are tagged in chats and automatically reads pm."""

    strings = {
        "name": "TagWatcher",
        "_cfg_doc_blacklist_chats": "List of chat IDs to ignore notifications from.",
        "_cfg_doc_blacklist_users": "List of user IDs to ignore notifications from.",
        "_cfg_doc_enabled": "Enable/Disable the module.",
        "_cfg_doc_ignore_bots": "Ignore messages from bots.",
        "_cfg_doc_pm_autoread": "Automatically mark private messages as read when you receive a message.",
        "_cfg_doc_ignore_chats": "List of chat IDs to ignore tags from.",
        "_cfg_doc_ignore_users": "List of user IDs to ignore tags from.",
        "_cfg_doc_pm_mark_unread": "Mark the PM as unread after automatically reading it.",
        "_cfg_doc_custom_notif_text": "Custom notification text. Available variables: {title}, {chat_id}, {name}, {user_id}, {msg_content}, {reply_content}, {link}.",
        "enabled": "<emoji document_id=5208808350858364013>✅</emoji> <b>TagWatcher is enabled.</b>",
        "disabled": "<emoji document_id=5219776129669276751>❌</emoji> <b>TagWatcher is disabled.</b>",
        "mentioned": "<b>You were mentioned in <code>{title}</code> [ <code>{chat_id}</code> ] by <a href='tg://user?id={user_id}'>{name}</a> [ <code>{user_id}</code> ]:</b>\nReplying to message:\n{reply_content}\n<b>Message content:</b> {msg_content}\n\n<a href='{link}'>Go to message</a>",
        "reply_content": "<b>Reply content:</b> {reply_content}",
        "no_message_content": "❓ Empty message text",
        "msg_link_btn": "<a href='{msg_url}'>Go to message</a>",
        "first_msg": "<b>This is the channel where you will receive notifications when someone mentions you in chats.</b>\n\nYou can disable notifications using the <code>{prefix}tagwatcher</code> (<code>{prefix}tw</code>) command.",
        "request_join_reason": "Stay tuned for updates.",
    }
    strings_ru = {
        "_cls_doc": "Сообщает когда вас отмечают в чатах.",
        "_cfg_doc_blacklist_chats": "Список ID чатов, от которых уведомления не будут приходить.",
        "_cfg_doc_blacklist_users": "Список ID пользователей, от которых уведомления не будут приходить.",
        "_cfg_doc_enabled": "Включить/Выключить модуль.",
        "_cfg_doc_ignore_bots": "Игнорировать сообщения от ботов.",
        "_cfg_doc_pm_autoread": "Автоматически отмечать личные сообщения как прочтённые при получении сообщения.",
        "_cfg_doc_ignore_chats": "Список ID чатов, от которых не будут срабатывать упоминания.",
        "_cfg_doc_ignore_users": "Список ID пользователей, от которых не будут срабатывать упоминания.",
        "_cfg_doc_pm_mark_unread": "Помечать ЛС как непрочитанные после автоматического прочтения.",
        "_cfg_doc_custom_notif_text": "Пользовательский текст уведомления. Доступные переменные: {title}, {chat_id}, {name}, {user_id}, {msg_content}, {reply_content}, {link}.",
        "enabled": "<emoji document_id=5208808350858364013>✅</emoji> <b>TagWatcher включен.</b>",
        "disabled": "<emoji document_id=5219776129669276751>❌</emoji> <b>TagWatcher выключен.</b>",
        "mentioned": "<b>Вас отметил(а) <a href='tg://user?id={user_id}'>{name}</a> [ <code>{user_id}</code> ] в <code>{title}</code> [ <code>{chat_id}</code> ]:</b>\nВ ответ на сообщение:\n{reply_content}\n<b>Текст сообщения:</b> {msg_content}\n\n<a href='{link}'>Перейти к сообщению</a>",
        "reply_content": "<b>Ответ на сообщение:</b> {reply_content}",
        "no_message_content": "❓ Пустой текст сообщения",
        "msg_link_btn": "<a href='{msg_url}'>Перейти к сообщению</a>",
        "first_msg": "<b>Это канал, в который вы будете получать уведомления, когда кто-то упомянет вас в чатах.</b>\n\nВы можете отключить уведомления с помощью команды <code>{prefix}tagwatcher</code> (<code>{prefix}tw</code>).",
        "request_join_reason": "Следите за обновлениями модулей.",
    }

    def __init__(self) -> None:
        self.config = loader.ModuleConfig(
            loader.ConfigValue(
                "custom_notif_text",
                None,
                doc=lambda: self.strings["_cfg_doc_custom_notif_text"],
                validator=loader.validators.Union(
                    loader.validators.String(), loader.validators.NoneType()
                ),
            ),
            loader.ConfigValue(
                "ignore_bots",
                True,
                doc=lambda: self.strings["_cfg_doc_ignore_bots"],
                validator=loader.validators.Boolean(),
            ),
            loader.ConfigValue(
                "ignore_chats",
                [],
                doc=lambda: self.strings["_cfg_doc_ignore_chats"],
                validator=loader.validators.Series(
                    validator=loader.validators.TelegramID()
                ),
            ),
            loader.ConfigValue(
                "blacklist_chats",
                [],
                doc=lambda: self.strings["_cfg_doc_blacklist_chats"],
                validator=loader.validators.Series(
                    validator=loader.validators.TelegramID()
                ),
            ),
            loader.ConfigValue(
                "ignore_users",
                [],
                doc=lambda: self.strings["_cfg_doc_ignore_users"],
                validator=loader.validators.Series(
                    validator=loader.validators.TelegramID()
                ),
            ),
            loader.ConfigValue(
                "blacklist_users",
                [],
                doc=lambda: self.strings["_cfg_doc_blacklist_users"],
                validator=loader.validators.Series(
                    validator=loader.validators.TelegramID()
                ),
            ),
            loader.ConfigValue(
                "pm_autoread",
                False,
                doc=lambda: self.strings["_cfg_doc_pm_autoread"],
                validator=loader.validators.Boolean(),
            ),
            loader.ConfigValue(
                "pm_mark_unread",
                False,
                doc=lambda: self.strings["_cfg_doc_pm_mark_unread"],
                validator=loader.validators.Boolean(),
            ),
        )
    async def client_ready(self):
        self.asset_channel = self._db.get("heroku.forums", "channel_id", 0)
        self._notif_topic = await utils.asset_forum_topic(
            self._client,
            self._db,
            self.asset_channel,
            "TagWatcher",
            description="Here will be notifications about mentions in chats.",
            icon_emoji_id=5409025823388741707,
        )
        self.xdlib = await self.import_lib(
            "https://raw.githubusercontent.com/coddrago/modules/refs/heads/main/libs/xdlib.py",
            suspend_on_error=True,
        )

    async def render_text(self, m):
        if self.config["custom_notif_text"]:
            text = self.config["custom_notif_text"]
        else:
            text = self.strings["mentioned"]
        chat = await m.get_chat()
        sender = await self.xdlib.messages.get_sender(m)
        title = (
            utils.escape_html(chat.title)
            if hasattr(chat, "title")
            else utils.escape_html(
                sender.first_name if hasattr(sender, "first_name") else sender.title
            )
        )
        name = (
            utils.escape_html(
                sender.first_name if hasattr(sender, "first_name") else sender.title
            )
            if sender
            else "Unknown"
        )
        msg_content = (
            utils.escape_html(m.message)
            if m.message
            else self.strings["no_message_content"]
        )
        id = sender.id if sender else 0
        reply_content = ""
        if m.is_reply:
            reply = await m.get_reply_message()
            if reply:
                reply_content = (
                    utils.escape_html(reply.message)
                    if reply.message
                    else self.strings["no_message_content"]
                )
        return text.format(
            title=title,
            name=name,
            chat_id=chat.id,
            user_id=id,
            msg_content=msg_content,
            reply_content=reply_content,
            link=await m.link(),
        )

    @loader.command(
        ru_doc="Вкл/выкл TagWatcher.",
        alias="tw",
    )
    async def tagwatcher(self, m):
        """Enable/Disable TagWatcher."""
        try:
            disabled = self._db.pointer(main.__name__, "disabled_watchers", {})
            if self.strings["name"] in list(disabled.keys()):
                del disabled[self.strings["name"]]
                await utils.answer(m, self.strings["enabled"])
            else:
                disabled[self.strings["name"]] = ["*"]
                await utils.answer(m, self.strings["disabled"])
        except Exception as e:
            logger.error(e)

    @loader.watcher("only_pm")
    async def pm_reader(self, m):
        """To automatically mark private messages as read."""
        if self.config["pm_autoread"]:
            chat = await m.get_chat()
            if chat.id in self.config["ignore_users"] or chat.bot:
                return
            try:
                await self._client.send_read_acknowledge(
                    chat.id, m, clear_mentions=True
                )
                if self.config["pm_mark_unread"]:
                    peer = await self._client.get_input_entity(chat.id)
                    await self._client(
                        MarkDialogUnreadRequest(peer, True if not m.out else False)
                    )
            except Exception as e:
                logger.error(e)

    @loader.watcher("mention", "no_pm")
    async def inform(self, m):
        """To inform when you are mentioned in chats."""
        try:
            sender = await utils.get_user(m)
            if (
                utils.get_chat_id(m) in self.config["ignore_chats"]
                or sender.id in self.config["ignore_users"]
            ):
                return
            await self._client.send_read_acknowledge(m.chat_id, m, clear_mentions=True)
            if (
                not sender
                or utils.get_chat_id(m) in self.config["blacklist_chats"]
                or utils.get_chat_id(m) == self._notif_topic.id
                or sender.id in self.config["blacklist_users"]
            ):
                return
            if self.config["ignore_bots"]:
                if hasattr(sender, "bot"):
                    if sender.bot:
                        return
            await self.inline.bot.send_message(
                int(f"-100{self.asset_channel}"),
                await self.render_text(m),
                disable_web_page_preview=True,
                message_thread_id=self._notif_topic.id,
            )
        except Exception as e:
            logger.error(e)
