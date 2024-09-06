# ---------------------------------------------------------------------------------
#░█▀▄░▄▀▀▄░█▀▄░█▀▀▄░█▀▀▄░█▀▀▀░▄▀▀▄░░░█▀▄▀█
#░█░░░█░░█░█░█░█▄▄▀░█▄▄█░█░▀▄░█░░█░░░█░▀░█
#░▀▀▀░░▀▀░░▀▀░░▀░▀▀░▀░░▀░▀▀▀▀░░▀▀░░░░▀░░▒▀
# Name: Dox?
# Description: Your Best doxing tool!
# Author: @codrago_m
# ---------------------------------------------------------------------------------
# 🔒    Licensed under the GNU AGPLv3
# 🌐 https://www.gnu.org/licenses/agpl-3.0.html
# ---------------------------------------------------------------------------------
# Author: @codrago
# Commands: gb, deanon
# scope: hikka_only
# meta developer: @codrago_m
# ---------------------------------------------------------------------------------

__version__ = (1, 0, 0)

from telethon.tl.types import Message # type: ignore
from .. import loader, utils
import asyncio, random

@loader.tds
class dox(loader.Module):
    """Maybe... doxing tool?"""
    
    strings = {
        "name": "DoxTool",
        "gb_1": "Searching for vicrim's number...",
        "gb_2": "Searching for victim's address and name...",
        "gb_3": "Search for parents...",
        "gb_4": "Searching for a school...",
        "gb_5": "Finding parents' jobs...",
        "gb_r": "Мой хозяин плохо себя вел и я решил слить инфу о нем!\n\n├ Телефон: разъебанный \n├ Страна: обычная \n├ Регион: пиздоболов \n├ Родители : скокро не будет\n├ Адрес: канава  на Арбате \n├ Имя: нахуй ты родился\n├ Отчество: отсутствует \n├ Фамилия: отсутствует \n├ Сколько раз ебали в дырку: 32\n├ Пол: ленолиум \n├ Дом : канава на Арбате \n├ сосёт в день: 20 (раз) за 10 руб\n├ больница : не пускают \n├ Цвет говна: нету, ибо не хавает \n├ Простата: массирована\n├Рот: выебан\n└ #####################\n\nМать : шлюха \nместо работы матери: трасса\nСтрана: \nсостоящаяся в снггород: я ебу? \nродилась: где-то под забором\n\nОтец: бомж, \nместо работы: на улице бичевать, просить мелочь\nСтрана: состоящаяся в снггород: я ебу?\nродился: в канализации\nШкола: далбоебов",
        "info": "This module was created solely for entertainment purposes, its functionality is created solely for the sake of a joke"
     }
    
    async def gbcmd(self, message):
        """search in databases eye of god!"""
        await utils.answer(message, self.strings["gb_1"])
        await asyncio.sleep(1)
        await message.edit(self.strings["gb_2"])
        await asyncio.sleep(1)
        await message.edit(self.strings["gb_3"])
        await asyncio.sleep(1)
        await message.edit(self.strings["gb_4"])
        await asyncio.sleep(1)
        await message.edit(self.strings["gb_5"])
        await asyncio.sleep(1)
        await message.edit(self.strings["gb_r"])

    async def deanoncmd(self, message):
        """Full information of user in global database"""
        deanon = ["It's bad to do something like this...","I’m tired of you!", "One more prank like this and I’ll delete your account.", "Didn’t you understand the first time?", "Why do you keep doing this??", "We both know that this doesn’t do us any good.", "what won't it lead to?"]
        await utils.answer(message, random.choice(deanon))

    async def dinfocmd(self, message):
        """info of module"""
        await utils.answer(message, self.strings["info"])
