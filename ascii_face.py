# ---------------------------------------------------------------------------------
#░█▀▄░▄▀▀▄░█▀▄░█▀▀▄░█▀▀▄░█▀▀▀░▄▀▀▄░░░█▀▄▀█
#░█░░░█░░█░█░█░█▄▄▀░█▄▄█░█░▀▄░█░░█░░░█░▀░█
#░▀▀▀░░▀▀░░▀▀░░▀░▀▀░▀░░▀░▀▀▀▀░░▀▀░░░░▀░░▒▀
# Name: Ascii face
# Description: random ascii face from utils
# Author: @codrago_m
# ---------------------------------------------------------------------------------
# 🔒    Licensed under the GNU AGPLv3
# 🌐 https://www.gnu.org/licenses/agpl-3.0.html
# ---------------------------------------------------------------------------------
# Author: @codrago
# Commands: ascii
# scope: hikka_only
# meta developer: @codrago_m
# meta banner: https://mods.codrago.top/banners/ascii_face.png
# meta pic: https://0x0.st/s/TGT42nesnQ5TwvixG8nFEQ/8KPa.webp
# ---------------------------------------------------------------------------------

__version__ = (1, 0, 0)

from .. import loader, utils

@loader.tds
class Ascii_face(loader.Module):
    """Random Ascii Face from utils"""

    strings = {
    "name": "Ascii_Face",
    "ascii_face": "<emoji document_id=5343719226450385808>😛</emoji> <b>Your random AsciiFace:</b> ",
    }
    
    strings_ru = {
    "ascii_face": "<emoji document_id=5343719226450385808>😛</emoji> <b>Ваш рандомный AsciiFace:</b> "
    }

    async def asciicmd(self, message):
        """| Get random ascii face"""
        
        ascii_face = utils.ascii_face()
        
        await utils.answer(message, (self.strings["ascii_face"] + f"<code>{ascii_face}</code>"))