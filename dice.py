# ---------------------------------------------------------------------------------
#░█▀▄░▄▀▀▄░█▀▄░█▀▀▄░█▀▀▄░█▀▀▀░▄▀▀▄░░░█▀▄▀█
#░█░░░█░░█░█░█░█▄▄▀░█▄▄█░█░▀▄░█░░█░░░█░▀░█
#░▀▀▀░░▀▀░░▀▀░░▀░▀▀░▀░░▀░▀▀▀▀░░▀▀░░░░▀░░▒▀
# Name: RandomNumbers
# Description: 
# Author: @codrago
# ---------------------------------------------------------------------------------

# 🔒    Licensed under the GNU AGPLv3
# 🌐 https://www.gnu.org/licenses/agpl-3.0.html

# meta developer: @codrago_m
# meta banner: https://raw.githubusercontent.com/coddrago/modules/refs/heads/master/banner.png
# meta pic: https://0x0.st/s/4xg5IubxTkikjI6JG2AU8w/8KP_.webp
# ---------------------------------------------------------------------------------

from .. import loader, utils
import requests, random

class RandomNumbersMod(loader.Module):
    """Развлекательный модуль"""

    strings = {"name": "RandomNumbers"}

    def __init__(self):
        self.config = loader.ModuleConfig(
            loader.ConfigValue(
                "min_num",
                1,
                lambda: "минимальное число для рандома",
                validator=loader.validators.Integer(minimum=0),
            ),
        
            loader.ConfigValue(
                "max_num",
                6,
                lambda: "Максимальное число для рандома",
                validator=loader.validators.Integer(minimum=1)
            ),
        )

    async def rnumcmd(self, message):
        """Угадывайте рандомные числа!"""
        min_num = min(self.config["min_num"], self.config["max_num"])
        max_num = max(self.config["min_num"], self.config["max_num"])
        num = random.randint(min_num, max_num)
        args = utils.get_args_raw(message)
        if not args:
            await utils.answer(message, f"Где аргументы?\nВведите число в радуисе {min_num} - {max_num}")
            return
        if min_num >= max_num:
            await utils.answer(message, "Ебанутый, не ломай мне модуль! Сделай минимальное число меньше максимального.")
            return
        if num == int(args):
            await utils.answer(message, f"Поздравляю! Вы угадали число!\nЧислом было: {num}")
            return
        else:
            await utils.answer(message, f"Вы не угадали число!\nЧислом было: {num}")
            return
        

