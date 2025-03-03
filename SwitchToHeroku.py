# ---------------------------------------------------------------------------------
#░█▀▄░▄▀▀▄░█▀▄░█▀▀▄░█▀▀▄░█▀▀▀░▄▀▀▄░░░█▀▄▀█
#░█░░░█░░█░█░█░█▄▄▀░█▄▄█░█░▀▄░█░░█░░░█░▀░█
#░▀▀▀░░▀▀░░▀▀░░▀░▀▀░▀░░▀░▀▀▀▀░░▀▀░░░░▀░░▒▀
# Name: switchtoheroku
# Description: Switch your hikka to heroku
# Author: @codrago_m
# ---------------------------------------------------------------------------------
# 🔒    Licensed under the GNU AGPLv3
# 🌐 https://www.gnu.org/licenses/agpl-3.0.html
# ---------------------------------------------------------------------------------
# Author: @codrago
# Commands: switchtoheroku
# meta developer: @codrago_m
# meta_desc: Switch your hikka to heroku
# meta banner: https://mods.codrago.top/banners/banner.png
# meta pic: https://kappa.lol/2Z_Q-
# ---------------------------------------------------------------------------------

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from hikkatl.types import Message
from .. import loader, utils
import asyncio

@loader.tds
class SwitchToHeroku(loader.Module):
    """Auto switching from Hikka to Heroku"""

    strings = {"name": "SwitchToHeroku"}

    async def client_ready(self, client, db):
        self._db = db

        if self.get("done"):
            keyboard = InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text='🥷 Support chat', url='https://t.me/heroku_talks')],[
                InlineKeyboardButton(text='📖 Github', url='https://github.com/coddrago/Heroku')
            ]]
            )
            await self.inline._bot.send_photo(
                self.tg_id, 
                "https://imgur.com/a/AYmh8W8.png",
                caption="<b>Hello, you switched to a Heroku, a Hikka Userbot fork with some improvements.</b>"
                "\nModule for switching is unloaded.",
                reply_markup=keyboard,
            )

            self.set("done", None) # db need to be clear, for case if user backup db and switches once more

            await self.invoke('unloadmod', 'SwitchToHeroku', self.inline.bot_id)

    @loader.command()
    async def switchtoheroku(self, message: Message):
        """ - Automatically switch to heroku"""

        await utils.answer(message, "Compatibility check... Wait")

        if "coddrago" in utils.get_git_info()[1]:
            return await utils.answer(message, "You`re already running fork.")

        await utils.answer(message, "Everything is okay, I started switching...")

        await asyncio.create_subprocess_shell(
            "git remote set-url origin https://github.com/coddrago/Heroku.git",
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=utils.get_base_dir(),
        )

        await asyncio.create_subprocess_shell(
            "git config --global user.email 'you@example.com'",
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=utils.get_base_dir(),
        )

        await asyncio.create_subprocess_shell(
            "git config --global user.name 'Your Name'",
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=utils.get_base_dir(),
        )

        await asyncio.create_subprocess_shell(
            "git pull",
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=utils.get_base_dir(),
        )

        peer_id = self.inline.bot_id

        await self.invoke('fconfig', 'updater GIT_ORIGIN_URL https://github.com/coddrago/Heroku', peer_id)

        await utils.answer(message, "Automatically restarting. (after restart, it's all done)")

        self.set("done", True)

        await self.invoke('update', '-f', peer_id)
