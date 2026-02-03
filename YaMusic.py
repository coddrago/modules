__version__ = (3, 2, 0)
# meta banner: https://raw.githubusercontent.com/kamekuro/hikka-mods/main/banners/yamusic.png
# packurl: https://raw.githubusercontent.com/coddrago/modules/refs/heads/dev/translations/yamusic.yml
# meta developer: @codrago
# old meta dev: @kamekuro xuesos
# scope: heroku_only
# scope: heroku_min 1.7.2
# requires: aiohttp asyncio pillow>=10.0.0 git+https://github.com/MarshalX/yandex-music-api

import aiohttp
import asyncio
import io
import json
import logging
import random
import string
import typing
import time
import uuid
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

import telethon
import yandex_music
import yandex_music.exceptions

from .. import loader, utils

logger = logging.getLogger(__name__)


class Banners:
    def __init__(
        self,
        title: str,
        artists: list[str],
        duration: int,
        progress: int,
        track_cover: bytes,
        fonts_data: list[bytes],
        album_title: str = "Сингл",
        meta_info: str = "Music",
        is_liked: bool = False,
        repeat_mode: str = "NONE",
        blur: int = 0,
    ):
        self.title = title
        self.artists = artists
        self.duration = duration
        self.progress = progress
        self.track_cover = track_cover
        self.fonts_data = fonts_data
        self.album_title = album_title
        self.meta_info = meta_info
        self.is_liked = is_liked
        self.repeat_mode = repeat_mode
        self.blur = blur

    def ultra(self) -> io.BytesIO:
        WIDTH, HEIGHT = 2560, 1220

        def get_font(size):
            for font_bytes in self.fonts_data:
                try:
                    return ImageFont.truetype(io.BytesIO(font_bytes), size)
                except Exception:
                    continue
            return ImageFont.load_default()

        try:
            original_cover = Image.open(io.BytesIO(self.track_cover)).convert("RGBA")
        except Exception:
            original_cover = Image.new("RGBA", (1000, 1000), "black")

        dominant_color_img = original_cover.resize((1, 1), Image.Resampling.LANCZOS)
        dominant_color = dominant_color_img.getpixel((0, 0))

        r, g, b, a = dominant_color
        brightness = (r * 299 + g * 587 + b * 114) / 1000
        if brightness < 60:
            r = min(255, r + 60)
            g = min(255, g + 60)
            b = min(255, b + 60)
            dominant_color = (r, g, b, 255)

        background = original_cover.copy()
        bg_w, bg_h = background.size

        target_ratio = WIDTH / HEIGHT
        current_ratio = bg_w / bg_h

        if current_ratio > target_ratio:
            new_w = int(bg_h * target_ratio)
            offset = (bg_w - new_w) // 2
            background = background.crop((offset, 0, offset + new_w, bg_h))
        else:
            new_h = int(bg_w / target_ratio)
            offset = (bg_h - new_h) // 2
            background = background.crop((0, offset, bg_w, offset + new_h))

        background = background.resize((WIDTH, HEIGHT), Image.Resampling.LANCZOS)
        
        if self.blur > 0:
            background = background.filter(ImageFilter.GaussianBlur(radius=self.blur))

        dark_overlay = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 180))
        background = Image.alpha_composite(background, dark_overlay)

        cover_size = 500
        cover_x = (WIDTH - cover_size) // 2
        cover_y = 160

        glow_layer = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
        draw_glow = ImageDraw.Draw(glow_layer)

        glow_rect_size = 620
        g_x = (WIDTH - glow_rect_size) // 2
        g_y = cover_y + (cover_size - glow_rect_size) // 2

        draw_glow.rounded_rectangle(
            (g_x, g_y, g_x + glow_rect_size, g_y + glow_rect_size),
            radius=50,
            fill=dominant_color,
        )

        glow_layer = glow_layer.filter(ImageFilter.GaussianBlur(radius=60))
        glow_layer = ImageEnhance.Brightness(glow_layer).enhance(1.4)
        glow_layer = ImageEnhance.Color(glow_layer).enhance(1.2)

        background = Image.alpha_composite(background, glow_layer)

        cover_img = original_cover.resize(
            (cover_size, cover_size), Image.Resampling.LANCZOS
        )

        mask = Image.new("L", (cover_size, cover_size), 0)
        draw_mask = ImageDraw.Draw(mask)
        draw_mask.rounded_rectangle((0, 0, cover_size, cover_size), radius=45, fill=255)

        background.paste(cover_img, (cover_x, cover_y), mask)

        draw = ImageDraw.Draw(background)
        center_x = WIDTH // 2
        current_y = cover_y + cover_size + 130

        def draw_text_shadow(text, pos, font, fill="white", anchor="ms"):
            x, y = pos
            draw.text(
                (x + 2, y + 2), text, font=font, fill=(0, 0, 0, 240), anchor=anchor
            )
            draw.text((x, y), text, font=font, fill=fill, anchor=anchor)

        font_title = get_font(100)
        title_text = self.title
        if len(title_text) > 30:
            title_text = title_text[:30] + "..."
        draw_text_shadow(title_text.upper(), (center_x, current_y), font_title)

        current_y += 85

        font_artist = get_font(65)
        artist_text = ", ".join(self.artists)
        if len(artist_text) > 45:
            artist_text = artist_text[:45] + "..."
        draw_text_shadow(
            artist_text.upper(),
            (center_x, current_y),
            font_artist,
            fill=(255, 255, 255, 240),
        )

        current_y += 80

        bar_width = 800
        bar_height = 6
        font_time = get_font(40)

        bar_start_x = center_x - (bar_width // 2)
        bar_end_x = center_x + (bar_width // 2)
        bar_y = current_y

        total_mins = self.duration // 1000 // 60
        total_secs = (self.duration // 1000) % 60
        total_time_str = f"{total_mins}:{total_secs:02d}"

        cur_mins = self.progress // 1000 // 60
        cur_secs = (self.progress // 1000) % 60
        cur_time_str = f"{cur_mins}:{cur_secs:02d}"

        draw_text_shadow(
            cur_time_str, (bar_start_x - 30, bar_y), font_time, anchor="rm"
        )
        draw_text_shadow(
            total_time_str, (bar_end_x + 30, bar_y), font_time, anchor="lm"
        )

        draw.line(
            [(bar_start_x, bar_y), (bar_end_x, bar_y)],
            fill=(255, 255, 255, 80),
            width=bar_height,
        )

        if self.duration > 0:
            progress_ratio = self.progress / self.duration
        else:
            progress_ratio = 0
        progress_px = int(bar_width * progress_ratio)
        if progress_px > bar_width:
            progress_px = bar_width

        draw.line(
            [(bar_start_x, bar_y), (bar_start_x + progress_px, bar_y)],
            fill="white",
            width=bar_height + 5,
        )
        draw.ellipse(
            (
                bar_start_x + progress_px - 10,
                bar_y - 10,
                bar_start_x + progress_px + 10,
                bar_y + 10,
            ),
            fill="white",
        )

        current_y += 80

        font_album = get_font(50)
        album_text = self.album_title
        if len(album_text) > 50:
            album_text = album_text[:50] + "..."
        draw_text_shadow(
            album_text, (center_x, current_y), font_album, fill=(230, 230, 230)
        )
        current_y += 60

        font_meta = get_font(40)

        draw_text_shadow(
            self.meta_info, (center_x, current_y), font_meta, fill=(210, 210, 210)
        )

        icon_y_center = current_y - 15

        if self.repeat_mode != "NONE":
            rep_x = bar_start_x
            rep_size = 18

            draw.arc(
                [
                    rep_x - rep_size,
                    icon_y_center - rep_size,
                    rep_x + rep_size,
                    icon_y_center + rep_size,
                ],
                start=40,
                end=320,
                fill=(220, 220, 220, 255),
                width=3,
            )

            draw.polygon(
                [
                    (rep_x + rep_size - 2, icon_y_center - 8),
                    (rep_x + rep_size + 8, icon_y_center),
                    (rep_x + rep_size - 8, icon_y_center + 4),
                ],
                fill=(220, 220, 220, 255),
            )

            if self.repeat_mode == "ONE":
                font_one = get_font(20)
                draw.text(
                    (rep_x + rep_size + 12, icon_y_center),
                    "1",
                    font=font_one,
                    fill="white",
                    anchor="lm",
                )

        heart_x = bar_end_x
        heart_size = 20

        c_r = heart_size // 2 + 2

        c1_box = (
            heart_x - c_r * 2,
            icon_y_center - c_r - 2,
            heart_x,
            icon_y_center + c_r - 2,
        )
        c2_box = (
            heart_x,
            icon_y_center - c_r - 2,
            heart_x + c_r * 2,
            icon_y_center + c_r - 2,
        )
        tri_points = [
            (heart_x - c_r * 2 + 2, icon_y_center + 1),
            (heart_x + c_r * 2 - 2, icon_y_center + 1),
            (heart_x, icon_y_center + heart_size + 5),
        ]

        by = io.BytesIO()
        background.save(by, format="PNG")
        by.seek(0)
        by.name = "banner.png"
        return by


@loader.tds
class YaMusicMod(loader.Module):
    """The module for Yandex.Music streaming service"""

    strings = {
        "name": "YaMusic"
    }

    def __init__(self):
        self.config = loader.ModuleConfig(
            loader.ConfigValue(
                option="token",
                default=None,
                doc=lambda: self.strings["_cfg"]["token"],
                validator=loader.validators.Hidden(),
            ),
            loader.ConfigValue(
                option="now_playing_text",
                default=(
                    "<emoji document_id=5474304919651491706>🎧</emoji> <b>{performer} — {title}</b>\n\n"
                    "<emoji document_id=6039404727542747508>⌨️</emoji> <b>Now is listening on <code>"
                    "{device}</code> (<emoji document_id=6039454987250044861>🔊</emoji> {volume}%)</b>\n"
                    "<emoji document_id=6039630677182254664>🗂</emoji> <b>Playing from:</b> {playing_from}"
                    "\n\n<emoji document_id=5242574232688298747>🎵</emoji> <b>{link} | "
                    '<a href="https://song.link/ya/{track_id}">song.link</a></b>'
                ),
                doc=lambda: self.strings["_cfg"]["now_playing_text"],
                validator=loader.validators.String(),
            ),
            loader.ConfigValue(
                option="autobio_text",
                default="{performer} — {title}",
                doc=lambda: self.strings["_cfg"]["autobio_text"],
                validator=loader.validators.String(),
            ),
            loader.ConfigValue(
                option="no_playing_bio_text",
                default="I use Heroku with YaMusic mod btw",
                doc=lambda: self.strings["_cfg"]["no_playing_bio_text"],
                validator=loader.validators.String(),
            ),
            loader.ConfigValue(
                option="banner_version",
                default="ultra",
                doc=lambda: self.strings["_cfg"]["banner_version"],
                validator=loader.validators.Choice(["ultra"]),
            ),
            loader.ConfigValue(
                option="blur",
                default=0,
            ),
        )

        self.ym_client = None
        self.device_id = "".join(random.choices(string.ascii_lowercase, k=16))

    async def client_ready(self, client, db):
        self._client: telethon.TelegramClient = client
        self._db = db

        utils.register_placeholder(
            "now_play", self._now_play_placeholder, "placeholder for nowplay music" 
        # Heroku 2.0.0 feature
        )
        utils.register_placeholder("duration", self._duration_placeholder, "progress bar")

        if not self.get("guide_sent", False):
            await self.inline.bot.send_message(self._tg_id, self.strings("iguide"))
            self.set("guide_sent", True)
        me = await self._client.get_me()
        self._premium = me.premium if hasattr(me, "premium") else False
        if self.get("autobio", False):
            self.autobio.start()

    async def _now_play_placeholder(self):
        """Placeholder for {now_play}"""
        if not self.config["token"]:
            return "No Token"

        try:
            now = await self.__get_now_playing()
            if not now or now.get("paused"):
                return "Not playing"

            title = now["track"]["title"]
            artists = ", ".join(now["track"]["artist"])
            return f"{title} — {artists}"
        except Exception:
            return "Error"

    async def _get_ym_client(self):
        """Lazy initialization of Yandex Music Client to prevent spamming init"""
        if not self.config["token"]:
            return None

        if self.ym_client:
            return self.ym_client

        try:
            self.ym_client = await yandex_music.ClientAsync(self.config["token"]).init()
            return self.ym_client
        except Exception as e:
            logger.error(f"Failed to init Yandex Music: {e}")
            return None

    @loader.loop(1800, autostart=True)
    async def premium_check(self):
        me = await self._client.get_me()
        self._premium = me.premium if hasattr(me, "premium") else False

    @loader.loop(30)
    async def autobio(self):
        if not self.config["token"]:
            self.autobio.stop()
            self.set("autobio", False)
            return
        now = await self.__get_now_playing()
        if now and (not now["paused"]):
            out = self.config["autobio_text"].format(
                title=now["track"]["title"],
                performer=", ".join(now["track"]["artist"]),
            )
        else:
            out = self.config["no_playing_bio_text"]
        try:
            await self._client(
                telethon.functions.account.UpdateProfileRequest(
                    about=out[: (140 if self._premium else 70)]
                )
            )
        except telethon.errors.rpcerrorlist.FloodWaitError as e:
            logger.info(f"Sleeping {max(e.seconds, 60)} because of floodwait")
            await asyncio.sleep(max(e.seconds, 60))

    @loader.command(ru_doc="👉 Гайд по получению токена Яндекс.Музыки", alias="yg")
    async def yguidecmd(self, message: telethon.types.Message):
        """👉 Guide for obtaining a Yandex.Music token"""
        await utils.answer(message, self.strings("iguide"))

    @loader.command(ru_doc="👉 Включить/выключить автобио", alias="yb")
    async def ybiocmd(self, message: telethon.types.Message):
        """👉 Enable/disable autobio"""
        client = await self._get_ym_client()
        if not client:
            return await utils.answer(
                message, self.strings("errors")["no_token_or_invalid"]
            )

        bio = not self.get("autobio", False)
        self.set("autobio", bio)
        if bio:
            await self.autobio.func(self)
            self.autobio.start()
        else:
            self.autobio.stop()
            try:
                await self._client(
                    telethon.functions.account.UpdateProfileRequest(
                        about=self.config["no_playing_bio_text"][
                            : (140 if self._premium else 70)
                        ]
                    )
                )
            except Exception:
                pass

        bio = self.get("autobio", False)
        await utils.answer(
            message, self.strings("autobio")["enabled" if bio else "disabled"]
        )

    @loader.command(ru_doc="👉 Поиск треков в Яндекс.Музыке", alias="yq")
    async def ysearchcmd(self, message: telethon.types.Message):
        """👉 Searching tracks in Yandex.Music"""
        ym_client = await self._get_ym_client()
        if not ym_client:
            return await utils.answer(
                message, self.strings("errors")["no_token_or_invalid"]
            )

        query = utils.get_args_raw(message)
        if not query:
            return await utils.answer(message, self.strings("errors")["no_query"])

        try:
            search = await ym_client.search(query, type_="track")
        except Exception:
            self.ym_client = None
            ym_client = await self._get_ym_client()
            search = await ym_client.search(query, type_="track")

        if (not search.tracks) or (len(search.tracks.results) == 0):
            return await utils.answer(message, self.strings("errors")["not_found"])

        track = search.tracks.results[0]
        out = self.strings("search").format(
            title=track.title,
            performer=", ".join(track.artists_name()),
            track_id=track.track_id,
        )
        await utils.answer(message, out + self.strings("downloading_track"))

        audio = await self.__download_track(ym_client, search.tracks.results[0].id)
        await utils.answer(
            message=message,
            response=out,
            file=audio,
            attributes=(
                [
                    telethon.types.DocumentAttributeAudio(
                        duration=int(search.tracks.results[0].duration_ms / 1000),
                        title=search.tracks.results[0].title,
                        performer=", ".join(
                            [x.name for x in search.tracks.results[0].artists]
                        ),
                    )
                ]
            ),
        )


    async def _duration_placeholder(self):
        """Placeholder for {duration} with custom emoji bar"""
        if not self.config["token"]:
            return "No Token"
        
        try:
            now = await self.__get_now_playing()
            if not now or now.get("paused"):
                return "<code>Not Playing</code>"

            duration = now.get("duration_ms", 0)
            progress = now.get("progress_ms", 0)
            
            if duration == 0:
                return "0%"
                
            percent = (progress / duration) * 100
            
            s_less_10 = (
                "<emoji document_id=5454137780454067986>➖</emoji>"
                "<emoji document_id=6158923355173949539>⭐</emoji>"
                "<emoji document_id=6159012102083188132>⭐</emoji>"
                "<emoji document_id=6159012102083188132>⭐</emoji>"
                "<emoji document_id=6158753257289158944>⭐</emoji>"
                "<emoji document_id=6156700344526049665>⭐</emoji>"
            )
            
            s_10_to_20 = (
                "<emoji document_id=5454137780454067986>➖</emoji>"
                "<emoji document_id=6159095673556840262>⭐</emoji>"
                "<emoji document_id=6159012102083188132>⭐</emoji>"
                "<emoji document_id=6156933677214341691>⭐</emoji>"
                "<emoji document_id=6158753257289158944>⭐</emoji>"
                "<emoji document_id=6156700344526049665>⭐</emoji>"
            )
            
            s_30_to_40 = (
                "<emoji document_id=5454137780454067986>➖</emoji>"
                "<emoji document_id=5454397458471750662>➖</emoji>"
                "<emoji document_id=5454397458471750662>➖</emoji>"
                "<emoji document_id=6158923355173949539>⭐</emoji>"
                "<emoji document_id=6159012102083188132>⭐</emoji>"
                "<emoji document_id=6156700344526049665>⭐</emoji>"
            )
            
            s_over_50 = (
                "<emoji document_id=5454137780454067986>➖</emoji>"
                "<emoji document_id=5454397458471750662>➖</emoji>"
                "<emoji document_id=5454397458471750662>➖</emoji>"
                "<emoji document_id=5454397458471750662>➖</emoji>"
                "<emoji document_id=6156933677214341691>⭐</emoji>"
                "<emoji document_id=6156700344526049665>⭐</emoji>"
            )

            s_over_80 = (
                "<emoji document_id=5454137780454067986>➖</emoji>"
                "<emoji document_id=5454397458471750662>➖</emoji>"
                "<emoji document_id=5454397458471750662>➖</emoji>"
                "<emoji document_id=5454397458471750662>➖</emoji>"
                "<emoji document_id=5454397458471750662>➖</emoji>"
                "<emoji document_id=6156700344526049665>⭐</emoji>"
            )

            if percent < 10:
                return s_less_10
            elif percent < 20:
                return s_10_to_20
            elif percent < 30: 
                return s_10_to_20
            elif percent < 40:
                return s_30_to_40
            elif percent < 50:
                return s_30_to_40
            elif percent < 80:
                return s_over_50
            else:
                return s_over_80

        except Exception as e:
            return f"Error: {e}"

    async def _download_bytes(self, url: str) -> typing.Optional[bytes]:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10
                ) as resp:
                    if resp.status == 200:
                        return await resp.read()
        except Exception:
            return None
        return None

    @loader.command(
        ru_doc="👉 Получить баннер трека, который играет сейчас", alias="yn"
    )
    async def ynowcmd(self, message: telethon.types.Message):
        """👉 Get the banner of the track playing right now"""
        ym_client = await self._get_ym_client()
        if not ym_client:
            return await utils.answer(
                message, self.strings("errors")["no_token_or_invalid"]
            )

        await utils.answer(message, self.strings("uploading_banner"))
        now = await self.__get_now_playing()

        if not now or now.get("paused"):
            return await utils.answer(message, self.strings("errors")["no_playing"])

        try:
            track_object = (await ym_client.tracks(now["playable_id"]))[0]
        except Exception:
            return await utils.answer(message, self.strings("errors")["error"])

        try:
            match now["entity_type"]:
                case "PLAYLIST":
                    playlist = (await ym_client.playlists_list(now["entity_id"]))[0]
                    playlist_name = (
                        f'<b><a href ="https://music.yandex.ru/users/'
                        f"{playlist.owner.login}/playlists/{playlist.kind}"
                        f'">{playlist.title}</a></b>'
                    )
                case "ALBUM":
                    album = (await ym_client.albums(now["entity_id"]))[0]
                    playlist_name = (
                        f'<b><a href ="https://music.yandex.ru/album/'
                        f'{album.id}">{album.title}</a></b>'
                    )
                case "ARTIST":
                    artist = (await ym_client.artists(now["entity_id"]))[0]
                    playlist_name = (
                        f'<b><a href ="https://music.yandex.ru/artist/'
                        f'{artist.id}">{artist.name}</a></b>'
                    )
                case _:
                    playlist_name = "Unknown"
        except Exception:
            playlist_name = "Unknown"

        if now["entity_type"] not in self.strings("_entity_types").keys():
            now["entity_type"] = "VARIOUS"

        device, volume = "Unknown Device", "❔"
        if now["device"]:
            device = now["device"][0]["info"]["title"]
            volume = round(now["device"][0]["volume"] * 100, 2)
        out = self.config["now_playing_text"].format(
            performer=", ".join(now["track"]["artist"]),
            title=now["track"]["title"],
            device=device,
            volume=volume,
            track_id=now["track"]["track_id"],
            album_id=now["track"]["album_id"],
            playing_from=self.strings("_entity_types")
            .get(now["entity_type"])
            .format(playlist_name),
            link=f"<a href=\"https://music.yandex.ru/track/{now['playable_id']}\">Яндекс.Музыка</a>",
        )
        try:
            await utils.answer(message, out + self.strings("uploading_banner"))
        except Exception:
            pass

        album_obj = track_object.albums[0] if track_object.albums else None

        album_title = album_obj.title if album_obj else "Сингл"
        year = str(album_obj.year) if album_obj and album_obj.year else ""
        genre_raw = album_obj.genre if album_obj and album_obj.genre else "music"

        genre_map = {
            "rusrap": "Русский рэп",
            "pop": "Поп",
            "rock": "Рок",
            "alternative": "Альтернатива",
            "electronics": "Электроника",
            "hip-hop": "Хип-хоп",
            "rap": "Рэп",
            "rnb": "R&B",
            "metal": "Метал",
            "indie": "Инди",
            "folk": "Фолк",
            "soundtrack": "Саундтрек",
        }
        genre = genre_map.get(genre_raw, genre_raw.capitalize())
        meta_info = f"{year} • {genre}" if year else genre

        is_liked = False
        if hasattr(track_object, "users_likes") and track_object.users_likes:
            is_liked = True

        repeat_mode = now.get("repeat_mode", "NONE")

        cover_url = f"https://{track_object.cover_uri[:-2]}1000x1000"
        cover_bytes = await self._download_bytes(cover_url)
        if not cover_bytes:
            cover_bytes = b""

        font_urls = [
            "https://raw.githubusercontent.com/google/fonts/main/ofl/montserrat/Montserrat-Bold.ttf",
            "https://raw.githubusercontent.com/kamekuro/assets/master/fonts/Onest-Bold.ttf",
        ]
        fonts_data = []
        for f_url in font_urls:
            fb = await self._download_bytes(f_url)
            if fb:
                fonts_data.append(fb)

        banners = Banners(
            title=now["track"]["title"],
            artists=now["track"]["artist"],
            duration=now["duration_ms"],
            progress=now["progress_ms"],
            track_cover=cover_bytes,
            fonts_data=fonts_data,
            album_title=album_title,
            meta_info=meta_info,
            is_liked=is_liked,
            repeat_mode=repeat_mode,
            blur=self.config["blur"],
        )


        file = await utils.run_sync(
            getattr(banners, self.config["banner_version"], banners.ultra)
        )
        await utils.answer(message=message, response=out, file=file)

    @loader.command(ru_doc="👉 Получить трек, который играет сейчас", alias="ynt")
    async def ynowtcmd(self, message: telethon.types.Message):
        """👉 Get the track playing right now"""
        ym_client = await self._get_ym_client()
        if not ym_client:
            return await utils.answer(
                message, self.strings("errors")["no_token_or_invalid"]
            )

        await utils.answer(message, self.strings("downloading_track"))
        now = await self.__get_now_playing()

        if not now or now.get("paused"):
            return await utils.answer(message, self.strings("errors")["no_playing"])

        try:
            match now["entity_type"]:
                case "PLAYLIST":
                    playlist = (await ym_client.playlists_list(now["entity_id"]))[0]
                    playlist_name = (
                        f'<b><a href ="https://music.yandex.ru/users/'
                        f"{playlist.owner.login}/playlists/{playlist.kind}"
                        f'">{playlist.title}</a></b>'
                    )
                case "ALBUM":
                    album = (await ym_client.albums(now["entity_id"]))[0]
                    playlist_name = (
                        f'<b><a href ="https://music.yandex.ru/album/'
                        f'{album.id}">{album.title}</a></b>'
                    )
                case "ARTIST":
                    artist = (await ym_client.artists(now["entity_id"]))[0]
                    playlist_name = (
                        f'<b><a href ="https://music.yandex.ru/artist/'
                        f'{artist.id}">{artist.name}</a></b>'
                    )
                case _:
                    playlist_name = "Unknown"
        except Exception:
            playlist_name = "Unknown"

        if now["entity_type"] not in self.strings("_entity_types").keys():
            now["entity_type"] = "VARIOUS"

        device, volume = "Unknown Device", "❔"
        if now["device"]:
            device = now["device"][0]["info"]["title"]
            volume = round(now["device"][0]["volume"] * 100, 2)
        out = self.config["now_playing_text"].format(
            performer=", ".join(now["track"]["artist"]),
            title=now["track"]["title"],
            device=device,
            volume=volume,
            track_id=now["track"]["track_id"],
            album_id=now["track"]["album_id"],
            playing_from=self.strings("_entity_types")
            .get(now["entity_type"])
            .format(playlist_name),
            link=f"<a href=\"https://music.yandex.ru/track/{now['playable_id']}\">Яндекс.Музыка</a>",
        )
        try:
            await utils.answer(message, out + self.strings("downloading_track"))
        except Exception:
            pass

        await utils.answer(
            message=message,
            response=out,
            file=(await self.__download_track(ym_client, now["track"]["track_id"])),
            attributes=(
                [
                    telethon.types.DocumentAttributeAudio(
                        duration=int(now["duration_ms"] / 1000),
                        title=now["track"]["title"],
                        performer=", ".join(now["track"]["artist"]),
                    )
                ]
            ),
        )

    @loader.command(ru_doc="👉 Лайкнуть играющий сейчас трек")
    async def ylikecmd(self, message: telethon.types.Message):
        """👉 Like the track playing right now"""
        ym_client = await self._get_ym_client()
        if not ym_client:
            return await utils.answer(
                message, self.strings("errors")["no_token_or_invalid"]
            )

        now = await self.__get_now_playing()

        if not now or now.get("paused"):
            return await utils.answer(message, self.strings("errors")["no_playing"])

        await ym_client.users_likes_tracks_add(now["track"]["track_id"])
        await utils.answer(
            message,
            self.strings("likes")["liked"].format(
                track_id=now["track"]["track_id"],
                track=f"{', '.join(now['track']['artist'])} — {now['track']['title']}",
            ),
        )

    @loader.command(ru_doc="👉 Снять лайк с играющего сейчас трека")
    async def yunlikecmd(self, message: telethon.types.Message):
        """👉 Unlike the track playing right now"""
        ym_client = await self._get_ym_client()
        if not ym_client:
            return await utils.answer(
                message, self.strings("errors")["no_token_or_invalid"]
            )

        now = await self.__get_now_playing()

        if not now or now.get("paused"):
            return await utils.answer(message, self.strings("errors")["no_playing"])

        await ym_client.users_likes_tracks_remove(now["track"]["track_id"])
        await utils.answer(
            message,
            self.strings("likes")["unliked"].format(
                track_id=now["track"]["track_id"],
                track=f"{', '.join(now['track']['artist'])} — {now['track']['title']}",
            ),
        )

    @loader.command(ru_doc="👉 Дизлайкнуть играющий сейчас трек")
    async def ydislikecmd(self, message: telethon.types.Message):
        """👉 Dislike the track playing right now"""
        ym_client = await self._get_ym_client()
        if not ym_client:
            return await utils.answer(
                message, self.strings("errors")["no_token_or_invalid"]
            )

        now = await self.__get_now_playing()

        if not now or now.get("paused"):
            return await utils.answer(message, self.strings("errors")["no_playing"])

        await ym_client.users_dislikes_tracks_add(now["track"]["track_id"])
        await utils.answer(
            message,
            self.strings("likes")["disliked"].format(
                track_id=now["track"]["track_id"],
                track=f"{', '.join(now['track']['artist'])} — {now['track']['title']}",
            ),
        )

    @loader.command(ru_doc="👉 Получить текст играющего сейчас трека")
    async def ylyricscmd(self, message: telethon.types.Message):
        """👉 Get the lyrics of the track playing right now"""
        ym_client = await self._get_ym_client()
        if not ym_client:
            return await utils.answer(
                message, self.strings("errors")["no_token_or_invalid"]
            )

        now = await self.__get_now_playing()

        if not now or now.get("paused"):
            return await utils.answer(message, self.strings("errors")["no_playing"])

        try:
            lyrics = await ym_client.tracks_lyrics(now["track"]["track_id"])

            lyrics_text = "Error"
            download_url = lyrics.download_url
            if download_url:
                lyrics_bytes = await self._download_bytes(download_url)
                if lyrics_bytes:
                    lyrics_text = lyrics_bytes.decode("utf-8")

            await utils.answer(
                message,
                self.strings("lyrics").format(
                    track_id=now["track"]["track_id"],
                    track=f"{', '.join(now['track']['artist'])} — {now['track']['title']}",
                    text=lyrics_text,
                    writers=", ".join(lyrics.writers) if lyrics.writers else "Unknown",
                ),
            )
        except yandex_music.exceptions.NotFoundError:
            await utils.answer(
                message,
                self.strings("no_lyrics").format(
                    track_id=now["track"]["track_id"],
                    track=f"{', '.join(now['track']['artist'])} — {now['track']['title']}",
                ),
            )

    @loader.command(ru_doc="👉 Включить повтор одного трека")
    async def yrepeatcmd(self, message: telethon.types.Message):
        """👉 Enable track repeat (One)"""
        if not self.config["token"]:
             return await utils.answer(message, self.strings("errors")["no_token_or_invalid"])
        
        def enable_repeat(state):
            state["player_state"]["player_queue"]["options"]["repeat_mode"] = "ONE"
            return state

        if await self.__send_ynison_command(enable_repeat):
            await utils.answer(message, self.strings("repeat_on"))
        else:
            await utils.answer(message, self.strings("ynison_error"))

    @loader.command(ru_doc="👉 Отключить повтор")
    async def ydrepeatcmd(self, message: telethon.types.Message):
        """👉 Disable track repeat"""
        if not self.config["token"]:
             return await utils.answer(message, self.strings("errors")["no_token_or_invalid"])
        
        def disable_repeat(state):
            state["player_state"]["player_queue"]["options"]["repeat_mode"] = "NONE"
            return state

        if await self.__send_ynison_command(disable_repeat):
            await utils.answer(message, self.strings("repeat_off"))
        else:
            await utils.answer(message, self.strings("ynison_error"))

    @loader.command(ru_doc="👉 Следующий трек")
    async def ynextcmd(self, message: telethon.types.Message):
        """👉 Skip to next track"""
        if not self.config["token"]:
             return await utils.answer(message, self.strings("errors")["no_token_or_invalid"])
        
        def next_track(state):
            idx = state["player_state"]["player_queue"]["current_playable_index"]
            state["player_state"]["player_queue"]["current_playable_index"] = idx + 1
            state["player_state"]["player_queue"]["entity_context"] = "BASED_ON_ENTITY_BY_DEFAULT"
            return state

        if await self.__send_ynison_command(next_track):
            await utils.answer(message, self.strings("next_track"))
        else:
            await utils.answer(message, self.strings("ynison_error"))

    @loader.command(ru_doc="👉 Предыдущий трек")
    async def ybackcmd(self, message: telethon.types.Message):
        """👉 Go to previous track"""
        if not self.config["token"]:
             return await utils.answer(message, self.strings("errors")["no_token_or_invalid"])
        
        def prev_track(state):
            idx = state["player_state"]["player_queue"]["current_playable_index"]
            if idx > 0:
                state["player_state"]["player_queue"]["current_playable_index"] = idx - 1
            state["player_state"]["player_queue"]["entity_context"] = "BASED_ON_ENTITY_BY_DEFAULT"
            return state

        if await self.__send_ynison_command(prev_track):
            await utils.answer(message, self.strings("prev_track"))
        else:
            await utils.answer(message, self.strings("ynison_error"))

    @loader.command(ru_doc="<0-100> 👉 Установить громкость")
    async def yvolumecmd(self, message: telethon.types.Message):
        """<0-100> 👉 Set volume"""
        if not self.config["token"]:
             return await utils.answer(message, self.strings("errors")["no_token_or_invalid"])
        
        args = utils.get_args_raw(message)
        if not args or not args.isdigit():
             return await utils.answer(message, self.strings("volume_invalid"))
        
        vol_int = int(args)
        if vol_int < 0 or vol_int > 100:
             return await utils.answer(message, self.strings("volume_invalid"))
             
        vol_float = vol_int / 100.0
        
        def set_volume(state):
            if "device" in state["player_state"]:
                state["player_state"]["device"]["volume_info"]["volume"] = vol_float
            return state

        if await self.__send_ynison_command(set_volume):
            await utils.answer(message, self.strings("volume_set").format(vol=vol_int))
        else:
            await utils.answer(message, self.strings("ynison_error"))

    async def __download_track(
        self,
        client: yandex_music.ClientAsync,
        track_id: typing.Union[int, str],
        link_only: bool = False,
    ):
        last_exception = None
        for attempt in range(5):
            try:
                info = await client.tracks_download_info(
                    track_id, get_direct_links=True
                )
                if link_only:
                    return info[0].direct_link
                by = io.BytesIO(await info[0].download_bytes_async())
                by.name = "audio.mp3"
                return by
            except Exception as e:
                last_exception = e
                if attempt != 4:
                    await asyncio.sleep(1)
                    continue
                raise e
    
    async def __send_ynison_command(self, mutate_func: typing.Callable):
        """
        Connects to Ynison, fetches current state, applies mutation, and sends it back.
        """
        if not self.config["token"]:
            return False

        async def create_ws(token, ws_proto):
            async with aiohttp.ClientSession() as session:
                async with session.ws_connect(
                    "wss://ynison.music.yandex.ru/redirector.YnisonRedirectService/GetRedirectToYnison",
                    headers={
                        "Sec-WebSocket-Protocol": f"Bearer, v2, {json.dumps(ws_proto)}",
                        "Origin": "http://music.yandex.ru",
                        "Authorization": f"OAuth {token}",
                    },
                ) as ws:
                    response = await ws.receive()
                    return json.loads(response.data)

        ws_proto = {
            "Ynison-Device-Id": self.device_id,
            "Ynison-Device-Info": json.dumps({"app_name": "Chrome", "type": 1}),
        }

        try:
            data = await create_ws(self.config["token"], ws_proto)
            ws_proto["Ynison-Redirect-Ticket"] = data["redirect_ticket"]
            
            initial_payload = {
                "update_full_state": {
                    "player_state": {
                        "player_queue": {
                            "current_playable_index": -1,
                            "entity_id": "",
                            "entity_type": "VARIOUS",
                            "playable_list": [],
                            "options": {"repeat_mode": "NONE"},
                            "entity_context": "BASED_ON_ENTITY_BY_DEFAULT",
                            "version": {
                                "device_id": self.device_id,
                                "version": 9021243204784341000,
                                "timestamp_ms": 0,
                            },
                            "from_optional": "",
                        },
                        "status": {
                            "duration_ms": 0,
                            "paused": True,
                            "playback_speed": 1,
                            "progress_ms": 0,
                            "version": {
                                "device_id": self.device_id,
                                "version": 8321822175199937000,
                                "timestamp_ms": 0,
                            },
                        },
                    },
                    "device": {
                        "capabilities": {
                            "can_be_player": True,
                            "can_be_remote_controller": False,
                            "volume_granularity": 16,
                        },
                        "info": {
                            "device_id": self.device_id,
                            "type": "WEB",
                            "title": "Chrome Browser",
                            "app_name": "Chrome",
                        },
                        "volume_info": {"volume": 0},
                        "is_shadow": True,
                    },
                    "is_currently_active": False,
                },
                "rid": str(uuid.uuid4()),
                "player_action_timestamp_ms": 0,
                "activity_interception_type": "DO_NOT_INTERCEPT_BY_DEFAULT",
            }

            async with aiohttp.ClientSession() as session:
                async with session.ws_connect(
                    f"wss://{data['host']}/ynison_state.YnisonStateService/PutYnisonState",
                    headers={
                        "Sec-WebSocket-Protocol": f"Bearer, v2, {json.dumps(ws_proto)}",
                        "Origin": "http://music.yandex.ru",
                        "Authorization": f"OAuth {self.config['token']}",
                    },
                ) as ws:
                    await ws.send_str(json.dumps(initial_payload))
                    response = await ws.receive()
                    current_state = json.loads(response.data)
                    
                    if "player_state" not in current_state:
                         return False

                    new_state = mutate_func(current_state)
                    
                    final_payload = {
                        "update_full_state": new_state,
                        "rid": str(uuid.uuid4()),
                        "player_action_timestamp_ms": int(time.time() * 1000),
                        "activity_interception_type": "DO_NOT_INTERCEPT_BY_DEFAULT",
                    }
                    
                    await ws.send_str(json.dumps(final_payload))
                    await ws.receive() 
                    return True
        except Exception as e:
            logger.error(f"Ynison Command Error: {e}")
            return False

    async def __get_ynison(self):
        async def create_ws(token, ws_proto):
            async with aiohttp.ClientSession() as session:
                async with session.ws_connect(
                    "wss://ynison.music.yandex.ru/redirector.YnisonRedirectService/GetRedirectToYnison",
                    headers={
                        "Sec-WebSocket-Protocol": f"Bearer, v2, {json.dumps(ws_proto)}",
                        "Origin": "http://music.yandex.ru",
                        "Authorization": f"OAuth {token}",
                    },
                ) as ws:
                    response = await ws.receive()
                    return json.loads(response.data)

        ws_proto = {
            "Ynison-Device-Id": self.device_id,
            "Ynison-Device-Info": json.dumps({"app_name": "Chrome", "type": 1}),
        }

        try:
            data = await create_ws(self.config["token"], ws_proto)
            ws_proto["Ynison-Redirect-Ticket"] = data["redirect_ticket"]
            payload = {
                "update_full_state": {
                    "player_state": {
                        "player_queue": {
                            "current_playable_index": -1,
                            "entity_id": "",
                            "entity_type": "VARIOUS",
                            "playable_list": [],
                            "options": {"repeat_mode": "NONE"},
                            "entity_context": "BASED_ON_ENTITY_BY_DEFAULT",
                            "version": {
                                "device_id": self.device_id,
                                "version": 9021243204784341000,
                                "timestamp_ms": 0,
                            },
                            "from_optional": "",
                        },
                        "status": {
                            "duration_ms": 0,
                            "paused": True,
                            "playback_speed": 1,
                            "progress_ms": 0,
                            "version": {
                                "device_id": self.device_id,
                                "version": 8321822175199937000,
                                "timestamp_ms": 0,
                            },
                        },
                    },
                    "device": {
                        "capabilities": {
                            "can_be_player": True,
                            "can_be_remote_controller": False,
                            "volume_granularity": 16,
                        },
                        "info": {
                            "device_id": self.device_id,
                            "type": "WEB",
                            "title": "Chrome Browser",
                            "app_name": "Chrome",
                        },
                        "volume_info": {"volume": 0},
                        "is_shadow": True,
                    },
                    "is_currently_active": False,
                },
                "rid": "ac281c26-a047-4419-ad00-e4fbfda1cba3",
                "player_action_timestamp_ms": 0,
                "activity_interception_type": "DO_NOT_INTERCEPT_BY_DEFAULT",
            }
            async with aiohttp.ClientSession() as session:
                async with session.ws_connect(
                    f"wss://{data['host']}/ynison_state.YnisonStateService/PutYnisonState",
                    headers={
                        "Sec-WebSocket-Protocol": f"Bearer, v2, {json.dumps(ws_proto)}",
                        "Origin": "http://music.yandex.ru",
                        "Authorization": f"OAuth {self.config['token']}",
                    },
                ) as ws:
                    await ws.send_str(json.dumps(payload))
                    response = await ws.receive()
                    ynison: dict = json.loads(response.data)
            return ynison
        except Exception as e:
            logger.error(f"Ynison Error: {e}")
            return {}

    async def __get_now_playing(self):
        ym_client = await self._get_ym_client()
        if not ym_client:
            return {}

        ynison = await self.__get_ynison()
        if not ynison or (
            len(
                ynison.get("player_state", {})
                .get("player_queue", {})
                .get("playable_list", [])
            )
            == 0
        ):
            return {}

        try:
            player_state = ynison["player_state"]
            raw_track = player_state["player_queue"]["playable_list"][
                player_state["player_queue"]["current_playable_index"]
            ]

            track_object = (await ym_client.tracks(raw_track["playable_id"]))[0]

            status = player_state["status"]
            progress_ms = int(status["progress_ms"])
            duration_ms = int(status["duration_ms"])

            repeat_mode = (
                player_state.get("player_queue", {})
                .get("options", {})
                .get("repeat_mode", "NONE")
            )

            return (
                {
                    "track_object": track_object,
                    "paused": status["paused"],
                    "playable_id": raw_track["playable_id"],
                    "duration_ms": duration_ms,
                    "progress_ms": progress_ms,
                    "entity_id": player_state["player_queue"]["entity_id"],
                    "entity_type": player_state["player_queue"]["entity_type"],
                    "repeat_mode": repeat_mode,
                    "device": [
                        x
                        for x in ynison["devices"]
                        if x["info"]["device_id"]
                        == ynison.get("active_device_id_optional", "")
                    ],
                    "track": {
                        "track_id": track_object.track_id,
                        "album_id": track_object.albums[0].id
                        if track_object.albums
                        else 0,
                        "title": track_object.title,
                        "artist": track_object.artists_name(),
                        "duration": track_object.duration_ms // 1000,
                        "minutes": round(track_object.duration_ms / 1000) // 60,
                        "seconds": round(track_object.duration_ms / 1000) % 60,
                    },
                }
                if raw_track["playable_type"] != "LOCAL_TRACK"
                else {}
            )
        except Exception as e:
            logger.error(f"Get Now Playing Error: {e}")
            return {}