# ---------------------------------------------------------------------------------
# ░█▀▄░▄▀▀▄░█▀▄░█▀▀▄░█▀▀▄░█▀▀▀░▄▀▀▄░░░█▀▄▀█
# ░█░░░█░░█░█░█░█▄▄▀░█▄▄█░█░▀▄░█░░█░░░█░▀░█
# ░▀▀▀░░▀▀░░▀▀░░▀░▀▀░▀░░▀░▀▀▀▀░░▀▀░░░░▀░░▒▀
#
#  _____      _   _                  
# | ____|_  _| |_| |_ __ _ ___ _   _ 
# |  _| \ \/ / __| __/ _` / __| | | |
# | |___ >  <| |_| || (_| \__ \ |_| |
# |_____/_/\_\\__|\__\__,_|___/\__, |
#                               |___/ 
# Name: PMBan
# Description: Ban in pm for time
# Author: @codrago_m, @exttasy1
# ---------------------------------------------------------------------------------
# 🔒    Licensed under the GNU AGPLv3
# 🌐 https://www.gnu.org/licenses/agpl-3.0.html
# ---------------------------------------------------------------------------------
# Author: @codrago, @exttasy1
# Commands: pmban, pmunban
# scope: hikka_only
# meta developer: @codrago_m, @exttasy1
# ---------------------------------------------------------------------------------

__version__ = (1, 0, 0)

from .. import loader, utils
import telethon, asyncio, re, pymorphy2, math, time, logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler

logging.getLogger('apscheduler').setLevel(logging.WARNING)
logging.getLogger('pymorphy2').setLevel(logging.WARNING)

@loader.tds
class PMBan(loader.Module):
    """Ban in pm for time"""

    strings = {
    "name": "PMBan",
    }

    @staticmethod
    def _pluralize(morph, count, word):
        word_morph = morph.parse(word)[0]
        return word_morph.make_agree_with_number(count).word
    
    def format_time(self, seconds):
        morph = pymorphy2.MorphAnalyzer()

        if seconds < 0 or seconds == 0:
            return "forever"

        days = math.floor(seconds / (60 * 60 * 24))
        seconds %= (60 * 60 * 24)
        hours = math.floor(seconds / (60 * 60))
        seconds %= (60 * 60)
        minutes = math.floor(seconds / 60)
        seconds = math.floor(seconds % 60)

        time_parts = []
        if days > 0:
           time_parts.append(f"for {days} {self._pluralize(morph, days, 'day')}")
        if hours > 0:
            time_parts.append(f"for {hours} {self._pluralize(morph, hours, 'hour')}")
        if minutes > 0:
            time_parts.append(f"for {minutes} {self._pluralize(morph, minutes, 'minute')}")
        if seconds > 0 or not time_parts:
            time_parts.append(f"for {seconds} {self._pluralize(morph, seconds, 'second')}")

        return " ".join(time_parts)

    
    @staticmethod
    def convert_time(text: str) -> int:
        try:
            if not str(text)[:-1].isdigit():
                return 0

            if "d" in str(text):
                text = int(text[:-1]) * 60 * 60 * 24

            if "h" in str(text):
                text = int(text[:-1]) * 60 * 60

            if "m" in str(text):
                text = int(text[:-1]) * 60

            if "s" in str(text):
                text = int(text[:-1])

            text = int(re.sub(r"[^0-9]", "", str(text)))
        except ValueError:
            return 0

        return text


    async def loop_unban(self):
        ban_list = self.get('ban_list')

        for user in ban_list:
            user_id, time_ban = next(iter(user.items()))
            
            if time_ban[0] <= 0:
                continue
            
            end_ban = time_ban[0] + time_ban[1]

            if end_ban <= time.time():
                await self.client(telethon.tl.functions.contacts.UnblockRequest(id=int(user_id)))
                await self.client.send_message(int(user_id), f"<b><emoji document_id=5021905410089550576>✅</emoji> You have been successfully unbanned.</b>")
                
                ban_list = [d for d in ban_list if int(user_id) not in d]
                self.set('ban_list', ban_list)


    async def client_ready(self):
        if not (ban_list := self.get('ban_list')) or not isinstance(ban_list, list): self.set('ban_list', [])
        self.scheduler = AsyncIOScheduler()
        self.scheduler.add_job(self.loop_unban, 'interval', seconds=3)
        self.scheduler.start()

    async def on_unload(self):
        self.scheduler.shutdown()


    @loader.command()
    async def pmban(self, message):
        """| ban in PM for time"""
    
        if not (args := utils.get_args_raw(message)):
            stime = 0

        ban_list = self.get('ban_list')

        if any(message.chat_id in d for d in ban_list):
            await utils.answer(message, f"<b><emoji document_id=5980953710157632545>❌</emoji> User already has been banned</b>")
            return

        if args:
            stime = self.convert_time(args)
        str_time = self.format_time(seconds=stime).replace("minutes", "minute").replace("second", "second")

        await self.client(telethon.tl.functions.contacts.BlockRequest(id=message.chat_id))

        await utils.answer(message, f"<b><emoji document_id=5021905410089550576>✅</emoji> User succesfully banned {str_time}.</b>")

        ban_list.append({message.chat_id: [stime, int(time.time())]})
        self.set('ban_list', ban_list)
    
    
    @loader.command()
    async def pmunban(self, message):
        """| unban in PM"""
        ban_list = self.get('ban_list')

        print(ban_list)
        reply = await message.get_reply_message()

        if not reply:
            await utils.answer(message, f"<b><emoji document_id=5980953710157632545>❌</emoji> User not found, please write this command in response to user messages.</b>")
            return

        if not any(reply.from_id in d for d in ban_list):
            await utils.answer(message, f"<b><emoji document_id=5980953710157632545>❌</emoji> User not banned</b>")
            return

        await self.client(telethon.tl.functions.contacts.UnblockRequest(id=reply.from_id))
        await utils.answer(message, f"<b><emoji document_id=5021905410089550576>✅</emoji> User succesfully unbanned.</b>")
        
        ban_list = [d for d in ban_list if reply.from_id not in d]
        self.set('ban_list', ban_list)