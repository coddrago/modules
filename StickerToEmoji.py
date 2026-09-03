# ---------------------------------------------------------------------------------
# ░█▀▄░▄▀▀▄░█▀▄░█▀▀▄░█▀▀▄░█▀▀▀░▄▀▀▄░░░█▀▄▀█
# ░█░░░█░░█░█░█░█▄▄▀░█▄▄█░█░▀▄░█░░█░░░█░▀░█
# ░▀▀▀░░▀▀░░▀▀░░▀░▀▀░▀░░▀░▀▀▀▀░░▀▀░░░░▀░░▒▀
# Name: StickerToEmoji
# Description: Convert static, TGS animated, and WEBM video stickers/packs into custom Telegram emoji packs
# Author: @codrago_m
# ---------------------------------------------------------------------------------
# 🔒    Licensed under the GNU AGPLv3
# 🌐 https://www.gnu.org/licenses/agpl-3.0.html
# ---------------------------------------------------------------------------------
# Author: @codrago
# Commands: s2e, s1e
# scope: heroku_only
# scope: ffmpeg
# meta developer: @codrago_m
# meta banner: https://raw.githubusercontent.com/coddrago/modules/refs/heads/main/banner.png
# requires: pillow
# ---------------------------------------------------------------------------------

import asyncio
import io
import os
import random
import shutil
import string
import tempfile
from PIL import Image

from telethon.errors import YouBlockedUserError
from telethon.tl.functions.messages import GetStickerSetRequest
from telethon.tl.types import (
    DocumentAttributeSticker,
    InputStickerSetID,
    InputStickerSetShortName,
)

from .. import loader, utils


@loader.tds
class StickerToEmojiMod(loader.Module):
    """Converts stickers and sticker packs (static, TGS, and WEBM) into custom Telegram emoji packs."""

    strings = {
        "name": "StickerToEmoji",
        "no_args": (
            "<tg-emoji emoji-id=5253864872780769235>❗️</tg-emoji> "
            "Reply to a sticker or provide a sticker pack link/shortname."
        ),
        "no_reply": (
            "<tg-emoji emoji-id=5253864872780769235>❗️</tg-emoji> "
            "Reply to a sticker to convert it into an emoji pack."
        ),
        "fetch_err": (
            "<tg-emoji emoji-id=5253864872780769235>❗️</tg-emoji> "
            "Failed to fetch sticker pack: <code>{}</code>"
        ),
        "empty_pack": (
            "<tg-emoji emoji-id=5253864872780769235>❗️</tg-emoji> "
            "Sticker pack is empty."
        ),
        "no_stickers": (
            "<tg-emoji emoji-id=5253864872780769235>❗️</tg-emoji> "
            "No suitable stickers of type <code>{}</code> found."
        ),
        "unsupported": (
            "<tg-emoji emoji-id=5253864872780769235>❗️</tg-emoji> "
            "Unsupported sticker format."
        ),
        "no_ffmpeg": (
            "<tg-emoji emoji-id=5253864872780769235>❗️</tg-emoji> "
            "FFmpeg is required on the server to convert video stickers (.webm)."
        ),
        "loading": (
            "<tg-emoji emoji-id=4911656069207426158>💘</tg-emoji> "
            "<i>Fetching sticker info...</i>"
        ),
        "processing": (
            "<tg-emoji emoji-id=4911656069207426158>💘</tg-emoji> "
            "Creating <b>{}</b> emojis «<b>{}</b>»\n"
            "<b>Progress:</b> <code>{}/{}</code>"
        ),
        "success": (
            "<tg-emoji emoji-id=4911656069207426158>💘</tg-emoji> "
            "Emoji pack successfully created!\n\n"
            "<b>Title:</b> <code>{}</code>\n"
            "<b>Type:</b> <code>{}</code>\n"
            "<b>Link:</b> <a href='{}'>Add Emoji Pack</a>"
        ),
        "bot_error": (
            "<tg-emoji emoji-id=5253864872780769235>❗️</tg-emoji> "
            "Response from @Stickers:\n<code>{}</code>"
        ),
        "unblock": (
            "<tg-emoji emoji-id=5253864872780769235>❗️</tg-emoji> "
            "Unblock @Stickers to continue."
        ),
        "error": (
            "<tg-emoji emoji-id=5253864872780769235>❗️</tg-emoji> "
            "Error: <code>{}</code>"
        ),
    }

    strings_ru = {
        "no_args": (
            "<tg-emoji emoji-id=5253864872780769235>❗️</tg-emoji> "
            "Ответьте на стикер или укажите ссылку/шортнейм пака."
        ),
        "no_reply": (
            "<tg-emoji emoji-id=5253864872780769235>❗️</tg-emoji> "
            "Ответьте на стикер, чтобы превратить его в эмодзи-пак."
        ),
        "fetch_err": (
            "<tg-emoji emoji-id=5253864872780769235>❗️</tg-emoji> "
            "Не удалось найти стикерпак: <code>{}</code>"
        ),
        "empty_pack": (
            "<tg-emoji emoji-id=5253864872780769235>❗️</tg-emoji> "
            "Стикерпак пуст."
        ),
        "no_stickers": (
            "<tg-emoji emoji-id=5253864872780769235>❗️</tg-emoji> "
            "Не найдено подходящих стикеров типа <code>{}</code>."
        ),
        "unsupported": (
            "<tg-emoji emoji-id=5253864872780769235>❗️</tg-emoji> "
            "Неподдерживаемый формат стикера."
        ),
        "no_ffmpeg": (
            "<tg-emoji emoji-id=5253864872780769235>❗️</tg-emoji> "
            "Для конвертации видео-стикеров (.webm) необходим FFmpeg на сервере."
        ),
        "loading": (
            "<tg-emoji emoji-id=4911656069207426158>💘</tg-emoji> "
            "<i>Получаю информацию о стикере...</i>"
        ),
        "processing": (
            "<tg-emoji emoji-id=4911656069207426158>💘</tg-emoji> "
            "Создаю <b>{}</b> эмодзи «<b>{}</b>»\n"
            "<b>Прогресс:</b> <code>{}/{}</code>"
        ),
        "success": (
            "<tg-emoji emoji-id=4911656069207426158>💘</tg-emoji> "
            "Эмодзи-пак успешно создан!\n\n"
            "<b>Название:</b> <code>{}</code>\n"
            "<b>Тип:</b> <code>{}</code>\n"
            "<b>Ссылка:</b> <a href='{}'>Добавить эмодзи</a>"
        ),
        "bot_error": (
            "<tg-emoji emoji-id=5253864872780769235>❗️</tg-emoji> "
            "Ответ от @Stickers:\n<code>{}</code>"
        ),
        "unblock": (
            "<tg-emoji emoji-id=5253864872780769235>❗️</tg-emoji> "
            "Разблокируйте @Stickers для корректной работы."
        ),
        "error": (
            "<tg-emoji emoji-id=5253864872780769235>❗️</tg-emoji> "
            "Ошибка: <code>{}</code>"
        ),
    }

    async def s2ecmd(self, message):
        """<pack link/shortname or reply to sticker> — convert whole sticker pack into Premium Emoji"""
        reply = await message.get_reply_message()
        args = utils.get_args_raw(message)

        sticker_set = None

        if reply and reply.document:
            for attr in reply.document.attributes:
                if isinstance(attr, DocumentAttributeSticker) and attr.stickerset:
                    if isinstance(attr.stickerset, InputStickerSetShortName):
                        sticker_set = attr.stickerset
                    elif isinstance(attr.stickerset, InputStickerSetID):
                        sticker_set = InputStickerSetID(
                            id=attr.stickerset.id,
                            access_hash=attr.stickerset.access_hash,
                        )
                    break

        if not sticker_set and args:
            pack_name = args.strip().split("/")[-1]
            sticker_set = InputStickerSetShortName(short_name=pack_name)

        if not sticker_set:
            await utils.answer(message, self.strings("no_args", message))
            return

        status = await utils.answer(message, self.strings("loading", message))

        try:
            full_set = await message.client(
                GetStickerSetRequest(stickerset=sticker_set, hash=0)
            )
        except Exception as exc:
            await utils.answer(status, self.strings("fetch_err", message).format(exc))
            return

        all_docs = full_set.documents
        if not all_docs:
            await utils.answer(status, self.strings("empty_pack", message))
            return

        is_anim = getattr(full_set.set, "animated", False) or any(
            d.mime_type == "application/x-tgsticker" for d in all_docs[:3]
        )
        is_video = getattr(full_set.set, "videos", False) or any(
            d.mime_type in ("video/webm", "video/mp4") for d in all_docs[:3]
        )

        if is_anim:
            pack_type = "animated"
            button_name = "Animated Emoji"
            docs = [d for d in all_docs if d.mime_type == "application/x-tgsticker"]
        elif is_video:
            pack_type = "video"
            button_name = "Video Emoji"
            if not shutil.which("ffmpeg"):
                await utils.answer(status, self.strings("no_ffmpeg", message))
                return
            docs = [d for d in all_docs if d.mime_type in ("video/webm", "video/mp4")]
        else:
            pack_type = "static"
            button_name = "Static Emoji"
            docs = [d for d in all_docs if d.mime_type in ("image/webp", "image/png")]

        total = len(docs)
        if total == 0:
            await utils.answer(
                status, self.strings("no_stickers", message).format(pack_type)
            )
            return

        docs = docs[:200]
        clean_name = "".join(
            c for c in getattr(full_set.set, "short_name", "pack")
            if c.isalnum() or c == "_"
        )[:16]
        title = f"{full_set.set.title[:50]} Emojis"

        await self._create_pack(
            message=message,
            status=status,
            docs=docs,
            pack_type=pack_type,
            button_name=button_name,
            title=title,
            clean_name=clean_name,
        )

    async def s1ecmd(self, message):
        """<reply to sticker> [title] — convert single replied sticker into a Premium Emoji pack"""
        reply = await message.get_reply_message()
        if not reply or not reply.document:
            await utils.answer(message, self.strings("no_reply", message))
            return

        is_sticker = any(
            isinstance(attr, DocumentAttributeSticker)
            for attr in reply.document.attributes
        )
        mime = reply.document.mime_type or ""

        if not is_sticker and not mime.startswith(
            ("image/", "video/", "application/x-tgsticker")
        ):
            await utils.answer(message, self.strings("unsupported", message))
            return

        status = await utils.answer(message, self.strings("loading", message))
        doc = reply.document

        if mime == "application/x-tgsticker":
            pack_type = "animated"
            button_name = "Animated Emoji"
        elif mime in ("video/webm", "video/mp4"):
            pack_type = "video"
            button_name = "Video Emoji"
            if not shutil.which("ffmpeg"):
                await utils.answer(status, self.strings("no_ffmpeg", message))
                return
        elif mime in ("image/webp", "image/png", "image/jpeg"):
            pack_type = "static"
            button_name = "Static Emoji"
        else:
            await utils.answer(status, self.strings("unsupported", message))
            return

        args = utils.get_args_raw(message)
        rnd_hash = "".join(random.choices(string.ascii_lowercase + string.digits, k=6))
        title = args.strip()[:50] if args else f"Emoji {rnd_hash.upper()}"
        clean_name = f"s_{rnd_hash}"

        await self._create_pack(
            message=message,
            status=status,
            docs=[doc],
            pack_type=pack_type,
            button_name=button_name,
            title=title,
            clean_name=clean_name,
        )

    async def _create_pack(
        self,
        message,
        status,
        docs: list,
        pack_type: str,
        button_name: str,
        title: str,
        clean_name: str,
    ):
        total = len(docs)
        rnd_hash = "".join(random.choices(string.ascii_lowercase + string.digits, k=6))
        short_name = f"e_{rnd_hash}_{clean_name}"[:32]

        await utils.answer(
            status,
            self.strings("processing", message).format(pack_type, title, 0, total),
        )

        try:
            async with message.client.conversation("@Stickers", timeout=60) as conv:
                await conv.send_message("/cancel")
                try:
                    await conv.get_response()
                except Exception:
                    pass

                await conv.send_message("/newemojipack")
                res = await conv.get_response()

                selected = False
                if res.buttons:
                    for row in res.buttons:
                        for btn in row:
                            if pack_type in btn.text.lower():
                                await btn.click()
                                selected = True
                                break
                        if selected:
                            break
                if not selected:
                    await conv.send_message(button_name)

                await conv.get_response()

                await conv.send_message(title)
                await conv.get_response()

                for idx, doc in enumerate(docs, start=1):
                    emoji = "⭐"
                    for attr in doc.attributes:
                        if isinstance(attr, DocumentAttributeSticker) and attr.alt:
                            emoji = attr.alt
                            break

                    raw = await message.client.download_media(doc, bytes)

                    if pack_type == "animated":
                        file_obj = io.BytesIO(raw)
                        file_obj.name = "emoji.tgs"
                        mime = "application/x-tgsticker"
                    elif pack_type == "video":
                        file_obj = await self._resize_video(raw)
                        mime = "video/webm"
                    else:
                        file_obj = self._resize_static(raw)
                        mime = "image/png"

                    await conv.send_file(file_obj, force_document=True, mime_type=mime)
                    await conv.get_response()

                    await conv.send_message(emoji)
                    await conv.get_response()

                    if idx % 5 == 0 or idx == total:
                        await utils.answer(
                            status,
                            self.strings("processing", message).format(
                                pack_type, title, idx, total
                            ),
                        )
                    await asyncio.sleep(0.5)

                await conv.send_message("/publish")
                await conv.get_response()

                await conv.send_message("/skip")
                await conv.get_response()

                await conv.send_message(short_name)
                final_res = await conv.get_response()

                if "https://t.me/addemoji/" in final_res.text:
                    link = f"https://t.me/addemoji/{short_name}"
                    await utils.answer(
                        status,
                        self.strings("success", message).format(
                            title, pack_type, link
                        ),
                    )
                else:
                    await utils.answer(
                        status,
                        self.strings("bot_error", message).format(final_res.text),
                    )

        except YouBlockedUserError:
            await utils.answer(status, self.strings("unblock", message))
        except Exception as exc:
            await utils.answer(status, self.strings("error", message).format(exc))

    @staticmethod
    def _resize_static(image_bytes: bytes) -> io.BytesIO:
        im = Image.open(io.BytesIO(image_bytes)).convert("RGBA")
        im.thumbnail((100, 100), Image.Resampling.LANCZOS)
        canvas = Image.new("RGBA", (100, 100), (0, 0, 0, 0))
        canvas.paste(im, ((100 - im.width) // 2, (100 - im.height) // 2))

        output = io.BytesIO()
        output.name = "emoji.png"
        canvas.save(output, format="PNG")
        output.seek(0)
        return output

    @staticmethod
    async def _resize_video(video_bytes: bytes) -> io.BytesIO:
        with tempfile.NamedTemporaryFile(suffix=".webm", delete=False) as in_file:
            in_path = in_file.name
            in_file.write(video_bytes)

        out_path = in_path + "_out.webm"
        try:
            proc = await asyncio.create_subprocess_exec(
                "ffmpeg",
                "-y",
                "-i",
                in_path,
                "-t",
                "3",
                "-vf",
                "scale=100:100:force_original_aspect_ratio=decrease,pad=100:100:(ow-iw)/2:(oh-ih)/2:color=0x00000000",
                "-c:v",
                "libvpx-vp9",
                "-b:v",
                "200k",
                "-r",
                "30",
                "-an",
                out_path,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.PIPE,
            )
            _, stderr = await proc.communicate()
            if proc.returncode != 0:
                raise RuntimeError(f"FFmpeg error: {stderr.decode(errors='ignore')}")

            with open(out_path, "rb") as f:
                output = io.BytesIO(f.read())
            output.name = "emoji.webm"
            output.seek(0)
            return output
        finally:
            if os.path.exists(in_path):
                os.remove(in_path)
            if os.path.exists(out_path):
                os.remove(out_path)
