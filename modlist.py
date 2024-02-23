# meta developer: @codrago

from telethon.types import Message

from .. import loader, utils

from datetime import datetime as dt
import datetime


@loader.tds
class ModulesList(loader.Module):
    """Модуль для быстрого доступа к каналам с модулями"""

    strings = {
        "name": "ModList",
        "setted": "Текст успешно поставлен",
        "added": "Чат <code>{}</code> добавлен",
        "channels": (
            "<emoji document_id=5188377234380954537>🌘</emoji> Community-made modules\n"
            "<emoji document_id=5370547013815376328>😶‍🌫️</emoji> @hikarimods"
            "\n<emoji document_id=5445096582238181549>🦋</emoji> @morisummermods"
            "\n<emoji document_id=5449380056201697322>💚</emoji> @nalinormods"
            "\n<emoji document_id=5373026167722876724>🤩</emoji> @AstroModules"
            "\n<emoji document_id=5249042457731024510>💪</emoji> @vsecoder_m"
            "\n<emoji document_id=5371037748188683677>☺️</emoji> @mm_mods"
            "\n<emoji document_id=5370856741086960948>😈</emoji> @apodiktum_modules"
            "\n<emoji document_id=5370947515220761242>😇</emoji> @wilsonmods"
            "\n<emoji document_id=5467406098367521267>👑</emoji> @DorotoroMods"
            "\n<emoji document_id=5469986291380657759>✌️</emoji> @HikkaFTGmods"
            "\n<emoji document_id=5472091323571903308>🎈</emoji> @nercymods"
            "\n<emoji document_id=5789790449594011537>🎈</emoji> @hikka_mods"
            "\n<emoji document_id=5298799263013151249>😐</emoji> @sqlmerr_m"
            "\n<emoji document_id=5296274178725396201>🥰</emoji> @AuroraModules"
            "\n<emoji document_id=5373141891321699086>😎</emoji> @famods"
            "\n<emoji document_id=5429400349377051725>😄</emoji> @BHikkaMods"
            "\n<emoji document_id=5355149418620272518>🌟</emoji> @BchModules"
        ),
        "officialChannels": (
            "<emoji document_id=5188377234380954537>🌘</emoji> Community-made modules\n"
            "<emoji document_id=5370547013815376328>😶‍🌫️</emoji> @hikarimods"
            "\n<emoji document_id=5445096582238181549>🦋</emoji> @morisummermods"
            "\n<emoji document_id=5449380056201697322>💚</emoji> @nalinormods"
            "\n<emoji document_id=5373026167722876724>🤩</emoji> @AstroModules"
            "\n<emoji document_id=5249042457731024510>💪</emoji> @vsecoder_m"
            "\n<emoji document_id=5371037748188683677>☺️</emoji> @mm_mods"
            "\n<emoji document_id=5370856741086960948>😈</emoji> @apodiktum_modules"
            "\n<emoji document_id=5370947515220761242>😇</emoji> @wilsonmods"
            "\n<emoji document_id=5467406098367521267>👑</emoji> @DorotoroMods"
            "\n<emoji document_id=5469986291380657759>✌️</emoji> @HikkaFTGmods"
            "\n<emoji document_id=5472091323571903308>🎈</emoji> @nercymods"
            "\n<emoji document_id=5789790449594011537>🎈</emoji> @hikka_mods"
            "\n<emoji document_id=5298799263013151249>😐</emoji> @sqlmerr_m"
        ),
    }

    async def client_ready(self, client, db):
        self.db = db
        self._text = self.get("text", self.strings["channels"])
        self._offtext = self.get("text", self.strings["OfficialChannels"])
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
        )
        self._ids: list = self.config["ids"]

    @loader.watcher()
    async def watcher_modules(self, message: Message):
        self._floodwait: dict = self.get("floodwait", {})
        if message.chat_id in self.config["ids"] and message.raw_text == "#modules":
            if message.from_id not in self._floodwait.keys():
                await message.reply(self._text)
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
        """| Quick access to channels with modules"""
        await utils.answer(message, self._text)

    @loader.command(alias="offmlist", ru_doc" | Оффициальные каналы с модулями ")
    async def offmodlist(self, message: Message): 
        """ | Official channel with modules"""
        await utils.answer(message, self._offtext)

    @loader.command(alias="setmlist", ru_doc=" [Текст] | Поставить текст")
    async def setmodlist(self, message):
        """[Text] | Set text"""
        reply = await message.get_reply_message()
        await utils.answer(message, self.strings["setted"])
        self.set("text", reply.text)
        self._text = self.get("text", self.strings["channels"])

    @loader.command(alias="addmchat", rudoc="[BOT API ID] | Добавить чат")
    async def addchat(self, message: Message):
        """[BOT API ID] | add chat"""
        if message.chat_id not in self.config["ids"]:
            self.config["ids"].append(message.chat_id)
            await utils.answer(message, self.strings["added"].format(message.chat_id))
        else:
            await utils.answer(message, "Чат уже был добавлен.")
