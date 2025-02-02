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
# Commands: purgetime, purgelength, purgekeyword, purge
# scope: hikka_only
# meta developer: @codrago_m
# meta banner: https://mods.codrago.top/banners/DelMessTools.png
# meta pic: https://0x0.st/s/JjNl2wBorRA1dLagHgUBvQ/8KK5.webp
# ---------------------------------------------------------------------------------

__version__ = (1, 0, 0)

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
        "purge_type_complete": "Messages of the specified type have been deleted."
    }

    strings_ru = {
    "purge_complete": "Все ваши сообщения были удалены.",
    "purge_reply_complete": "Сообщения до указанного ответа были удалены.",
    "purge_keyword_complete": "Сообщения, содержащие ключевое слово, были удалены.",
    "purge_time_complete": "Сообщения в указанном временном диапазоне были удалены.",
    "purge_media_complete": "Все ваши медиа-сообщения были удалены.",
    "purge_length_complete": "Сообщения указанной длины были удалены.",
    "purge_type_complete": "Сообщения указанного типа были удалены."
    }


    async def purgecmd(self, message: Message):
        """ [reply] [-img] [-voice] [-file] - delete all your messages in current chat or only ones up to the message you replied to"""
        reply = await message.get_reply_message()
        is_last = False
        types_filter = self.get_types_filter(message)

        async for i in self.client.iter_messages(message.peer_id):
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
        """ <keyword> [-img] [-voice] [-file] - delete all your messages containing the specified keyword in the current chat"""
        args = utils.get_args_raw(message)
        if not args:
            return await utils.answer(message, "Please specify a keyword to delete messages.")
        
        types_filter = self.get_types_filter(message)

        async for i in self.client.iter_messages(message.peer_id):
            if i.from_id == self.tg_id and args.lower() in (i.text or '').lower() and self.is_valid_type(i, types_filter):
                await message.client.delete_messages(message.chat.id, [i.id])

        await utils.answer(message, self.strings["purge_keyword_complete"])

    async def purgetimecmd(self, message: Message):
        """ <start_time> <end_time> [-img] [-voice] [-file] - delete all your messages within the specified time range in the current chat
        Time format: YYYY-MM-DD HH:MM:SS
        """
        args = utils.get_args_raw(message).split('/')
        if len(args) != 2:
            return await utils.answer(message, "Please specify the start and end time in the format: YYYY-MM-DD HH:MM:SS")

        from datetime import datetime

        try:
            start_time = datetime.strptime(args[0], "%Y-%m-%d %H:%M:%S")
            end_time = datetime.strptime(args[1], "%Y-%m-%d %H:%M:%S")
        except ValueError:
            return await utils.answer(message, "Invalid time format. Please use the format: YYYY-MM-DD HH:MM:SS")

        types_filter = self.get_types_filter(message)

        async for i in self.client.iter_messages(message.peer_id):
            if i.from_id == self.tg_id and start_time <= i.date <= end_time and self.is_valid_type(i, types_filter):
                await message.client.delete_messages(message.peer_id, [i.id])

        await utils.answer(message, self.strings["purge_time_complete"])

    async def purgelengthcmd(self, message: Message):
        """ <length> [-img] [-voice] [-file] - delete all your messages with the specified length in the current chat"""
        args = utils.get_args_raw(message)
        if not args.isdigit():
            return await utils.answer(message, "Please specify a valid length.")

        length = int(args)
        types_filter = self.get_types_filter(message)

        async for i in self.client.iter_messages(message.peer_id):
            if i.from_id == self.tg_id and len(i.text or '') == length and self.is_valid_type(i, types_filter):
                await message.client.delete_messages(message.peer_id, [i.id])

        await utils.answer(message, self.strings["purge_length_complete"])

    def get_types_filter(self, message: Message):
        """ Get the types filter from the command arguments. """
        types_filter = []
        args = utils.get_args_raw(message).split()
        
        if "-img" in args:
            types_filter.append("img")
        if "-voice" in args:
            types_filter.append("voice")
        if "-file" in args:
            types_filter.append("file")
        
        return types_filter

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