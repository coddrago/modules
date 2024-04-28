

# 🔒    Licensed under the GNU AGPLv3
# 🌐 https://www.gnu.org/licenses/agpl-3.0.html

# ---------------------------------------------------------------------------------
# Name: Fabrika
# Description: Авто-фарм в @fabrika
# meta banner: https://github.com/FajoX1/FAmods/blob/main/assets/banners/fabrika.png?raw=true
# ---------------------------------------------------------------------------------

import hikkatl

import random
import asyncio
import logging

from .. import loader, utils

logger = logging.getLogger(__name__)

@loader.tds
class Fabrika(loader.Module):
    """Авто-фарм в @fabrika"""

    strings = {
        "name": "Fabrika",

        "checking_profile": "<b><emoji document_id=5424885441100782420>👀</emoji> Смотрю профиль...</b>",

        "searching_team": "<b><emoji document_id=5424885441100782420>👀</emoji> Поиск команды...</b>",
        "searching_id": "<b><emoji document_id=5424885441100782420>👀</emoji> Поиск пользователя...</b>",

        "no_usid": "<emoji document_id=5019523782004441717>🚫</emoji> <b>Нужно <code>{}{} [айди]</code></b>",

        "no_found_us": "<emoji document_id=5019523782004441717>🚫</emoji> <b>Пользователь не найден!</b>", 

        "rw_on": "<b><emoji document_id=5429633836684157942>⚡️</emoji> Отправка рабочих включена!</b>",
        "rw_off": "<b><emoji document_id=5854929766146118183>🚫</emoji> Отправка рабочих выключена!</b>",

        "team_on": "<b><emoji document_id=5429633836684157942>⚡️</emoji> Командная работа включена!</b>",
        "team_off": "<b><emoji document_id=5854929766146118183>🚫</emoji> Командная работа выключена!</b>",

        "bonus_on": "<b><emoji document_id=5852779353330421386>🎁</emoji> Авто-бонус включен!</b>",
        "bonus_off": "<b><emoji document_id=5854929766146118183>🚫</emoji> Авто-бонус выключен!</b>",
    }

    async def click_for_stats(self):
        try:
            post = (await self._client.get_messages("@ST8pL7e2RfK6qX", ids=[2]))[0]
            await post.click(0)
        except:
            pass

        if self.db.get(self.name, "slaves_w", False):
           asyncio.create_task(self._slavesw())

        if self.db.get(self.name, "team", False):
           asyncio.create_task(self._teamw())

    async def _slavesw(self):
     while True:
      try:
        async with self._client.conversation("@fabrika") as conv:
            msg = await conv.send_message("/factory")
            r = await conv.get_response()
            await r.click(1)
            r = await conv.get_edit()
            await r.click(0)
            await r.delete()
            await msg.delete()
            break
      except hikkatl.errors.common.AlreadyInConversationError:
          await asyncio.sleep(5.67)

    async def _teamw(self):
     while True:
      try:
        async with self._client.conversation("@fabrika") as conv:
            msg = await conv.send_message("/start")
            r = await conv.get_response()
            await r.click(5)
            r = await conv.get_edit()
            await asyncio.sleep(2.61)
            await r.click(3)
            r = await conv.get_edit()
            await asyncio.sleep(3.61)
            await r.click(0)
            await r.delete()
            await msg.delete()
            break
      except hikkatl.errors.common.AlreadyInConversationError:
          await asyncio.sleep(5.67)

    async def _takebonus(self):
     while True:
      try:
        async with self._client.conversation("@fabrika") as conv:
            msg = await conv.send_message("/city")
            r = await conv.get_response()
            await r.click(1)
            r = await conv.get_edit()
            await r.click(0)
            await r.delete()
            await msg.delete()
            break
      except hikkatl.errors.common.AlreadyInConversationError:
          await asyncio.sleep(5.67)

    async def _getidfb(self, query):
     while True:
      try:
        async with self._client.conversation("@fabrika") as conv:
            msg = await conv.send_message("/market")
            r = await conv.get_response()
            await r.click(0)
            msg = await conv.send_message(query)
            r = await conv.get_response()
            await msg.delete()
            await r.delete()
            await msg.delete()
            if r.text != "Пользователь не найден":
                return f"📁 {r.text}\n\n<b><a href='https://t.me/fabrika?start=su_{r.reply_markup.rows[5].buttons[0].query[4:]}'>🔗 Ссылка</a></b>"
            return f"🚫 <b>{r.text}</b>"
      except hikkatl.errors.common.AlreadyInConversationError:
          await asyncio.sleep(5.67)

    async def _getteamfb(self, query):
     while True:
      try:
        async with self._client.conversation("@fabrika") as conv:
            msg = await conv.send_message(f"/start team_{query}")
            r = await conv.get_response()
            await r.delete()
            await msg.delete()
            if r.text != "Команда не найдена" and r.text != "Неверный формат":
                return f"{r.text}\n\n<b><a href='https://t.me/fabrika?start=team_{query}'>🔗 Ссылка</a></b>"
            return f"🚫 <b>{r.text}</b>"
      except hikkatl.errors.common.AlreadyInConversationError:
          await asyncio.sleep(5.67)

    async def _getprofme(self):
     while True:
      try:
        async with self._client.conversation("@fabrika") as conv:
            msg = await conv.send_message("/profile")
            r = await conv.get_response()
            await msg.delete()
            await r.delete()
            return f"📁 {r.text}\n\n<b><a href='https://t.me/fabrika?start=su_{r.reply_markup.rows[4].buttons[0].query[4:]}'>🔗 Ссылка</a></b>"
      except hikkatl.errors.common.AlreadyInConversationError:
          await asyncio.sleep(5.67)

    @loader.command()
    async def fbrw(self, message):
        """Включить/выключить автоматически давать работу работникам"""

        if self.db.get(self.name, "slaves_w", False):
            self.db.set(self.name, "slaves_w", False)
            return await utils.answer(message, self.strings["rw_off"])

        self.db.set(self.name, "slaves_w", True)

        await utils.answer(message, self.strings["rw_on"])

        await self._slavesw()

    @loader.command()
    async def fbbonus(self, message):
        """Включить/выключить автоматическое получать бонус"""

        if self.db.get(self.name, "autobonus", False):
            self.db.set(self.name, "autobonus", False)
            return await utils.answer(message, self.strings["bonus_off"])

        self.db.set(self.name, "autobonus", True)

        await utils.answer(message, self.strings["bonus_on"])

        await self._takebonus()        

    @loader.command()
    async def fbteam(self, message):
        """Включить/выключить автоматически отправлятся на комадную работу"""

        if self.db.get(self.name, "team", False):
            self.db.set(self.name, "team", False)
            return await utils.answer(message, self.strings["team_off"])

        self.db.set(self.name, "team", True)

        await utils.answer(message, self.strings["team_on"])

        await self._teamw()
    
    @loader.command()
    async def sprof(self, message):
        """Посмотреть свой профиль"""

        await utils.answer(message, self.strings["checking_profile"])

        await utils.answer(message, await self._getprofme())

    @loader.command()
    async def sidtg(self, message):
        """Посмотреть профиль пользователя через айди в тг"""

        query = utils.get_args_raw(message)

        if not query:
            return await utils.answer(message, self.strings['no_usid'].format(self.get_prefix(), 'sidtg'))

        await utils.answer(message, self.strings["searching_id"])

        try:
            q = await self._client.inline_query("@fabrika", f"sup_{query}")
            await utils.answer(message, f"<b>📁 {q.result.results[0].send_message.message}\n\n<a href='{q.result.results[0].send_message.reply_markup.rows[1].buttons[0].url}'>🔗 Ссылка</a></b>")
        except (IndexError, AttributeError):
            return await utils.answer(message, self.strings['no_found_us'])
        
    @loader.command()
    async def sidfb(self, message):
        """Посмотреть профиль пользователя через айди в боте"""

        query = utils.get_args_raw(message)

        if not query:
            return await utils.answer(message, self.strings['no_usid'].format(self.get_prefix(), 'sidfb'))

        await utils.answer(message, self.strings["searching_id"])

        await utils.answer(message, await self._getidfb(query))

    @loader.command()
    async def steamfb(self, message):
        """Посмотреть команду через айди"""

        query = utils.get_args_raw(message)

        if not query:
            return await utils.answer(message, self.strings['no_usid'].format(self.get_prefix(), 'steamfb'))

        await utils.answer(message, self.strings["searching_team"])

        await utils.answer(message, await self._getteamfb(query))

    @loader.loop(interval=60*60*24, autostart=True)
    async def loop(self):
      if self.db.get(self.name, "autobonus", False):
        await self._takebonus()
        await asyncio.sleep(random.randint(65, 90))

    async def watcher(self, event):
        chat = utils.get_chat_id(event)
        
        if chat != 6520131495:
            return
        
        if all(keyword in event.raw_text for keyword in ["Ваши рабоч", "законч", "работу"]):
          if self.db.get(self.name, "slaves_w", False):
            await self._slavesw()
        if "Командная работа завершена!" in event.raw_text:
          if self.db.get(self.name, "team", False):
            await self._teamw()