# ---------------------------------------------------------------------------------
# ░█▀▄░▄▀▀▄░█▀▄░█▀▀▄░█▀▀▄░█▀▀▀░▄▀▀▄░░░█▀▄▀█
# ░█░░░█░░█░█░█░█▄▄▀░█▄▄█░█░▀▄░█░░█░░░█░▀░█
# ░▀▀▀░░▀▀░░▀▀░░▀░▀▀░▀░░▀░▀▀▀▀░░▀▀░░░░▀░░▒▀
# Name: SoundGif
# Description: Convert videos into compact Telegram animations with sound
# Author: @codrago_m
# ---------------------------------------------------------------------------------
# 🔒    Licensed under the GNU AGPLv3
# 🌐 https://www.gnu.org/licenses/agpl-3.0.html
# ---------------------------------------------------------------------------------
# Commands: soundgif
# scope: heroku_only
# scope: ffmpeg
# meta developer: @codrago_m
# meta banner: https://raw.githubusercontent.com/coddrago/modules/refs/heads/main/banner.png
# ---------------------------------------------------------------------------------

import asyncio
import contextlib
import json
import logging
import math
import shlex
import shutil
import struct
import tempfile
from pathlib import Path

from herokutl.tl.types import (
    DocumentAttributeAnimated,
    DocumentAttributeFilename,
    DocumentAttributeVideo,
    Message,
)

from .. import loader, utils


__version__ = (1, 0, 3)

logger = logging.getLogger(__name__)


@loader.tds
class SoundGifMod(loader.Module):
    """Converts videos into compact Telegram animations with sound."""

    strings = {
        "name": "SoundGif",
        "_cls_doc": "Converts videos into compact Telegram animations with sound.",
        "busy": "<tg-emoji emoji-id=5870982283724328568>⚙</tg-emoji> <b>Another video is being processed. Please wait.</b>",
        "no_ffmpeg": "<tg-emoji emoji-id=5870931487146119264>❗️</tg-emoji> <b>FFmpeg and ffprobe are required.</b> Install the <code>ffmpeg</code> system package.",
        "no_reply": "<tg-emoji emoji-id=5870931487146119264>❗️</tg-emoji> <b>Reply to a video with an audio track.</b>",
        "too_large": "<tg-emoji emoji-id=5870931487146119264>❗️</tg-emoji> <b>The input file must not exceed 100 MiB.</b>",
        "rendering": "<tg-emoji emoji-id=5870982283724328568>⚙</tg-emoji> <b>rendering…</b>",
        "done": "<tg-emoji emoji-id=5870633910337015697>✅</tg-emoji> <b>Animation ready</b>\n\n<tg-emoji emoji-id=5873153278023307367>📄</tg-emoji> <b>Size:</b> <code>{size:.0f} KB</code>\n<tg-emoji emoji-id=5870496192210669260>⏲</tg-emoji> <b>Duration:</b> <code>{duration:.1f} s</code>\n<tg-emoji emoji-id=5870782662234346251>🖼</tg-emoji> <b>Resolution:</b> <code>{width} × {height}</code>",
        "not_animated": "<tg-emoji emoji-id=5870931487146119264>❗️</tg-emoji> <b>File sent, but Telegram did not confirm the animation attribute.</b>",
        "download_empty": "Telegram did not return a downloaded file.",
        "download_missing": "The downloaded file was not found on disk.",
        "download_incomplete": "Incomplete download: received {actual} of {expected} bytes.",
        "timeout": "<tg-emoji emoji-id=5870657884844462243>❌</tg-emoji> <b>Timed out. Try a shorter video or retry later.</b>",
        "error": "<tg-emoji emoji-id=5870657884844462243>❌</tg-emoji> <b>SoundGif · Error</b>\n<blockquote expandable>{error}</blockquote>",
    }

    strings_ru = {
        "_cls_doc": "Превращает видео в компактные Telegram-анимации со звуком.",
        "_cmd_doc_soundgif": "Ответом на видео: [--square] [--size 720] [--start 0] [--duration 10] — GIF со звуком.",
        "busy": "<tg-emoji emoji-id=5870982283724328568>⚙</tg-emoji> <b>Уже обрабатываю видео, подожди.</b>",
        "no_ffmpeg": "<tg-emoji emoji-id=5870931487146119264>❗️</tg-emoji> <b>Нужны FFmpeg и ffprobe.</b> Установи системный пакет <code>ffmpeg</code>.",
        "no_reply": "<tg-emoji emoji-id=5870931487146119264>❗️</tg-emoji> <b>Ответь на видео со звуковой дорожкой.</b>",
        "too_large": "<tg-emoji emoji-id=5870931487146119264>❗️</tg-emoji> <b>Максимальный размер исходника — 100 МиБ.</b>",
        "rendering": "<tg-emoji emoji-id=5870982283724328568>⚙</tg-emoji> <b>rendering…</b>",
        "done": "<tg-emoji emoji-id=5870633910337015697>✅</tg-emoji> <b>Анимация готова</b>\n\n<tg-emoji emoji-id=5873153278023307367>📄</tg-emoji> <b>Размер:</b> <code>{size:.0f} КБ</code>\n<tg-emoji emoji-id=5870496192210669260>⏲</tg-emoji> <b>Длительность:</b> <code>{duration:.1f} с</code>\n<tg-emoji emoji-id=5870782662234346251>🖼</tg-emoji> <b>Разрешение:</b> <code>{width} × {height}</code>",
        "not_animated": "<tg-emoji emoji-id=5870931487146119264>❗️</tg-emoji> <b>Файл отправлен, но Telegram не подтвердил атрибут анимации.</b>",
        "download_empty": "Telegram не вернул скачанный файл.",
        "download_missing": "Скачанный файл не найден на диске.",
        "download_incomplete": "Файл скачан не полностью: получено {actual} из {expected} байт.",
        "timeout": "<tg-emoji emoji-id=5870657884844462243>❌</tg-emoji> <b>Превышено время ожидания. Попробуй более короткое видео или повтори позже.</b>",
        "error": "<tg-emoji emoji-id=5870657884844462243>❌</tg-emoji> <b>SoundGif · Ошибка</b>\n<blockquote expandable>{error}</blockquote>",
    }

    LIMIT = 950_000
    MAX_INPUT = 100 * 1024 * 1024

    def __init__(self):
        self._lock = asyncio.Lock()

    @staticmethod
    def _options(raw):
        args = shlex.split(raw)
        options = {"size": 720, "square": False, "start": 0.0, "duration": None}
        while args:
            key = args.pop(0)
            if key == "--square":
                options["square"] = True
            elif key in ("--size", "--start", "--duration") and args:
                value = args.pop(0)
                options[key[2:]] = int(value) if key == "--size" else float(value)
            else:
                raise ValueError("Аргументы: --square, --size 128…720, --start секунды, --duration секунды.")
        if not 128 <= options["size"] <= 720:
            raise ValueError("Размер стороны должен быть от 128 до 720.")
        if not math.isfinite(options["start"]) or options["start"] < 0:
            raise ValueError("Начало должно быть неотрицательным числом секунд.")
        duration = options["duration"]
        if duration is not None and (not math.isfinite(duration) or not 0 < duration <= 120):
            raise ValueError("Длительность должна быть больше 0 и не больше 120 секунд.")
        return options

    @staticmethod
    async def _run(*args, timeout=240):
        process = await asyncio.create_subprocess_exec(
            *map(str, args), stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout)
        except (asyncio.TimeoutError, asyncio.CancelledError):
            if process.returncode is None:
                with contextlib.suppress(ProcessLookupError):
                    process.kill()
            await process.communicate()
            raise
        if process.returncode:
            detail = stderr.decode(errors="replace")[-1200:]
            raise RuntimeError(f"{Path(args[0]).name}: {detail}")
        return stdout

    async def _probe(self, path):
        result = await self._run(
            "ffprobe", "-v", "error", "-show_streams", "-show_format",
            "-of", "json", path, timeout=30,
        )
        return json.loads(result)

    @staticmethod
    def _patch(data):
        def walk(start, end):
            count = 0
            pos = start
            while pos + 8 <= end:
                size = struct.unpack_from(">I", data, pos)[0]
                kind = bytes(data[pos + 4:pos + 8])
                header = 8
                if size == 1:
                    if pos + 16 > end:
                        raise ValueError("Повреждён extended MP4 box.")
                    size = struct.unpack_from(">Q", data, pos + 8)[0]
                    header = 16
                elif size == 0:
                    size = end - pos
                if size < header or pos + size > end:
                    raise ValueError("Повреждена структура MP4.")
                body = pos + header
                if kind in (b"moov", b"trak", b"mdia"):
                    count += walk(body, pos + size)
                elif kind == b"hdlr" and body + 24 <= pos + size:
                    if data[body + 8:body + 12] == b"soun":
                        data[body + 8:body + 12] = b"vide"
                        count += 1
                    if data[body + 24:body + 29] == b"soun\x00":
                        data[body + 24:body + 28] = b"vide"
                pos += size
            return count
        return walk(0, len(data))

    async def _convert(self, source, target, options):
        info = await self._probe(source)
        streams = info.get("streams", [])
        video = next((s for s in streams if s.get("codec_type") == "video"
                      and not s.get("disposition", {}).get("attached_pic")), None)
        audio = next((s for s in streams if s.get("codec_type") == "audio"), None)
        if not video or not audio:
            raise ValueError("Нужно видео со звуковой дорожкой; в этом файле нет видео или аудио.")
        total = float(info.get("format", {}).get("duration") or video.get("duration") or 0)
        if not math.isfinite(total) or total <= options["start"]:
            raise ValueError("Не удалось определить длительность или начало находится за концом видео.")
        duration = min(total - options["start"], options["duration"] or total)
        if duration > 120:
            raise ValueError("Ролик длиннее 120 секунд. Выбери фрагмент через --start и --duration.")
        width, height = int(video["width"]), int(video["height"])
        sar = video.get("sample_aspect_ratio", "1:1").split(":")
        if len(sar) == 2 and all(part.isdigit() for part in sar) and int(sar[1]) and int(sar[0]):
            width *= int(sar[0]) / int(sar[1])
        rotation = float(video.get("tags", {}).get("rotate", 0))
        for side in video.get("side_data_list", []):
            if "rotation" in side:
                rotation = float(side["rotation"])
        if abs(rotation) % 180 == 90:
            width, height = height, width
        if min(width, height) <= 0:
            raise ValueError("Некорректное разрешение видео.")
        total_rate = self.LIMIT * 8 / duration / 1000 * 0.86
        audio_rate = min(96, max(24, int(total_rate * 0.24)))
        video_rate = min(1600, int(total_rate - audio_rate))
        if video_rate < 24:
            raise ValueError("Фрагмент слишком длинный для лимита размера; уменьши --duration.")
        for attempt in range(4):
            side = min(options["size"], 360 if video_rate < 160 else 480 if video_rate < 350 else 720)
            scale = min(side / width, side / height, 1)
            out_w = max(2, int(width * scale) // 2 * 2)
            out_h = max(2, int(height * scale) // 2 * 2)
            vf = f"scale={out_w}:{out_h},setsar=1"
            if options["square"]:
                square = max(out_w, out_h)
                vf += f",pad={square}:{square}:(ow-iw)/2:(oh-ih)/2"
            fps = 15 if video_rate < 160 else 24
            await self._run(
                "ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-y",
                "-ss", options["start"], "-i", source, "-t", duration,
                "-map", f"0:{video['index']}", "-map", f"0:{audio['index']}",
                "-map_metadata", "-1", "-map_chapters", "-1", "-sn", "-dn",
                "-vf", vf, "-r", fps, "-c:v", "libx264", "-profile:v", "baseline",
                "-pix_fmt", "yuv420p", "-preset", "fast", "-threads", "2",
                "-b:v", f"{video_rate}k", "-maxrate", f"{video_rate}k",
                "-bufsize", f"{video_rate * 2}k", "-c:a", "aac",
                "-b:a", f"{audio_rate}k", "-ar", "44100", "-ac", "1",
                "-movflags", "+faststart", target,
            )
            size = target.stat().st_size
            if 0 < size < self.LIMIT:
                break
            factor = min(0.8, self.LIMIT / max(size, 1) * 0.8)
            video_rate = max(24, int(video_rate * factor))
            audio_rate = max(24, int(audio_rate * factor))
        else:
            raise ValueError("Не удалось сжать файл до 950 КБ. Выбери более короткий фрагмент.")
        result = await self._probe(target)
        out_video = next(s for s in result["streams"] if s.get("codec_type") == "video")
        if not any(s.get("codec_type") == "audio" for s in result["streams"]):
            raise ValueError("В выбранном фрагменте нет звуковой дорожки.")
        metadata = (float(result["format"]["duration"]), out_video["width"], out_video["height"])
        data = bytearray(target.read_bytes())
        if self._patch(data) != 1:
            raise ValueError("Не удалось изменить MP4 handler звуковой дорожки.")
        target.write_bytes(data)
        return metadata

    async def _download(self, client, message: Message, folder: Path) -> Path:
        downloaded = await asyncio.wait_for(
            client.download_media(message, file=str(folder / "input")),
            timeout=180,
        )
        if not downloaded:
            raise ValueError(self.strings("download_empty"))
        source = Path(downloaded)
        if not source.is_file():
            raise ValueError(self.strings("download_missing"))
        actual = source.stat().st_size
        expected = message.document.size
        if actual == 0 or (expected and actual != expected):
            raise ValueError(
                self.strings("download_incomplete").format(
                    actual=actual, expected=expected or 0,
                )
            )
        if actual > self.MAX_INPUT:
            raise ValueError(self.strings("too_large"))
        return source

    @loader.command()
    async def soundgif(self, message: Message):
        """Reply to a video: [--square] [--size 720] [--start 0] [--duration 10] — GIF with sound."""
        if self._lock.locked():
            await utils.answer(message, self.strings("busy"))
            return
        if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
            await utils.answer(message, self.strings("no_ffmpeg"))
            return
        try:
            options = self._options(utils.get_args_raw(message))
        except ValueError as error:
            await utils.answer(
                message,
                self.strings("error").format(error=utils.escape_html(str(error))),
            )
            return
        source_message = await message.get_reply_message()
        if not source_message or not source_message.document:
            await utils.answer(message, self.strings("no_reply"))
            return
        if source_message.document.size > self.MAX_INPUT:
            await utils.answer(message, self.strings("too_large"))
            return
        client = message.client
        async with self._lock:
            status = await utils.answer(message, self.strings("rendering"))
            try:
                with tempfile.TemporaryDirectory(prefix="soundgif_") as folder:
                    source = await self._download(client, source_message, Path(folder))
                    target = Path(folder) / "SoundGif.mp4"
                    duration, width, height = await self._convert(source, target, options)
                    caption = self.strings("done").format(
                        size=target.stat().st_size / 1000,
                        duration=duration, width=width, height=height,
                    )
                    sent = await utils.answer(
                        status,
                        caption,
                        file=str(target),
                        force_document=False,
                        attributes=[
                            DocumentAttributeVideo(
                                duration=duration, w=width, h=height,
                                supports_streaming=True,
                            ),
                            DocumentAttributeAnimated(),
                            DocumentAttributeFilename(file_name="SoundGif.mp4"),
                        ],
                        parse_mode="HTML",
                    )
                    if isinstance(sent, list):
                        sent = sent[0]
                    status = sent
                    animated = any(
                        isinstance(attr, DocumentAttributeAnimated)
                        for attr in getattr(getattr(sent, "document", None), "attributes", [])
                    )
                    if not animated:
                        await utils.answer(
                            status,
                            caption + "\n\n" + self.strings("not_animated"),
                            parse_mode="HTML",
                        )
            except asyncio.TimeoutError:
                await utils.answer(status, self.strings("timeout"))
            except Exception as error:
                logger.exception("SoundGif conversion failed")
                detail = f"{type(error).__name__}: {error}"[:1600]
                await utils.answer(
                    status,
                    self.strings("error").format(error=utils.escape_html(detail)),
                )
