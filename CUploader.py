# ---------------------------------------------------------------------------------
#░█▀▄░▄▀▀▄░█▀▄░█▀▀▄░█▀▀▄░█▀▀▀░▄▀▀▄░░░█▀▄▀█
#░█░░░█░░█░█░█░█▄▄▀░█▄▄█░█░▀▄░█░░█░░░█░▀░█
#░▀▀▀░░▀▀░░▀▀░░▀░▀▀░▀░░▀░▀▀▀▀░░▀▀░░░░▀░░▒▀
# Name: C:Uploader
# Description: Uploads a replied file/media to a chosen file hosting service
# Author: @codrago
# ---------------------------------------------------------------------------------
# 🔒    Licensed under the GNU AGPLv3
# 🌐 https://www.gnu.org/licenses/agpl-3.0.html
# ---------------------------------------------------------------------------------
# Commands: x0, x0at, tmpfiles, uguu, quax, gofile, filebin, pixeldrain, imgbb, kappa
# scope: heroku_only
# meta developer: @codrago_m
# meta banner: https://raw.githubusercontent.com/coddrago/modules/refs/heads/main/banner.png
# ---------------------------------------------------------------------------------

__version__ = (3, 0, 0)

import base64
import logging
import os
import random
import shutil
import string
import tempfile

import aiohttp
from herokutl.tl.types import Message

from .. import loader, utils

logger = logging.getLogger(__name__)

UA = "Mozilla/5.0 (compatible; UploaderMod/3.0; +https://github.com/coddrago/Heroku)"


def _rand_bin(n: int = 10) -> str:
    return "".join(random.choices(string.ascii_lowercase + string.digits, k=n))


@loader.tds
class UploaderMod(loader.Module):
    """Uploads a replied file/media to a chosen file hosting service (0x0.st, x0.at, kappa.lol, tmpfiles.org, uguu.se, qu.ax, pixeldrain.com, gofile.io, filebin.net, imgbb.com)"""

    strings = {
        "name": "Uploader",
        "_cls_doc": "Uploads a replied file/media to a chosen file hosting service (0x0.st, x0.at, kappa.lol, tmpfiles.org, uguu.se, qu.ax, pixeldrain.com, gofile.io, filebin.net, imgbb.com)",
        "no_file": "<emoji document_id=5219776129669276751>❌</emoji> <b>Reply to a file or media message</b>",
        "processing": "<emoji document_id=5474304919651491706>📤</emoji> <b>Uploading to {service}...</b>",
        "result": "<emoji document_id=5409029658794537988>✅</emoji> <b>Uploaded to {service}:</b>\n{url}",
        "failed": "<emoji document_id=5219776129669276751>❌</emoji> <b>{service} upload failed:</b>\n<code>{err}</code>",
        "need_key": (
            "<emoji document_id=5219776129669276751>❌</emoji> <b>{service} requires an API key.</b>\n"
            "Open <code>.config Uploader</code> and set <code>{field}</code>."
        ),
        "gofile_token_doc": "Gofile API token (optional, gofile.io/myProfile) — leave empty for anonymous upload",
        "pixeldrain_key_doc": "Pixeldrain API key (REQUIRED, pixeldrain.com/user/api_keys) — anonymous uploads no longer allowed",
        "imgbb_key_doc": "ImgBB API key (REQUIRED, get one at api.imgbb.com) — images only",
        "timeout_doc": "Upload timeout in seconds",
    }

    strings_ru = {
        "_cls_doc": "Заливает файл/медиа из реплая на выбранный файлхостинг",
        "no_file": "<emoji document_id=5219776129669276751>❌</emoji> <b>Ответь на файл или медиасообщение</b>",
        "processing": "<emoji document_id=5474304919651491706>📤</emoji> <b>Заливаю на {service}...</b>",
        "result": "<emoji document_id=5409029658794537988>✅</emoji> <b>Залито на {service}:</b>\n{url}",
        "failed": "<emoji document_id=5219776129669276751>❌</emoji> <b>Ошибка загрузки на {service}:</b>\n<code>{err}</code>",
        "need_key": (
            "<emoji document_id=5219776129669276751>❌</emoji> <b>Для {service} нужен API-ключ.</b>\n"
            "Открой <code>.config Uploader</code> и впиши его в поле <code>{field}</code>."
        ),
        "gofile_token_doc": "Gofile API токен (опционально, gofile.io/myProfile) — можно оставить пустым для анонимной загрузки",
        "pixeldrain_key_doc": "Pixeldrain API ключ (ОБЯЗАТЕЛЕН, pixeldrain.com/user/api_keys) — анонимные загрузки больше не разрешены",
        "imgbb_key_doc": "ImgBB API ключ (ОБЯЗАТЕЛЕН, получить на api.imgbb.com) — только изображения",
        "timeout_doc": "Таймаут загрузки в секундах",
    }

    def __init__(self):
        self.config = loader.ModuleConfig(
            loader.ConfigValue(
                "gofile_token",
                "",
                lambda: self.strings("gofile_token_doc"),
                validator=loader.validators.Hidden(),
            ),
            loader.ConfigValue(
                "pixeldrain_key",
                "",
                lambda: self.strings("pixeldrain_key_doc"),
                validator=loader.validators.Hidden(),
            ),
            loader.ConfigValue(
                "imgbb_key",
                "",
                lambda: self.strings("imgbb_key_doc"),
                validator=loader.validators.Hidden(),
            ),
            loader.ConfigValue(
                "timeout",
                60,
                lambda: self.strings("timeout_doc"),
                validator=loader.validators.Integer(minimum=10),
            ),
        )

    async def client_ready(self, client, db):
        self.client = client

    def _session(self) -> aiohttp.ClientSession:
        timeout = aiohttp.ClientTimeout(total=self.config["timeout"])
        return aiohttp.ClientSession(timeout=timeout, headers={"User-Agent": UA})

    async def _up_0x0_clone(self, base_url: str, file_bytes: bytes, filename: str) -> str:
        data = aiohttp.FormData()
        data.add_field("file", file_bytes, filename=filename, content_type="application/octet-stream")
        async with self._session() as session:
            async with session.post(base_url, data=data) as resp:
                text = (await resp.text()).strip()
                if resp.status != 200 or not text.startswith("http"):
                    raise RuntimeError(text[:200])
                return text

    async def _up_kappa(self, file_bytes: bytes, filename: str) -> str:
        data = aiohttp.FormData()
        data.add_field("file", file_bytes, filename=filename, content_type="application/octet-stream")
        async with self._session() as session:
            async with session.post("https://kappa.lol/api/upload", data=data) as resp:
                body = await resp.json(content_type=None)
                link = body.get("link")
                if not link:
                    raise RuntimeError(str(body)[:200])
                return link

    async def _up_tmpfiles(self, file_bytes: bytes, filename: str) -> str:
        data = aiohttp.FormData()
        data.add_field("file", file_bytes, filename=filename, content_type="application/octet-stream")
        async with self._session() as session:
            async with session.post("https://tmpfiles.org/api/v1/upload", data=data) as resp:
                body = await resp.json(content_type=None)
                if body.get("status") != "success":
                    raise RuntimeError(str(body)[:200])
                url = body["data"]["url"]
                return url.replace("tmpfiles.org/", "tmpfiles.org/dl/", 1)

    async def _up_pomf_family(self, base_url: str, file_bytes: bytes, filename: str) -> str:
        data = aiohttp.FormData()
        data.add_field("files[]", file_bytes, filename=filename, content_type="application/octet-stream")
        async with self._session() as session:
            async with session.post(base_url, data=data) as resp:
                body = await resp.json(content_type=None)
                if not body.get("success"):
                    raise RuntimeError(str(body)[:200])
                f = body["files"][0]
                return f["url"] if isinstance(f, dict) else f

    async def _up_pixeldrain(self, file_bytes: bytes, filename: str) -> str:
        key = self.config["pixeldrain_key"]
        auth = aiohttp.BasicAuth("", key)
        async with self._session() as session:
            async with session.put(
                f"https://pixeldrain.com/api/file/{filename}", data=file_bytes, auth=auth
            ) as resp:
                body = await resp.json(content_type=None)
                file_id = body.get("id")
                if not file_id:
                    raise RuntimeError(str(body)[:200])
                return f"https://pixeldrain.com/u/{file_id}"

    async def _up_gofile(self, file_bytes: bytes, filename: str) -> str:
        token = self.config["gofile_token"]
        async with self._session() as session:
            async with session.get("https://api.gofile.io/servers") as resp:
                servers_body = await resp.json(content_type=None)
            server = servers_body["data"]["servers"][0]["name"]

            data = aiohttp.FormData()
            data.add_field("file", file_bytes, filename=filename, content_type="application/octet-stream")
            if token:
                data.add_field("token", token)

            async with session.post(f"https://{server}.gofile.io/contents/uploadfile", data=data) as resp:
                body = await resp.json(content_type=None)
                if body.get("status") != "ok":
                    raise RuntimeError(str(body)[:200])
                return body["data"]["downloadPage"]

    async def _up_filebin(self, file_bytes: bytes, filename: str) -> str:
        binname = _rand_bin()
        async with self._session() as session:
            async with session.post(
                f"https://filebin.net/{binname}/{filename}",
                data=file_bytes,
                headers={"Content-Type": "application/octet-stream"},
            ) as resp:
                if resp.status not in (200, 201):
                    text = await resp.text()
                    raise RuntimeError(text[:200])
                return f"https://filebin.net/{binname}/{filename}"

    async def _up_imgbb(self, file_bytes: bytes, filename: str) -> str:
        key = self.config["imgbb_key"]
        b64 = base64.b64encode(file_bytes).decode()
        data = aiohttp.FormData()
        data.add_field("image", b64)
        async with self._session() as session:
            async with session.post(f"https://api.imgbb.com/1/upload?key={key}", data=data) as resp:
                body = await resp.json(content_type=None)
                if not body.get("success"):
                    raise RuntimeError(str(body)[:300])
                return body["data"]["url"]

    async def _run_upload(self, message: Message, service: str, upload_fn, key_field: str = None):
        if key_field and not self.config[key_field]:
            await utils.answer(
                message,
                self.strings["need_key"].format(service=service, field=key_field),
            )
            return

        reply = await message.get_reply_message()
        target = reply if (reply and reply.media) else (message if message.media else None)
        if not target:
            await utils.answer(message, self.strings["no_file"])
            return

        await utils.answer(message, self.strings["processing"].format(service=service))

        tmpdir = tempfile.mkdtemp(prefix="upl_")
        try:
            path = await self.client.download_media(target, file=tmpdir + "/")
            filename = os.path.basename(path)
            with open(path, "rb") as f:
                file_bytes = f.read()
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

        try:
            url = await upload_fn(file_bytes, filename)
        except Exception as e:
            await utils.answer(message, self.strings["failed"].format(service=service, err=str(e)[:300]))
            return

        await utils.answer(message, self.strings["result"].format(service=service, url=url))

    @loader.command(ru_doc="(в ответ на файл/медиа) — загрузить на 0x0.st")
    async def x0(self, message: Message):
        """(reply to a file/media) — upload to 0x0.st"""
        await self._run_upload(message, "0x0.st", lambda fb, fn: self._up_0x0_clone("https://0x0.st", fb, fn))

    @loader.command(ru_doc="(в ответ на файл/медиа) — загрузить на x0.at")
    async def x0at(self, message: Message):
        """(reply to a file/media) — upload to x0.at"""
        await self._run_upload(message, "x0.at", lambda fb, fn: self._up_0x0_clone("https://x0.at", fb, fn))

    @loader.command(ru_doc="(в ответ на файл/медиа) — загрузить на kappa.lol")
    async def kappa(self, message: Message):
        """(reply to a file/media) — upload to kappa.lol"""
        await self._run_upload(message, "kappa.lol", self._up_kappa)

    @loader.command(ru_doc="(в ответ на файл/медиа) — загрузить на tmpfiles.org")
    async def tmpfiles(self, message: Message):
        """(reply to a file/media) — upload to tmpfiles.org"""
        await self._run_upload(message, "tmpfiles.org", self._up_tmpfiles)

    @loader.command(ru_doc="(в ответ на файл/медиа) — загрузить на uguu.se")
    async def uguu(self, message: Message):
        """(reply to a file/media) — upload to uguu.se"""
        await self._run_upload(
            message, "uguu.se", lambda fb, fn: self._up_pomf_family("https://uguu.se/upload.php", fb, fn)
        )

    @loader.command(ru_doc="(в ответ на файл/медиа) — загрузить на qu.ax")
    async def quax(self, message: Message):
        """(reply to a file/media) — upload to qu.ax"""
        await self._run_upload(
            message, "qu.ax", lambda fb, fn: self._up_pomf_family("https://qu.ax/upload.php", fb, fn)
        )

    @loader.command(ru_doc="(в ответ на файл/медиа) — загрузить на pixeldrain.com (нужен API-ключ)")
    async def pixeldrain(self, message: Message):
        """(reply to a file/media) — upload to pixeldrain.com (requires API key)"""
        await self._run_upload(message, "pixeldrain", self._up_pixeldrain, key_field="pixeldrain_key")

    @loader.command(ru_doc="(в ответ на файл/медиа) — загрузить на gofile.io")
    async def gofile(self, message: Message):
        """(reply to a file/media) — upload to gofile.io"""
        await self._run_upload(message, "gofile", self._up_gofile)

    @loader.command(ru_doc="(в ответ на файл/медиа) — загрузить на filebin.net")
    async def filebin(self, message: Message):
        """(reply to a file/media) — upload to filebin.net"""
        await self._run_upload(message, "filebin.net", self._up_filebin)

    @loader.command(ru_doc="(в ответ на файл/медиа, только изображения) — загрузить на imgbb.com (нужен API-ключ)")
    async def imgbb(self, message: Message):
        """(reply to a file/media, images only) — upload to imgbb.com (requires API key)"""
        await self._run_upload(message, "imgbb", self._up_imgbb, key_field="imgbb_key")
