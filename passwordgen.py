# ---------------------------------------------------------------------------------
#░█▀▄░▄▀▀▄░█▀▄░█▀▀▄░█▀▀▄░█▀▀▀░▄▀▀▄░░░█▀▄▀█
#░█░░░█░░█░█░█░█▄▄▀░█▄▄█░█░▀▄░█░░█░░░█░▀░█
#░▀▀▀░░▀▀░░▀▀░░▀░▀▀░▀░░▀░▀▀▀▀░░▀▀░░░░▀░░▒▀
# Name: Password Generator
# Description: Generate password
# Author: @codrago_m
# ---------------------------------------------------------------------------------
# 🔒    Licensed under the GNU AGPLv3
# 🌐 https://www.gnu.org/licenses/agpl-3.0.html
# ---------------------------------------------------------------------------------
# Author: @codrago
# Commands: pass, passg
# meta developer: @codrago_m
# meta banner: https://raw.githubusercontent.com/coddrago/modules/refs/heads/master/banner.png
# meta pic: https://envs.sh/Hoe.webp
# ---------------------------------------------------------------------------------

from .. import loader, utils
import string
import random

@loader.tds
class PassGen(loader.Module):
  """Generate password"""

  strings = {
    "name": "PassGen",
    "no_args": "<emoji document_id=5328145443106873128>✖️</emoji> <b>Where args?</b>",
    "pass": "<emoji document_id=5832546462478635761>🔒</emoji> <b>Here your password:</b> ",
  }

  strings_ru = {
    "no_args": "<emoji document_id=5328145443106873128>✖️</emoji> <b>Где аргументы?</b>",
    "pass": "<emoji document_id=5832546462478635761>🔒</emoji> <b>Твой пароль:</b> ",
  }
  
  @loader.command()
  async def passcmd(self, message):
    """| Generate password from utils"""

    args = int(utils.get_args_raw(message))
    password = utils.rand(args)
    
    if not args:
      await utils.answer(message, self.strings["no_args"])
    else:
      await utils.answer(message, f"{self.strings['pass']},<code>{password}</code>")

  @loader.command()
  async def passgcmd(self, message):
    """| Generate password from string"""

    args = int(utils.get_args_raw(message))
    characters = string.ascii_letters + string.digits + string.punctuation
    password = ''.join(random.choice(characters) for _ in range(args))
    
    if not args:
      await utils.answer(message, self.strings["no_args"])
    else:
      await utils.answer(message, f"{self.strings['pass']}, <code>{password}</code>")
    
