# ---------------------------------------------------------------------------------
#░█▀▄░▄▀▀▄░█▀▄░█▀▀▄░█▀▀▄░█▀▀▀░▄▀▀▄░░░█▀▄▀█
#░█░░░█░░█░█░█░█▄▄▀░█▄▄█░█░▀▄░█░░█░░░█░▀░█
#░▀▀▀░░▀▀░░▀▀░░▀░▀▀░▀░░▀░▀▀▀▀░░▀▀░░░░▀░░▒▀
# Name: VoiceToText
# Description: Transcribes voice/video messages to text via free APIs (Google STT / Groq Whisper)
# Author: @codrago
# ---------------------------------------------------------------------------------
# 🔒    Licensed under the GNU AGPLv3
# 🌐 https://www.gnu.org/licenses/agpl-3.0.html
# ---------------------------------------------------------------------------------
# Commands: v2t, v2tauto, v2tkey
# scope: heroku_only
# meta developer: @codrago_m
# requires: aiohttp
# meta banner: https://raw.githubusercontent.com/coddrago/modules/refs/heads/main/banner.png
# ---------------------------------------------------------------------------------

__version__ = (1, 1, 2)

import asyncio
import json
import logging
import os
import tempfile

import aiohttp
from herokutl.tl.types import Message

from .. import loader, utils

logger = logging.getLogger(__name__)

GOOGLE_SPEECH_KEY = "AIzaSyBOti4mM-6x9WDnZIjIeyEU21OpBXqWBgw"
GOOGLE_SPEECH_URL = "http://www.google.com/speech-api/v2/recognize"

GROQ_URL = "https://api.groq.com/openai/v1/audio/transcriptions"
GROQ_MODEL = "whisper-large-v3-turbo"

DEEPGRAM_URL = "https://api.deepgram.com/v1/listen"

MISTRAL_URL = "https://api.mistral.ai/v1/audio/transcriptions"
MISTRAL_MODEL = "voxtral-mini-latest"

PROVIDER_KEYS = {"groq", "deepgram", "mistral"}


@loader.tds
class VoiceToTextMod(loader.Module):
    """Transcribes voice/video messages to text via free APIs (Google STT / Groq Whisper / Deepgram / Mistral)"""

    strings = {
        "name": "VoiceToText",
        "_cls_doc": "Transcribes voice/video messages to text via free APIs (Google STT / Groq Whisper / Deepgram / Mistral)",
        "no_reply": "<emoji document_id=5219776129669276751>❌</emoji> <b>Reply to a voice or video message</b>",
        "not_voice": "<emoji document_id=5219776129669276751>❌</emoji> <b>This is not a voice or video message</b>",
        "processing": "<emoji document_id=5474304919651491706>🎧</emoji> <b>Transcribing...</b>",
        "result": "<emoji document_id=5474304919651491706>🎧</emoji> <b>Transcription:</b>\n\n<blockquote expandable>{text}</blockquote>",
        "empty_result": "<emoji document_id=5319088379281815108>🤷‍♀️</emoji> <b>Could not recognize speech</b>",
        "all_failed": "<emoji document_id=5980953710157632545>❌</emoji> <b>All providers failed to transcribe the audio</b>\n<code>{err}</code>",
        "ffmpeg_missing": "<emoji document_id=5980953710157632545>❌</emoji> <b>ffmpeg not found on the system</b>",
        "auto_on": "<emoji document_id=5409029658794537988>✅</emoji> <b>Auto-transcription enabled in this chat</b>",
        "auto_off": "<emoji document_id=5219776129669276751>❌</emoji> <b>Auto-transcription disabled in this chat</b>",
        "key_set": "<emoji document_id=5832546462478635761>🔒</emoji> <b>{provider} API key saved</b>",
        "key_removed": "<emoji document_id=5832546462478635761>🔒</emoji> <b>{provider} API key removed</b>",
        "key_usage": "<emoji document_id=5219776129669276751>❌</emoji> <b>Usage: .v2tkey &lt;groq|deepgram|mistral&gt; [api_key]</b>",
        "groq_api_key_doc": "Groq API key (free, console.groq.com) — fallback for long/complex audio",
        "deepgram_api_key_doc": "Deepgram API key (console.deepgram.com) — fallback provider",
        "mistral_api_key_doc": "Mistral API key (console.mistral.ai) — fallback provider (Voxtral)",
        "lang_doc": "Recognition language (Google/Deepgram — ru-RU format, Groq/Mistral use the short code)",
        "max_duration_doc": "Maximum audio duration in seconds for auto-transcription",
    }

    strings_ru = {
        "_cls_doc": "Расшифровывает голосовые/видеосообщения в текст через бесплатные API (Google STT / Groq Whisper / Deepgram / Mistral)",
        "no_reply": "<emoji document_id=5219776129669276751>❌</emoji> <b>Ответь на голосовое или видеосообщение</b>",
        "not_voice": "<emoji document_id=5219776129669276751>❌</emoji> <b>Это не голосовое и не видеосообщение</b>",
        "processing": "<emoji document_id=5474304919651491706>🎧</emoji> <b>Расшифровываю...</b>",
        "result": "<emoji document_id=5474304919651491706>🎧</emoji> <b>Расшифровка:</b>\n\n<blockquote expandable>{text}</blockquote>",
        "empty_result": "<emoji document_id=5319088379281815108>🤷‍♀️</emoji> <b>Не удалось разобрать речь</b>",
        "all_failed": "<emoji document_id=5980953710157632545>❌</emoji> <b>Все провайдеры не смогли расшифровать аудио</b>\n<code>{err}</code>",
        "ffmpeg_missing": "<emoji document_id=5980953710157632545>❌</emoji> <b>ffmpeg не найден в системе</b>",
        "auto_on": "<emoji document_id=5409029658794537988>✅</emoji> <b>Автотранскрибация включена в этом чате</b>",
        "auto_off": "<emoji document_id=5219776129669276751>❌</emoji> <b>Автотранскрибация выключена в этом чате</b>",
        "_cmd_doc_v2tauto": "[on/off] — включить/выключить автотранскрибацию входящих голосовых в текущем чате",
        "key_set": "<emoji document_id=5832546462478635761>🔒</emoji> <b>{provider} API ключ сохранён</b>",
        "key_removed": "<emoji document_id=5832546462478635761>🔒</emoji> <b>{provider} API ключ удалён</b>",
        "key_usage": "<emoji document_id=5219776129669276751>❌</emoji> <b>Использование: .v2tkey &lt;groq|deepgram|mistral&gt; [api_key]</b>",
        "groq_api_key_doc": "Groq API ключ (бесплатный, console.groq.com) — резерв для длинных/сложных аудио",
        "deepgram_api_key_doc": "Deepgram API ключ (console.deepgram.com) — резервный провайдер",
        "mistral_api_key_doc": "Mistral API ключ (console.mistral.ai) — резервный провайдер (Voxtral)",
        "lang_doc": "Язык распознавания (для Google/Deepgram — формат ru-RU, для Groq/Mistral берётся короткий код)",
        "max_duration_doc": "Максимальная длительность аудио в секундах для автотранскрибации",
    }

    def __init__(self):
        self.config = loader.ModuleConfig(
            loader.ConfigValue(
                "groq_api_key",
                "",
                lambda: self.strings("groq_api_key_doc"),
                validator=loader.validators.Hidden(),
            ),
            loader.ConfigValue(
                "deepgram_api_key",
                "",
                lambda: self.strings("deepgram_api_key_doc"),
                validator=loader.validators.Hidden(),
            ),
            loader.ConfigValue(
                "mistral_api_key",
                "",
                lambda: self.strings("mistral_api_key_doc"),
                validator=loader.validators.Hidden(),
            ),
            loader.ConfigValue(
                "lang",
                "ru-RU",
                lambda: self.strings("lang_doc"),
                validator=loader.validators.String(),
            ),
            loader.ConfigValue(
                "max_duration",
                180,
                lambda: self.strings("max_duration_doc"),
                validator=loader.validators.Integer(minimum=1),
            ),
        )

    async def client_ready(self, client, db):
        self.client = client

    async def _run(self, *cmd: str) -> tuple[int, bytes, bytes]:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        return proc.returncode, stdout, stderr

    async def _to_flac(self, src_path: str) -> str:
        dst_path = src_path + ".flac"
        rc, _, stderr = await self._run(
            "ffmpeg", "-y", "-i", src_path,
            "-ar", "16000", "-ac", "1", "-f", "flac", dst_path,
        )
        if rc != 0 or not os.path.exists(dst_path):
            raise RuntimeError(f"ffmpeg error: {stderr.decode(errors='replace')[:300]}")
        return dst_path

    async def _probe_duration(self, path: str) -> float:
        rc, stdout, _ = await self._run(
            "ffprobe", "-v", "error", "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1", path,
        )
        try:
            return float(stdout.decode().strip())
        except Exception:
            return 0.0

    async def _google_stt(self, flac_bytes: bytes, lang: str) -> str | None:
        headers = {"Content-Type": "audio/x-flac; rate=16000"}
        params = {
            "output": "json",
            "lang": lang,
            "key": GOOGLE_SPEECH_KEY,
            "pFilter": "0",
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(
                GOOGLE_SPEECH_URL, params=params, headers=headers, data=flac_bytes, timeout=30
            ) as resp:
                text = await resp.text()
                if resp.status != 200:
                    raise RuntimeError(f"google http {resp.status}: {text[:200]}")

        best = None
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            result = obj.get("result") or []
            if result and result[0].get("alternative"):
                best = result[0]["alternative"][0].get("transcript")
                break
        return best

    async def _groq_stt(self, flac_bytes: bytes, key: str, lang: str) -> str | None:
        form = aiohttp.FormData()
        form.add_field("file", flac_bytes, filename="audio.flac", content_type="audio/flac")
        form.add_field("model", GROQ_MODEL)
        form.add_field("response_format", "json")
        short_lang = (lang or "").split("-")[0]
        if short_lang:
            form.add_field("language", short_lang)

        headers = {"Authorization": f"Bearer {key}"}
        async with aiohttp.ClientSession() as session:
            async with session.post(GROQ_URL, data=form, headers=headers, timeout=60) as resp:
                body = await resp.text()
                if resp.status != 200:
                    raise RuntimeError(f"groq http {resp.status}: {body[:300]}")
                data = json.loads(body)
                return data.get("text")

    async def _deepgram_stt(self, flac_bytes: bytes, key: str, lang: str) -> str | None:
        headers = {
            "Authorization": f"Token {key}",
            "Content-Type": "audio/flac",
        }
        params = {
            "language": lang or "ru-RU",
            "punctuate": "true",
            "smart_format": "true",
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(
                DEEPGRAM_URL, params=params, headers=headers, data=flac_bytes, timeout=60
            ) as resp:
                body = await resp.text()
                if resp.status != 200:
                    raise RuntimeError(f"deepgram http {resp.status}: {body[:300]}")
                data = json.loads(body)
                try:
                    return data["results"]["channels"][0]["alternatives"][0]["transcript"]
                except (KeyError, IndexError):
                    return None

    async def _mistral_stt(self, flac_bytes: bytes, key: str, lang: str) -> str | None:
        form = aiohttp.FormData()
        form.add_field("file", flac_bytes, filename="audio.flac", content_type="audio/flac")
        form.add_field("model", MISTRAL_MODEL)
        short_lang = (lang or "").split("-")[0]
        if short_lang:
            form.add_field("language", short_lang)

        headers = {"Authorization": f"Bearer {key}"}
        async with aiohttp.ClientSession() as session:
            async with session.post(MISTRAL_URL, data=form, headers=headers, timeout=60) as resp:
                body = await resp.text()
                if resp.status != 200:
                    raise RuntimeError(f"mistral http {resp.status}: {body[:300]}")
                data = json.loads(body)
                return data.get("text")

    async def _transcribe(self, flac_bytes: bytes) -> str:
        lang = self.config["lang"] or "ru-RU"
        errors = []

        mistral_key = self.config["mistral_api_key"]
        if mistral_key:
            try:
                text = await self._mistral_stt(flac_bytes, mistral_key, lang)
                if text:
                    return text.strip()
            except Exception as e:
                errors.append(f"mistral: {e}")

        deepgram_key = self.config["deepgram_api_key"]
        if deepgram_key:
            try:
                text = await self._deepgram_stt(flac_bytes, deepgram_key, lang)
                if text:
                    return text.strip()
            except Exception as e:
                errors.append(f"deepgram: {e}")

        groq_key = self.config["groq_api_key"]
        if groq_key:
            try:
                text = await self._groq_stt(flac_bytes, groq_key, lang)
                if text:
                    return text.strip()
            except Exception as e:
                errors.append(f"groq: {e}")

        try:
            text = await self._google_stt(flac_bytes, lang)
            if text:
                return text.strip()
        except Exception as e:
            errors.append(f"google: {e}")

        raise RuntimeError("\n".join(errors) if errors else "empty response")

    async def _process_media(self, message: Message, target: Message) -> str | None:
        with tempfile.TemporaryDirectory() as tmpdir:
            src_path = os.path.join(tmpdir, "input.ogg")
            await self.client.download_media(target, file=src_path)

            try:
                flac_path = await self._to_flac(src_path)
            except FileNotFoundError:
                await utils.answer(message, self.strings["ffmpeg_missing"])
                return None
            except RuntimeError as e:
                await utils.answer(message, self.strings["all_failed"].format(err=str(e)))
                return None

            with open(flac_path, "rb") as f:
                flac_bytes = f.read()

        try:
            text = await self._transcribe(flac_bytes)
        except RuntimeError as e:
            await utils.answer(message, self.strings["all_failed"].format(err=str(e)))
            return None

        if not text:
            await utils.answer(message, self.strings["empty_result"])
            return None

        return text

    def _is_voice_media(self, msg: Message) -> bool:
        return bool(msg and (msg.voice or msg.video_note))

    @loader.command(ru_doc="(reply на голосовое/видеосообщение) — расшифровать в текст")
    async def v2t(self, message: Message):
        """(reply to a voice/video message) — transcribe it to text"""
        reply = await message.get_reply_message()
        if not reply:
            await utils.answer(message, self.strings["no_reply"])
            return
        if not self._is_voice_media(reply):
            await utils.answer(message, self.strings["not_voice"])
            return

        await utils.answer(message, self.strings["processing"])
        text = await self._process_media(message, reply)
        if text:
            await utils.answer(message, self.strings["result"].format(text=utils.escape_html(text)))

    @loader.command()
    async def v2tauto(self, message: Message):
        """[on/off] — enable/disable auto-transcription of incoming voice messages in this chat"""
        args = utils.get_args_raw(message).strip().lower()
        chat_id = message.chat_id
        if chat_id is None:
            return
        chats = set(self.get("auto_chats", []))
        if args in ("on", "1", "true", "вкл"):
            enabled = True
        elif args in ("off", "0", "false", "выкл"):
            enabled = False
        else:
            enabled = chat_id not in chats

        if enabled:
            chats.add(chat_id)
        else:
            chats.discard(chat_id)
        self.set("auto_chats", sorted(chats))

        await utils.answer(
            message,
            self.strings["auto_on"] if enabled else self.strings["auto_off"],
        )

    @loader.command(ru_doc="<groq|deepgram|mistral> [api_key] — задать/удалить ключ провайдера (резервного)")
    async def v2tkey(self, message: Message):
        """<groq|deepgram|mistral> [api_key] — set/remove a provider API key (fallback)"""
        args = utils.get_args(message)

        if len(args) == 1 and args[0].lower() not in PROVIDER_KEYS:
            provider = "groq"
            key = args[0]
        elif args and args[0].lower() in PROVIDER_KEYS:
            provider = args[0].lower()
            key = args[1] if len(args) > 1 else ""
        else:
            await utils.answer(message, self.strings["key_usage"])
            return

        config_key = f"{provider}_api_key"
        if not key:
            self.config[config_key] = ""
            await utils.answer(message, self.strings["key_removed"].format(provider=provider.capitalize()))
            return

        self.config[config_key] = key
        await utils.answer(message, self.strings["key_set"].format(provider=provider.capitalize()))

    @loader.watcher(only_messages=True)
    async def watcher(self, message: Message):
        if message.chat_id is None or message.chat_id not in self.get("auto_chats", []):
            return
        if message.out:
            return
        if not self._is_voice_media(message):
            return

        with tempfile.TemporaryDirectory() as tmpdir:
            src_path = os.path.join(tmpdir, "probe.ogg")
            await self.client.download_media(message, file=src_path)
            duration = await self._probe_duration(src_path)

        if duration and duration > self.config["max_duration"]:
            return

        try:
            text = await self._process_media(message, message)
        except Exception as e:
            logger.error(f"VoiceToText watcher error: {e}")
            return

        if text:
            await utils.answer(
                message,
                self.strings["result"].format(text=utils.escape_html(text)),
                reply_to=message.id,
                parse_mode="HTML",
            )
