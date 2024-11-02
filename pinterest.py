# ---------------------------------------------------------------------------------
#░█▀▄░▄▀▀▄░█▀▄░█▀▀▄░█▀▀▄░█▀▀▀░▄▀▀▄░░░█▀▄▀█
#░█░░░█░░█░█░█░█▄▄▀░█▄▄█░█░▀▄░█░░█░░░█░▀░█
#░▀▀▀░░▀▀░░▀▀░░▀░▀▀░▀░░▀░▀▀▀▀░░▀▀░░░░▀░░▒▀
# Name: PinterestDownloader
# Description: Gives a link to download a file from Pinterest
# Author: @codrago_m
# ---------------------------------------------------------------------------------
# 🔒    Licensed under the GNU AGPLv3
# 🌐 https://www.gnu.org/licenses/agpl-3.0.html
# ---------------------------------------------------------------------------------
# Author: @codrago
# Commands: pinterest
# scope: hikka_only
# meta developer: @codrago_m
# ---------------------------------------------------------------------------------

__version__ = (1, 0, 0)

from .. import loader, utils

@loader.tds
class PinterestDownloader(loader.Module):
    """Gives a link to download a file from Pinterest"""
    
    strings = { 
    "name": "PinterestDownloader",
    "Error": "<emoji document_id=5328145443106873128>✖️</emoji> Where args?",
    }

    strings_ru = {
    "Error": "<emoji document_id=5328145443106873128>✖️</emoji> Где аргументы?"
    }
    
    async def pinterestcmd(self, message):
        """Gives a link to download"""
        
        args = utils.get_args_raw(message)
        link = f"https://pinterestdownloader.com?share_url={args}"
       
        if not args:
            await utils.answer(message, self.strings["Error"])
        elif 'pin.it' in args:
            await utils.answer(message, f'<emoji document_id=5319172556345851345>✨</emoji> <b><u>Pin ready to download!</u></b>\n\n<emoji document_id=5316719099227684154>🌕</emoji> <b>Link for download:</b> <i><a href="{link}">just tap here</a></i>')
        else:
            await utils.answer(message, f"<emoji document_id=5319088379281815108>🤷‍♀️</emoji> '{args}' <b>No have</b> 'pin.it' \n\n<b>Link is invalid</b>")