# ---------------------------------------------------------------------------------
# Name: Loli Hentai!
# Description: words superfluous?
# Author: @codrago_m
# ---------------------------------------------------------------------------------

# 🔒    Licensed under the GNU AGPLv3
# 🌐 https://www.gnu.org/licenses/agpl-3.0.html

# meta developer: @codrago_m
# ---------------------------------------------------------------------------------
import os
import logging
from .. import loader, utils

logger = logging.getLogger("LoliHentai")

@loader.tds
class lolihentai(loader.Module):
    """Your the best friend in loli hentai"""
    strings = {
        "name": "LoliHentai",
        "loading_photo": "<emoji document_id=5215327832040811010>⏳</emoji> <b>loading your loli photo...</b>",
        "error_loading": "<b>Failed to get photos. Please unblock @ferganteusbot</b>",
    }
    
    async def lolicmd(self, message):
        """random loli photo"""

        await utils.answer(message, self.strings("loading_photo"))
        
        async with self._client.conversation("@ferganteusbot") as conv:
            
            await conv.send_message("/lh")
        
            otvet = await conv.get_response()
          
            if otvet.photo:
                phota = await self._client.download_media(otvet.photo, "loli_hentai")
        
                await message.client.send_message(
                    message.peer_id,
                    file=phota,
                    )

                os.remove(phota)
                
                await message.delete()