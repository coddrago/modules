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
# Commands: getava, delavas, setava, stopava, gifava, avadaily
# scope: heroku_only
# meta developer: @codrago_m
# meta banner: https://raw.githubusercontent.com/coddrago/modules/refs/heads/main/banner.png
# ---------------------------------------------------------------------------------

import asyncio
import json
import os
import shutil
import tempfile
import time
import zipfile
from datetime import datetime, timedelta
from math import ceil
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
        "no_media_reply": "<tg-emoji emoji-id=4916086774649848789>🔗</tg-emoji> <b>Reply to a photo, video, GIF, or a .zip of avatars.</b>",
        "unsupported_media": "<tg-emoji emoji-id=4916086774649848789>🔗</tg-emoji> <b>Only images, video files and .zip archives are supported.</b>",
        "zip_empty": "<tg-emoji emoji-id=4916086774649848789>🔗</tg-emoji> <b>The archive has no avatar images.</b>",
        "zip_bad": "<tg-emoji emoji-id=4916086774649848789>🔗</tg-emoji> <b>Couldn't read the .zip.</b>",
        "zip_queued": (
            "<tg-emoji emoji-id=4916086774649848789>🔗</tg-emoji> <b>Avatar queue started.</b>\n"
            "<tg-emoji emoji-id=5873022839866527761>⚪️</tg-emoji> Photos: <code>{total}</code>\n"
            "<tg-emoji emoji-id=5873022839866527761>⚪️</tg-emoji> Days needed: <code>{days}</code>\n"
            "<tg-emoji emoji-id=5873022839866527761>⚪️</tg-emoji> Finishes: <code>{finish}</code>\n"
            "<tg-emoji emoji-id=5873022839866527761>⚪️</tg-emoji> Stop: <code>.stopava</code>"
        ),
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
            "<tg-emoji emoji-id=5873022839866527761>⚪️</tg-emoji> <code>.setava</code> (reply to .zip) — 100 photos/day queue\n"
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
        "avadaily_started": (
            "<tg-emoji emoji-id=4916086774649848789>🔗</tg-emoji> <b>Daily avatar autopilot started!</b>\n"
            "<tg-emoji emoji-id=5873022839866527761>⚪️</tg-emoji> Type: <code>{}</code>\n"
            "<tg-emoji emoji-id=5873022839866527761>⚪️</tg-emoji> Amount: <code>{}</code> per day\n"
            "<tg-emoji emoji-id=5873022839866527761>⚪️</tg-emoji> Interval: <code>{}</code> sec.\n"
            "<tg-emoji emoji-id=5873022839866527761>⚪️</tg-emoji> Restart-safe. Disable: <code>.avadaily stop</code>"
        ),
        "avadaily_progress": (
            "<tg-emoji emoji-id=4916086774649848789>🔗</tg-emoji> <b>Daily avatar batch in progress...</b>\n"
            "<tg-emoji emoji-id=5873022839866527761>⚪️</tg-emoji> Progress: <b>{}/{}</b>"
        ),
        "avadaily_done": (
            "<tg-emoji emoji-id=4916086774649848789>🔗</tg-emoji> <b>Daily batch finished: {}/{} avatars set.</b>\n"
            "<tg-emoji emoji-id=5873022839866527761>⚪️</tg-emoji> Next run: <code>{}</code>"
        ),
        "avadaily_limit": (
            "<tg-emoji emoji-id=4916086774649848789>🔗</tg-emoji> <b>Telegram daily limit hit at {}/{}. FloodWait respected.</b>\n"
            "<tg-emoji emoji-id=5873022839866527761>⚪️</tg-emoji> Next run: <code>{}</code>"
        ),
        "avadaily_stopped": "<tg-emoji emoji-id=5255831443816327915>🗑</tg-emoji> <b>Daily autopilot disabled.</b>",
        "avadaily_off": (
            "<tg-emoji emoji-id=5873022839866527761>⚪️</tg-emoji> <b>Daily autopilot is off.</b>\n"
            "Reply to a photo/video and send <code>.avadaily</code> to enable."
        ),
        "avadaily_status": (
            "<tg-emoji emoji-id=4916086774649848789>🔗</tg-emoji> <b>Daily autopilot status</b>\n"
            "<tg-emoji emoji-id=5873022839866527761>⚪️</tg-emoji> Amount: <code>{}</code>/day\n"
            "<tg-emoji emoji-id=5873022839866527761>⚪️</tg-emoji> Interval: <code>{}</code> sec.\n"
            "<tg-emoji emoji-id=5873022839866527761>⚪️</tg-emoji> Last batch set: <code>{}</code>\n"
            "<tg-emoji emoji-id=5873022839866527761>⚪️</tg-emoji> Next run: <code>{}</code>"
        ),
        "avadaily_no_media": (
            "<tg-emoji emoji-id=4916086774649848789>🔗</tg-emoji> <b>Saved avatar file is missing — autopilot stopped.</b>\n"
            "Re-enable with <code>.avadaily</code> replying to media."
        ),
        "avadaily_usage": (
            "<tg-emoji emoji-id=4916086774649848789>🔗</tg-emoji> <b>Usage:</b>\n"
            "<tg-emoji emoji-id=5873022839866527761>⚪️</tg-emoji> <code>.avadaily</code> (reply to photo/video) — 100 avatars/day\n"
            "<tg-emoji emoji-id=5873022839866527761>⚪️</tg-emoji> <code>.avadaily 50 60</code> — 50/day, 60 sec interval\n"
            "<tg-emoji emoji-id=5873022839866527761>⚪️</tg-emoji> <code>.avadaily -p</code> — public (fallback) avatar\n"
            "<tg-emoji emoji-id=5873022839866527761>⚪️</tg-emoji> <code>.avadaily stop</code> — disable\n"
            "<tg-emoji emoji-id=5873022839866527761>⚪️</tg-emoji> <code>.avadaily status</code> — show status"
        ),
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
        "no_media_reply": "<tg-emoji emoji-id=4916086774649848789>🔗</tg-emoji> <b>Ответьте реплаем на фото, видео, GIF или .zip с аватарками.</b>",
        "unsupported_media": "<tg-emoji emoji-id=4916086774649848789>🔗</tg-emoji> <b>Поддерживаются только изображения, видео и .zip-архивы.</b>",
        "zip_empty": "<tg-emoji emoji-id=4916086774649848789>🔗</tg-emoji> <b>В архиве нет картинок для аватарок.</b>",
        "zip_bad": "<tg-emoji emoji-id=4916086774649848789>🔗</tg-emoji> <b>Не удалось прочитать .zip.</b>",
        "zip_queued": (
            "<tg-emoji emoji-id=4916086774649848789>🔗</tg-emoji> <b>Очередь аватарок запущена.</b>\n"
            "<tg-emoji emoji-id=5873022839866527761>⚪️</tg-emoji> Фоток: <code>{total}</code>\n"
            "<tg-emoji emoji-id=5873022839866527761>⚪️</tg-emoji> Понадобится дней: <code>{days}</code>\n"
            "<tg-emoji emoji-id=5873022839866527761>⚪️</tg-emoji> Закончит: <code>{finish}</code>\n"
            "<tg-emoji emoji-id=5873022839866527761>⚪️</tg-emoji> Остановить: <code>.stopava</code>"
        ),
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
            "<tg-emoji emoji-id=5873022839866527761>⚪️</tg-emoji> <code>.setava</code> (реплай на .zip) — очередь по 100 фоток в день\n"
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
        "avadaily_started": (
            "<tg-emoji emoji-id=4916086774649848789>🔗</tg-emoji> <b>Запущен ежедневный автопилот аватарок!</b>\n"
            "<tg-emoji emoji-id=5873022839866527761>⚪️</tg-emoji> Тип: <code>{}</code>\n"
            "<tg-emoji emoji-id=5873022839866527761>⚪️</tg-emoji> Количество: <code>{}</code> шт. в день\n"
            "<tg-emoji emoji-id=5873022839866527761>⚪️</tg-emoji> Интервал: <code>{}</code> сек.\n"
            "<tg-emoji emoji-id=5873022839866527761>⚪️</tg-emoji> Переживает рестарты. Выключить: <code>.avadaily stop</code>"
        ),
        "avadaily_progress": (
            "<tg-emoji emoji-id=4916086774649848789>🔗</tg-emoji> <b>Ежедневная партия в процессе...</b>\n"
            "<tg-emoji emoji-id=5873022839866527761>⚪️</tg-emoji> Прогресс: <b>{}/{}</b>"
        ),
        "avadaily_done": (
            "<tg-emoji emoji-id=4916086774649848789>🔗</tg-emoji> <b>Ежедневная партия завершена: {}/{} аватарок.</b>\n"
            "<tg-emoji emoji-id=5873022839866527761>⚪️</tg-emoji> Следующий запуск: <code>{}</code>"
        ),
        "avadaily_limit": (
            "<tg-emoji emoji-id=4916086774649848789>🔗</tg-emoji> <b>Достигнут дневной лимит Telegram на {}/{}. FloodWait учтён.</b>\n"
            "<tg-emoji emoji-id=5873022839866527761>⚪️</tg-emoji> Следующий запуск: <code>{}</code>"
        ),
        "avadaily_stopped": "<tg-emoji emoji-id=5255831443816327915>🗑</tg-emoji> <b>Ежедневный автопилот выключен.</b>",
        "avadaily_off": (
            "<tg-emoji emoji-id=5873022839866527761>⚪️</tg-emoji> <b>Ежедневный автопилот выключен.</b>\n"
            "Ответь реплаем на фото/видео и отправь <code>.avadaily</code>, чтобы включить."
        ),
        "avadaily_status": (
            "<tg-emoji emoji-id=4916086774649848789>🔗</tg-emoji> <b>Статус ежемесячного автопилота</b>\n"
            "<tg-emoji emoji-id=5873022839866527761>⚪️</tg-emoji> Количество: <code>{}</code> шт./день\n"
            "<tg-emoji emoji-id=5873022839866527761>⚪️</tg-emoji> Интервал: <code>{}</code> сек.\n"
            "<tg-emoji emoji-id=5873022839866527761>⚪️</tg-emoji> В прошлой партии: <code>{}</code> шт.\n"
            "<tg-emoji emoji-id=5873022839866527761>⚪️</tg-emoji> Следующий запуск: <code>{}</code>"
        ),
        "avadaily_no_media": (
            "<tg-emoji emoji-id=4916086774649848789>🔗</tg-emoji> <b>Сохранённый файл аватарки потерян — автопилот остановлен.</b>\n"
            "Включи заново: <code>.avadaily</code> реплаем на медиа."
        ),
        "avadaily_usage": (
            "<tg-emoji emoji-id=4916086774649848789>🔗</tg-emoji> <b>Использование:</b>\n"
            "<tg-emoji emoji-id=5873022839866527761>⚪️</tg-emoji> <code>.avadaily</code> (реплай на фото/видео) — 100 аватарок/день\n"
            "<tg-emoji emoji-id=5873022839866527761>⚪️</tg-emoji> <code>.avadaily 50 60</code> — 50 шт./день, интервал 60 сек.\n"
            "<tg-emoji emoji-id=5873022839866527761>⚪️</tg-emoji> <code>.avadaily -p</code> — публичная аватарка\n"
            "<tg-emoji emoji-id=5873022839866527761>⚪️</tg-emoji> <code>.avadaily stop</code> — выключить\n"
            "<tg-emoji emoji-id=5873022839866527761>⚪️</tg-emoji> <code>.avadaily status</code> — статус"
        ),
    }

    def __init__(self):
        self._task = None
        self._daily_task = None

    async def on_unload(self):
        for t in (self._task, self._daily_task):
            if t and not t.done():
                t.cancel()

    async def client_ready(self, client, db):
        try:
            cfg = self._load_cfg()
            if cfg.get("enabled") and not (self._daily_task and not self._daily_task.done()):
                self._daily_task = asyncio.create_task(self._daily_loop())
        except Exception:
            pass

    async def _stop_callback(self, call):
        if self._daily_task and not self._daily_task.done():
            cfg = self._load_cfg()
            cfg["enabled"] = False
            if cfg.get("mode") == "queue":
                self._clear_queue_files()
                cfg["mode"] = "single"
                cfg["queue_index"] = 0
            self._save_cfg(cfg)
        for t in (self._task, self._daily_task):
            if t and not t.done():
                t.cancel()
        self._task = None
        self._daily_task = None
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

    def _is_zip_reply(self, reply):
        doc = getattr(reply, "document", None)
        if not doc:
            return False
        name = ""
        for attr in getattr(doc, "attributes", []) or []:
            fname = getattr(attr, "file_name", None)
            if fname:
                name = fname
                break
        mime = (getattr(doc, "mime_type", None) or "").lower()
        return name.lower().endswith(".zip") or mime in (
            "application/zip",
            "application/x-zip-compressed",
        )

    def _queue_dir(self):
        path = os.path.join(tempfile.gettempdir(), "avatars_queue")
        os.makedirs(path, exist_ok=True)
        return path

    def _clear_queue_files(self):
        path = os.path.join(tempfile.gettempdir(), "avatars_queue")
        if os.path.isdir(path):
            shutil.rmtree(path, ignore_errors=True)

    def _extract_avatar_zip(self, zip_path):
        dest = self._queue_dir()
        for name in os.listdir(dest):
            target = os.path.join(dest, name)
            if os.path.isdir(target):
                shutil.rmtree(target, ignore_errors=True)
            else:
                try:
                    os.remove(target)
                except OSError:
                    pass

        image_ext = (".jpg", ".jpeg", ".png", ".webp")
        saved = []
        with zipfile.ZipFile(zip_path) as archive:
            names = []
            for info in archive.infolist():
                if info.is_dir():
                    continue
                base = os.path.basename(info.filename.replace("\\", "/"))
                if not base or base.startswith(".") or base.startswith("__"):
                    continue
                if not base.lower().endswith(image_ext):
                    continue
                names.append(info.filename)
            names.sort(key=lambda item: os.path.basename(item.replace("\\", "/")).lower())
            for index, name in enumerate(names, 1):
                ext = os.path.splitext(os.path.basename(name.replace("\\", "/")))[1].lower()
                if ext == ".jpeg":
                    ext = ".jpg"
                out = os.path.join(dest, f"{index:06d}{ext}")
                with archive.open(name) as src, open(out, "wb") as dst:
                    shutil.copyfileobj(src, dst)
                saved.append(out)
        return saved

    async def setavacmd(self, message):
        """[-p] <interval> <count> (reply) — set avatar once, loop, or queue a .zip by 100/day"""
        reply = await message.get_reply_message()
        if not reply or not reply.media:
            return await utils.answer(message, self.strings("no_media_reply"))

        if self._is_zip_reply(reply):
            return await self._setava_zip(message, reply)

        is_video = False
        if getattr(reply, "video", None):
            is_video = True
        elif reply.document:
            if reply.document.mime_type.startswith("video/"):
                is_video = True
            elif any(isinstance(x, DocumentAttributeVideo) for x in reply.document.attributes):
                is_video = True
            elif not (reply.document.mime_type or "").startswith("image/"):
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

    async def _setava_zip(self, message, reply):
        if (self._task and not self._task.done()) or (
            self._daily_task and not self._daily_task.done()
        ):
            return await utils.answer(message, self.strings("already_running"))

        raw_args = utils.get_args_raw(message)
        parts = raw_args.split() if raw_args else []
        fallback = False
        nums = []
        for part in parts:
            if part.lower() in ["-p", "--public", "public", "паблик"]:
                fallback = True
            else:
                nums.append(part)

        per_day = 100
        interval = 30.0
        if len(nums) >= 2:
            try:
                interval = max(1.0, float(nums[0]))
                per_day = max(1, min(100, int(nums[1])))
            except ValueError:
                return await utils.answer(message, self.strings("invalid_setava_args"))
        elif len(nums) == 1:
            try:
                per_day = max(1, min(100, int(nums[0])))
            except ValueError:
                return await utils.answer(message, self.strings("invalid_setava_args"))

        status = await utils.answer(message, self.strings("downloading"))
        zip_file = tempfile.NamedTemporaryFile(suffix=".zip", delete=False)
        zip_path = zip_file.name
        zip_file.close()
        try:
            await self.client.download_media(reply, file=zip_path)
            try:
                files = await asyncio.to_thread(self._extract_avatar_zip, zip_path)
            except zipfile.BadZipFile:
                self._clear_queue_files()
                return await utils.answer(status, self.strings("zip_bad"))
        except Exception as e:
            self._clear_queue_files()
            return await utils.answer(status, self.strings("error").format(e))
        finally:
            if os.path.exists(zip_path):
                os.remove(zip_path)

        if not files:
            return await utils.answer(status, self.strings("zip_empty"))

        total = len(files)
        days = ceil(total / per_day)
        finish = (datetime.now() + timedelta(days=days - 1)).strftime("%d.%m.%Y")
        cfg = self._load_cfg()
        cfg.update(
            {
                "enabled": True,
                "mode": "queue",
                "queue_dir": self._queue_dir(),
                "queue_index": 0,
                "queue_total": total,
                "count": per_day,
                "interval": interval,
                "public": fallback,
                "is_video": False,
                "last_batch": 0,
                "next_run": time.time(),
            }
        )
        cfg.pop("media_path", None)
        self._save_cfg(cfg)

        if self._daily_task and not self._daily_task.done():
            self._daily_task.cancel()
        self._daily_task = asyncio.create_task(self._daily_loop())
        await utils.answer(
            status,
            self.strings("zip_queued").format(
                total=total,
                days=days,
                finish=finish,
            ),
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
        """— stop current avatar auto-set, animation or daily autopilot"""
        daily_running = bool(self._daily_task and not self._daily_task.done())
        task_running = bool(self._task and not self._task.done())
        if not daily_running and not task_running:
            return await utils.answer(message, self.strings("not_running"))

        if daily_running:
            cfg = self._load_cfg()
            cfg["enabled"] = False
            if cfg.get("mode") == "queue":
                self._clear_queue_files()
                cfg["mode"] = "single"
                cfg["queue_index"] = 0
            self._save_cfg(cfg)
        for t in (self._task, self._daily_task):
            if t and not t.done():
                t.cancel()
        self._task = None
        self._daily_task = None
        await utils.answer(message, self.strings("stopped"))

    def _cfg_path(self):
        return os.path.join(tempfile.gettempdir(), "avadaily.json")

    def _media_path(self, suffix=".jpg"):
        return os.path.join(tempfile.gettempdir(), "avadaily_avatar" + suffix)

    def _load_cfg(self):
        try:
            with open(self._cfg_path(), "r") as f:
                return json.load(f)
        except Exception:
            return {}

    def _save_cfg(self, cfg):
        try:
            with open(self._cfg_path(), "w") as f:
                json.dump(cfg, f)
        except Exception:
            pass

    def _default_next_run(self):
        now = datetime.now()
        tomorrow = (now + timedelta(days=1)).replace(hour=12, minute=0, second=0, microsecond=0)
        return tomorrow.timestamp()

    async def avadailycmd(self, message):
        """[reply | 50 60 | -p | stop | status | now] — daily 100-avatar autopilot (survives restarts)"""
        args = utils.get_args_raw(message).lower()
        parts = args.split() if args else []
        reply = await message.get_reply_message()

        if parts and parts[0] in ["stop", "off", "выкл", "стоп"]:
            cfg = self._load_cfg()
            cfg["enabled"] = False
            if cfg.get("mode") == "queue":
                self._clear_queue_files()
                cfg["mode"] = "single"
                cfg["queue_index"] = 0
            self._save_cfg(cfg)
            if self._daily_task and not self._daily_task.done():
                self._daily_task.cancel()
            self._daily_task = None
            return await utils.answer(message, self.strings("avadaily_stopped"))

        if parts and parts[0] in ["status", "статус"]:
            cfg = self._load_cfg()
            if not cfg.get("enabled"):
                return await utils.answer(message, self.strings("avadaily_off"))
            nxt = datetime.fromtimestamp(cfg.get("next_run", 0))
            last = cfg.get("last_batch", "?")
            return await utils.answer(
                message,
                self.strings("avadaily_status").format(
                    cfg.get("count", 100),
                    cfg.get("interval", 30),
                    last,
                    nxt.strftime("%d.%m %H:%M"),
                ),
            )

        cfg = self._load_cfg()
        run_now = bool(parts and parts[0] in ["now", "сейчас"])
        public = any(p in ["-p", "--public", "public", "паблик"] for p in parts)

        num_parts = [p for p in parts if p not in ["-p", "--public", "public", "паблик", "now", "сейчас"]]
        count = 100
        interval = 30.0
        if len(num_parts) >= 2:
            try:
                count = max(1, int(num_parts[0]))
                interval = max(1.0, float(num_parts[1]))
            except ValueError:
                return await utils.answer(message, self.strings("avadaily_usage"))
        elif len(num_parts) == 1:
            try:
                count = max(1, int(num_parts[0]))
            except ValueError:
                return await utils.answer(message, self.strings("avadaily_usage"))

        is_video = False
        new_media = False
        if reply and reply.media:
            if getattr(reply, "video", None):
                is_video = True
            elif reply.document:
                if (reply.document.mime_type or "").startswith("video/"):
                    is_video = True
                elif any(isinstance(x, DocumentAttributeVideo) for x in reply.document.attributes):
                    is_video = True
                elif not (reply.document.mime_type or "").startswith("image/"):
                    return await utils.answer(message, self.strings("unsupported_media"))

            suffix = ".mp4" if is_video else ".jpg"
            media_path = self._media_path(suffix)
            try:
                await self.client.download_media(reply, file=media_path)
            except Exception as e:
                return await utils.answer(message, self.strings("error").format(e))
            cfg["media_path"] = media_path
            cfg["is_video"] = is_video
            new_media = True
        elif cfg.get("media_path") and os.path.exists(cfg["media_path"]):
            media_path = cfg["media_path"]
            is_video = cfg.get("is_video", False)
        else:
            return await utils.answer(message, self.strings("avadaily_usage"))

        if not run_now and cfg.get("enabled") and self._daily_task and not self._daily_task.done():
            self._daily_task.cancel()
            self._daily_task = None

        cfg.update(
            {
                "enabled": True,
                "count": count,
                "interval": interval,
                "public": public,
                "last_batch": cfg.get("last_batch", 0),
                "next_run": time.time() if (new_media or run_now) else cfg.get("next_run", self._default_next_run()),
            }
        )
        self._save_cfg(cfg)

        if self._daily_task and not self._daily_task.done():
            return await utils.answer(
                message,
                self.strings("avadaily_started").format(
                    "Public" if public else "Profile", count, interval
                ),
            )

        self._daily_task = asyncio.create_task(self._daily_loop())
        await utils.answer(
            message,
            self.strings("avadaily_started").format(
                "Public" if public else "Profile", count, interval
            ),
        )

    async def _daily_loop(self):
        try:
            while True:
                cfg = self._load_cfg()
                if not cfg.get("enabled"):
                    return

                queue_mode = cfg.get("mode") == "queue"
                media_path = cfg.get("media_path", "")
                if not queue_mode and (not media_path or not os.path.exists(media_path)):
                    cfg["enabled"] = False
                    self._save_cfg(cfg)
                    try:
                        await self.client.send_message("me", self.strings("avadaily_no_media"))
                    except Exception:
                        pass
                    return

                now = time.time()
                next_run = cfg.get("next_run", 0)
                if now < next_run:
                    await asyncio.sleep(min(next_run - now, 3600))
                    continue

                count = cfg.get("count", 100)
                interval = cfg.get("interval", 30.0)
                is_video = cfg.get("is_video", False)
                public = cfg.get("public", False)
                batch = []
                if queue_mode:
                    queue_dir = cfg.get("queue_dir") or self._queue_dir()
                    index = int(cfg.get("queue_index", 0))
                    names = sorted(
                        name
                        for name in os.listdir(queue_dir)
                        if os.path.isfile(os.path.join(queue_dir, name))
                    ) if os.path.isdir(queue_dir) else []
                    if index >= len(names):
                        cfg["enabled"] = False
                        cfg["mode"] = "single"
                        cfg["queue_index"] = len(names)
                        self._save_cfg(cfg)
                        self._clear_queue_files()
                        try:
                            await self.client.send_message(
                                "me",
                                self.strings("done").format(cfg.get("queue_total", len(names))),
                            )
                        except Exception:
                            pass
                        return
                    batch = [
                        os.path.join(queue_dir, name)
                        for name in names[index:index + count]
                    ]
                    count = len(batch)

                set_count = 0
                done_reason = "done"
                try:
                    for i in range(1, count + 1):
                        cfg = self._load_cfg()
                        if not cfg.get("enabled"):
                            return
                        current = batch[i - 1] if queue_mode else media_path
                        try:
                            uploaded = await self.client.upload_file(current)
                            if is_video and not queue_mode:
                                await self.client(
                                    UploadProfilePhotoRequest(
                                        video=uploaded,
                                        video_start_ts=0.0,
                                        fallback=public,
                                    )
                                )
                            else:
                                await self.client(
                                    UploadProfilePhotoRequest(
                                        file=uploaded,
                                        fallback=public,
                                    )
                                )
                            set_count += 1
                            if queue_mode:
                                cfg = self._load_cfg()
                                cfg["queue_index"] = int(cfg.get("queue_index", 0)) + 1
                                cfg["last_batch"] = set_count
                                self._save_cfg(cfg)
                                try:
                                    os.remove(current)
                                except OSError:
                                    pass
                        except FloodWaitError as e:
                            cfg = self._load_cfg()
                            cfg["next_run"] = time.time() + e.seconds + 60
                            self._save_cfg(cfg)
                            done_reason = "limit"
                            break
                        if i < count:
                            await asyncio.sleep(interval)
                except asyncio.CancelledError:
                    raise
                except Exception:
                    pass

                nxt = time.time() + 86400
                cfg = self._load_cfg()
                if done_reason == "done":
                    cfg["next_run"] = nxt
                cfg["last_batch"] = set_count
                if queue_mode and int(cfg.get("queue_index", 0)) >= int(cfg.get("queue_total", 0)):
                    cfg["enabled"] = False
                    cfg["mode"] = "single"
                    self._clear_queue_files()
                    try:
                        await self.client.send_message(
                            "me",
                            self.strings("done").format(cfg.get("queue_total", set_count)),
                        )
                    except Exception:
                        pass
                self._save_cfg(cfg)
        except asyncio.CancelledError:
            return

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
