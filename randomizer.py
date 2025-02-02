# ---------------------------------------------------------------------------------
#░█▀▄░▄▀▀▄░█▀▄░█▀▀▄░█▀▀▄░█▀▀▀░▄▀▀▄░░░█▀▄▀█
#░█░░░█░░█░█░█░█▄▄▀░█▄▄█░█░▀▄░█░░█░░░█░▀░█
#░▀▀▀░░▀▀░░▀▀░░▀░▀▀░▀░░▀░▀▀▀▀░░▀▀░░░░▀░░▒▀
# Name: randomizer
# Description: Random it your life!
# Author: @codrago_m
# ---------------------------------------------------------------------------------
# 🔒    Licensed under the GNU AGPLv3
# 🌐 https://www.gnu.org/licenses/agpl-3.0.html
# ---------------------------------------------------------------------------------
# Author: @codrago
# Commands: id, chatid, userid
# scope: hikka_only
# meta developer: @codrago_m
# meta banner: https://mods.codrago.top/banners/randomizer.png
# meta pic: https://0x0.st/s/de32M5VljJzzSJxSUjrqtA/8KPR.webp
# ---------------------------------------------------------------------------------

__version__ = (1, 0, 0)

from .. import loader, utils
import random
from telethon.tl.types import InputPeerChannel

@loader.tds
class Randomizer(loader.Module):
    """Random - it's life!"""
    strings = {
    "name": "Randomizer",
    "not_args": "<emoji document_id=5328145443106873128>✖️</emoji> Your arguments were not stated.",
    "Num1": "Number 1 for RandomCMD",
    "Num2": "Number 2 for RandomCMD",
    "Not_chat": "<emoji document_id=5328145443106873128>✖️</emoji> This is not a chat!",
    "Error_num": "<emoji document_id=5328145443106873128>✖️</emoji> Error with numbers! Check your config",
    }

    strings_ru = {
    "not_args": "<emoji document_id=5328145443106873128>✖️</emoji> Ваши аргументы не были указаны.",
    "Num1": "Число 1 для RandomCMD",
    "Num2": "Число 2 для RandomCMD",
    "Not_chat": "<emoji document_id=5328145443106873128>✖️</emoji> Это не чат!",
    "Error_num": "<emoji document_id=5328145443106873128>✖️</emoji> Ошибка с числами! Проверьте ваш конфиг",
    }

    
    def __init__(self):
        self.config = loader.ModuleConfig(
            loader.ConfigValue(
                "Num_1",
                1,
                lambda: self.strings["Num1"],
            ),

            loader.ConfigValue(
                "Num_2",
                10,
                lambda: self.strings["Num2"],
            ),
        )
    
    async def chancecmd(self, message):
        """[args] | A chance for your success!"""
    
        args = utils.get_args_raw(message)
        chance = random.randint(1, 100)
    
        if not args:
            await utils.answer(message, self.strings["not_args"])
        else:
            await utils.answer(message, f"<emoji document_id=5298620403395074835>🤩</emoji> The chance that {args} is equal to {chance}%!")
    
    async def randomcmd(self, message):
        """!cfg | random number"""
        
        min_num = min(self.config["Num_1"], self.config["Num_2"])
        max_num = max(self.config["Num_1"], self.config["Num_2"])
        random_num = random.randint(min_num, max_num)
        
        if min_num >= max_num:
            await utils.answer(message, self.strings["Error_Num"])
        else:
            await utils.answer(message, f"<emoji document_id=5406611523487411073>😇</emoji> Your random number in the range {min_num} - {max_num}: {random_num}")
           
    async def shipcmd(self, message):
        """| Ship from iris?"""
        
        chat = message.peer_id
        channel = await self.client.get_entity(chat)
        participants = await self.client.get_participants(channel)
        random_user = random.choice(participants)
        random_user2 = random.choice(participants)
        user = random_user.id
        user_name = random_user.first_name
        user2 = random_user2.id
        user_name2 = random_user2.first_name
        loh_a = f'<a href = "tg://user?id={user}">{user_name}</a>'
        loh_b = f'<a href = "tg://user?id={user2}">{user_name2}</a>'
        if message.is_private:
            await utils.answer(message, self.strings["Not_chat"])
        else:
            await utils.answer(message, f'<emoji document_id=5341674117642854617>❤️</emoji> Random ship: {loh_a} + {loh_b}\n\n<emoji document_id=5341364514925321015>🌹</emoji> Love and appreciate each other!')
    
    async def randusercmd(self, message):
        """| Random user!"""
       
        chat = message.peer_id
        channel = await self.client.get_entity(chat)
        participants = await self.client.get_participants(channel)
        random_user = random.choice(participants)
        user = random_user.id
        user_name = random_user.first_name
        
        if message.is_private:
            await utils.answer(message, self.strings["Not_chat"])
        else: 
            await utils.answer(message, f'<emoji document_id=5287404392654319394>🔥</emoji> Your random user: <a href = "tg://user?id={user}">{user_name}</a>')
        
       
       
    