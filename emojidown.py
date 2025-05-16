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
# Author: @codrago, @mardaster
# Commands: emojidown
# scope: hikka_only
# meta developer: @codrago_m
# meta banner: https://raw.githubusercontent.com/coddrago/modules/refs/heads/master/banner.png
# meta pic: https://0x0.st/s/xMv47XPyGMimCREVC6vfXA/8KPp.webp
# ---------------------------------------------------------------------------------

__version__ = (1, 0, 0)
from .. import loader, utils
from telethon.tl.types import Message  # type: ignore
import asyncio

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
            return
        if self.client.hikka_me.premium == False:
            await utils.answer(message, "<emoji document_id=5328145443106873128>✖️</emoji> Sorry, but module only for premium users")
            return

        try:
            async with self._client.conversation(self.bot) as conv:
                reply = await message.get_reply_message()
                await conv.send_message(reply)
                emoji = await conv.get_response()
                await conv.mark_read()
                await utils.answer(message, emoji)

            await asyncio.sleep(5)
            await self._client.delete_dialog(5792368019)

        except ValueError:
            await utils.answer(message, "<emoji document_id=5328145443106873128>✖️</emoji> Where is reply for your emoji?")
