# ---------------------------------------------------------------------------------
#░█▀▄░▄▀▀▄░█▀▄░█▀▀▄░█▀▀▄░█▀▀▀░▄▀▀▄░░░█▀▄▀█
#░█░░░█░░█░█░█░█▄▄▀░█▄▄█░█░▀▄░█░░█░░░█░▀░█
#░▀▀▀░░▀▀░░▀▀░░▀░▀▀░▀░░▀░▀▀▀▀░░▀▀░░░░▀░░▒▀
# Name: ID
# Description: Tool for ID's
# Author: @codrago_m
# ---------------------------------------------------------------------------------
# 🔒    Licensed under the GNU AGPLv3
# 🌐 https://www.gnu.org/licenses/agpl-3.0.html
# ---------------------------------------------------------------------------------
# Author: @codrago
# Commands: id, chatid, userid
# scope: hikka_only
# meta developer: @codrago_m
# ---------------------------------------------------------------------------------

__version__ = (1, 0, 0)

from .. import loader, utils

@loader.tds
class ID(loader.Module):
    """ID of all!"""
    strings = {
    "name": "ID",
    "Error_reply": "<emoji document_id=5328145443106873128>✖️</emoji> <b>Where your reply?</b>",
    "not_chat": "<emoji document_id=5328145443106873128>✖️</emoji> <b>This is not a chat!</b>"
    }

    strings_ru = {
    "Error_reply": "<emoji document_id=5328145443106873128>✖️</emoji> <b>Где твой реплай?</b>",
    "not_chat": "<emoji document_id=5328145443106873128>✖️</emoji> <b>Это не чат!</b>"
}

    
    async def useridcmd(self, message):
        """[reply] | Get User ID"""
        reply = await message.get_reply_message()
        if reply != None:
            await utils.answer(message, f"<emoji document_id=5436024756610546212>⚡</emoji> <b>User ID</b>: <code>{reply.sender_id}</code>")
        else:
            await utils.answer(message, self.strings["Error_reply"])

    async def idcmd(self, message):
        """| Get your ID"""
        await utils.answer(message, f"<emoji document_id=5436024756610546212>⚡</emoji> <b>Your ID</b>: <code>{message.sender_id}</code>")

    async def chatidcmd(self, message):
        """| Get chat ID"""

        await utils.answer(message, f"<emoji document_id=5436024756610546212>⚡</emoji> <b>Chat ID</b>: <code>{message.peer_id.channel_id}</code>")