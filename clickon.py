#meta developer: @codrago_m, @ytkanelox

from telethon import events
from .. import loader, utils
import asyncio

@loader.tds
class AutoClickerMod(loader.Module):
    """Модуль для автоматического нажатия на инлайн кнопки."""
    strings = {'name': 'AutoClicker'}

    async def clickoncmd(self, message):
        """Используйте .clickon <интервал в секундах> для начала кликов."""
        if not message.is_reply:
            await message.edit('<b>Нету реплая.</b>')
            return

        args = utils.get_args_raw(message)
        interval = int(args) if args.isdigit() else 20 
        self.clicker = True
        await message.edit(f'<b>Кликер включен. Интервал: {interval} секунд.</b>')
        
        while self.clicker:
            reply = await message.get_reply_message()
            if reply and reply.buttons:
                button = reply.buttons[0][0]
                await button.click()
                await asyncio.sleep(interval)
            else:
                await message.edit('<b>В сообщении нет инлайн кнопок для нажатия.</b>')
                self.clicker = False
                break

    async def clickoffcmd(self, message):
        """Используйте .clickoff для остановки кликера."""
        self.clicker = False
        await message.edit('<b>Кликер выключен.</b>')

    async def client_ready(self, client, db):
        self.db = db
        