# ---------------------------------------------------------------------------------
#░█▀▄░▄▀▀▄░█▀▄░█▀▀▄░█▀▀▄░█▀▀▀░▄▀▀▄░░░█▀▄▀█
#░█░░░█░░█░█░█░█▄▄▀░█▄▄█░█░▀▄░█░░█░░░█░▀░█
#░▀▀▀░░▀▀░░▀▀░░▀░▀▀░▀░░▀░▀▀▀▀░░▀▀░░░░▀░░▒▀
# Name: Avatars
# Description: Flexible profile avatar management & auto-setter
# Commands: getava, delavas, setava, stopava
# ---------------------------------------------------------------------------------
# 🔒    Licensed under the GNU AGPLv3
# 🌐 https://www.gnu.org/licenses/agpl-3.0.html
# ---------------------------------------------------------------------------------
# Author: @codrago
# scope: heroku_only
# meta developer: @codrago_m
# meta banner: https://raw.githubusercontent.com/coddrago/modules/refs/heads/main/banner.png
# ---------------------------------------------------------------------------------

import asyncio
import os
import tempfile
from telethon.errors import FloodWaitError
from telethon.tl import types
from telethon.tl.functions.photos import DeletePhotosRequest, UploadProfilePhotoRequest
from telethon.tl.types import DocumentAttributeVideo, InputPhoto
from .. import loader, utils


@loader.tds
class AvatarsMod(loader.Module):
    """Module for flexible profile avatar management"""

    strings = {
        "name": "Avatars",
        "no_avas": "<tg-emoji emoji-id=5287372146039861774>⛔️</tg-emoji> <b>User has no profile photos.</b>",
        "downloading": "<tg-emoji emoji-id=5872771279337033184>⬇️</tg-emoji> <b>Downloading avatar...</b>",
        "deleted": "<tg-emoji emoji-id=5255831443816327915>🗑</tg-emoji> <b>Successfully deleted avatars:</b> <code>{}</code>.",
        "invalid_args": "<tg-emoji emoji-id=4916086774649848789>🔗</tg-emoji> <b>Specify a number or <code>all</code>.</b>",
        "user_not_found": "<tg-emoji emoji-id=4916086774649848789>🔗</tg-emoji> <b>Specified user could not be found.</b>",
        "no_media_reply": "<tg-emoji emoji-id=4916086774649848789>🔗</tg-emoji> <b>Reply to a photo, video, or GIF.</b>",
        "unsupported_media": "<tg-emoji emoji-id=4916086774649848789>🔗</tg-emoji> <b>Only images and video files are supported.</b>",
        "avatar_set": "<tg-emoji emoji-id=4916086774649848789>🔗</tg-emoji> <b>Avatar successfully updated!</b>",
        "already_running": "<tg-emoji emoji-id=4916086774649848789>🔗</tg-emoji> <b>Auto-set process is already running! Stop it with <code>.stopava</code>.</b>",
        "not_running": "<tg-emoji emoji-id=4916086774649848789>🔗</tg-emoji> <b>No active avatar auto-set process found.</b>",
        "started": (
            "<tg-emoji emoji-id=4916086774649848789>🔗</tg-emoji> <b>Avatar loop process started!</b>\n"
            "<tg-emoji emoji-id=5873022839866527761>⚪️</tg-emoji> Amount: <code>{}</code>\n"
            "<tg-emoji emoji-id=5873022839866527761>⚪️</tg-emoji> Interval: <code>{}</code> sec."
        ),
        "progress": (
            "<tg-emoji emoji-id=4916086774649848789>🔗</tg-emoji> <b>Avatar loop in progress...</b>\n"
            "<tg-emoji emoji-id=5873022839866527761>⚪️</tg-emoji> Progress: <b>{}/{}</b>"
        ),
        "done": "<tg-emoji emoji-id=4916086774649848789>🔗</tg-emoji> <b>Successfully finished! Total avatars set:</b> <code>{}</code>.",
        "stopped": "<tg-emoji emoji-id=4916086774649848789>🔗</tg-emoji> <b>Avatar auto-set process stopped.</b>",
        "flood_wait": "<tg-emoji emoji-id=4916086774649848789>🔗</tg-emoji> <b>Telegram FloodWait received for <code>{}</code> seconds. Process stopped for safety.</b>",
        "error": "<tg-emoji emoji-id=4916086774649848789>🔗</tg-emoji> <b>Error:</b> <code>{}</code>",
        "invalid_setava_args": (
            "<tg-emoji emoji-id=4916086774649848789>🔗</tg-emoji> <b>Invalid arguments.</b>\n"
            "Usage:\n"
            "<tg-emoji emoji-id=5873022839866527761>⚪️</tg-emoji> <code>.setava</code> — set once\n"
            "<tg-emoji emoji-id=5873022839866527761>⚪️</tg-emoji> <code>.setava <interval_sec> <amount></code> — start loop"
        ),
        "btn_stop": "❌ Stop",
    }

    strings_ru = {
        "name": "Avatars",
        "no_avas": "<tg-emoji emoji-id=5287372146039861774>⛔️</tg-emoji> <b>У пользователя нет аватарок.</b>",
        "downloading": "<tg-emoji emoji-id=5872771279337033184>⬇️</tg-emoji> <b>Загрузка аватарки...</b>",
        "deleted": "<tg-emoji emoji-id=5255831443816327915>🗑</tg-emoji> <b>Успешно удалено аватарок:</b> <code>{}</code>.",
        "invalid_args": "<tg-emoji emoji-id=4916086774649848789>🔗</tg-emoji> <b>Укажите число или <code>all</code>.</b>",
        "user_not_found": "<tg-emoji emoji-id=4916086774649848789>🔗</tg-emoji> <b>Не удалось найти указанного пользователя.</b>",
        "no_media_reply": "<tg-emoji emoji-id=4916086774649848789>🔗</tg-emoji> <b>Ответьте реплаем на фото, видео или GIF.</b>",
        "unsupported_media": "<tg-emoji emoji-id=4916086774649848789>🔗</tg-emoji> <b>Поддерживаются только изображения и видеофайлы.</b>",
        "avatar_set": "<tg-emoji emoji-id=4916086774649848789>🔗</tg-emoji> <b>Аватарка успешно установлена!</b>",
        "already_running": "<tg-emoji emoji-id=4916086774649848789>🔗</tg-emoji> <b>Процесс автопостановки уже активен! Остановите его командой <code>.stopava</code>.</b>",
        "not_running": "<tg-emoji emoji-id=4916086774649848789>🔗</tg-emoji> <b>На данный момент нет активного процесса автопостановки.</b>",
        "started": (
            "<tg-emoji emoji-id=4916086774649848789>🔗</tg-emoji> <b>Запущен процесс установки аватарок!</b>\n"
            "<tg-emoji emoji-id=5873022839866527761>⚪️</tg-emoji> Количество: <code>{}</code> шт.\n"
            "<tg-emoji emoji-id=5873022839866527761>⚪️</tg-emoji> Интервал: <code>{}</code> сек."
        ),
        "progress": (
            "<tg-emoji emoji-id=4916086774649848789>🔗</tg-emoji> <b>Автопостановка в процессе...</b>\n"
            "<tg-emoji emoji-id=5873022839866527761>⚪️</tg-emoji> Прогресс: <b>{}/{}</b>"
        ),
        "done": "<tg-emoji emoji-id=4916086774649848789>🔗</tg-emoji> <b>Успешно завершено! Установлено аватарок:</b> <code>{}</code>.",
        "stopped": "<tg-emoji emoji-id=4916086774649848789>🔗</tg-emoji> <b>Процесс автопостановки аватарок остановлен.</b>",
        "flood_wait": "<tg-emoji emoji-id=4916086774649848789>🔗</tg-emoji> <b>Telegram выдал FloodWait на <code>{}</code> сек. Процесс прерван в целях безопасности.</b>",
        "error": "<tg-emoji emoji-id=4916086774649848789>🔗</tg-emoji> <b>Ошибка:</b> <code>{}</code>",
        "invalid_setava_args": (
            "<tg-emoji emoji-id=4916086774649848789>🔗</tg-emoji> <b>Неверные аргументы.</b>\n"
            "Использование:\n"
            "<tg-emoji emoji-id=5873022839866527761>⚪️</tg-emoji> <code>.setava</code> — установить 1 раз\n"
            "<tg-emoji emoji-id=5873022839866527761>⚪️</tg-emoji> <code>.setava <интервал_сек> <кол-во></code> — запустить цикл"
        ),
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

    async def getavacmd(self, message):
        """[reply | username/id] — get current avatar (photo or video)"""
        args = utils.get_args_raw(message)
        reply = await message.get_reply_message()

        target = "me"
        if reply:
            target = reply.sender_id
        elif args:
            target = args

        try:
            ava = await self.client.get_profile_photos(target, limit=1)
            photo = ava[0] if ava else None
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
                await utils.answer(message, file=downloaded)
            finally:
                if os.path.exists(temp_path):
                    os.remove(temp_path)
        else:
            await utils.answer(message, file=photo)

    async def delavascmd(self, message):
        """<count | all> — delete specified number of avatars or all of them"""
        args = utils.get_args_raw(message)
        if not args:
            return await utils.answer(message, self.strings("invalid_args"))

        args = args.lower().strip()
        if args in ["all", "все", "всё"]:
            photos = await self.client.get_profile_photos("me", limit=None)
        else:
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
        """<interval> <count> (reply) — auto-set avatar in a loop via inline form"""
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

        args = utils.get_args_raw(message)
        interval = 5.0
        count = 1

        if args:
            parts = args.split()
            if len(parts) >= 2:
                try:
                    interval = float(parts[0])
                    count = int(parts[1])
                except ValueError:
                    return await utils.answer(message, self.strings("invalid_setava_args"))
            elif len(parts) == 1:
                try:
                    count = int(parts[0])
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

        suffix = ".mp4" if is_video else ".jpg"
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
                    await self.client(UploadProfilePhotoRequest(video=uploaded, video_start_ts=0.0))
                else:
                    await self.client(UploadProfilePhotoRequest(file=uploaded))
                await form.edit(text=self.strings("avatar_set"))
            except Exception as e:
                await form.edit(text=self.strings("error").format(e))
            finally:
                if os.path.exists(temp_path):
                    os.remove(temp_path)
            return

        self._task = asyncio.create_task(
            self._avatar_loop(form, temp_path, is_video, interval, count)
        )
        await form.edit(
            text=self.strings("started").format(count, interval),
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
        """— stop current avatar auto-set process"""
        if not self._task or self._task.done():
            return await utils.answer(message, self.strings("not_running"))

        self._task.cancel()
        self._task = None
        await utils.answer(message, self.strings("stopped"))

    async def _avatar_loop(self, form, file_path, is_video, interval, count):
        try:
            for i in range(1, count + 1):
                uploaded = await self.client.upload_file(file_path)
                if is_video:
                    await self.client(UploadProfilePhotoRequest(video=uploaded, video_start_ts=0.0))
                else:
                    await self.client(UploadProfilePhotoRequest(file=uploaded))

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
