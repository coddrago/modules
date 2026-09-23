# meta developer: @codrago_m
# scope: disable_onload_docs
# packurl: https://raw.githubusercontent.com/coddrago/modules/refs/heads/main/translations/chatmodule.yml

import logging
import typing
from datetime import datetime, timedelta, timezone

from telethon.tl import types
from telethon.tl.functions import channels, messages

from .. import loader, utils

logger = logging.getLogger("ChatModule")


@loader.tds
class ChatModuleMod(loader.Module):
    strings = {
        "name": "ChatModule",
    }

    async def client_ready(self, client, db):
        self._client = client
        self._db = db
        self.xdlib = await self.import_lib(
            "https://raw.githubusercontent.com/coddrago/modules/refs/heads/main/libs/xdlib.py",
            suspend_on_error=True,
        )

    @loader.command(ru_doc="[reply] - Узнать ID")
    async def id(self, message):
        """[reply] - Get the ID"""
        ids = [self.strings["my_id"].format(id=self.tg_id)]
        if message.is_private:
            ids.append(self.strings["user_id"].format(id=message.to_id.user_id))
            return await utils.answer(message, "\n".join(ids))
        ids.append(self.strings["chat_id"].format(id=message.chat_id))
        reply = await message.get_reply_message()
        if (
            reply
            and not getattr(reply, "is_private")
            and not getattr(reply, "sender_id") == self.tg_id
        ):
            user_id = (await reply.get_sender()).id
            ids.append(self.strings["user_id"].format(id=user_id))
        return await utils.answer(message, "\n".join(ids))

    @loader.command(
        ru_doc="[reply/-u username/id] - Посмотреть права администратора пользователя",
    )
    @loader.tag("no_pm")
    async def rights(self, message):
        """[reply/-u username/id] - Check user's admin rights"""
        opts = self.xdlib.parse.opts(utils.get_args(message))
        reply = await message.get_reply_message()
        user = opts.get("u") or opts.get("user") or (reply.sender_id if reply else None)
        if not user:
            return await utils.answer(message, self.strings["no_user"])
        rights = await self.xdlib.chat.get_rights(message.chat, user)

        participant = rights.participant
        user = await self._client.get_entity(user)
        if not hasattr(participant, "admin_rights"):
            return await utils.answer(
                message, self.strings["not_an_admin"].format(user=user.first_name)
            )
        if participant.admin_rights:
            can_do = []
            rights = participant.to_dict().get("admin_rights")
            for right, is_permitted in rights.items():
                if right == "_":
                    continue
                if is_permitted:
                    can_do.append(right)
            promoter = (
                await self._client.get_entity(participant.promoted_by)
                if hasattr(participant, "promoted_by")
                else None
            )
            return await utils.answer(
                message,
                self.strings["admin_rights"].format(
                    rights="\n".join(
                        [
                            f"<emoji document_id=5409029658794537988>✅</emoji> {self.strings[right]}"
                            for right in can_do
                        ]
                    ),
                    promoter_id=promoter.id if promoter else 0,
                    promoter_name=(
                        promoter.first_name if promoter else self.strings["no"]
                    ),
                    name=user.first_name,
                ),
            )
        return await utils.answer(
            message, self.strings["not_an_admin"].format(user=user.first_name)
        )

    @loader.command(
        ru_doc="Покинуть чат",
    )
    @loader.tag("no_pm")
    async def leave(self, message):
        """Leave chat"""
        await message.delete()
        await self._client(channels.LeaveChannelRequest((await message.get_chat()).id))

    @loader.command(
        ru_doc="[a[1-100] b[1-100]] | [reply] Удалить сообщения",
    )
    async def d(self, message):
        """[a[1-100] b[1-100]] | [reply] - Delete messages"""
        await self.xdlib.messages.delete_messages(message)

    @loader.command(ru_doc="[reply] - Закрепить сообщение")
    @loader.tag("only_reply")
    async def pin(self, message):
        """[reply] - Pin a message"""
        reply = await message.get_reply_message()
        try:
            await reply.pin(notify=True, pm_oneside=False)
        except Exception as e:
            logger.error(str(e))
            return await utils.answer(message, self.strings["pin_failed"])
        await utils.answer(message, self.strings["pinned"])

    @loader.command(ru_doc="Открепить сообщение")
    @loader.tag("only_reply")
    async def unpin(self, message):
        """Unpin a message"""
        reply = await message.get_reply_message()
        try:
            await reply.unpin()
        except Exception as e:
            logger.error(str(e))
            return await utils.answer(message, self.strings["unpin_failed"])
        await utils.answer(message, self.strings["unpinned"])

    @loader.command(ru_doc="[-c id] Удаляет группу/канал")
    async def dgc(self, message):
        """[-c id] Delete chat/channel"""
        args = utils.get_args(message)
        opts = self.xdlib.parse.opts(args)
        chat_id = opts.get("c") or opts.get("chat")
        if chat_id:
            chat = await self._client.get_entity(chat_id)
            if isinstance(chat, types.Channel):
                await self._client(channels.DeleteChannelRequest(chat.id))
            elif isinstance(chat, types.Chat):
                await self._client(messages.DeleteChatRequest(chat.id))
            else:
                return await utils.answer(message, self.strings["failed_to_delete"])
            return await utils.answer(message, self.strings["successful_delete"])
        if isinstance(message.chat, types.Channel):
            await self._client(channels.DeleteChannelRequest(message.chat))
        elif isinstance(message.chat, types.Chat):
            await self._client(messages.DeleteChatRequest(message.chat))
        else:
            return await utils.answer(message, self.strings["failed_to_delete"])
        return

    @loader.command(ru_doc="Очищает группу/канал от удаленных аккаунтов")
    @loader.tag("no_pm")
    async def flush(self, message):
        """Removes deleted accounts from the chat/channel"""
        chat = await message.get_chat()

        if not getattr(chat, "admin_rights", False) and not getattr(
            getattr(chat, "admin_rights", None), "ban_users", False
        ):
            return await utils.answer(message, self.strings["no_rights"])

        deleted = await self.xdlib.chat.get_deleted(chat)
        if not deleted:
            return await utils.answer(message, self.strings["no_deleted_accounts"])
        for to_delete in deleted:
            try:
                await self._client.kick_participant(chat, to_delete)
            except Exception as e:
                logger.error(str(e))
                return await utils.answer(message, self.strings["error"])
        return await utils.answer(message, self.strings["kicked_deleted_accounts"])

    @loader.command(ru_doc="Показывает админов в группе/канале")
    @loader.tag("no_pm")
    async def admins(self, message):
        """Shows the admins in the chat/channel"""
        admins = await self.xdlib.chat.get_admins(message.chat, True)
        creator = await self.xdlib.chat.get_creator(message.chat)
        return await utils.answer(
            message,
            self.strings["admin_list"].format(
                id=creator.id if creator else 0,
                name=creator.first_name if creator else self.strings["no"],
                admins_count=len(admins) or 0,
                admins=(
                    "\n".join(
                        f"<emoji document_id=5774022692642492953>✅</emoji> <a href='tg://user?id={admin.id}'>{admin.first_name}</a> [<code>{admin.id}</code>] / <code>{admin.participant.rank}</code>"
                        for admin in admins
                    )
                    if admins
                    else f"\n{self.strings['no_admins_in_chat']}"
                ),
            ),
        )

    @loader.command(ru_doc="Показывает ботов в группе/канале")
    @loader.tag("no_pm")
    async def bots(self, message):
        """Shows the bots in the chat/channel"""
        bots = await self.xdlib.chat.get_bots(message.chat)
        if not bots:
            return await utils.answer(message, self.strings["no_bots_in_chat"])
        await utils.answer(
            message,
            self.strings["bot_list"].format(
                count=len(bots),
                bots="\n".join(
                    [
                        f"<emoji document_id=5774022692642492953>✅</emoji> <a href='tg://user?id={bot.id}'>{bot.first_name}</a> [<code>{bot.id}</code>]"
                        for bot in bots
                    ]
                ),
            ),
        )

    @loader.command(ru_doc="Показывает простых участников чата/канала")
    @loader.tag("no_pm")
    async def users(self, message):
        """Shows the users in the chat/channel"""
        users = await self.xdlib.chat.get_members(message.chat)
        if not users:
            return await utils.answer(message, self.strings["no_user_in_chat"])
        await utils.answer(
            message,
            self.strings["user_list"].format(
                count=len(users),
                users="\n".join(
                    [
                        f"<emoji document_id=5774022692642492953>✅</emoji> <a href='tg://user?id={user.id}'>{user.first_name}</a> [<code>{user.id}</code>]"
                        for user in users
                    ]
                ),
            ),
        )

    @loader.command(ru_doc="[-u] [-t] [-r] Забанить участника")
    @loader.tag("no_pm")
    async def ban(self, message):
        """[-u] [-t] [-r] Ban a participant temporarily or permanently"""
        opts = self.xdlib.parse.opts(utils.get_args(message))
        reason = opts.get("r")
        reply = await message.get_reply_message()
        user = opts.get("u") or (reply.sender_id if reply else None)
        user = await self._client.get_entity(user) if user else None
        strings = []
        if not user:
            return await utils.answer(message, self.strings["no_user"])

        seconds = self.xdlib.parse.time(opts.get("t")) if opts.get("t") else None
        until_date = (
            (datetime.now(timezone.utc) + timedelta(seconds=seconds))
            if seconds
            else None
        )
        time_info = f" {self.xdlib.format.time(seconds)}" if seconds else None
        try:
            await self._client.edit_permissions(
                message.chat,
                user,
                until_date=until_date,
                view_messages=False,
            )
        except Exception as e:
            logger.error(str(e))
            return await utils.answer(message, self.strings["error"])
        strings.append(
            self.strings["user_is_banned"].format(
                id=user.id,
                name=(
                    getattr(user, "first_name")
                    if hasattr(user, "first_name")
                    else getattr(user, "title")
                ),
                time_info=time_info or self.strings["forever"],
            )
        )

        if reason:
            strings.append(self.strings["reason"].format(reason=reason))
        return await utils.answer(message, "\n".join(strings))

    @loader.command(ru_doc="Разбанить пользователя")
    @loader.tag("no_pm")
    async def unban(self, message):
        """[-u] Unban a user"""
        opts = self.xdlib.parse.opts(utils.get_args(message))
        reply = await message.get_reply_message()
        user = opts.get("u") or (reply.sender_id if reply else None)
        user = await self._client.get_entity(user) if user else None
        if not user:
            return await utils.answer(message, self.strings["no_user"])
        try:
            await self._client.edit_permissions(message.chat, user, view_messages=True)
        except Exception as e:
            logger.error(str(e))
            return await utils.answer(message, self.strings["error"])
        return await utils.answer(
            message,
            self.strings["user_is_unbanned"].format(
                id=user.id,
                name=(
                    getattr(user, "first_name")
                    if hasattr(user, "first_name")
                    else getattr(user, "title")
                ),
            ),
        )

    @loader.command(ru_doc="[-u] [-r] Кикнуть участника")
    @loader.tag("no_pm")
    async def kick(self, message):
        """[-u] [-r] Kick a participant"""
        opts = self.xdlib.parse.opts(utils.get_args(message))
        reason = opts.get("r")
        reply = await message.get_reply_message()
        user = opts.get("u") or (reply.sender_id if reply else None)
        user = await self._client.get_entity(user) if user else None
        strings = []
        if not user:
            return await utils.answer(message, self.strings["no_user"])
        try:
            await self._client.kick_participant(message.chat, user)
        except Exception as e:
            logging.error(str(e))
            return await utils.answer(message, self.strings["error"])
        strings.append(
            self.strings["user_is_kicked"].format(
                id=user.id,
                name=(
                    getattr(user, "first_name")
                    if hasattr(user, "first_name")
                    else getattr(user, "title")
                ),
            )
        )
        if reason:
            strings.append(self.strings["reason"].format(reason=reason))
        return await utils.answer(message, "\n".join(strings))

    @loader.command(ru_doc="[-u] [-t] [-r] Замутить участника")
    @loader.tag("no_pm")
    async def mute(self, message):
        """[-u] [-t] [-r] Mute a participant temporarily or permanently"""
        opts = self.xdlib.parse.opts(utils.get_args(message))
        reason = opts.get("r")
        reply = await message.get_reply_message()
        user = opts.get("u") or (reply.sender_id if reply else None)
        user = await self._client.get_entity(user) if user else None
        strings = []
        if not user:
            return await utils.answer(message, self.strings["no_user"])

        seconds = self.xdlib.parse.time(opts.get("t")) if opts.get("t") else None
        until_date = (
            (datetime.now(timezone.utc) + timedelta(seconds=seconds))
            if seconds
            else None
        )
        time_info = f" {self.xdlib.format.time(seconds)}" if seconds else None
        try:
            await self._client.edit_permissions(
                message.chat,
                user,
                until_date=until_date,
                send_messages=False,
            )
        except Exception as e:
            logger.error(str(e))
            return await utils.answer(message, self.strings["error"])
        strings.append(
            self.strings["user_is_muted"].format(
                id=user.id,
                name=(
                    getattr(user, "first_name")
                    if hasattr(user, "first_name")
                    else getattr(user, "title")
                ),
                time_info=time_info or self.strings["forever"],
            )
        )

        if reason:
            strings.append(self.strings["reason"].format(reason=reason))
        return await utils.answer(message, "\n".join(strings))

    @loader.command(ru_doc="Размутить участника")
    @loader.tag("no_pm")
    async def unmute(self, message):
        """Unmute a participant"""
        opts = self.xdlib.parse.opts(utils.get_args(message))
        reply = await message.get_reply_message()
        user = opts.get("u") or (reply.sender_id if reply else None)
        user = await self._client.get_entity(user) if user else None
        if not user:
            return await utils.answer(message, self.strings["no_user"])
        try:
            await self._client.edit_permissions(message.chat, user, send_messages=True)
        except Exception as e:
            logger.error(str(e))
            return await utils.answer(message, self.strings["error"])
        return await utils.answer(
            message,
            self.strings["user_is_unmuted"].format(
                id=user.id,
                name=(
                    getattr(user, "first_name")
                    if hasattr(user, "first_name")
                    else getattr(user, "title")
                ),
            ),
        )

    @loader.command(
        ru_doc="[-g|--group name] [-c|--channel name] - Создать группу/канал"
    )
    async def create(self, message):
        """[-g|--group name] [-c|--channel name] - Create group/channel"""
        opts = self.xdlib.parse.opts(utils.get_args(message))
        group_name = opts.get("g") or opts.get("group")
        channel_name = opts.get("c") or opts.get("channel")
        if channel_name:
            result = await self._client(
                channels.CreateChannelRequest(
                    title=channel_name, broadcast=True, about=""
                )
            )
            chat = await self.xdlib.chat.get_info(result.chats[0])
            return await utils.answer(
                message,
                self.strings["channel_created"].format(
                    link=chat.get("link"), title=channel_name
                ),
            )
        if group_name:
            result = await self._client(
                channels.CreateChannelRequest(
                    title=group_name, megagroup=True, about=""
                )
            )
            chat = await self.xdlib.chat.get_info(result.chats[0])
            return await utils.answer(
                message,
                self.strings["group_created"].format(
                    link=chat.get("link"), title=group_name
                ),
            )
        return await utils.answer(message, self.strings["invalid_args"])

    @loader.command(
        ru_doc="Отключает звук и архивирует чат",
    )
    async def dnd(self, message):
        """Mutes and archives the current chat"""
        dnd = await utils.dnd(self._client, await message.get_chat())
        if dnd:
            return await utils.answer(message, self.strings["dnd"])
        else:
            return await utils.answer(message, self.strings["dnd_failed"])

    @loader.command(
        ru_doc="-u username/id - Пригласить пользователя в чат (-b пригласить инлайн бота)"
    )
    async def invite(self, message):
        """-u username/id - Invite a user to the chat (use -b to invite the inline bot)"""
        args = utils.get_args(message)
        opts = self.xdlib.parse.opts(args)
        if opts.get("b") or opts.get("bot"):
            invited = await self.xdlib.chat.invite_bot(self._client, message.chat)
            entity = await self._client.get_entity(self.inline.bot_id)
            if invited:
                return await utils.answer(
                    message,
                    self.strings["user_invited"].format(
                        user=entity.first_name, id=entity.id
                    ),
                )
            return await utils.answer(message, self.strings["user_not_invited"])
        reply = await message.get_reply_message()
        user = opts.get("u") or opts.get("user") or (reply.sender_id if reply else None)
        if not user:
            return await utils.answer(message, self.strings["no_user"])
        entity = await self._client.get_entity(user)
        invited = await self.xdlib.chat.invite_user(message.chat, user)
        if invited:
            return await utils.answer(
                message,
                self.strings["user_invited"].format(
                    user=entity.first_name, id=entity.id
                ),
            )
        return await utils.answer(message, self.strings["user_not_invited"])

    @loader.command(ru_doc="[-i] Получить информацию о сущности")
    async def inspect(self, message):
        """[-i] Get the info about the entity"""
        opts = self.xdlib.parse.opts(utils.get_args(message))
        reply = await message.get_reply_message()
        target = (
            opts.get("i")
            or (reply.sender if reply else await message.get_chat())
            or None
        )
        if not target:
            return await utils.answer(message, self.strings["no_user"])
        ent = await self._client.get_entity(target)
        if isinstance(ent, types.Channel):
            try:
                chatinfo = await self.xdlib.chat.get_info(ent)
                photo = chatinfo.get("chat_photo")
                photo = photo if not isinstance(photo, types.PhotoEmpty) else None
                return await utils.answer(
                    message,
                    self.strings["chatinfo"].format(
                        id=chatinfo.get("id"),
                        title=chatinfo.get("title"),
                        about=chatinfo.get("about") or self.strings["no"],
                        admins_count=chatinfo.get("admins_count"),
                        online_count=chatinfo.get("online_count"),
                        participants_count=chatinfo.get("participants_count"),
                        kicked_count=chatinfo.get("kicked_count"),
                        slowmode_seconds=(
                            self.xdlib.format.time(chatinfo.get("slowmode_seconds"))
                            if chatinfo.get("slowmode_seconds")
                            else self.strings["no"]
                        ),
                        call=(
                            self.strings["yes"]
                            if chatinfo.get("call")
                            else self.strings["no"]
                        ),
                        ttl_period=(
                            self.xdlib.format.time(chatinfo.get("ttl_period"))
                            if chatinfo.get("ttl_period")
                            else self.strings["no"]
                        ),
                        requests_pending=chatinfo.get("requests_pending"),
                        recent_requesters=", ".join(
                            [
                                f"<code>{user}</code>"
                                for user in chatinfo.get("recent_requesters")
                            ]
                        )
                        or self.strings["no"],
                        linked_chat_id=chatinfo.get("linked_chat_id")
                        or self.strings["no"],
                        antispam=(
                            self.strings["yes"]
                            if chatinfo.get("antispam")
                            else self.strings["no"]
                        ),
                        participants_hidden=(
                            self.strings["yes"]
                            if chatinfo.get("participants_hidden")
                            else self.strings["no"]
                        ),
                        link=chatinfo.get("link") or self.strings["no"],
                        is_forum=(
                            self.strings["yes"]
                            if chatinfo.get("is_forum")
                            else self.strings["no"]
                        ),
                        type_of=(
                            self.strings["type_group"]
                            if chatinfo.get("is_group")
                            else (
                                self.strings["type_channel"]
                                if chatinfo.get("is_channel")
                                else self.strings["type_unknown"]
                            )
                        ),
                    ),
                    file=(
                        types.InputMediaPhoto(
                            types.InputPhoto(
                                photo.id, photo.access_hash, photo.file_reference
                            )
                        )
                        if photo
                        else None
                    ),
                )
            except Exception as e:
                logger.error(str(e))
                return await utils.answer(message, self.strings["error"])
        if isinstance(ent, types.User):
            try:
                userinfo = await self.xdlib.user.get_info(ent)
                photo = userinfo.get("profile_photo")
                working_hours = (
                    userinfo.get("business_work_hours").weekly_open
                    if userinfo.get("business_work_hours")
                    else 0
                )
                weekdays = [
                    self.strings["monday"],
                    self.strings["tuesday"],
                    self.strings["wednesday"],
                    self.strings["thursday"],
                    self.strings["friday"],
                    self.strings["saturday"],
                    self.strings["sunday"],
                ]
                personal_channel = userinfo.get("personal_channel")
                working_hours_output = []
                if working_hours:
                    for item in working_hours:
                        day_index = item.start_minute // (24 * 60)
                        day = weekdays[day_index]

                        start = self.xdlib.parse.minutes_to_hhmm(item.start_minute)
                        end = self.xdlib.parse.minutes_to_hhmm(item.end_minute)
                        working_hours_output.append(f"<b>{day}: {start} - {end}</b>")
                return await utils.answer(
                    message,
                    self.strings["userinfo"].format(
                        common_chats_count=userinfo.get("common_chats_count") or 0,
                        phone=userinfo.get("phone") or self.strings["no"],
                        common_chats=(
                            ", ".join(
                                [
                                    f"<a href='{(await self.xdlib.chat.get_info(channel)).get('link')}'>{channel.title}</a>"
                                    for channel in userinfo.get("common_chats")
                                ]
                            )
                            if userinfo.get("common_chats")
                            else self.strings["no"]
                        ),
                        user_id=userinfo.get("id", 0),
                        first_name=userinfo.get("first_name") or self.strings["no"],
                        last_name=userinfo.get("last_name") or self.strings["no"],
                        about=userinfo.get("about") or self.strings["no"],
                        emoji_status=(
                            f"<emoji document_id={userinfo.get('emoji_status')}>🌙</emoji>"
                            if userinfo.get("emoji_status")
                            else self.strings["no"]
                        ),
                        business_work_hours=", ".join(working_hours_output)
                        or self.strings["no"],
                        birthday=(
                            f"{userinfo.get('birthday').day or ''}."
                            f"{userinfo.get('birthday').month or ''}."
                            f"{userinfo.get('birthday').year or ''}"
                            if userinfo.get("birthday")
                            else self.strings["no"]
                        ),
                        stargifts_count=userinfo.get("stargifts_count")
                        or self.strings["no"],
                        usernames=(
                            ", ".join(
                                [
                                    f"@{username}"
                                    for username in userinfo.get("usernames")
                                ]
                            )
                            if userinfo.get("usernames")
                            else self.strings["no"]
                        ),
                        personal_channel=(
                            f"<a href='{(await self.xdlib.chat.get_info(personal_channel)).get('link')}'>"
                            f"{personal_channel.title}</a>"
                            if personal_channel
                            else self.strings["no"]
                        ),
                    ),
                    file=(
                        types.InputMediaPhoto(
                            types.InputPhoto(
                                photo.id, photo.access_hash, photo.file_reference
                            )
                        )
                        if photo
                        else None
                    ),
                )
            except Exception as e:
                logger.error(e)
                return await utils.answer(message, self.strings["error"])

    @loader.command(ru_doc="[-a] [-d] Управлять заявками на вступление")
    @loader.tag("no_pm")
    async def requests(self, message):
        """[-a] [-d] Manage join requests"""
        opts = self.xdlib.parse.opts(utils.get_args(message))
        approve_list = [x for x in str(opts.get("a", "")).split(",") if x]
        dismiss_list = [x for x in str(opts.get("d", "")).split(",") if x]
        sanitized_approve_list = [int(x) if x.isdigit() else x for x in approve_list]
        sanitized_dismiss_list = [int(x) if x.isdigit() else x for x in approve_list]
        all_list = sanitized_approve_list + sanitized_dismiss_list
        all_targets = [
            await self._client.get_entity(
                int(ent.strip()) if ent.strip().isdigit() else ent.strip()
            )
            for ent in all_list
        ]
        for approve in approve_list:
            if approve.isdigit():
                await self.xdlib.chat.join_request(message.chat, int(approve), True)
            else:
                await self.xdlib.chat.join_request(message.chat, approve, True)
        for dismiss in dismiss_list:
            if dismiss.isdigit():
                await self.xdlib.chat.join_request(message.chat, int(dismiss), False)
            else:
                await self.xdlib.chat.join_request(message.chat, dismiss, False)
        return await utils.answer(
            message,
            self.strings["requests_checked"].format(
                entities=", ".join(
                    ent.first_name
                    or getattr(ent, "username", None)
                    or str(getattr(ent, "id", "unknown"))
                    for ent in all_targets
                )
            ),
        )

    @loader.command(ru_doc="Получить все свои чаты/каналы")
    async def owns(self, message):
        """Get all your chats/channels"""
        owns = await self.xdlib.dialog.get_owns(self._client)
        return await utils.answer(
            message,
            self.strings["owns"].format(
                num=len(owns),
                owns="\n".join(
                    [
                        f"<emoji document_id=5458833171846029357>✅</emoji> {own.title} [<code>{str(own.id).replace('-100', '')}</code>]"
                        for own in owns
                    ]
                ),
            ),
        )

    @loader.command(ru_doc="[-r] [-u] [-f] - Выдать админку участнику")
    @loader.tag("no_pm")
    async def promote(self, message):
        """[-r] [-u] [-f] - Promote a participant"""
        reply = await message.get_reply_message()
        opts = self.xdlib.parse.opts(utils.get_args(message))
        user = opts.get("u") or getattr(reply, "sender_id") or None
        if not user:
            return await utils.answer(message, self.strings["no_user"])
        user = await self._client.get_entity(user)
        rank = (opts.get("r")) or "XD Admin"
        chat = await message.get_chat()
        rights = await self.xdlib.chat.get_rights(message.chat, user)
        if (
            not chat.admin_rights
            or not getattr(chat.admin_rights, "add_admins")
            or (
                getattr(rights.participant, "promoted_by", self.tg_id) != self.tg_id
                and not getattr(chat, "creator", False)
            )
        ):
            return await utils.answer(message, self.strings["no_rights"])
        full = opts.get("f")
        if full:
            my_rights = [
                r for r, y in chat.admin_rights.to_dict().items() if y and r != "_"
            ]
            perms = self.xdlib.admin_rights(0)
            perms = perms.add(*my_rights)
            await self.xdlib.admin.set_rights(chat, user, perms.to_int(), rank)
            return await utils.answer(
                message,
                self.strings["promoted"].format(
                    id=user.id,
                    name=user.first_name
                    if hasattr(user, "first_name")
                    else user.title
                    if hasattr(user, "title")
                    else "None",
                    rights=self.strings["full_rights"],
                ),
            )
        mask = (
            self.xdlib.admin_rights.to_mask(rights.participant.admin_rights)
            if hasattr(rights.participant, "admin_rights")
            else 0
        )

        await utils.answer(
            message,
            self.strings["promote"].format(
                id=user.id,
                name=user.first_name
                if hasattr(user, "first_name")
                else user.title
                if hasattr(user, "title")
                else "None",
                rank=rank,
            ),
            reply_markup=await self.build_markup(user.id, chat.id, mask, rank),
        )

    @loader.command(ru_doc="[-t] [-u] - Ограничить участника")
    @loader.tag("no_pm")
    async def restrict(self, message):
        """[-t] [-u] - Restrict a participant"""
        reply = await message.get_reply_message()
        opts = self.xdlib.parse.opts(utils.get_args(message))

        user = opts.get("u") or getattr(reply, "sender_id") or None
        if not user:
            return await utils.answer(message, self.strings["no_user"])

        user = await self._client.get_entity(user)
        chat = await message.get_chat()

        if not chat.admin_rights or not getattr(chat.admin_rights, "ban_users"):
            return await utils.answer(message, self.strings["no_rights"])
        duration = opts.get("t", None)
        if duration:
            duration = self.xdlib.format.time(self.xdlib.parse.time(duration))

        rights = await self.xdlib.chat.get_rights(chat, user)
        mask = (
            self.xdlib.banned_rights.MAX_MASK
            - self.xdlib.banned_rights.to_mask(rights.participant.banned_rights)
            if hasattr(rights.participant, "banned_rights")
            else 0
        )
        rank = "-"

        await utils.answer(
            message,
            self.strings["restrict"].format(
                id=user.id,
                name=user.first_name
                if hasattr(user, "first_name")
                else user.title
                if hasattr(user, "title")
                else "None",
                time=f" {duration}" if duration else self.strings["forever"],
            ),
            reply_markup=await self.build_markup(
                user.id,
                chat.id,
                mask,
                rank,
                mode="restrict",
                duration=f" {duration}" if duration else None,
            ),
        )

    async def build_markup(
        self,
        user_id: int,
        chat_id: int,
        mask: int,
        rank: str,
        duration: typing.Optional[int] = None,
        mode="admin",
    ):
        rights_cls = (
            self.xdlib.admin_rights if mode == "admin" else self.xdlib.banned_rights
        )
        rights_names = rights_cls.RIGHTS_LIST
        rights = rights_cls(mask)
        chat = await self._client.get_entity(chat_id)

        markup = utils.chunks(
            [
                {
                    "text": f"{'🟢' if rights.has_index(idx) else '🔴'} {self.strings[name]}",
                    "callback": self._toggle_right,
                    "args": (user_id, chat_id, mask, idx, rank, mode, duration),
                }
                for idx, name in enumerate(rights_names)
                if (
                    name != "until_date"
                    and not (
                        getattr(chat.default_banned_rights, name, True)
                        if mode != "admin"
                        else False
                    )
                )
            ],
            2,
        )

        markup.append(
            [
                {
                    "text": self.strings["apply"],
                    "callback": self._apply_rights,
                    "args": (user_id, chat_id, mask, rank, mode, duration),
                }
            ]
        )

        markup.append([{"text": self.strings["close"], "action": "close"}])
        return markup

    async def _toggle_right(
        self,
        call,
        user_id: int,
        chat_id: int,
        mask: int,
        idx: int,
        rank: str,
        mode: str,
        duration: str,
    ):
        new_mask = mask ^ (1 << idx)

        new_markup = await self.build_markup(
            user_id, chat_id, new_mask, rank, mode=mode, duration=duration
        )

        user = await self._client.get_entity(user_id)

        title = self.strings["promote"] if mode == "admin" else self.strings["restrict"]

        await utils.answer(
            call,
            title.format(
                id=user_id,
                name=user.first_name
                if hasattr(user, "first_name")
                else user.title
                if hasattr(user, "title")
                else "None",
                rank=rank,
                time=f" {duration}" if duration else self.strings["forever"],
            ),
            reply_markup=new_markup,
        )

    async def _apply_rights(
        self,
        call,
        user_id: int,
        chat_id: int,
        mask: int,
        rank: str,
        mode: str,
        duration: typing.Optional[str] = None,
    ):
        user = await self._client.get_entity(user_id)
        chat = await self._client.get_entity(chat_id)

        if mode == "admin":
            ok = await self.xdlib.admin.set_rights(chat, user, mask, rank)
            rights_items = self.xdlib.admin_rights(mask).to_dict()
        else:
            ok = await self.xdlib.chat.set_restrictions(
                chat, user, mask, duration=duration
            )
            rights_items = self.xdlib.banned_rights(mask).to_dict()

        rights_list = [r for r, v in rights_items.items() if v]

        if ok:
            text = (
                self.strings["promoted"]
                if mode == "admin" and mask
                else self.strings["demoted"]
                if mode == "admin" and not mask
                else self.strings["restricted"]
            )

            await utils.answer(
                call,
                text.format(
                    id=user_id,
                    name=user.first_name
                    if hasattr(user, "first_name")
                    else user.title
                    if hasattr(user, "title")
                    else "None",
                    rights=", ".join([self.strings[r] for r in rights_list])
                    if rights_list
                    else self.strings["no"],
                    duration=f" {duration}" if duration else self.strings["forever"],
                    time=f" {duration}" if duration else self.strings["forever"],
                ),
                reply_markup=[[{"text": self.strings["close"], "action": "close"}]],
            )
        else:
            await utils.answer(
                call,
                self.strings["error"],
                reply_markup=[[{"text": self.strings["close"], "action": "close"}]],
            )