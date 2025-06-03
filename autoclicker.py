# ---------------------------------------------------------------------------------
#░█▀▄░▄▀▀▄░█▀▄░█▀▀▄░█▀▀▄░█▀▀▀░▄▀▀▄░░░█▀▄▀█
#░█░░░█░░█░█░█░█▄▄▀░█▄▄█░█░▀▄░█░░█░░░█░▀░█
#░▀▀▀░░▀▀░░▀▀░░▀░▀▀░▀░░▀░▀▀▀▀░░▀▀░░░░▀░░▒▀
# Name: ButtonAutoClicker.
# Description: Click on button!
# Author: @codrago_m, @unneyon :P
# ---------------------------------------------------------------------------------

# 🔒    Licensed under the GNU AGPLv3
# 🌐 https://www.gnu.org/licenses/agpl-3.0.html

# meta developer: @codrago_m, @unneyon_hmods
# meta banner: https://raw.githubusercontent.com/coddrago/modules/refs/heads/master/banner.png
# meta pic: https://envs.sh/HJv.webp
# ---------------------------------------------------------------------------------

from telethon import events
from .. import loader, utils
import asyncio

@loader.tds
class AutoClickerMod(loader.Module):
    """Autoclicker for inline buttons."""

    strings = {
        "name": "AutoClicker",
        "clicker_on": "<b>AutoClicker on!</b>",
        "no_args": "<b>Where arguments and reply?</b>",
        "clicker_off": "<b>AutoClicker off!</b>",
        "no_button": "<b>There are no inline buttons in the message.</b>",
    }


    async def client_ready(self, client, db):
        self._client = client
        self._db = db


    async def clickoncmd(self, message):
        """[interval button_line button] | Enable Autoclicker"""
        if not message.is_reply:
            return await utils.answer(message, self.strings["no_args"])
        args = utils.get_args(message)
        reply = await message.get_reply_message()
        if len(args) < 1:
            return await utils.answer(message, self.strings["no_args"])

        interval = int(args[0]) if args[0].isdigit() else 20
        button_line = 0
        button_item = 0
        if (len(args) >= 2) and args[1].isdigit():
            button_line = int(args[1])
        if (len(args) >= 3) and args[2].isdigit():
            button_item = int(args[2])

        if reply and reply.buttons:
            if len(reply.buttons) < button_line+1:
                button_line = 0
            if len(reply.buttons[button_line]) < button_item+1:
                button_item = 0
        else:
            return await utils.answer(message, self.strings["no_button"])

        self.clicker = True
        await utils.answer(message, self.strings["clicker_on"])

        while self.clicker:
            button = reply.buttons[button_line][button_item]
            await button.click()
            await asyncio.sleep(interval)


    async def clickoffcmd(self, message):
        """| disable autoclicker."""

        self.clicker = False
        await utils.answer(message, self.strings["clicker_off"])