# ---------------------------------------------------------------------------------
#░█▀▄░▄▀▀▄░█▀▄░█▀▀▄░█▀▀▄░█▀▀▀░▄▀▀▄░░░█▀▄▀█
#░█░░░█░░█░█░█░█▄▄▀░█▄▄█░█░▀▄░█░░█░░░█░▀░█
#░▀▀▀░░▀▀░░▀▀░░▀░▀▀░▀░░▀░▀▀▀▀░░▀▀░░░░▀░░▒▀
# Name: Avatars
# Description: Flexible profile avatar management & auto-setter
# Author: @codrago_m
# ---------------------------------------------------------------------------------
# 🔒    Licensed under the GNU AGPLv3
# 🌐 https://www.gnu.org/licenses/agpl-3.0.html
# ---------------------------------------------------------------------------------
# Author: @codrago
# Commands: getava, delavas, setava, stopava, gifava
# scope: heroku_only
# meta developer: @codrago_m
# meta banner: https://raw.githubusercontent.com/coddrago/modules/refs/heads/main/banner.png
# ---------------------------------------------------------------------------------

import asyncio
import os
import shutil
import tempfile
import zipfile
from telethon.errors import FloodWaitError
from telethon.tl import types
from telethon.tl.functions.photos import (
    DeletePhotosRequest,
    UpdateProfilePhotoRequest,
    UploadProfilePhotoRequest,
)
from telethon.tl.functions.users import GetFullUserRequest
from telethon.tl.types import DocumentAttributeVideo, InputPhoto, InputPhotoEmpty
from .. import loader, utils


@loader.tds
class AvatarsMod(loader.Module):
    """Module for flexible profile avatar management"""

    strings = {
        "name": "Avatars",
        "no_avas": "<tg-emoji emoji-id=5287372146039861774>⛔️</tg-emoji> <b>User has no profile photos.</b>",
        "downloading": "<tg-emoji emoji-id=5872771279337033184>⬇️</tg-emoji> <b>Downloading avatar...</b>",
        "archiving": "<tg-emoji emoji-id=5872771279337033184>⬇️</tg-emoji> <b>Downloading all avatars to avatars.zip...</b>",
        "deleted": "<tg-emoji emoji-id=5255831443816327915>🗑</tg-emoji> <b>Successfully deleted avatars:</b> <code>{}</code>.",
        "deleted_public": "<tg-emoji emoji-id=5255831443816327915>🗑</tg-emoji> <b>Successfully deleted public avatar.</b>",
        "invalid_args": "<tg-emoji emoji-id=4916086774649848789>🔗</tg-emoji> <b>Specify a number, <code>all</code> or <code>-p</code>.</b>",
        "user_not_found": "<tg-emoji emoji-id=4916086774649848789>🔗</tg-emoji> <b>Specified user could not be found.</b>",
        "no_media_reply": "<tg-emoji emoji-id=4916086774649848789>🔗</tg-emoji> <b>Reply to a photo, video, or GIF.</b>",
        "unsupported_media": "<tg-emoji emoji-id=4916086774649848789>🔗</tg-emoji> <b>Only images and video files are supported.</b>",
        "avatar_set": "<tg-emoji emoji-id=4916086774649848789>🔗</tg-emoji> <b>Avatar successfully updated!</b>",
        "public_avatar_set": "<tg-emoji emoji-id=4916086774649848789>🔗</tg-emoji> <b>Public avatar successfully updated!</b>",
        "already_running": "<tg-emoji emoji-id=4916086774649848789>🔗</tg-emoji> <b>A process is already running! Stop it with <code>.stopava</code>.</b>",
        "not_running": "<tg-emoji emoji-id=4916086774649848789>🔗</tg-emoji> <b>No active avatar process found.</b>",
        "started": (
            "<tg-emoji emoji-id=4916086774649848789>🔗</tg-emoji> <b>Avatar loop process started!</b>\n"
            "<tg-emoji emoji-id=5873022839866527761>⚪️</tg-emoji> Type: <code>{}</code>\n"
            "<tg-emoji emoji-id=5873022839866527761>⚪️</tg-emoji> Amount: <code>{}</code>\n"
            "<tg-emoji emoji-id=5873022839866527761>⚪️</tg-emoji> Interval: <code>{}</code> sec."
        ),
        "progress": (
            "<tg-emoji emoji-id=4916086774649848789>🔗</tg-emoji> <b>Avatar loop in progress...</b>\n"
            "<tg-emoji emoji-id=5873022839866527761>⚪️</tg-emoji> Progress: <b>{}/{}</b>"
        ),
        "done": "<tg-emoji emoji-id=4916086774649848789>🔗</tg-emoji> <b>Successfully finished! Total avatars set:</b> <code>{}</code>.",
        "stopped": "<tg-emoji emoji-id=4916086774649848789>🔗</tg-emoji> <b>Avatar process stopped.</b>",
        "flood_wait": "<tg-emoji emoji-id=4916086774649848789>🔗</tg-emoji> <b>Telegram FloodWait received for <code>{}</code> seconds. Process stopped for safety.</b>",
        "error": "<tg-emoji emoji-id=4916086774649848789>🔗</tg-emoji> <b>Error:</b> <code>{}</code>",
        "invalid_setava_args": (
            "<tg-emoji emoji-id=4916086774649848789>🔗</tg-emoji> <b>Invalid arguments.</b>\n"
            "Usage:\n"
            "<tg-emoji emoji-id=5873022839866527761>⚪️</tg-emoji> <code>.setava [-p]</code> — set once instantly\n"
            "<tg-emoji emoji-id=5873022839866527761>⚪️</tg-emoji> <code>.setava [-p] <interval_sec> <amount></code> — start loop"
        ),
        "extracting_frames": "<tg-emoji emoji-id=4916086774649848789>🔗</tg-emoji> <b>Extracting all video frames at native FPS...</b>",
        "gifava_progress": (
            "<tg-emoji emoji-id=4916086774649848789>🔗</tg-emoji> <b>Uploading animation frames (10s delay)...</b>\n"
            "<tg-emoji emoji-id=5873022839866527761>⚪️</tg-emoji> Progress: <b>{}/{}</b>"
        ),
        "gifava_done": "<tg-emoji emoji-id=4916086774649848789>🔗</tg-emoji> <b>Animation successfully created! Total frames uploaded:</b> <code>{}</code>.",
        "no_frames": "<tg-emoji emoji-id=4916086774649848789>🔗</tg-emoji> <b>Failed to extract frames from media.</b>",
        "btn_stop": "❌ Stop",
    }

    strings_ru = {
        "name": "Avatars",
        "no_avas": "<tg-emoji emoji-id=5287372146039861774>⛔️</tg-emoji> <b>У пользователя нет аватарок.</b>",
        "downloading": "<tg-emoji emoji-id=5872771279337033184>⬇️</tg-emoji> <b>Загрузка аватарки...</b>",
        "archiving": "<tg-emoji emoji-id=5872771279337033184>⬇️</tg-emoji> <b>Загрузка всех аватарок в avatars.zip...</b>",
        "deleted": "<tg-emoji emoji-id=5255831443816327915>🗑</tg-emoji> <b>Успешно удалено аватарок:</b> <code>{}</code>.",
        "deleted_public": "<tg-emoji emoji-id=5255831443816327915>🗑</tg-emoji> <b>Публичная аватарка успешно удалена.</b>",
        "invalid_args": "<tg-emoji emoji-id=4916086774649848789>🔗</tg-emoji> <b>Укажите число, <code>all</code> или <code>-p</code>.</b>",
        "user_not_found": "<tg-emoji emoji-id=4916086774649848789>🔗</tg-emoji> <b>Не удалось найти указанного пользователя.</b>",
        "no_media_reply": "<tg-emoji emoji-id=4916086774649848789>🔗</tg-emoji> <b>Ответьте реплаем на фото, видео или GIF.</b>",
        "unsupported_media": "<tg-emoji emoji-id=4916086774649848789>🔗</tg-emoji> <b>Поддерживаются только изображения и видеофайлы.</b>",
        "avatar_set": "<tg-emoji emoji-id=4916086774649848789>🔗</tg-emoji> <b>Аватарка успешно установлена!</b>",
        "public_avatar_set": "<tg-emoji emoji-id=4916086774649848789>🔗</tg-emoji> <b>Публичная аватарка успешно установлена!</b>",
        "already_running": "<tg-emoji emoji-id=4916086774649848789>🔗</tg-emoji> <b>Процесс уже активен! Остановите его командой <code>.stopava</code>.</b>",
        "not_running": "<tg-emoji emoji-id=4916086774649848789>🔗</tg-emoji> <b>На данный момент нет активного процесса.</b>",
        "started": (
            "<tg-emoji emoji-id=4916086774649848789>🔗</tg-emoji> <b>Запущен процесс установки аватарок!</b>\n"
            "<tg-emoji emoji-id=5873022839866527761>⚪️</tg-emoji> Тип: <code>{}</code>\n"
            "<tg-emoji emoji-id=5873022839866527761>⚪️</tg-emoji> Количество: <code>{}</code> шт.\n"
            "<tg-emoji emoji-id=5873022839866527761>⚪️</tg-emoji> Интервал: <code>{}</code> сек."
        ),
        "progress": (
            "<tg-emoji emoji-id=4916086774649848789>🔗</tg-emoji> <b>Автопостановка в процессе...</b>\n"
            "<tg-emoji emoji-id=5873022839866527761>⚪️</tg-emoji> Прогресс: <b>{}/{}</b>"
        ),
        "done": "<tg-emoji emoji-id=4916086774649848789>🔗</tg-emoji> <b>Успешно завершено! Установлено аватарок:</b> <code>{}</code>.",
        "stopped": "<tg-emoji emoji-id=4916086774649848789>🔗</tg-emoji> <b>Процесс остановлен.</b>",
        "flood_wait": "<tg-emoji emoji-id=4916086774649848789>🔗</tg-emoji> <b>Telegram выдал FloodWait на <code>{}</code> сек. Процесс прерван в целях безопасности.</b>",
        "error": "<tg-emoji emoji-id=4916086774649848789>🔗</tg-emoji> <b>Ошибка:</b> <code>{}</code>",
        "invalid_setava_args": (
            "<tg-emoji emoji-id=4916086774649848789>🔗</tg-emoji> <b>Неверные аргументы.</b>\n"
            "Использование:\n"
            "<tg-emoji emoji-id=5873022839866527761>⚪️</tg-emoji> <code>.setava [-p]</code> — установить 1 раз моментально\n"
            "<tg-emoji emoji-id=5873022839866527761>⚪️</tg-emoji> <code>.setava [-p] <интервал_сек> <кол-во></code> — запустить цикл"
        ),
        "extracting_frames": "<tg-emoji emoji-id=4916086774649848789>🔗</tg-emoji> <b>Извлечение всех кадров видео в исходном FPS...</b>",
        "gifava_progress": (
            "<tg-emoji emoji-id=4916086774649848789>🔗</tg-emoji> <b>Загрузка кадров анимации (задержка 10с)...</b>\n"
            "<tg-emoji emoji-id=5873022839866527761>⚪️</tg-emoji> Прогресс: <b>{}/{}</b>"
        ),
        "gifava_done": "<tg-emoji emoji-id=4916086774649848789>🔗</tg-emoji> <b>Покадровая анимация успешно создана! Загружено кадров:</b> <code>{}</code>.",
        "no_frames": "<tg-emoji emoji-id=4916086774649848789>🔗</tg-emoji> <b>Не удалось извлечь кадры из медиа.</b>",
        "btn_stop": "❌ Остановить",
    }

    def __init__(self):
        self._task = None

    async def on_unload(self):
        if self._task and not self._task.done():
            self._task.cancel()

    async def _stop_callback(self, call):
        if self._task and not self._task.done():
            self._task.cancel()
            self._task = None
        await call.edit(self.strings("stopped"))

    async def _resolve_avatar(self, target, public=False):
        photo = None
        if not public:
            try:
                photos = await self.client.get_profile_photos(target, limit=1)
                if photos:
                    photo = photos[0]
            except Exception:
                pass

        if not photo:
            try:
                full = await self.client(GetFullUserRequest(target))
                fu = getattr(full, "full_user", full)
                if public:
                    photo = getattr(fu, "fallback_photo", None)
                else:
                    photo = getattr(fu, "fallback_photo", None) or getattr(fu, "profile_photo", None)
            except Exception:
                pass

        return photo

    async def getavacmd(self, message):
        """[reply | username/id] [all] [-p] — get current avatar or download all to avatars.zip"""
        args = utils.get_args_raw(message)
        reply = await message.get_reply_message()
        target = "me"
        public = False
        download_all = False

        if args:
            parts = args.split()
            clean_parts = []
            for part in parts:
                p_lower = part.lower()
                if p_lower in ["-p", "--public", "public", "паблик"]:
                    public = True
                elif p_lower in ["all", "все", "всё"]:
                    download_all = True
                else:
                    clean_parts.append(part)
            if clean_parts:
                target = clean_parts[0]
                if target.isdigit() or (target.startswith("-") and target[1:].isdigit()):
                    target = int(target)
            elif reply:
                target = reply.sender_id
        elif reply:
            target = reply.sender_id

        if download_all:
            await utils.answer(message, self.strings("archiving"))
            try:
                photos = await self.client.get_profile_photos(target, limit=None)
            except Exception:
                return await utils.answer(message, self.strings("user_not_found"))

            if not photos:
                try:
                    full = await self.client(GetFullUserRequest(target))
                    fu = getattr(full, "full_user", full)
                    fb = getattr(fu, "fallback_photo", None)
                    if fb:
                        photos = [fb]
                except Exception:
                    pass

            if not photos:
                return await utils.answer(message, self.strings("no_avas"))

            temp_dir = tempfile.mkdtemp()
            zip_dir = tempfile.mkdtemp()
            zip_path = os.path.join(zip_dir, "avatars.zip")

            try:
                with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
                    for idx, p in enumerate(photos, 1):
                        is_vid = bool(getattr(p, "video_sizes", None))
                        ext = ".mp4" if is_vid else ".jpg"
                        fname = f"avatar_{idx:03d}{ext}"
                        fpath = os.path.join(temp_dir, fname)
                        if is_vid:
                            await self.client.download_media(p, file=fpath, thumb=p.video_sizes[-1])
                        else:
                            await self.client.download_media(p, file=fpath)
                        zipf.write(fpath, arcname=fname)

                await utils.answer(message, "", file=zip_path)
            finally:
                shutil.rmtree(temp_dir, ignore_errors=True)
                shutil.rmtree(zip_dir, ignore_errors=True)
            return

        try:
            photo = await self._resolve_avatar(target, public=public)
        except Exception:
            return await utils.answer(message, self.strings("user_not_found"))

        if not photo:
            return await utils.answer(message, self.strings("no_avas"))

        if getattr(photo, "video_sizes", None):
            await utils.answer(message, self.strings("downloading"))
            temp_file = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False)
            temp_path = temp_file.name
            temp_file.close()

            try:
                downloaded = await self.client.download_media(
                    photo,
                    file=temp_path,
                    thumb=photo.video_sizes[-1],
                )
                await utils.answer(message, "", file=downloaded)
            finally:
                if os.path.exists(temp_path):
                    os.remove(temp_path)
        else:
            await utils.answer(message, "", file=photo)

    async def delavascmd(self, message):
        """<count | all | -p> — delete specified number of avatars, all of them, or public avatar"""
        args = utils.get_args_raw(message)
        if not args:
            return await utils.answer(message, self.strings("invalid_args"))

        args = args.lower().strip()

        if args in ["-p", "--public", "public", "паблик", "fallback"]:
            deleted_fallback = False
            try:
                full = await self.client(GetFullUserRequest("me"))
                fu = getattr(full, "full_user", full)
                fb = getattr(fu, "fallback_photo", None)
                if fb:
                    try:
                        await self.client(
                            DeletePhotosRequest(
                                id=[
                                    InputPhoto(
                                        id=fb.id,
                                        access_hash=fb.access_hash,
                                        file_reference=fb.file_reference,
                                    )
                                ]
                            )
                        )
                    except Exception:
                        pass
                await self.client(UpdateProfilePhotoRequest(id=InputPhotoEmpty(), fallback=True))
                deleted_fallback = True
            except Exception:
                pass

            if deleted_fallback:
                return await utils.answer(message, self.strings("deleted_public"))
            return await utils.answer(message, self.strings("no_avas"))

        if args in ["all", "все", "всё"]:
            photos = await self.client.get_profile_photos("me", limit=None)
            input_photos = []
            if photos:
                input_photos = [
                    InputPhoto(
                        id=p.id,
                        access_hash=p.access_hash,
                        file_reference=p.file_reference,
                    )
                    for p in photos
                ]
                chunk_size = 100
                for i in range(0, len(input_photos), chunk_size):
                    await self.client(DeletePhotosRequest(id=input_photos[i : i + chunk_size]))

            deleted_fallback = False
            try:
                full = await self.client(GetFullUserRequest("me"))
                fu = getattr(full, "full_user", full)
                fb = getattr(fu, "fallback_photo", None)
                if fb:
                    try:
                        await self.client(
                            DeletePhotosRequest(
                                id=[
                                    InputPhoto(
                                        id=fb.id,
                                        access_hash=fb.access_hash,
                                        file_reference=fb.file_reference,
                                    )
                                ]
                            )
                        )
                    except Exception:
                        pass
                await self.client(UpdateProfilePhotoRequest(id=InputPhotoEmpty(), fallback=True))
                if fb:
                    deleted_fallback = True
            except Exception:
                pass

            total_deleted = len(input_photos) + (1 if deleted_fallback else 0)
            if total_deleted == 0:
                return await utils.answer(message, self.strings("no_avas"))

            return await utils.answer(message, self.strings("deleted").format(total_deleted))

        try:
            count = int(args)
            if count <= 0:
                raise ValueError
            photos = await self.client.get_profile_photos("me", limit=count)
        except ValueError:
            return await utils.answer(message, self.strings("invalid_args"))

        if not photos:
            return await utils.answer(message, self.strings("no_avas"))

        input_photos = [
            InputPhoto(
                id=p.id,
                access_hash=p.access_hash,
                file_reference=p.file_reference,
            )
            for p in photos
        ]

        chunk_size = 100
        for i in range(0, len(input_photos), chunk_size):
            await self.client(DeletePhotosRequest(id=input_photos[i : i + chunk_size]))

        await utils.answer(message, self.strings("deleted").format(len(input_photos)))

    async def setavacmd(self, message):
        """[-p] <interval> <count> (reply) — set avatar once instantly or loop via inline form"""
        reply = await message.get_reply_message()
        if not reply or not reply.media:
            return await utils.answer(message, self.strings("no_media_reply"))

        is_video = False
        if getattr(reply, "video", None):
            is_video = True
        elif reply.document:
            if reply.document.mime_type.startswith("video/"):
                is_video = True
            elif any(isinstance(x, DocumentAttributeVideo) for x in reply.document.attributes):
                is_video = True
            elif not reply.document.mime_type.startswith("image/"):
                return await utils.answer(message, self.strings("unsupported_media"))

        raw_args = utils.get_args_raw(message)
        parts = raw_args.split() if raw_args else []
        fallback = False
        clean_parts = []
        for p in parts:
            if p.lower() in ["-p", "--public", "public", "паблик"]:
                fallback = True
            else:
                clean_parts.append(p)

        suffix = ".mp4" if is_video else ".jpg"

        if not clean_parts:
            temp_file = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
            temp_path = temp_file.name
            temp_file.close()

            try:
                await self.client.download_media(reply, file=temp_path)
                uploaded = await self.client.upload_file(temp_path)
                if is_video:
                    await self.client(
                        UploadProfilePhotoRequest(
                            video=uploaded,
                            video_start_ts=0.0,
                            fallback=fallback,
                        )
                    )
                else:
                    await self.client(
                        UploadProfilePhotoRequest(
                            file=uploaded,
                            fallback=fallback,
                        )
                    )
                success_text = (
                    self.strings("public_avatar_set")
                    if fallback
                    else self.strings("avatar_set")
                )
                return await utils.answer(message, success_text)
            except Exception as e:
                return await utils.answer(message, self.strings("error").format(e))
            finally:
                if os.path.exists(temp_path):
                    os.remove(temp_path)

        if len(clean_parts) >= 2:
            try:
                interval = float(clean_parts[0])
                count = int(clean_parts[1])
            except ValueError:
                return await utils.answer(message, self.strings("invalid_setava_args"))
        elif len(clean_parts) == 1:
            try:
                interval = 5.0
                count = int(clean_parts[0])
            except ValueError:
                return await utils.answer(message, self.strings("invalid_setava_args"))
        else:
            return await utils.answer(message, self.strings("invalid_setava_args"))

        if interval < 0 or count <= 0:
            return await utils.answer(message, self.strings("invalid_setava_args"))

        if count > 1 and interval < 1.0:
            interval = 1.0

        if self._task and not self._task.done():
            return await utils.answer(message, self.strings("already_running"))

        form = await self.inline.form(
            text=self.strings("downloading"),
            message=message,
        )

        temp_file = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
        temp_path = temp_file.name
        temp_file.close()

        try:
            await self.client.download_media(reply, file=temp_path)
        except Exception as e:
            if os.path.exists(temp_path):
                os.remove(temp_path)
            return await form.edit(text=self.strings("error").format(e))

        if count == 1:
            try:
                uploaded = await self.client.upload_file(temp_path)
                if is_video:
                    await self.client(
                        UploadProfilePhotoRequest(
                            video=uploaded,
                            video_start_ts=0.0,
                            fallback=fallback,
                        )
                    )
                else:
                    await self.client(
                        UploadProfilePhotoRequest(
                            file=uploaded,
                            fallback=fallback,
                        )
                    )
                success_text = (
                    self.strings("public_avatar_set")
                    if fallback
                    else self.strings("avatar_set")
                )
                await form.edit(text=success_text)
            except Exception as e:
                await form.edit(text=self.strings("error").format(e))
            finally:
                if os.path.exists(temp_path):
                    os.remove(temp_path)
            return

        self._task = asyncio.create_task(
            self._avatar_loop(form, temp_path, is_video, interval, count, fallback)
        )
        type_str = "Public" if fallback else "Profile"
        await form.edit(
            text=self.strings("started").format(type_str, count, interval),
            reply_markup=[
                [
                    {
                        "text": self.strings("btn_stop"),
                        "callback": self._stop_callback,
                    }
                ]
            ],
        )

    async def gifavacmd(self, message):
        """(reply) — create frame-by-frame avatar animation from entire video at full FPS"""
        reply = await message.get_reply_message()
        if not reply or not reply.media:
            return await utils.answer(message, self.strings("no_media_reply"))

        is_video = False
        if getattr(reply, "video", None):
            is_video = True
        elif reply.document:
            if reply.document.mime_type.startswith("video/"):
                is_video = True
            elif any(isinstance(x, DocumentAttributeVideo) for x in reply.document.attributes):
                is_video = True
            elif getattr(reply.document, "mime_type", "") == "image/gif":
                is_video = True

        if not is_video:
            return await utils.answer(message, self.strings("unsupported_media"))

        if self._task and not self._task.done():
            return await utils.answer(message, self.strings("already_running"))

        form = await self.inline.form(
            text=self.strings("downloading"),
            message=message,
        )

        temp_video = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False)
        temp_video_path = temp_video.name
        temp_video.close()

        try:
            await self.client.download_media(reply, file=temp_video_path)
        except Exception as e:
            if os.path.exists(temp_video_path):
                os.remove(temp_video_path)
            return await form.edit(text=self.strings("error").format(e))

        await form.edit(text=self.strings("extracting_frames"))

        temp_dir = tempfile.mkdtemp()

        ffmpeg_cmd = [
            "ffmpeg",
            "-y",
            "-i", temp_video_path,
            "-q:v", "2",
            os.path.join(temp_dir, "frame_%06d.jpg"),
        ]

        try:
            proc = await asyncio.create_subprocess_exec(
                *ffmpeg_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await proc.communicate()
        except Exception as e:
            if os.path.exists(temp_video_path):
                os.remove(temp_video_path)
            shutil.rmtree(temp_dir, ignore_errors=True)
            return await form.edit(text=self.strings("error").format(e))

        frames = sorted(
            [
                os.path.join(temp_dir, f)
                for f in os.listdir(temp_dir)
                if f.startswith("frame_") and f.endswith(".jpg")
            ]
        )

        if not frames:
            if os.path.exists(temp_video_path):
                os.remove(temp_video_path)
            shutil.rmtree(temp_dir, ignore_errors=True)
            return await form.edit(text=self.strings("no_frames"))

        upload_frames = list(reversed(frames))

        self._task = asyncio.create_task(
            self._gifava_loop(form, temp_video_path, temp_dir, upload_frames)
        )
        await form.edit(
            text=self.strings("gifava_progress").format(0, len(upload_frames)),
            reply_markup=[
                [
                    {
                        "text": self.strings("btn_stop"),
                        "callback": self._stop_callback,
                    }
                ]
            ],
        )

    async def stopavacmd(self, message):
        """— stop current avatar auto-set or animation process"""
        if not self._task or self._task.done():
            return await utils.answer(message, self.strings("not_running"))

        self._task.cancel()
        self._task = None
        await utils.answer(message, self.strings("stopped"))

    async def _avatar_loop(self, form, file_path, is_video, interval, count, fallback=False):
        try:
            for i in range(1, count + 1):
                uploaded = await self.client.upload_file(file_path)
                if is_video:
                    await self.client(
                        UploadProfilePhotoRequest(
                            video=uploaded,
                            video_start_ts=0.0,
                            fallback=fallback,
                        )
                    )
                else:
                    await self.client(
                        UploadProfilePhotoRequest(
                            file=uploaded,
                            fallback=fallback,
                        )
                    )

                if i < count:
                    if interval >= 3.0 or i % 5 == 0:
                        try:
                            await form.edit(
                                text=self.strings("progress").format(i, count),
                                reply_markup=[
                                    [
                                        {
                                            "text": self.strings("btn_stop"),
                                            "callback": self._stop_callback,
                                        }
                                    ]
                                ],
                            )
                        except Exception:
                            pass
                    await asyncio.sleep(interval)

            try:
                await form.edit(text=self.strings("done").format(count))
            except Exception:
                pass
        except asyncio.CancelledError:
            try:
                await form.edit(text=self.strings("stopped"))
            except Exception:
                pass
        except FloodWaitError as e:
            try:
                await form.edit(text=self.strings("flood_wait").format(e.seconds))
            except Exception:
                pass
        except Exception as e:
            try:
                await form.edit(text=self.strings("error").format(e))
            except Exception:
                pass
        finally:
            if os.path.exists(file_path):
                os.remove(file_path)
            self._task = None

    async def _gifava_loop(self, form, video_path, temp_dir, frames):
        total = len(frames)
        try:
            for i, frame_path in enumerate(frames, 1):
                uploaded = await self.client.upload_file(frame_path)
                await self.client(UploadProfilePhotoRequest(file=uploaded))

                if i < total:
                    try:
                        await form.edit(
                            text=self.strings("gifava_progress").format(i, total),
                            reply_markup=[
                                [
                                    {
                                        "text": self.strings("btn_stop"),
                                        "callback": self._stop_callback,
                                    }
                                ]
                            ],
                        )
                    except Exception:
                        pass
                    await asyncio.sleep(10)

            try:
                await form.edit(text=self.strings("gifava_done").format(total))
            except Exception:
                pass
        except asyncio.CancelledError:
            try:
                await form.edit(text=self.strings("stopped"))
            except Exception:
                pass
        except FloodWaitError as e:
            try:
                await form.edit(text=self.strings("flood_wait").format(e.seconds))
            except Exception:
                pass
        except Exception as e:
            try:
                await form.edit(text=self.strings("error").format(e))
            except Exception:
                pass
        finally:
            if os.path.exists(video_path):
                os.remove(video_path)
            shutil.rmtree(temp_dir, ignore_errors=True)
            self._task = None
