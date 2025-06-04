# ---------------------------------------------------------------------------------
#░█▀▄░▄▀▀▄░█▀▄░█▀▀▄░█▀▀▄░█▀▀▀░▄▀▀▄░░░█▀▄▀█
#░█░░░█░░█░█░█░█▄▄▀░█▄▄█░█░▀▄░█░░█░░░█░▀░█
#░▀▀▀░░▀▀░░▀▀░░▀░▀▀░▀░░▀░▀▀▀▀░░▀▀░░░░▀░░▒▀
# Name: send
# Description: феля не бей меня попросили
# Author: @codrago_m
# ---------------------------------------------------------------------------------
# 🔒    Licensed under the GNU AGPLv3
# 🌐 https://www.gnu.org/licenses/agpl-3.0.html
# ---------------------------------------------------------------------------------
# Author: @codrago
# Commands: id, chatid, userid
# scope: hikka_only
# meta developer: @codrago_m
# meta banner: https://raw.githubusercontent.com/coddrago/modules/refs/heads/main/banner.png
# meta pic: https://kappa.lol/p3wVI
# ---------------------------------------------------------------------------------

from .. import utils, loader

@loader.tds
class Send(loader.Module):
    """| module to send messages"""

    strings = {
        "name": "Send",
        "no_args": "<b>Where args?</b>",
        "nobody_s": "<b>Who should i send it to?</b>",
        "succesfully_send": "<b>Message succesfully sended</b>",
    }

    @loader.command()
    async def send(self, message):
        """[user] [text] | Send message to user"""

        try:
            args = utils.get_args_raw(message)
            reply = await message.get_reply_message()
            user = str(args.split(" ")[0])
            msg = str(args.split(" ", maxsplit=1)[1])

            if msg != None:
                await self.client.send_message(user, msg)
                await utils.answer(message, self.strings["succesfully_send"])
            else:
                await utils.answer(message, self.strings["no_args"])
        except Exception as e:
            await utils.answer(message, f"<pre><code class='language-python'>{e}</code></pre>")

    @loader.command()
    async def sendsm(self, message):
        """[reply or text] | send message to saved messages"""

        try:
            args = utils.get_args_raw(message)
            reply = await message.get_reply_message()
            user = message.sender_id
            msg = []

            for i in args:
                msg.append(i)

            if len(msg) <= 1:
                msgsend = reply
            else: 
                msgsend = utils.get_args_raw(message)
            if msgsend:
                await self.client.send_message(user, msgsend)
                await utils.answer(message, self.strings["succesfully_send"])
            else:
                await utils.answer(message, self.strings["no_args"])
        except Exception as e:
            await utils.answer(message, f"<pre><code class='language-python'>{e}</code></pre>")