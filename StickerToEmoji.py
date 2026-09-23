# ---------------------------------------------------------------------------------
# ░█▀▄░▄▀▀▄░█▀▄░█▀▀▄░█▀▀▄░█▀▀▀░▄▀▀▄░░░█▀▄▀█
# ░█░░░█░░█░█░█░█▄▄▀░█▄▄█░█░▀▄░█░░█░░░█░▀░█
# ░▀▀▀░░▀▀░░▀▀░░▀░▀▀░▀░░▀░▀▀▀▀░░▀▀░░░░▀░░▒▀
# Name: StickerToEmoji
# Description: Convert static, TGS animated, and WEBM video stickers/packs into custom Telegram emoji packs directly via Telegram API
# Author: @codrago_m
# ---------------------------------------------------------------------------------
# 🔒    Licensed under the GNU AGPLv3
# 🌐 https://www.gnu.org/licenses/agpl-3.0.html
# ---------------------------------------------------------------------------------
# Commands: s2e, s1e
# scope: heroku_only
# scope: ffmpeg
# meta developer: @codrago_m
# meta banner: https://raw.githubusercontent.com/coddrago/modules/refs/heads/main/banner.png
# requires: pillow
# ---------------------------------------------------------------------------------

import asyncio
import contextlib
import io
import os
import random
import re
import shutil
import string
import tempfile
from PIL import Image

from telethon.errors import FloodWaitError
from telethon.tl import functions, types
from telethon.tl.functions.messages import GetStickerSetRequest, UploadMediaRequest
from telethon.tl.types import (
    DocumentAttributeCustomEmoji,
    DocumentAttributeFilename,
    DocumentAttributeImageSize,
    DocumentAttributeSticker,
    DocumentAttributeVideo,
    InputDocument,
    InputMediaUploadedDocument,
    InputPeerSelf,
    InputStickerSetEmpty,
    InputStickerSetID,
    InputStickerSetItem,
    InputStickerSetShortName,
    InputUserSelf,
    Message,
)

from .. import loader, utils

MAX_EMOJI_VIDEO_SIZE = 63 * 1024


@loader.tds
class StickerToEmojiMod(loader.Module):
    """Converts stickers and sticker packs (static, TGS, and WEBM) into custom Telegram emoji packs via Telegram API."""

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
        "btn_add": "Add Pack",
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
        "btn_add": "Добавить пак",
        "error": (
            "<tg-emoji emoji-id=5253864872780769235>❗️</tg-emoji> "
            "Ошибка: <code>{}</code>"
        ),
    }

    @staticmethod
    def _clean_short_name(raw_name: str) -> str:
        name = re.sub(r"_by_.*$", "", raw_name, flags=re.IGNORECASE)
        name = re.sub(r"[^a-zA-Z0-9_]", "", name)
        name = re.sub(r"_+", "_", name).strip("_")
        name = name[:16].rstrip("_")
        return name or "pack"

    @loader.command(
        ru_doc="<пак / реплай> — конвертировать стикерпак в Premium Emoji через API",
        en_doc="<pack / reply> — convert sticker pack into Premium Emoji via API",
    )
    async def s2ecmd(self, message: Message):
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
            await self.inline.form(
                text=self.strings("no_args", message),
                message=message,
                silent=True,
            )
            return

        form = await self.inline.form(
            text=self.strings("loading", message),
            message=message,
            silent=True,
        )

        try:
            full_set = await message.client(
                GetStickerSetRequest(stickerset=sticker_set, hash=0)
            )
        except Exception as exc:
            with contextlib.suppress(Exception):
                await form.edit(
                    text=self.strings("fetch_err", message).format(exc),
                    reply_markup=None,
                )
            return

        all_docs = full_set.documents
        if not all_docs:
            with contextlib.suppress(Exception):
                await form.edit(
                    text=self.strings("empty_pack", message),
                    reply_markup=None,
                )
            return

        is_anim = getattr(full_set.set, "animated", False) or any(
            d.mime_type == "application/x-tgsticker" for d in all_docs[:3]
        )
        is_video = getattr(full_set.set, "videos", False) or any(
            d.mime_type in ("video/webm", "video/mp4") for d in all_docs[:3]
        )

        if is_anim:
            pack_type = "animated"
            docs = [d for d in all_docs if d.mime_type == "application/x-tgsticker"]
        elif is_video:
            pack_type = "video"
            if not shutil.which("ffmpeg"):
                with contextlib.suppress(Exception):
                    await form.edit(
                        text=self.strings("no_ffmpeg", message),
                        reply_markup=None,
                    )
                return
            docs = [d for d in all_docs if d.mime_type in ("video/webm", "video/mp4")]
        else:
            pack_type = "static"
            docs = [d for d in all_docs if d.mime_type in ("image/webp", "image/png")]

        total = len(docs)
        if total == 0:
            with contextlib.suppress(Exception):
                await form.edit(
                    text=self.strings("no_stickers", message).format(pack_type),
                    reply_markup=None,
                )
            return

        docs = docs[:200]
        raw_short = getattr(full_set.set, "short_name", "") or "pack"
        clean_name = self._clean_short_name(raw_short)
        title = f"{full_set.set.title[:50]} Emojis"

        await self._create_pack(
            message=message,
            form=form,
            docs=docs,
            pack_type=pack_type,
            title=title,
            clean_name=clean_name,
        )

    @loader.command(
        ru_doc="<реплай на стикер> [название] — конвертировать стикер в отдельный эмодзи-пак через API",
        en_doc="<reply to sticker> [title] — convert single sticker into an emoji pack via API",
    )
    async def s1ecmd(self, message: Message):
        reply = await message.get_reply_message()
        if not reply or not reply.document:
            await self.inline.form(
                text=self.strings("no_reply", message),
                message=message,
                silent=True,
            )
            return

        is_sticker = any(
            isinstance(attr, DocumentAttributeSticker)
            for attr in reply.document.attributes
        )
        mime = reply.document.mime_type or ""

        if not is_sticker and not mime.startswith(
            ("image/", "video/", "application/x-tgsticker")
        ):
            await self.inline.form(
                text=self.strings("unsupported", message),
                message=message,
                silent=True,
            )
            return

        form = await self.inline.form(
            text=self.strings("loading", message),
            message=message,
            silent=True,
        )

        doc = reply.document

        if mime == "application/x-tgsticker":
            pack_type = "animated"
        elif mime in ("video/webm", "video/mp4"):
            pack_type = "video"
            if not shutil.which("ffmpeg"):
                with contextlib.suppress(Exception):
                    await form.edit(
                        text=self.strings("no_ffmpeg", message),
                        reply_markup=None,
                    )
                return
        elif mime in ("image/webp", "image/png", "image/jpeg"):
            pack_type = "static"
        else:
            with contextlib.suppress(Exception):
                await form.edit(
                    text=self.strings("unsupported", message),
                    reply_markup=None,
                )
            return

        args = utils.get_args_raw(message)
        rnd_hash = "".join(random.choices(string.ascii_lowercase + string.digits, k=6))
        title = args.strip()[:50] if args else f"Emoji {rnd_hash.upper()}"
        clean_name = f"s_{rnd_hash}"

        await self._create_pack(
            message=message,
            form=form,
            docs=[doc],
            pack_type=pack_type,
            title=title,
            clean_name=clean_name,
        )

    async def _create_pack(
        self,
        message: Message,
        form,
        docs: list,
        pack_type: str,
        title: str,
        clean_name: str,
    ):
        total = len(docs)
        me = await message.client.get_me()
        my_name = me.username or f"id{me.id}"
        rnd_hash = "".join(random.choices(string.ascii_lowercase + string.digits, k=5))
        clean_base = self._clean_short_name(clean_name)[:16]
        short_name = f"e_{rnd_hash}_{clean_base}_by_{my_name}"[:64].rstrip("_")

        with contextlib.suppress(Exception):
            await form.edit(
                text=self.strings("processing", message).format(pack_type, title, 0, total),
                reply_markup=None,
            )

        sem = asyncio.Semaphore(4)
        progress = [0]
        last_edit = [0.0]
        lock = asyncio.Lock()

        async def _update_progress():
            now = asyncio.get_event_loop().time()
            if now - last_edit[0] < 2.0:
                return
            last_edit[0] = now
            p = progress[0]
            bar_len = 12
            filled = int(p / total * bar_len)
            bar = "█" * filled + "░" * (bar_len - filled)
            with contextlib.suppress(Exception):
                await form.edit(
                    text=(
                        f"{self.strings('processing', message).format(pack_type, title, p, total)}\n"
                        f"<code>[{bar}]</code> {int(p / total * 100)}%"
                    ),
                    reply_markup=None,
                )

        async def _worker(idx: int, doc):
            emoji = "⭐"
            for attr in doc.attributes:
                if (
                    isinstance(attr, (DocumentAttributeSticker, DocumentAttributeCustomEmoji))
                    and getattr(attr, "alt", None)
                ):
                    emoji = attr.alt
                    break

            raw = await message.client.download_media(doc, bytes)
            loop = asyncio.get_running_loop()

            if pack_type == "animated":
                file_obj = io.BytesIO(raw)
                file_obj.name = "emoji.tgs"
                mime = "application/x-tgsticker"
            elif pack_type == "video":
                file_obj = await self._resize_video(raw)
                mime = "video/webm"
            else:
                file_obj = await loop.run_in_executor(None, self._resize_static, raw)
                mime = "image/webp"

            for attempt in range(3):
                try:
                    async with sem:
                        item = await self._upload_item(
                            client=message.client,
                            file_obj=file_obj,
                            mime=mime,
                            emoji_str=emoji,
                            pack_type=pack_type,
                        )
                    async with lock:
                        progress[0] += 1
                    if total > 1:
                        await _update_progress()
                    return (idx, item)
                except FloodWaitError as fwe:
                    await asyncio.sleep(fwe.seconds + 1)
                except Exception:
                    if attempt == 2:
                        return None
                    await asyncio.sleep(1)
            return None

        try:
            tasks = [_worker(i, doc) for i, doc in enumerate(docs)]
            results = await asyncio.gather(*tasks)
            valid_results = [r for r in results if r is not None]
            valid_results.sort(key=lambda x: x[0])
            items = [item for _, item in valid_results]
        except Exception as exc:
            with contextlib.suppress(Exception):
                await form.edit(
                    text=self.strings("error", message).format(exc),
                    reply_markup=None,
                )
            return

        if not items:
            with contextlib.suppress(Exception):
                await form.edit(
                    text=self.strings("no_stickers", message).format(pack_type),
                    reply_markup=None,
                )
            return

        try:
            final_sn, err = await self._safe_create_set(
                client=message.client,
                title=title,
                short_name=short_name,
                stickers=items,
            )
            if err:
                raise RuntimeError(err)

            link = f"https://t.me/addemoji/{final_sn}"
            btn_markup = [[{"text": self.strings("btn_add", message), "url": link}]]
            with contextlib.suppress(Exception):
                await form.edit(
                    text=self.strings("success", message).format(
                        title, pack_type, link
                    ),
                    reply_markup=btn_markup,
                )
        except Exception as exc:
            with contextlib.suppress(Exception):
                await form.edit(
                    text=self.strings("error", message).format(exc),
                    reply_markup=None,
                )

    async def _safe_create_set(
        self,
        client,
        title: str,
        short_name: str,
        stickers: list,
        retries: int = 3,
    ):
        for i in range(retries):
            sn = short_name if i == 0 else f"{short_name}_{i+1}"
            sn = sn[:64]
            try:
                await client(
                    functions.stickers.CreateStickerSetRequest(
                        user_id=InputUserSelf(),
                        title=title,
                        short_name=sn,
                        stickers=stickers,
                        emojis=True,
                    )
                )
                return sn, None
            except Exception as e:
                err = str(e)
                if (
                    "SHORT_NAME_OCCUPIED" in err
                    or "already exists" in err.lower()
                    or "STICKERSET_INVALID" in err
                ):
                    if i < retries - 1:
                        continue
                return None, err
        return None, "SHORT_NAME_OCCUPIED"

    @staticmethod
    async def _upload_item(
        client,
        file_obj: io.BytesIO,
        mime: str,
        emoji_str: str,
        pack_type: str,
    ) -> InputStickerSetItem:
        attr_emoji = DocumentAttributeCustomEmoji(
            alt=emoji_str,
            stickerset=InputStickerSetEmpty(),
            free=False,
            text_color=False,
        )

        if pack_type == "animated":
            mt = "application/x-tgsticker"
            fn = "emoji.tgs"
            extra_attrs = []
        elif pack_type == "video":
            mt = "video/webm"
            fn = "emoji.webm"
            extra_attrs = [
                DocumentAttributeVideo(
                    duration=3,
                    w=100,
                    h=100,
                )
            ]
        else:
            mt = "image/webp"
            fn = "emoji.webp"
            extra_attrs = [DocumentAttributeImageSize(w=100, h=100)]

        file_obj.seek(0)
        uploaded = await client.upload_file(file_obj, file_name=fn)
        media = InputMediaUploadedDocument(
            file=uploaded,
            mime_type=mt,
            attributes=[DocumentAttributeFilename(file_name=fn), attr_emoji] + extra_attrs,
        )
        r = await client(
            UploadMediaRequest(
                peer=InputPeerSelf(),
                media=media,
            )
        )
        doc = r.document
        return InputStickerSetItem(
            document=InputDocument(
                id=doc.id,
                access_hash=doc.access_hash,
                file_reference=doc.file_reference,
            ),
            emoji=emoji_str,
        )

    @staticmethod
    def _resize_static(image_bytes: bytes) -> io.BytesIO:
        im = Image.open(io.BytesIO(image_bytes)).convert("RGBA")
        im.thumbnail((100, 100), Image.Resampling.LANCZOS)

        if im.width == 100 and im.height == 100:
            output = io.BytesIO()
            output.name = "emoji.webp"
            im.save(output, format="WEBP", lossless=True)
            output.seek(0)
            return output

        canvas = Image.new("RGBA", (100, 100), (0, 0, 0, 0))
        offset = ((100 - im.width) // 2, (100 - im.height) // 2)
        canvas.alpha_composite(im, dest=offset)

        output = io.BytesIO()
        output.name = "emoji.webp"
        canvas.save(output, format="WEBP", lossless=True)
        output.seek(0)
        return output

    @staticmethod
    async def _resize_video(video_bytes: bytes) -> io.BytesIO:
        with tempfile.NamedTemporaryFile(suffix=".webm", delete=False) as in_file:
            in_path = in_file.name
            in_file.write(video_bytes)

        out_path = in_path + "_out.webm"
        try:
            presets = [
                {"crf": "34", "b": "110k", "maxrate": "130k", "bufsize": "80k"},
                {"crf": "40", "b": "80k", "maxrate": "100k", "bufsize": "60k"},
                {"crf": "48", "b": "50k", "maxrate": "65k", "bufsize": "40k"},
                {"crf": "54", "b": "35k", "maxrate": "45k", "bufsize": "30k"},
            ]

            vf_filter = (
                "format=rgba,"
                "scale=100:100:force_original_aspect_ratio=decrease:flags=bicubic,"
                "pad=100:100:(ow-iw)/2:(oh-ih)/2:color=0x00000000,"
                "format=yuva420p"
            )

            for use_vpx_dec in (True, False):
                success = False
                for preset in presets:
                    if os.path.exists(out_path):
                        os.remove(out_path)

                    cmd = ["ffmpeg", "-y"]
                    if use_vpx_dec:
                        cmd.extend(["-c:v", "libvpx-vp9"])
                    cmd.extend([
                        "-i", in_path,
                        "-t", "2.99",
                        "-vf", vf_filter,
                        "-c:v", "libvpx-vp9",
                        "-pix_fmt", "yuva420p",
                        "-auto-alt-ref", "0",
                        "-metadata:s:v:0", "alpha_mode=1",
                        "-crf", preset["crf"],
                        "-b:v", preset["b"],
                        "-minrate", "20k",
                        "-maxrate", preset["maxrate"],
                        "-bufsize", preset["bufsize"],
                        "-r", "30",
                        "-an",
                        out_path,
                    ])

                    proc = await asyncio.create_subprocess_exec(
                        *cmd,
                        stdout=asyncio.subprocess.DEVNULL,
                        stderr=asyncio.subprocess.PIPE,
                    )
                    _, stderr = await proc.communicate()

                    if proc.returncode == 0 and os.path.exists(out_path):
                        if os.path.getsize(out_path) <= MAX_EMOJI_VIDEO_SIZE:
                            success = True
                            break
                    else:
                        break

                if success:
                    break

            if not os.path.exists(out_path) or os.path.getsize(out_path) == 0:
                raise RuntimeError("Failed to compress video sticker with transparency")

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
