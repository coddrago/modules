# ---------------------------------------------------------------------------------
#░█▀▄░▄▀▀▄░█▀▄░█▀▀▄░█▀▀▄░█▀▀▀░▄▀▀▄░░░█▀▄▀█
#░█░░░█░░█░█░█░█▄▄▀░█▄▄█░█░▀▄░█░░█░░░█░▀░█
#░▀▀▀░░▀▀░░▀▀░░▀░▀▀░▀░░▀░▀▀▀▀░░▀▀░░░░▀░░▒▀
# Name: Speedtest
# Description: Module to run speedtest using speedtest library
# Author: @codrago_m
# ---------------------------------------------------------------------------------
# 🔒    Licensed under the GNU AGPLv3
# 🌐 https://www.gnu.org/licenses/agpl-3.0.html
# ---------------------------------------------------------------------------------
# Author: @codrago
# Commands: speedtest
# scope: hikka_only
# meta developer: @codrago_m
# requires: speedtest-cli
# ---------------------------------------------------------------------------------

import speedtest
from .. import loader, utils

@loader.tds
class SpeedTestMod(loader.Module):
    """Module to run speedtest using speedtest library"""

    strings = {
        "name": "SpeedTest",
        "running": "<emoji document_id=5870718740236079262>🌐</emoji> <b>Running speedtest...</b>",
        "results": "<emoji document_id=5870718740236079262>🌐</emoji> <b>Speedtest Results:</b>\n\n"
                   "<emoji document_id=5870718740236079262>🌐</emoji> <b>Download:</b> {download} Mbps\n"
                   "<emoji document_id=5870729082517328189>📊</emoji> <b>Upload:</b> {upload} Mbps\n"
                   "<emoji document_id=5222108309795908493>✨</emoji> <b>Ping:</b> {ping} ms",
        "error": "🚫 <b>Error running speedtest:</b> <code>{error}</code>",
    }
    
    strings_ru = { 
        "running": "<emoji document_id=5870718740236079262>🌐</emoji> Запуск теста скорости...",
        "results": "<emoji document_id=5870718740236079262>🌐</emoji> Результаты теста скорости:\n\n"
                   "<emoji document_id=5870718740236079262>🌐</emoji> Скачивание: {download} Мбит/с\n"
                   "<emoji document_id=5870729082517328189>📊</emoji> Загрузка: {upload} Мбит/с\n"
                   "<emoji document_id=5222108309795908493>✨</emoji> Пинг: {ping} мс",
        "error": "🚫 Ошибка при запуске теста скорости: {error}",
    }

    async def client_ready(self, client, db):
        self.client = client

    async def speedtestcmd(self, message):
        """Speedtest of your server internet"""
        await utils.answer(message, self.strings("running"))

        try:
            st = speedtest.Speedtest()
            st.download()
            st.upload()
            results = st.results.dict()

            download = results["download"] / 1_000_000  # Convert to Mbps
            upload = results["upload"] / 1_000_000  # Convert to Mbps
            ping = results["ping"]

            await utils.answer(
                message,
                self.strings("results").format(
                ping=round(ping, 2), 
                download=round(download, 2), 
                upload=round(upload, 2)
            )
        )
        except Exception as e:
            await utils.answer(message, self.strings("error").format(error=str(e)))
            