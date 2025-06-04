# ---------------------------------------------------------------------------------
#░█▀▄░▄▀▀▄░█▀▄░█▀▀▄░█▀▀▄░█▀▀▀░▄▀▀▄░░░█▀▄▀█
#░█░░░█░░█░█░█░█▄▄▀░█▄▄█░█░▀▄░█░░█░░░█░▀░█
#░▀▀▀░░▀▀░░▀▀░░▀░▀▀░▀░░▀░▀▀▀▀░░▀▀░░░░▀░░▒▀
# Name: LastFM
# Description: Module for music from different services
# Author: @codrago_m
# ---------------------------------------------------------------------------------
# 🔒    Licensed under the GNU AGPLv3
# 🌐 https://www.gnu.org/licenses/agpl-3.0.html
# ---------------------------------------------------------------------------------
# Author: @codrago
# Commands: nowplay
# scope: heroku_only
# meta developer: @codrago_m
# meta banner: https://raw.githubusercontent.com/coddrago/modules/refs/heads/main/banner.png
# meta pic: https://envs.sh/Hob.webp
# ---------------------------------------------------------------------------------

from .. import loader, utils 
from herokutl import events
import requests
import asyncio


@loader.tds
class lastfmmod(loader.Module):
    """Module for music from different services"""
    def __init__(self):
        self.config = loader.ModuleConfig(
            loader.ConfigValue(
                "username_lastfm",
                None,
                lambda: self.strings["_doc_username_lastfm"],
            ),
            loader.ConfigValue(
                "text",
                "<emoji document_id=6007938409857815902>🎧</emoji> <b>now playing...</b>\n"
                "<emoji document_id=5915480455603295660>🎶</emoji><b> playlist: </b><code>{song_album}</code>\n"
                "<emoji document_id=5891249688933305846>🎵</emoji> <b>track:</b> <code>{song_name}</code>\n"
                "<emoji document_id=5897554554894946515>🎤</emoji> <b>artist:</b> <code>{song_artist}</code>",
                lambda: self.strings["_doc_text"],
            ),
        )

    strings = {
        "name": "LastFm",
        "loading":"<emoji document_id=5873204392429096339>⌨️</emoji> Loading song...",
        "bot_no_result": "<emoji document_id=5465665476971471368>❌</emoji> Nothing found.\nTitle: {song_name}\nAuthor: {song_artist}\nAlbum:{song_album}",
        "_doc_text": "The text that will be written next to the file",
        "_doc_username_lastfm": "Your username from last.fm",
        "nick_error": "<emoji document_id=5465665476971471368>❌</emoji> Put your nickname from last.fm",
        "tutorial": "Go to last.fm and register.\nBE SURE to remember the username and password, they will come in handy later.\nLet's look at the VK version\nAfter that, go to the @vkxci channel, download VK X and log in to your VK account, then go to settings and click «Integrations», select Last FM.\nEnter the username and password.\nThen you're almost done!\nWrite <code>{prefix}fcfg lastfm username_lastfm</code> {username}\nUse the <code>{prefix}nowplay</code> command and enjoy life!",
    }

    strings_ru = {
        "name": "LastFm",
        "loading": "<emoji document_id=5873204392429096339>⌨️</emoji> Загрузка трека...",
        "bot_no_result": "<emoji document_id=5465665476971471368>❌</emoji> Ничего не найдено.\nНазвание: {song_name}\nИсполнитель: {song_artist}\nАльбом: {song_album}",
        "_doc_text": "Текст, который будет написан рядом с файлом",
        "_doc_username_lastfm": "Ваш username с last.fm",
        "nick_error": "<emoji document_id=5465665476971471368>❌</emoji> Укажите ваш никнейм с last.fm",
        "tutorial": "Зайдите на last.fm и зарегистрируйтесь.\nОБЯЗАТЕЛЬНО запомните логин и пароль, они пригодятся позже.\nРассмотрим вариант для VK\nПосле этого зайдите в канал @vkxci, скачайте VK X и авторизуйтесь в своём аккаунте VK, затем зайдите в настройки и нажмите «Интеграции», выберите Last FM.\nВведите логин и пароль.\nЗатем вы почти закончили!\nНапишите <code>{prefix}fcfg lastfm username_lastfm</code> {username}\nИспользуйте команду <code>{prefix}nowplay</code> и наслаждайтесь жизнью!",
    }

    @loader.command(alias="np")
    async def nowplay(self, message):
        """| send playing track"""

        lastfm_username = self.config["username_lastfm"]
        API_KEY = "460cda35be2fbf4f28e8ea7a38580730" # Облегчение жизни школьникам

        if not lastfm_username:
            response_text = self.strings["nick_error"]
            await self.invoke("config", "lastfm", message=message)
            await utils.answer(message, response_text)
        else:
            try:
                current_track_url = f'http://ws.audioscrobbler.com/2.0/?method=user.getrecenttracks&nowplaying=true&user={lastfm_username}&api_key={API_KEY}&format=json'
                response = requests.get(current_track_url)
                data = response.json()

                if 'recenttracks' in data and 'track' in data['recenttracks'] and data['recenttracks']['track']:
                    nowplaying_track = None
                    for track in data['recenttracks']['track']:
                        if '@attr' in track and 'nowplaying' in track['@attr']:
                            nowplaying_track = track
                            break

                    if nowplaying_track:
                        song_name = nowplaying_track.get('name', 'Unknown song')
                        song_artist = nowplaying_track.get('artist', {}).get('#text', 'Unknown Artist')
                        if nowplaying_track.get('album', {}).get('#text') == nowplaying_track.get('name'):
                            song_album = "single"
                        else:
                            song_album = nowplaying_track.get('album', {}).get('#text', 'Unknown Album')
                        response_text = f"/search {song_name} - {song_artist}"

                        try:
                            async with message.client.conversation("@LyaDownbot") as conv:
                                await conv.send_message(response_text)
                                while True:
                                    response_bot = await conv.get_response()
                                    if "Не удалось найти трек" in response_bot.text:
                                        await utils.answer(message, self.strings["bot_no_result"])
                                        return
                                        
                                    if "Ищем треки..." in response_bot.text:
                                        await utils.answer(message, self.strings["loading"])

                                    if response_bot.media:
                                        await message.client.send_file(message.chat_id, response_bot.media, caption = self.config["text"].format(song_artist=song_artist, song_album=song_album, song_name=song_name))
                                        await message.delete()
                                        return
                        except Exception as e:
                            await utils.answer(message, f"<pre><code class='language-python'>{e}</code></pre>")
            except Exception as e:
                await utils.answer(message, f"<pre><code class='language-python'>{e}</code></pre>")

    @loader.command()
    async def tutorl(self, message):
        """| tutorial"""

        await utils.answer(message, self.strings['tutorial'].format(prefix = self.get_prefix(), username="{username}"))
