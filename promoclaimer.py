# ---------------------------------------------------------------------------------
# ░█▀▄░▄▀▀▄░█▀▄░█▀▀▄░█▀▀▄░█▀▀▀░▄▀▀▄░░░█▀▄▀█
# ░█░░░█░░█░█░█░█▄▄▀░█▄▄█░█░▀▄░█░░█░░░█░▀░█
# ░▀▀▀░░▀▀░░▀▀░░▀░▀▀░▀░░▀░▀▀▀▀░░▀▀░░░░▀░░▒▀
# Name: PromoClaimer
# Description: Automatically claim https://t.me/StableWaifuBot promo from any chat
# Author: @codrago_m
# ---------------------------------------------------------------------------------
# 🔒    Licensed under the GNU AGPLv3
# 🌐 https://www.gnu.org/licenses/agpl-3.0.html
# ---------------------------------------------------------------------------------
# Author: @codrago
# Commands: checktokens
# scope: hikka_only
# meta developer: @codrago_m
# ---------------------------------------------------------------------------------

__version__ = (1, 0, 0)

import logging

from telethon.errors import AlreadyInConversationError
from telethon.tl.types import Message
import re

from .. import loader, utils

logger = logging.getLogger('PromoClaimer')

@loader.tds
class PromoClaimerMod(loader.Module):
    """Automatically claim https://t.me/StableWaifuBot promo from any chat"""
    strings = {
        "name": "PromoClaimer",
        "claimed_promo": "[PromoClaimer] 👌 I successfully claimed promo {promo} for {amount} tokens!",
        "error_watcher": "[PromoClaimer] ⛔️ An error occurred while watching for messages:\n{e}",
        "invalid_promo": "[PromoClaimer] 😢 Promo code {promo} is invalid!",
        "already_claimed": "[PromoClaimer] 😢 Promo code {promo} has already been claimed!",
    }

    strings_ru = {
        "claimed_promo": "[PromoClaimer] 👌 Я успешно активировал промокод {promo} на {amount} токен(-ов)!",
        "error_watcher": "[PromoClaimer] ⛔️ Во время отслеживания сообщений произошла ошибка:\n{e}",
        "invalid_promo": "[PromoClaimer] 😢 Промокод {promo} недействителен, либо уже истек!",
        "already_claimed": "[PromoClaimer] 😢 Промокод {promo} уже активирован!",
        "_cls_doc": "Автоматически забирать промокоды для https://t.me/StableWaifuBot",
    }

    @loader.command(ru_doc='| Посмотреть баланс токенов')
    async def checktokens(self, message: Message):
        """| check tokens balance"""

        try:
            async with self.client.conversation('@StableWaifuBot') as conv:
                msg = await conv.send_message('/tokens')
                response = await conv.get_response()
                tokens = response.text.splitlines()[0]
                await conv.mark_read()
                await msg.delete()
                await response.delete()

            await utils.answer(message, tokens)

        except AlreadyInConversationError:
            pass

    @loader.watcher()
    async def watcher(self, message: Message):
        try:
            pattern = r'https://t\.me/StableWaifuBot\?start=promo_(\w+)'
            matches = re.findall(pattern, message.text)

            for match in matches:
                async with self.client.conversation('StableWaifuBot') as conv:
                    promo = 'promo_' + match
                    msg = await conv.send_message(f'/start {promo}')
                    response = await conv.get_response()

                    await conv.mark_read()
                    await msg.delete()
                    await response.delete()
                if response.text == '🥲 Промокод недействителен или уже истёк!':
                    logger.info(self.strings("invalid_promo").format(promo=promo))
                elif response.text == '❌ Этот промокод уже активирован, проверь выше!':
                    logger.info(self.strings('already_claimed').format(promo=promo))

                else:
                    amount = response.text.split('(+')[1]
                    logger.info(self.strings('claimed_promo').format(promo=promo, amount=amount))

        except Exception as e:
            logger.info(self.strings('error_watcher').format(e=str(e)))



