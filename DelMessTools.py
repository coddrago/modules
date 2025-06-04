# ---------------------------------------------------------------------------------
#░█▀▄░▄▀▀▄░█▀▄░█▀▀▄░█▀▀▄░█▀▀▀░▄▀▀▄░░░█▀▄▀█
#░█░░░█░░█░█░█░█▄▄▀░█▄▄█░█░▀▄░█░░█░░░█░▀░█
#░▀▀▀░░▀▀░░▀▀░░▀░▀▀░▀░░▀░▀▀▀▀░░▀▀░░░░▀░░▒▀
# Name: DelMessTools
# Description: Module to manage and delete your messages in the current chat
# Author: @codrago_m
# ---------------------------------------------------------------------------------
# 🔒    Licensed under the GNU AGPLv3
# 🌐 https://www.gnu.org/licenses/agpl-3.0.html
# ---------------------------------------------------------------------------------
# Author: @codrago
# Commands: nopurge, purgetime, purgelength, purgekeyword, purge
# scope: hikka_only
# meta developer: @codrago_m
# meta banner: https://raw.githubusercontent.com/coddrago/modules/refs/heads/main/banner.png
# meta pic: https://envs.sh/HJx.webp
# ---------------------------------------------------------------------------------

__version__ = (1, 1, 0)

from hikkatl.tl.types import Message, DocumentAttributeFilename

from .. import loader, utils

class DelMessTools(loader.Module):
    """Module to manage and delete your messages in the current chat"""

    strings = {
        "name": "DelMessTools",
        "purge_complete": "All your messages have been deleted.",
        "purge_reply_complete": "Messages up to the replied message have been deleted.",
        "purge_keyword_complete": "Messages containing the keyword have been deleted.",
        "purge_time_complete": "Messages within the specified time range have been deleted.",
        "purge_media_complete": "All your media messages have been deleted.",
        "purge_length_complete": "Messages with the specified length have been deleted.",
        "purge_type_complete": "Messages of the specified type have been deleted.",
        "enabled": "It's not operational now anyway.",
        "disabled": "Operation status changed to disabled.",
        "interrupted": "The deletion was interrupted because you changed your mind.",
        "none": "You didn't even intend to delete anything here, but anyway it's disabled now."
    }

    strings_ru = {
        "purge_complete": "Все ваши сообщения были удалены.",
        "purge_reply_complete": "Сообщения до указанного ответа были удалены.",
        "purge_keyword_complete": "Сообщения, содержащие ключевое слово, были удалены.",
        "purge_time_complete": "Сообщения в указанном временном диапазоне были удалены.",
        "purge_media_complete": "Все ваши медиа-сообщения были удалены.",
        "purge_length_complete": "Сообщения указанной длины были удалены.",
        "purge_type_complete": "Сообщения указанного типа были удалены.",
        "enabled": "Оно итак сейчас не работает.",
        "disabled": "Режим работы изменен на выключено.",
        "interrupted": "Удаление было прервано т.к вы передумали.",
        "none": "Вы даже не пытались ничего здесь удалить, в любом случае сейчас оно выключено."
    }


    async def purgecmd(self, message: Message):
        """ [reply] [-img] [-voice] [-file] [-all] - delete all your messages in current chat or only ones up to the message you replied to
        -all - to delete messages in each topic if this is a forum otherwise the flag'll just be ingored
        """
        reply = await message.get_reply_message()
        is_last = False
        args, types_filter, is_each = self.get_types_filter(message)
        is_forum = (await self.client.get_entity(message.chat.id)).forum

        status = self.db.get(__name__, "status", {})
        status[message.chat.id] = True
        self.db.set(__name__, "status", status)

        async for i in self.client.iter_messages(message.peer_id):
            status = self.db.get(__name__, "status", {})
            if status.get(message.chat.id, None) is not True:
                return await utils.answer(message, self.strings["interrupted"])

            if is_forum and not is_each and utils.get_topic(message) != utils.get_topic(i):
                continue

            if i.from_id == self.tg_id and self.is_valid_type(i, types_filter):
                if reply:
                    if is_last:
                        break
                    if i.id == reply.id:
                        is_last = True
                await message.client.delete_messages(message.peer_id, [i.id])

        if reply:
            await utils.answer(message, self.strings["purge_reply_complete"])
        else:
            await utils.answer(message, self.strings["purge_complete"])

    async def purgekeywordcmd(self, message: Message):
        """ <keyword> [-img] [-voice] [-file] [-all] - delete all your messages containing the specified keyword in the current chat
        -all - to delete messages in each topic if this is a forum otherwise the flag'll just be ingored
        """
        args = utils.get_args_raw(message)
        if not args:
            return await utils.answer(message, "Please specify anything because you didn't.")

        args, types_filter, is_each = self.get_types_filter(message)
        if not args:
            return await utils.answer(message, "Please specify a keyword to delete messages.")

        is_forum = (await self.client.get_entity(message.chat.id)).forum

        status = self.db.get(__name__, "status", {})
        status[message.chat.id] = True
        self.db.set(__name__, "status", status)

        async for i in self.client.iter_messages(message.peer_id):
            status = self.db.get(__name__, "status", {})
            if status.get(message.chat.id, None) is not True:
                return await utils.answer(message, self.strings["interrupted"])

            if is_forum and not is_each and utils.get_topic(message) != utils.get_topic(i):
                continue

            if i.from_id == self.tg_id and args.lower() in (i.text or '').lower() and self.is_valid_type(i, types_filter):
                await message.client.delete_messages(message.chat.id, [i.id])

        await utils.answer(message, self.strings["purge_keyword_complete"])

    async def purgetimecmd(self, message: Message):
        """ <start_time> <end_time> [-img] [-voice] [-file] [-all] - delete all your messages within the specified time range in the current chat
        -all - to delete messages in each topic if this is a forum otherwise the flag'll just be ingored
        Time format: YYYY-MM-DD HH:MM:SS
        """
        args = utils.get_args_raw(message)
        if not args:
            return await utils.answer(message, "Please specify anything because you didn't.")

        args, types_filter, is_each = self.get_types_filter(message)
        args = args.split()

        if not args or len(args) < 2:
            return await utils.answer(message, "Please specify the start and end time in the format: YYYY-MM-DD HH:MM:SS")

        from datetime import datetime

        try:
            start_time = datetime.strptime(args[0], "%Y-%m-%d %H:%M:%S")
            end_time = datetime.strptime(args[1], "%Y-%m-%d %H:%M:%S")
        except ValueError:
            return await utils.answer(message, "Invalid time format. Please use the format: YYYY-MM-DD HH:MM:SS")

        is_forum = (await self.client.get_entity(message.chat.id)).forum

        status = self.db.get(__name__, "status", {})
        status[message.chat.id] = True
        self.db.set(__name__, "status", status)

        async for i in self.client.iter_messages(message.peer_id):
            status = self.db.get(__name__, "status", {})
            if status.get(message.chat.id, None) is not True:
                return await utils.answer(message, self.strings["interrupted"])

            if is_forum and not is_each and utils.get_topic(message) != utils.get_topic(i):
                continue

            if i.from_id == self.tg_id and start_time <= i.date <= end_time and self.is_valid_type(i, types_filter):
                await message.client.delete_messages(message.peer_id, [i.id])

        await utils.answer(message, self.strings["purge_time_complete"])

    async def purgelengthcmd(self, message: Message):
        """ <length> [-img] [-voice] [-file] [-all] - delete all your messages with the specified length in the current chat
        -all - to delete messages in each topic if this is a forum otherwise the flag'll just be ingored
        """
        args = utils.get_args_raw(message)
        if not args:
            return await utils.answer(message, "Please specify anything because you didn't.")

        args, types_filter, is_each = self.get_types_filter(message)
        if not args:
            return await utils.answer(message, "Please specify a valid length.")

        length = int(args)
        is_forum = (await self.client.get_entity(message.chat.id)).forum

        status = self.db.get(__name__, "status", {})
        status[message.chat.id] = True
        self.db.set(__name__, "status", status)

        async for i in self.client.iter_messages(message.peer_id):
            status = self.db.get(__name__, "status", {})
            if status.get(message.chat.id, None) is not True:
                return await utils.answer(message, self.strings["interrupted"])

            if is_forum and not is_each and utils.get_topic(message) != utils.get_topic(i):
                continue

            if i.from_id == self.tg_id and len(i.text or '') == length and self.is_valid_type(i, types_filter):
                await message.client.delete_messages(message.peer_id, [i.id])

        await utils.answer(message, self.strings["purge_length_complete"])

    async def nopurgecmd(self, message: Message):
        """
        Interrupt the deletion process
        Use in the chat where you've previously started deletion
        """
        chat_id = utils.get_chat_id(message)
        
        status = self.db.get(__name__, "status", {})
        _status = status.get(chat_id, None)
        status[chat_id] = False
        self.db.set(__name__, "status", status)

        if _status is True:
            await utils.answer(message, self.strings["disabled"])
        elif _status is False:
            await utils.answer(message, self.strings["enabled"])
        else:
            await utils.answer(message, self.strings["none"])


    def get_types_filter(self, message: Message):
        """ Get the types filter from the command arguments."""
        args = utils.get_args_raw(message).split()
        types_filter = []
        valid_types = ["-img", "-voice", "-file", "-all"]
        is_each = "-all" in args

        for i, arg in enumerate(args):
            if arg in valid_types:
                _args = " ".join(args[:i])
                args_ = " ".join(args[i:])
                break
                    
        if "-img" in args_:
            types_filter.append("img")
        if "-voice" in args_:
            types_filter.append("voice")
        if "-file" in args_:
            types_filter.append("file")
        if "-all" in args_:
            is_each = True

        return _args, types_filter, is_each

    def is_valid_type(self, message: Message, types_filter):
        """ Check if the message matches the specified types filter. """
        if not types_filter:
            return True  # No filtering means all types are valid

        if "img" in types_filter and message.photo:
            return True
        if "voice" in types_filter and message.voice:
            return True
        if "file" in types_filter and isinstance(message.document, DocumentAttributeFilename):
            return True

        return False
