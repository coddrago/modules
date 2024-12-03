# ---------------------------------------------------------------------------------
#░█▀▄░▄▀▀▄░█▀▄░█▀▀▄░█▀▀▄░█▀▀▀░▄▀▀▄░░░█▀▄▀█
#░█░░░█░░█░█░█░█▄▄▀░█▄▄█░█░▀▄░█░░█░░░█░▀░█
#░▀▀▀░░▀▀░░▀▀░░▀░▀▀░▀░░▀░▀▀▀▀░░▀▀░░░░▀░░▒▀
# Name: ModulesList.
# Description: Channels of modules for userbot Hikka.
# Author: @codrago
# ---------------------------------------------------------------------------------

# 🔒    Licensed under the GNU AGPLv3
# 🌐 https://www.gnu.org/licenses/agpl-3.0.html

# meta developer: @codrago_m
# ---------------------------------------------------------------------------------

from telethon.types import Message

from .. import loader, utils

from datetime import datetime as dt
import datetime
import json
import requests


@loader.tds
class ModulesList(loader.Module):
    """Модуль для быстрого доступа к каналам с модулями"""

    strings = {
        "name": "ModList",
        "setted": "Text successfully added",
        "added": "Chat <code>{}</code> added",
        "chat_added": "Chat already added!",
        "channels": (
            "<emoji document_id=5188377234380954537>🌘</emoji> Community-made modules\n"
        ),
        "officialChannels": (
            "<emoji document_id=5188377234380954537>🌘</emoji> Community-made modules\n"
            "\n<emoji document_id=5445096582238181549>🦋</emoji> <b>@morisummermods</b>"
            "\n<emoji document_id=5449380056201697322>💚</emoji> <b>@nalinormods</b>"
            "\n<emoji document_id=5373026167722876724>🤩</emoji> <b>@AstroModules</b>"
            "\n<emoji document_id=5249042457731024510>💪</emoji> <b>@vsecoder_m</b>"
            "\n<emoji document_id=5371037748188683677>☺️</emoji> <b>@mm_mods</b>"
            "\n<emoji document_id=5370856741086960948>😈</emoji> <b>@apodiktum_modules</b>"
            "\n<emoji document_id=5370947515220761242>😇</emoji> <b>@wilsonmods</b>"
            "\n<emoji document_id=5467406098367521267>👑</emoji> <b>@DorotoroMods</b>"
            "\n<emoji document_id=5469986291380657759>✌️</emoji> <b>@HikkaFTGmods</b>"
            "\n<emoji document_id=5472091323571903308>🎈</emoji> <b>@nercymods</b>"
            "\n<emoji document_id=5298799263013151249>😐</emoji> <b>@sqlmerr_m</b>"
            "\n<emoji document_id=5231165412275668380>🥰</emoji> <b>@AuroraModules</b>"
            "\n<emoji document_id=5418360054338314186>📢</emoji> <b>@codrago_m</b>"
        ),
    }
    strings_ru = {
        "name": "ModList",
        "setted": "Текст успешно поставлен",
        "added": "Чат <code>{}</code> добавлен",
        "chat_added": "Чат уже добавлен!",
    }

    async def client_ready(self, client, db):
        self.db = db
        self._text = self.get("text", self.strings["channels"])
        self._offtext = self.get("offtext", self.strings["officialChannels"])
        self._floodwait: dict = self.get("floodwait", {})

    def __init__(self):
        self.config = loader.ModuleConfig(
            loader.ConfigValue(
                "ids",
                [0],
                lambda: "айди где будет работать заметка BOT API ID REQUIRED",
                validator=loader.validators.Union(
                    loader.validators.Series(), loader.validators.TelegramID()
                ),
            ),
                loader.ConfigValue(
                    "linktodata",
                    "https://github.com/coddrago/modules/raw/main/modules.json",
                    lambda: 'link for modules',
                    validator=loader.validators.Link()
                ),
            )
        self._ids: list = self.config["ids"]

    def get_data(self, official: bool=False, unofficial: bool=False):
        if official:
            data: dict = json.loads(
                requests.get(self.config['linktodata']).text
            )['official']
        elif unofficial:
            data: dict = json.loads(
                requests.get(self.config['linktodata']).text
            )['unofficial']

        developers = []

        for username, emoji in data.items():
            developers.append(f'{emoji} <b>@{username}</b>')

        return developers

    @loader.watcher()
    async def watcher_modules(self, message: Message):
        self._floodwait: dict = self.get("floodwait", {})
        if message.chat_id in self.config["ids"] and message.raw_text == "#modules":
            if message.from_id not in self._floodwait.keys():
                await message.reply(self._offtext)
                now = dt.now()
                fw_time = now + datetime.timedelta(seconds=3.5)
                self._floodwait.update({message.from_id: fw_time})
            else:
                time = self._floodwait.get(message.from_id)
                if dt.now() > time:
                    self._floodwait.pop(message.from_id)
            
        else:
            return

    @loader.command(alias="mlist", ru_doc=" | Быстрый доступ к каналам с модулями ")
    async def modlist(self, message: Message):
        """ | Quick access to channels with modules"""
        devs_unoff = self.get_data(unofficial=True)
        devs_off = self.get_data(official=True)

        await utils.answer(message, '\n'.join(devs_off + devs_unoff))

    @loader.command(alias="offmlist", ru_doc=" | Оффициальные каналы с модулями ")
    async def offmodlist(self, message: Message): 
        """ | Official channel with modules"""
        devs = self.get_data(official=True)

        await utils.answer(message, '\n'.join(devs))

    @loader.command(rudoc="[BOT API ID] | Добавить чат")
    async def addmchat(self, message: Message):
        """[BOT API ID] | add chat"""
        if message.chat_id not in self.config["ids"]:
            self.config["ids"].append(message.chat_id)
            await utils.answer(message, self.strings["added"].format(message.chat_id))
        else:
            await utils.answer(message, self.strings["chat_added"])