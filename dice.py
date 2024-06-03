# ---------------------------------------------------------------------------------
# Name: ModulesList.
# Description: Channels of modules for userbot Hikka.
# Author: @codrago
# ---------------------------------------------------------------------------------

# 🔒    Licensed under the GNU AGPLv3
# 🌐 https://www.gnu.org/licenses/agpl-3.0.html

# meta developer: @codrago_m
# ---------------------------------------------------------------------------------

from .. import loader, utils
import requests, random

class DiceMod(loader.Module):
    """Развлекательный модуль"""
    strings = {"name": "Dice"}
    async def dicecmd(self, message):
        """Загадать рандомное число от 1 до 6"""
        num = random.randint(1, 6)
        args = utils.get_args_raw(message)
        if not args:
            await utils.answer(message, "Где аргументы?")
            return
        if num == int(args):
            await utils.answer(message, f"Поздравляю! Вы угадали число!\nЧислом было: {num}")
            return
        else:
            await utils.answer(message, f"Вы не угадали число!\nЧислом было: {num}")
            return
