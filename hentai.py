# ---------------------------------------------------------------------------------
#░█▀▄░▄▀▀▄░█▀▄░█▀▀▄░█▀▀▄░█▀▀▀░▄▀▀▄░░░█▀▄▀█
#░█░░░█░░█░█░█░█▄▄▀░█▄▄█░█░▀▄░█░░█░░░█░▀░█
#░▀▀▀░░▀▀░░▀▀░░▀░▀▀░▀░░▀░▀▀▀▀░░▀▀░░░░▀░░▒▀
# Name: Hentai!
# Description: random hentai media
# Author: @codrago_m
# ---------------------------------------------------------------------------------
# 🔒    Licensed under the GNU AGPLv3
# 🌐 https://www.gnu.org/licenses/agpl-3.0.html
# ---------------------------------------------------------------------------------
# Author: @codrago
# Commands: fem, sfw, furry, nsfw, loli
# scope: hikka_only
# meta developer: @codrago_m
# meta banner: https://mods.codrago.top/banners/loli.png
# meta pic: https://0x0.st/s/MqdHp2_yaHlLXdmaXTJ9lQ/8KPW.webp
# ---------------------------------------------------------------------------------

__version__ = (1, 0, 0)

import os
import logging
from .. import loader, utils
import random
import time
import datetime
from telethon import functions
from telethon.tl.custom import Message

logger = logging.getLogger("Hentai")

@loader.tds
class Hentai(loader.Module):
    """Send to you random hentai media!"""
    strings = {
        "name": "Hentai",
        "loading_photo_loli": "<emoji document_id=5215327832040811010>⏳</emoji> <b>loading your loli photo...</b>",
        "error_loading": "<b>Failed to get photos. Please unblock @ferganteusbot</b>",
        "search": "<emoji document_id=5328311576736833844>🔴</emoji> loading your media..."
    }

    strings_ru = {
    "name": "Hentai",
    "loading_photo_loli": "<emoji document_id=5215327832040811010>⏳</emoji> <b>загрузка вашей лоли фотографии...</b>",
    "error_loading": "<b>Не удалось получить фотографии. Пожалуйста, разблокируйте @ferganteusbot</b>",
    "search": "<emoji document_id=5328311576736833844>🔴</emoji> загрузка вашего медиа..."
    }
    
    async def lolicmd(self, message):
        """| random loli photo"""

        await utils.answer(message, self.strings("loading_photo_loli"))
        
        async with self._client.conversation("@ferganteusbot") as conv:
            try: 
                lh = await conv.send_message("/lh")
                
                
            except Exception as e:
                return await utils.answer(message, self.strings("error_loading"))
        
            otvet = await conv.get_response()
            await lh.delete()
            if otvet.media:
                await message.client.send_message(
                    message.peer_id,
                    message=otvet,
                    reply_to=getattr(message, "reply_to_msg_id", None))
                await otvet.delete()
                await message.delete()
                
    async def femcmd(self, message):
        """| random femboy media"""

        await utils.answer(message, self.strings("search"))
        
        async with self._client.conversation("@ferganteusbot") as conv:
            try: 
                fm = await conv.send_message("/fm")
                
                
            except Exception as e:
                return await utils.answer(message, self.strings("error_loading"))
        
            response = await conv.get_response()
            await fm.delete()
            if response.media:
                await message.client.send_message(
                    message.peer_id,
                    message=response,
                    reply_to=getattr(message, "reply_to_msg_id", None))
                await response.delete()
                await message.delete()
                
    async def sfwcmd(self, message):
        """| random SFW media"""

        await utils.answer(message, self.strings("search"))
        
        async with self._client.conversation("@ferganteusbot") as conv:
            try: 
                rc = await conv.send_message("/rc")
                
                
            except Exception as e:
                return await utils.answer(message, self.strings("error_loading"))
        
            response = await conv.get_response()
            await rc.delete()
            if response.media:
                await message.client.send_message(
                    message.peer_id,
                    message=response,
                    reply_to=getattr(message, "reply_to_msg_id", None))
                await response.delete()
                await message.delete()
                
    async def furrycmd(self, message: Message):
         """| to get random furry media"""
         await message.edit(self.strings("search"))
         time.sleep(0.5)
         chat = "furrylov"
         result = await message.client(
             functions.messages.GetHistoryRequest(
                 peer=chat,
                 offset_id=0,
                 offset_date=datetime.datetime.now(),
                 add_offset=random.choice(range(1, 12436, 2)),
                 limit=1,
                 max_id=0,
                 min_id=0,
                 hash=0,
             ),
         )
         await message.delete()
         await message.client.send_file(
             message.to_id, 
             result.messages[0].media, 
             reply_to=getattr(message, "reply_to_msg_id", None),
             )
    
    async def nsfwcmd(self, message: Message):
         """| to get random NSFW media"""
         await message.edit(self.strings("search"))
         time.sleep(0.5)
         chat = "hdjrkdjrkdkd"
         result = await message.client(
             functions.messages.GetHistoryRequest(
                 peer=chat,
                 offset_id=0,
                 offset_date=datetime.datetime.now(),
                 add_offset=random.choice(range(1, 851, 2)),
                 limit=1,
                 max_id=0,
                 min_id=0,
                 hash=0,
             ),
         )
         await message.delete()
         await message.client.send_file(
             message.to_id, 
             result.messages[0].media, 
             reply_to=getattr(message, "reply_to_msg_id", None),
             )