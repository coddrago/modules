# ---------------------------------------------------------------------------------
# Name: Who you?
# Description: It doesn’t matter who you are, the main thing is... who are you?
# Author: @codrago_m
# ---------------------------------------------------------------------------------

# 🔒    Licensed under the GNU AGPLv3
# 🌐 https://www.gnu.org/licenses/agpl-3.0.html

# meta developer: @codrago_m
# meta banner: https://mods.codrago.top/banners/whoyou.png
# meta pic: https://0x0.st/s/1Ygc1jQQyLJJ2f0Z1vyJ6w/8KPF.webp
# ---------------------------------------------------------------------------------

from telethon import events
from .. import loader, utils

@loader.tds
class WhoYouMod(loader.Module):
    """Who you? Who i'm? Who all in this world?"""

    strings = {
        "name": "WhoYou",
        "Answer": "The response that should cause the module's response to be different from the others.",
        "Question": "Just your question",
        "Answer_a": "Module response to a given response in the config",
        "Answer_b": "Module response to a random or any answer",
    }
    
    strings_ru = {
    "Answer": "Ответ, который должен сделать ответ модуля отличным от других.",
    "Question": "Просто ваш вопрос",
    "Answer_a": "Ответ модуля на заданный ответ в конфиге",
    "Answer_b": "Ответ модуля на случайный или любой ответ",
    }

    
    def __init__(self):
        self.config = loader.ModuleConfig(
            loader.ConfigValue(
                "Answer",
                "Who?",
                lambda: self.strings["Answer"],
            ),
            loader.ConfigValue(
                "Question",
                "Who are you?",
                lambda: self.strings["Question"],
            ),
            loader.ConfigValue(
                "Answer_a",
                None,
                lambda: self.strings["Answer_a"],
            ),
            loader.ConfigValue(
                "Answer_b",
                None,
                lambda: self.strings["Answer_b"],
            ),
        )

    @loader.command()
    async def questioncmd(self, message):
        """Answer the question asked in the config!"""
        answer = self.config["Answer"]
        args = utils.get_args_raw(message)
        if not args:
            await utils.answer(message, "Where arguments?")
        if args == answer:
            await utils.answer(message, self.config["Answer_a"])
        else:
            await utils.answer(message, self.config["Answer_b"])