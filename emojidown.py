# ---------------------------------------------------------------------------------
#░█▀▄░▄▀▀▄░█▀▄░█▀▀▄░█▀▀▄░█▀▀▀░▄▀▀▄░░░█▀▄▀█
#░█░░░█░░█░█░█░█▄▄▀░█▄▄█░█░▀▄░█░░█░░░█░▀░█
#░▀▀▀░░▀▀░░▀▀░░▀░▀▀░▀░░▀░▀▀▀▀░░▀▀░░░░▀░░▒▀
# Name: EmojiDownloader
# Description: Download emoji from reply
# Author: @codrago_m
# ---------------------------------------------------------------------------------
# 🔒    Licensed under the GNU AGPLv3
# 🌐 https://www.gnu.org/licenses/agpl-3.0.html
# ---------------------------------------------------------------------------------
# Author: @codrago
# Commands: emojidown
# scope: hikka_only
# meta developer: @codrago_m
# ---------------------------------------------------------------------------------

__version__ = (1, 0, 0)
from .. import loader, utils
from telethon.tl.types import Message  # type: ignore


@loader.tds
class EmojiDownloadMod(loader.Module):
    """Download emoji from reply"""

    strings = {
        "name": "EmojiDownload",
    }

    def __init__(self):
        self.bot = "@emojidownloadbot"

    async def on_dlmod(self):
        await utils.dnd(self._client, self.bot, True)

    async def emojidowncmd(self, message: Message):
        """[reply] | Download emoji from reply"""
        reply = await message.get_reply_message()
        if not getattr(reply, "id", None):
            await utils.answer(message, "<emoji document_id=5328145443106873128>✖️</emoji> Where is reply for your emoji?")
        if self.client.hikka_me.premium == False:
            await utils.answer(message, "<emoji document_id=5328145443106873128>✖️</emoji> Sorry, but module only for premium users")
            return

        try:
            async with self._client.conversation(self.bot) as conv:
                reply = await message.get_reply_message()
                await conv.send_message(reply)
                emoji = await conv.get_response()
                await conv.mark_read()
                await message.delete()
                await utils.answer(message, emoji)
        except ValueError:
            await utils.answer(message, "<emoji document_id=5328145443106873128>✖️</emoji> Where is reply for your emoji?")