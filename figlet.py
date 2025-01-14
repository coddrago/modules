# ---------------------------------------------------------------------------------
#░█▀▄░▄▀▀▄░█▀▄░█▀▀▄░█▀▀▄░█▀▀▀░▄▀▀▄░░░█▀▄▀█
#░█░░░█░░█░█░█░█▄▄▀░█▄▄█░█░▀▄░█░░█░░░█░▀░█
#░▀▀▀░░▀▀░░▀▀░░▀░▀▀░▀░░▀░▀▀▀▀░░▀▀░░░░▀░░▒▀
# Name: Figlet
# Description: Tool for Figlet
# Author: @codrago_m
# ---------------------------------------------------------------------------------
# 🔒    Licensed under the GNU AGPLv3
# 🌐 https://www.gnu.org/licenses/agpl-3.0.html
# ---------------------------------------------------------------------------------
# Author: @codrago
# Commands: figlet
# scope: hikka_only
# meta developer: @codrago_m
# ---------------------------------------------------------------------------------

__version__ = (1, 0, 0)

import subprocess
import traceback
from .. import loader, utils

@loader.tds
class Figlet(loader.Module):
    """Tool for work with figlet"""
    strings = {
    "name": "Figlet",
    "not_installed": "<emoji document_id=5328145443106873128>✖️</emoji> <b>You don't have Figlet installed! Install it with <code>.terminal sudo apt install figlet -y</code></b>"
    }

    strings_ru = {
    "not_installed": "<emoji document_id=5328145443106873128>✖️</emoji> <b>У вас не установлен Figlet! Установите его командой <code>.terminal sudo apt install figlet -y</code></b>"
}

    async def figletcmd(self, message):
        """[args] | run figlet command"""

        args=utils.get_args_raw(message)
        
        try:
            result = subprocess.run(["figlet", f"{args}"], capture_output=True, text=True)
            output = result.stdout
            await utils.answer(message, f"<pre>{utils.escape_html(output)}</pre>")
            
        except FileNotFoundError:
            await utils.answer(message, self.strings["not_installed"])