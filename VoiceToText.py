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
# Commands: v2t, v2tauto, v2tlist, v2tkey
# scope: heroku_only
# meta developer: @codrago_m
# requires: aiohttp
# meta banner: https://raw.githubusercontent.com/coddrago/modules/refs/heads/main/banner.png
# ---------------------------------------------------------------------------------

__version__ = (1, 2, 0)

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
        "no_reply": "<tg-emoji emoji-id=\"5267310332325437921\">💢</tg-emoji> <b>Reply to a voice or video message</b>",
        "not_voice": "<tg-emoji emoji-id=\"5267310332325437921\">💢</tg-emoji> <b>This is not a voice or video message</b>",
        "processing": "<tg-emoji emoji-id=\"5267003499861810620\">✨</tg-emoji> <b>Transcribing...</b>",
        "result": "<tg-emoji emoji-id=\"5267003499861810620\">✨</tg-emoji> <b>Transcription:</b>\n\n<blockquote expandable>{text}</blockquote>",
        "empty_result": "<tg-emoji emoji-id=\"5267139079094442194\">🫥</tg-emoji> <b>Could not recognize speech</b>",
        "all_failed": "<tg-emoji emoji-id=\"5267310332325437921\">💢</tg-emoji> <b>All providers failed to transcribe the audio</b>\n<code>{err}</code>",
        "ffmpeg_missing": "<tg-emoji emoji-id=\"5267310332325437921\">💢</tg-emoji> <b>ffmpeg not found on the system</b>",
        "auto_on": "<tg-emoji emoji-id=\"5267003499861810620\">✨</tg-emoji> <b>Auto-transcription enabled in this chat</b>",
        "auto_off": "<tg-emoji emoji-id=\"5264902955911388775\">🌙</tg-emoji> <b>Auto-transcription disabled in this chat</b>",
        "key_set": "<tg-emoji emoji-id=\"5267003499861810620\">✨</tg-emoji> <b>{provider} API key saved</b>",
        "key_removed": "<tg-emoji emoji-id=\"5264902955911388775\">🌙</tg-emoji> <b>{provider} API key removed</b>",
        "key_usage": "<tg-emoji emoji-id=\"5267310332325437921\">💢</tg-emoji> <b>Usage:</b> <code>{prefix}v2tkey &lt;groq|deepgram|mistral&gt; [api_key]</code>",
        "groq_api_key_doc": "Groq API key (free, console.groq.com) — fallback for long/complex audio",
        "deepgram_api_key_doc": "Deepgram API key (console.deepgram.com) — fallback provider",
        "mistral_api_key_doc": "Mistral API key (console.mistral.ai) — fallback provider (Voxtral)",
        "lang_doc": "Recognition language (Google/Deepgram — ru-RU format, Groq/Mistral use the short code)",
        "max_duration_doc": "Maximum audio duration in seconds for auto-transcription",
        "list_header": '<tg-emoji emoji-id="5267003499861810620">✨</tg-emoji> <b>Chats with auto-transcription: {count}</b>',
        "list_empty": '<tg-emoji emoji-id="5267139079094442194">🫥</tg-emoji> <b>Auto-transcription is not enabled in any chat.</b>\nEnable it in the desired chat: <code>{prefix}v2tauto on</code>',
        "list_unavailable": "Chat unavailable",
        "list_page": 'Page {page}/{pages} · <code>{prefix}v2tlist &lt;page&gt;</code>',
        "list_usage": '<tg-emoji emoji-id="5267310332325437921">💢</tg-emoji> <b>Enter a page from 1 to {pages}:</b> <code>{prefix}v2tlist &lt;page&gt;</code>',
        "_cmd_doc_v2t": "(reply to a voice/video message) — transcribe it to text",
        "_cmd_doc_v2tauto": "[on/off] — enable/disable auto-transcription of incoming voice messages in this chat",
        "_cmd_doc_v2tlist": "[page] — list chats with auto-transcription enabled",
        "_cmd_doc_v2tkey": "<groq|deepgram|mistral> [api_key] — set/remove a provider API key (fallback)",
    }

    strings_ru = {
        "_cls_doc": "Расшифровывает голосовые/видеосообщения в текст через бесплатные API (Google STT / Groq Whisper / Deepgram / Mistral)",
        "no_reply": "<tg-emoji emoji-id=\"5267310332325437921\">💢</tg-emoji> <b>Ответь на голосовое или видеосообщение</b>",
        "not_voice": "<tg-emoji emoji-id=\"5267310332325437921\">💢</tg-emoji> <b>Это не голосовое и не видеосообщение</b>",
        "processing": "<tg-emoji emoji-id=\"5267003499861810620\">✨</tg-emoji> <b>Расшифровываю...</b>",
        "result": "<tg-emoji emoji-id=\"5267003499861810620\">✨</tg-emoji> <b>Расшифровка:</b>\n\n<blockquote expandable>{text}</blockquote>",
        "empty_result": "<tg-emoji emoji-id=\"5267139079094442194\">🫥</tg-emoji> <b>Не удалось разобрать речь</b>",
        "all_failed": "<tg-emoji emoji-id=\"5267310332325437921\">💢</tg-emoji> <b>Все провайдеры не смогли расшифровать аудио</b>\n<code>{err}</code>",
        "ffmpeg_missing": "<tg-emoji emoji-id=\"5267310332325437921\">💢</tg-emoji> <b>ffmpeg не найден в системе</b>",
        "auto_on": "<tg-emoji emoji-id=\"5267003499861810620\">✨</tg-emoji> <b>Автотранскрибация включена в этом чате</b>",
        "auto_off": "<tg-emoji emoji-id=\"5264902955911388775\">🌙</tg-emoji> <b>Автотранскрибация выключена в этом чате</b>",
        "_cmd_doc_v2tauto": "[on/off] — включить/выключить автотранскрибацию входящих голосовых в текущем чате",
        "key_set": "<tg-emoji emoji-id=\"5267003499861810620\">✨</tg-emoji> <b>{provider} API ключ сохранён</b>",
        "key_removed": "<tg-emoji emoji-id=\"5264902955911388775\">🌙</tg-emoji> <b>{provider} API ключ удалён</b>",
        "key_usage": "<tg-emoji emoji-id=\"5267310332325437921\">💢</tg-emoji> <b>Использование:</b> <code>{prefix}v2tkey &lt;groq|deepgram|mistral&gt; [api_key]</code>",
        "groq_api_key_doc": "Groq API ключ (бесплатный, console.groq.com) — резерв для длинных/сложных аудио",
        "deepgram_api_key_doc": "Deepgram API ключ (console.deepgram.com) — резервный провайдер",
        "mistral_api_key_doc": "Mistral API ключ (console.mistral.ai) — резервный провайдер (Voxtral)",
        "lang_doc": "Язык распознавания (для Google/Deepgram — формат ru-RU, для Groq/Mistral берётся короткий код)",
        "max_duration_doc": "Максимальная длительность аудио в секундах для автотранскрибации",
        "list_header": '<tg-emoji emoji-id="5267003499861810620">✨</tg-emoji> <b>Чаты с авторасшифровкой: {count}</b>',
        "list_empty": '<tg-emoji emoji-id="5267139079094442194">🫥</tg-emoji> <b>Авторасшифровка нигде не включена.</b>\nВключить в нужном чате: <code>{prefix}v2tauto on</code>',
        "list_unavailable": "Чат недоступен",
        "list_page": 'Страница {page}/{pages} · <code>{prefix}v2tlist &lt;страница&gt;</code>',
        "list_usage": '<tg-emoji emoji-id="5267310332325437921">💢</tg-emoji> <b>Укажи страницу от 1 до {pages}:</b> <code>{prefix}v2tlist &lt;страница&gt;</code>',
        "_cmd_doc_v2t": "(ответ на голосовое/видеосообщение) — расшифровать в текст",
        "_cmd_doc_v2tlist": "[страница] — чаты, в которых включена авторасшифровка",
        "_cmd_doc_v2tkey": "<groq|deepgram|mistral> [api_key] — задать/удалить ключ резервного провайдера",
    }

    strings_ua = {
        "_cls_doc": "Розшифровує голосові та відеоповідомлення за допомогою Google STT / Groq Whisper / Deepgram / Mistral",
        "no_reply": '<tg-emoji emoji-id="5267310332325437921">💢</tg-emoji> <b>Дай відповідь на голосове або відеоповідомлення</b>',
        "not_voice": '<tg-emoji emoji-id="5267310332325437921">💢</tg-emoji> <b>Це не голосове і не відеоповідомлення</b>',
        "processing": '<tg-emoji emoji-id="5267003499861810620">✨</tg-emoji> <b>Розшифровую...</b>',
        "result": '<tg-emoji emoji-id="5267003499861810620">✨</tg-emoji> <b>Розшифровка:</b>\n\n<blockquote expandable>{text}</blockquote>',
        "empty_result": '<tg-emoji emoji-id="5267139079094442194">🫥</tg-emoji> <b>Не вдалося розпізнати мовлення</b>',
        "all_failed": '<tg-emoji emoji-id="5267310332325437921">💢</tg-emoji> <b>Жоден провайдер не зміг розшифрувати аудіо</b>\n<code>{err}</code>',
        "ffmpeg_missing": '<tg-emoji emoji-id="5267310332325437921">💢</tg-emoji> <b>ffmpeg не знайдено в системі</b>',
        "auto_on": '<tg-emoji emoji-id="5267003499861810620">✨</tg-emoji> <b>Авторозшифровку ввімкнено в цьому чаті</b>',
        "auto_off": '<tg-emoji emoji-id="5264902955911388775">🌙</tg-emoji> <b>Авторозшифровку вимкнено в цьому чаті</b>',
        "key_set": '<tg-emoji emoji-id="5267003499861810620">✨</tg-emoji> <b>API-ключ {provider} збережено</b>',
        "key_removed": '<tg-emoji emoji-id="5264902955911388775">🌙</tg-emoji> <b>API-ключ {provider} видалено</b>',
        "key_usage": '<tg-emoji emoji-id="5267310332325437921">💢</tg-emoji> <b>Використання:</b> <code>{prefix}v2tkey &lt;groq|deepgram|mistral&gt; [api_key]</code>',
        "groq_api_key_doc": "API-ключ Groq (console.groq.com) — резерв для довгих або складних аудіо",
        "deepgram_api_key_doc": "API-ключ Deepgram (console.deepgram.com) — резервний провайдер",
        "mistral_api_key_doc": "API-ключ Mistral (console.mistral.ai) — резервний провайдер (Voxtral)",
        "lang_doc": "Мова розпізнавання (Google/Deepgram — формат ru-RU, Groq/Mistral — короткий код)",
        "max_duration_doc": "Максимальна тривалість аудіо в секундах для авторозшифровки",
        "list_header": '<tg-emoji emoji-id="5267003499861810620">✨</tg-emoji> <b>Чати з авторозшифровкою: {count}</b>',
        "list_empty": '<tg-emoji emoji-id="5267139079094442194">🫥</tg-emoji> <b>Авторозшифровку ніде не ввімкнено.</b>\nУвімкнути в потрібному чаті: <code>{prefix}v2tauto on</code>',
        "list_unavailable": "Чат недоступний",
        "list_page": 'Сторінка {page}/{pages} · <code>{prefix}v2tlist &lt;сторінка&gt;</code>',
        "list_usage": '<tg-emoji emoji-id="5267310332325437921">💢</tg-emoji> <b>Вкажи сторінку від 1 до {pages}:</b> <code>{prefix}v2tlist &lt;сторінка&gt;</code>',
        "_cmd_doc_v2t": "(відповідь на голосове/відеоповідомлення) — розшифрувати в текст",
        "_cmd_doc_v2tauto": "[on/off] — увімкнути/вимкнути авторозшифровку вхідних голосових у цьому чаті",
        "_cmd_doc_v2tlist": "[сторінка] — чати, у яких увімкнено авторозшифровку",
        "_cmd_doc_v2tkey": "<groq|deepgram|mistral> [api_key] — задати/видалити ключ резервного провайдера",
    }

    strings_de = {
        "_cls_doc": "Transkribiert Sprach- und Videonachrichten mit Google STT / Groq Whisper / Deepgram / Mistral",
        "no_reply": '<tg-emoji emoji-id="5267310332325437921">💢</tg-emoji> <b>Antworte auf eine Sprach- oder Videonachricht</b>',
        "not_voice": '<tg-emoji emoji-id="5267310332325437921">💢</tg-emoji> <b>Dies ist keine Sprach- oder Videonachricht</b>',
        "processing": '<tg-emoji emoji-id="5267003499861810620">✨</tg-emoji> <b>Transkription läuft...</b>',
        "result": '<tg-emoji emoji-id="5267003499861810620">✨</tg-emoji> <b>Transkription:</b>\n\n<blockquote expandable>{text}</blockquote>',
        "empty_result": '<tg-emoji emoji-id="5267139079094442194">🫥</tg-emoji> <b>Sprache konnte nicht erkannt werden</b>',
        "all_failed": '<tg-emoji emoji-id="5267310332325437921">💢</tg-emoji> <b>Kein Anbieter konnte das Audio transkribieren</b>\n<code>{err}</code>',
        "ffmpeg_missing": '<tg-emoji emoji-id="5267310332325437921">💢</tg-emoji> <b>ffmpeg wurde im System nicht gefunden</b>',
        "auto_on": '<tg-emoji emoji-id="5267003499861810620">✨</tg-emoji> <b>Automatische Transkription in diesem Chat aktiviert</b>',
        "auto_off": '<tg-emoji emoji-id="5264902955911388775">🌙</tg-emoji> <b>Automatische Transkription in diesem Chat deaktiviert</b>',
        "key_set": '<tg-emoji emoji-id="5267003499861810620">✨</tg-emoji> <b>API-Schlüssel für {provider} gespeichert</b>',
        "key_removed": '<tg-emoji emoji-id="5264902955911388775">🌙</tg-emoji> <b>API-Schlüssel für {provider} entfernt</b>',
        "key_usage": '<tg-emoji emoji-id="5267310332325437921">💢</tg-emoji> <b>Verwendung:</b> <code>{prefix}v2tkey &lt;groq|deepgram|mistral&gt; [api_key]</code>',
        "groq_api_key_doc": "Groq-API-Schlüssel (console.groq.com) — Ersatz für lange oder komplexe Audios",
        "deepgram_api_key_doc": "Deepgram-API-Schlüssel (console.deepgram.com) — Ersatzanbieter",
        "mistral_api_key_doc": "Mistral-API-Schlüssel (console.mistral.ai) — Ersatzanbieter (Voxtral)",
        "lang_doc": "Erkennungssprache (Google/Deepgram: Format ru-RU; Groq/Mistral: Sprachkürzel)",
        "max_duration_doc": "Maximale Audiodauer in Sekunden für die automatische Transkription",
        "list_header": '<tg-emoji emoji-id="5267003499861810620">✨</tg-emoji> <b>Chats mit automatischer Transkription: {count}</b>',
        "list_empty": '<tg-emoji emoji-id="5267139079094442194">🫥</tg-emoji> <b>Automatische Transkription ist in keinem Chat aktiviert.</b>\nIm gewünschten Chat aktivieren: <code>{prefix}v2tauto on</code>',
        "list_unavailable": "Chat nicht verfügbar",
        "list_page": 'Seite {page}/{pages} · <code>{prefix}v2tlist &lt;Seite&gt;</code>',
        "list_usage": '<tg-emoji emoji-id="5267310332325437921">💢</tg-emoji> <b>Gib eine Seite von 1 bis {pages} an:</b> <code>{prefix}v2tlist &lt;Seite&gt;</code>',
        "_cmd_doc_v2t": "(Antwort auf eine Sprach-/Videonachricht) — in Text umwandeln",
        "_cmd_doc_v2tauto": "[on/off] — automatische Transkription eingehender Sprachnachrichten in diesem Chat umschalten",
        "_cmd_doc_v2tlist": "[Seite] — Chats mit aktivierter automatischer Transkription anzeigen",
        "_cmd_doc_v2tkey": "<groq|deepgram|mistral> [api_key] — API-Schlüssel eines Ersatzanbieters setzen/entfernen",
    }

    strings_jp = {
        "_cls_doc": "Google STT / Groq Whisper / Deepgram / Mistral を使って音声・ビデオメッセージを文字起こしします",
        "no_reply": '<tg-emoji emoji-id="5267310332325437921">💢</tg-emoji> <b>音声またはビデオメッセージに返信してください</b>',
        "not_voice": '<tg-emoji emoji-id="5267310332325437921">💢</tg-emoji> <b>これは音声・ビデオメッセージではありません</b>',
        "processing": '<tg-emoji emoji-id="5267003499861810620">✨</tg-emoji> <b>文字起こし中...</b>',
        "result": '<tg-emoji emoji-id="5267003499861810620">✨</tg-emoji> <b>文字起こし結果:</b>\n\n<blockquote expandable>{text}</blockquote>',
        "empty_result": '<tg-emoji emoji-id="5267139079094442194">🫥</tg-emoji> <b>音声を認識できませんでした</b>',
        "all_failed": '<tg-emoji emoji-id="5267310332325437921">💢</tg-emoji> <b>すべてのプロバイダーで文字起こしに失敗しました</b>\n<code>{err}</code>',
        "ffmpeg_missing": '<tg-emoji emoji-id="5267310332325437921">💢</tg-emoji> <b>システムに ffmpeg が見つかりません</b>',
        "auto_on": '<tg-emoji emoji-id="5267003499861810620">✨</tg-emoji> <b>このチャットで自動文字起こしを有効にしました</b>',
        "auto_off": '<tg-emoji emoji-id="5264902955911388775">🌙</tg-emoji> <b>このチャットで自動文字起こしを無効にしました</b>',
        "key_set": '<tg-emoji emoji-id="5267003499861810620">✨</tg-emoji> <b>{provider} の API キーを保存しました</b>',
        "key_removed": '<tg-emoji emoji-id="5264902955911388775">🌙</tg-emoji> <b>{provider} の API キーを削除しました</b>',
        "key_usage": '<tg-emoji emoji-id="5267310332325437921">💢</tg-emoji> <b>使い方:</b> <code>{prefix}v2tkey &lt;groq|deepgram|mistral&gt; [api_key]</code>',
        "groq_api_key_doc": "Groq API キー (console.groq.com) — 長い音声や複雑な音声用の予備",
        "deepgram_api_key_doc": "Deepgram API キー (console.deepgram.com) — 予備プロバイダー",
        "mistral_api_key_doc": "Mistral API キー (console.mistral.ai) — 予備プロバイダー (Voxtral)",
        "lang_doc": "認識言語 (Google/Deepgram は ru-RU 形式、Groq/Mistral は短い言語コード)",
        "max_duration_doc": "自動文字起こしの音声の最大長（秒）",
        "list_header": '<tg-emoji emoji-id="5267003499861810620">✨</tg-emoji> <b>自動文字起こしが有効なチャット: {count}</b>',
        "list_empty": '<tg-emoji emoji-id="5267139079094442194">🫥</tg-emoji> <b>自動文字起こしが有効なチャットはありません。</b>\n対象のチャットで有効にする: <code>{prefix}v2tauto on</code>',
        "list_unavailable": "チャットにアクセスできません",
        "list_page": '{page}/{pages} ページ · <code>{prefix}v2tlist &lt;ページ&gt;</code>',
        "list_usage": '<tg-emoji emoji-id="5267310332325437921">💢</tg-emoji> <b>1 から {pages} までのページを指定してください:</b> <code>{prefix}v2tlist &lt;ページ&gt;</code>',
        "_cmd_doc_v2t": "(音声・ビデオメッセージへの返信) — 文字起こしする",
        "_cmd_doc_v2tauto": "[on/off] — このチャットの受信音声の自動文字起こしを有効/無効にする",
        "_cmd_doc_v2tlist": "[ページ] — 自動文字起こしが有効なチャットを表示する",
        "_cmd_doc_v2tkey": "<groq|deepgram|mistral> [api_key] — 予備プロバイダーの API キーを設定/削除する",
    }

    strings_neofit = {
        "_cls_doc": "Speech-to-text pipeline: Google STT / Groq Whisper / Deepgram / Mistral",
        "no_reply": '<tg-emoji emoji-id="5267310332325437921">💢</tg-emoji> <b>InputError: reply to a voice or video message</b>',
        "not_voice": '<tg-emoji emoji-id="5267310332325437921">💢</tg-emoji> <b>TypeError: expected a voice or video message</b>',
        "processing": '<tg-emoji emoji-id="5267003499861810620">✨</tg-emoji> <b>Transcription job: running...</b>',
        "result": '<tg-emoji emoji-id="5267003499861810620">✨</tg-emoji> <b>Transcription stdout:</b>\n\n<blockquote expandable>{text}</blockquote>',
        "empty_result": '<tg-emoji emoji-id="5267139079094442194">🫥</tg-emoji> <b>EmptyResult: no speech recognized</b>',
        "all_failed": '<tg-emoji emoji-id="5267310332325437921">💢</tg-emoji> <b>TranscriptionError: all providers failed</b>\n<code>{err}</code>',
        "ffmpeg_missing": '<tg-emoji emoji-id="5267310332325437921">💢</tg-emoji> <b>FileNotFoundError: ffmpeg is not in PATH</b>',
        "auto_on": '<tg-emoji emoji-id="5267003499861810620">✨</tg-emoji> <b>auto_transcription[this_chat] = True</b>',
        "auto_off": '<tg-emoji emoji-id="5264902955911388775">🌙</tg-emoji> <b>auto_transcription[this_chat] = False</b>',
        "key_set": '<tg-emoji emoji-id="5267003499861810620">✨</tg-emoji> <b>{provider}: API key persisted</b>',
        "key_removed": '<tg-emoji emoji-id="5264902955911388775">🌙</tg-emoji> <b>{provider}: API key unset</b>',
        "key_usage": '<tg-emoji emoji-id="5267310332325437921">💢</tg-emoji> <b>Usage:</b> <code>{prefix}v2tkey &lt;groq|deepgram|mistral&gt; [api_key]</code>',
        "groq_api_key_doc": "groq_api_key (console.groq.com): fallback for long or complex audio",
        "deepgram_api_key_doc": "deepgram_api_key (console.deepgram.com): fallback provider",
        "mistral_api_key_doc": "mistral_api_key (console.mistral.ai): Voxtral fallback provider",
        "lang_doc": "Recognition locale: ru-RU format for Google/Deepgram; short code for Groq/Mistral",
        "max_duration_doc": "Auto-transcription audio duration limit, in seconds",
        "list_header": '<tg-emoji emoji-id="5267003499861810620">✨</tg-emoji> <b>auto_transcription.enabled_chats: {count}</b>',
        "list_empty": '<tg-emoji emoji-id="5267139079094442194">🫥</tg-emoji> <b>auto_transcription.enabled_chats = []</b>\nRun in the target chat: <code>{prefix}v2tauto on</code>',
        "list_unavailable": "EntityLookupError: chat unavailable",
        "list_page": 'Page {page}/{pages} · <code>{prefix}v2tlist &lt;page&gt;</code>',
        "list_usage": '<tg-emoji emoji-id="5267310332325437921">💢</tg-emoji> <b>IndexError: page must be between 1 and {pages}:</b> <code>{prefix}v2tlist &lt;page&gt;</code>',
        "_cmd_doc_v2t": "(reply to voice/video) — run the speech-to-text pipeline",
        "_cmd_doc_v2tauto": "[on/off] — set auto-transcription for incoming voice messages in this chat",
        "_cmd_doc_v2tlist": "[page] — print auto_transcription.enabled_chats",
        "_cmd_doc_v2tkey": "<groq|deepgram|mistral> [api_key] — set/unset a fallback provider key",
    }

    strings_tiktok = {
        "_cls_doc": "Переводит войсы и кружочки в текст через Google STT / Groq Whisper / Deepgram / Mistral",
        "no_reply": '<tg-emoji emoji-id="5267310332325437921">💢</tg-emoji> <b>Ответь на войс или кружочек, чел</b>',
        "not_voice": '<tg-emoji emoji-id="5267310332325437921">💢</tg-emoji> <b>Это ни войс, ни кружочек</b>',
        "processing": '<tg-emoji emoji-id="5267003499861810620">✨</tg-emoji> <b>Разбираю, что там наговорили...</b>',
        "result": '<tg-emoji emoji-id="5267003499861810620">✨</tg-emoji> <b>Вот что в войсе:</b>\n\n<blockquote expandable>{text}</blockquote>',
        "empty_result": '<tg-emoji emoji-id="5267139079094442194">🫥</tg-emoji> <b>Речь не разобрал, печаль</b>',
        "all_failed": '<tg-emoji emoji-id="5267310332325437921">💢</tg-emoji> <b>Все провайдеры отвалились, войс не расшифрован</b>\n<code>{err}</code>',
        "ffmpeg_missing": '<tg-emoji emoji-id="5267310332325437921">💢</tg-emoji> <b>ffmpeg на сервере нет, без него никак</b>',
        "auto_on": '<tg-emoji emoji-id="5267003499861810620">✨</tg-emoji> <b>Авторасшифровку в этом чате врубил</b>',
        "auto_off": '<tg-emoji emoji-id="5264902955911388775">🌙</tg-emoji> <b>Авторасшифровку в этом чате вырубил</b>',
        "key_set": '<tg-emoji emoji-id="5267003499861810620">✨</tg-emoji> <b>Ключ {provider} сохранил, погнали</b>',
        "key_removed": '<tg-emoji emoji-id="5264902955911388775">🌙</tg-emoji> <b>Ключ {provider} удалил</b>',
        "key_usage": '<tg-emoji emoji-id="5267310332325437921">💢</tg-emoji> <b>Юзай так:</b> <code>{prefix}v2tkey &lt;groq|deepgram|mistral&gt; [api_key]</code>',
        "groq_api_key_doc": "Ключ Groq (console.groq.com) — подстраховка для длинных и сложных войсов",
        "deepgram_api_key_doc": "Ключ Deepgram (console.deepgram.com) — запасной провайдер",
        "mistral_api_key_doc": "Ключ Mistral (console.mistral.ai) — запасной провайдер Voxtral",
        "lang_doc": "Язык войсов: Google/Deepgram — типа ru-RU, Groq/Mistral — короткий код",
        "max_duration_doc": "Лимит длины войса в секундах для авторасшифровки",
        "list_header": '<tg-emoji emoji-id="5267003499861810620">✨</tg-emoji> <b>Авторасшифровка пашет тут: {count} чатов</b>',
        "list_empty": '<tg-emoji emoji-id="5267139079094442194">🫥</tg-emoji> <b>Авторасшифровка нигде не врублена.</b>\nВ нужном чате пиши: <code>{prefix}v2tauto on</code>',
        "list_unavailable": "Чат недоступен, бывает",
        "list_page": 'Страница {page}/{pages} · <code>{prefix}v2tlist &lt;страница&gt;</code>',
        "list_usage": '<tg-emoji emoji-id="5267310332325437921">💢</tg-emoji> <b>Дай страницу от 1 до {pages}:</b> <code>{prefix}v2tlist &lt;страница&gt;</code>',
        "_cmd_doc_v2t": "(ответ на войс/кружочек) — вытащить текст",
        "_cmd_doc_v2tauto": "[on/off] — врубить/вырубить авторасшифровку входящих войсов в этом чате",
        "_cmd_doc_v2tlist": "[страница] — глянуть, где пашет авторасшифровка",
        "_cmd_doc_v2tkey": "<groq|deepgram|mistral> [api_key] — закинуть/удалить ключ запасного провайдера",
    }

    strings_uwu = {
        "_cls_doc": "Twanscwibes voice/video messages to text via fwee APIs (Google STT / Groq Whisper / Deepgram / Mistral)",
        "no_reply": "<tg-emoji emoji-id=\"5267310332325437921\">💢</tg-emoji> <b>Wepwy to a voice ow video message</b>",
        "not_voice": "<tg-emoji emoji-id=\"5267310332325437921\">💢</tg-emoji> <b>This is not a voice ow video message</b>",
        "processing": "<tg-emoji emoji-id=\"5267003499861810620\">✨</tg-emoji> <b>Twanscwibing...</b>",
        "result": "<tg-emoji emoji-id=\"5267003499861810620\">✨</tg-emoji> <b>Twanscwiption:</b>\n\n<blockquote expandable>{text}</blockquote>",
        "empty_result": "<tg-emoji emoji-id=\"5267139079094442194\">🫥</tg-emoji> <b>Couwd not wecognize speech</b>",
        "all_failed": "<tg-emoji emoji-id=\"5267310332325437921\">💢</tg-emoji> <b>Aww pwovidews faiwed to twanscwibe the audio</b>\n<code>{err}</code>",
        "ffmpeg_missing": "<tg-emoji emoji-id=\"5267310332325437921\">💢</tg-emoji> <b>ffmpeg not found on the system</b>",
        "auto_on": "<tg-emoji emoji-id=\"5267003499861810620\">✨</tg-emoji> <b>Auto-twanscwiption enabwed in this chat</b>",
        "auto_off": "<tg-emoji emoji-id=\"5264902955911388775\">🌙</tg-emoji> <b>Auto-twanscwiption disabwed in this chat</b>",
        "key_set": "<tg-emoji emoji-id=\"5267003499861810620\">✨</tg-emoji> <b>{provider} API key saved</b>",
        "key_removed": "<tg-emoji emoji-id=\"5264902955911388775\">🌙</tg-emoji> <b>{provider} API key wemoved</b>",
        "key_usage": "<tg-emoji emoji-id=\"5267310332325437921\">💢</tg-emoji> <b>Usage:</b> <code>{prefix}v2tkey &lt;groq|deepgram|mistral&gt; [api_key]</code>",
        "groq_api_key_doc": "Groq API key (fwee, console.groq.com) — fawwback fow wong/compwex audio",
        "deepgram_api_key_doc": "Deepgram API key (console.deepgram.com) — fawwback pwovidew",
        "mistral_api_key_doc": "Mistral API key (console.mistral.ai) — fawwback pwovidew (Voxtral)",
        "lang_doc": "Wecognition wanguage (Google/Deepgram — ru-RU fowmat, Groq/Mistral use the showt code)",
        "max_duration_doc": "Maximum audio duwation in seconds fow auto-twanscwiption",
        "list_header": "<tg-emoji emoji-id=\"5267003499861810620\">✨</tg-emoji> <b>Chats with auto-twanscwiption: {count}</b>",
        "list_empty": "<tg-emoji emoji-id=\"5267139079094442194\">🫥</tg-emoji> <b>Auto-twanscwiption is not enabwed in any chat.</b>\nEnabwe it in the desiwed chat: <code>{prefix}v2tauto on</code>",
        "list_unavailable": "Chat unavaiwabwe",
        "list_page": "Page {page}/{pages} · <code>{prefix}v2tlist &lt;page&gt;</code>",
        "list_usage": "<tg-emoji emoji-id=\"5267310332325437921\">💢</tg-emoji> <b>Entew a page fwom 1 to {pages}:</b> <code>{prefix}v2tlist &lt;page&gt;</code>",
        "_cmd_doc_v2t": "(wepwy to a voice/video message) — twanscwibe it to text",
        "_cmd_doc_v2tauto": "[on/off] — enabwe/disabwe auto-twanscwiption of incoming voice messages in this chat",
        "_cmd_doc_v2tlist": "[page] — wist chats with auto-twanscwiption enabwed",
        "_cmd_doc_v2tkey": "<groq|deepgram|mistral> [api_key] — set/wemove a pwovidew API key (fawwback)",
    }

    strings_leet = {
        "_cls_doc": "7r4n5cr1b35 v01c3/v1d30 m3554g35 70 73x7 v14 fr33 4P15 (Google STT / Groq Whisper / Deepgram / Mistral)",
        "no_reply": "<tg-emoji emoji-id=\"5267310332325437921\">💢</tg-emoji> <b>R3ply 70 4 v01c3 0r v1d30 m3554g3</b>",
        "not_voice": "<tg-emoji emoji-id=\"5267310332325437921\">💢</tg-emoji> <b>7h15 15 n07 4 v01c3 0r v1d30 m3554g3</b>",
        "processing": "<tg-emoji emoji-id=\"5267003499861810620\">✨</tg-emoji> <b>7r4n5cr1b1ng...</b>",
        "result": "<tg-emoji emoji-id=\"5267003499861810620\">✨</tg-emoji> <b>7r4n5cr1p710n:</b>\n\n<blockquote expandable>{text}</blockquote>",
        "empty_result": "<tg-emoji emoji-id=\"5267139079094442194\">🫥</tg-emoji> <b>C0uld n07 r3c0gn1z3 5p33ch</b>",
        "all_failed": "<tg-emoji emoji-id=\"5267310332325437921\">💢</tg-emoji> <b>4ll pr0v1d3r5 f41l3d 70 7r4n5cr1b3 7h3 4ud10</b>\n<code>{err}</code>",
        "ffmpeg_missing": "<tg-emoji emoji-id=\"5267310332325437921\">💢</tg-emoji> <b>ffmpeg n07 f0und 0n 7h3 5y573m</b>",
        "auto_on": "<tg-emoji emoji-id=\"5267003499861810620\">✨</tg-emoji> <b>4u70-7r4n5cr1p710n 3n4bl3d 1n 7h15 ch47</b>",
        "auto_off": "<tg-emoji emoji-id=\"5264902955911388775\">🌙</tg-emoji> <b>4u70-7r4n5cr1p710n d154bl3d 1n 7h15 ch47</b>",
        "key_set": "<tg-emoji emoji-id=\"5267003499861810620\">✨</tg-emoji> <b>{provider} API k3y 54v3d</b>",
        "key_removed": "<tg-emoji emoji-id=\"5264902955911388775\">🌙</tg-emoji> <b>{provider} API k3y r3m0v3d</b>",
        "key_usage": "<tg-emoji emoji-id=\"5267310332325437921\">💢</tg-emoji> <b>U54g3:</b> <code>{prefix}v2tkey &lt;groq|deepgram|mistral&gt; [api_key]</code>",
        "groq_api_key_doc": "Groq API k3y (fr33, console.groq.com) — f4llb4ck f0r l0ng/c0mpl3x 4ud10",
        "deepgram_api_key_doc": "Deepgram API k3y (console.deepgram.com) — f4llb4ck pr0v1d3r",
        "mistral_api_key_doc": "Mistral API k3y (console.mistral.ai) — f4llb4ck pr0v1d3r (Voxtral)",
        "lang_doc": "R3c0gn1710n l4ngu4g3 (Google/Deepgram — ru-RU f0rm47, Groq/Mistral u53 7h3 5h0r7 c0d3)",
        "max_duration_doc": "M4x1mum 4ud10 dur4710n 1n 53c0nd5 f0r 4u70-7r4n5cr1p710n",
        "list_header": "<tg-emoji emoji-id=\"5267003499861810620\">✨</tg-emoji> <b>Ch475 w17h 4u70-7r4n5cr1p710n: {count}</b>",
        "list_empty": "<tg-emoji emoji-id=\"5267139079094442194\">🫥</tg-emoji> <b>4u70-7r4n5cr1p710n 15 n07 3n4bl3d 1n 4ny ch47.</b>\n3n4bl3 17 1n 7h3 d351r3d ch47: <code>{prefix}v2tauto on</code>",
        "list_unavailable": "Ch47 un4v41l4bl3",
        "list_page": "P4g3 {page}/{pages} · <code>{prefix}v2tlist &lt;page&gt;</code>",
        "list_usage": "<tg-emoji emoji-id=\"5267310332325437921\">💢</tg-emoji> <b>3n73r 4 p4g3 fr0m 1 70 {pages}:</b> <code>{prefix}v2tlist &lt;page&gt;</code>",
        "_cmd_doc_v2t": "(r3ply 70 4 v01c3/v1d30 m3554g3) — 7r4n5cr1b3 17 70 73x7",
        "_cmd_doc_v2tauto": "[on/off] — 3n4bl3/d154bl3 4u70-7r4n5cr1p710n 0f 1nc0m1ng v01c3 m3554g35 1n 7h15 ch47",
        "_cmd_doc_v2tlist": "[p4g3] — l157 ch475 w17h 4u70-7r4n5cr1p710n 3n4bl3d",
        "_cmd_doc_v2tkey": "<groq|deepgram|mistral> [api_key] — 537/r3m0v3 4 pr0v1d3r API k3y (f4llb4ck)",
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

    @loader.command()
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

    async def _auto_chat_name(self, chat_id, semaphore):
        async with semaphore:
            try:
                entity = await asyncio.wait_for(self.client.get_entity(chat_id), timeout=3)
                name = (
                    getattr(entity, "title", None)
                    or " ".join(
                        part for part in (
                            getattr(entity, "first_name", None),
                            getattr(entity, "last_name", None),
                        ) if part
                    )
                    or getattr(entity, "username", None)
                )
            except Exception:
                name = None
        name = " ".join((name or "").split())
        return utils.escape_html(name[:100] or self.strings["list_unavailable"])

    @loader.command()
    async def v2tlist(self, message: Message):
        """[page] — list chats with auto-transcription enabled"""
        chats = sorted(set(self.get("auto_chats", [])))
        prefix = utils.escape_html(self.get_prefix())
        if not chats:
            await utils.answer(message, self.strings["list_empty"].format(prefix=prefix))
            return

        pages = (len(chats) + 9) // 10
        try:
            page = int(utils.get_args_raw(message).strip() or "1")
        except ValueError:
            page = 0
        if not 1 <= page <= pages:
            await utils.answer(
                message,
                self.strings["list_usage"].format(prefix=prefix, pages=pages),
            )
            return

        offset = (page - 1) * 10
        selected = chats[offset:offset + 10]
        semaphore = asyncio.Semaphore(4)
        names = await asyncio.gather(
            *(self._auto_chat_name(chat_id, semaphore) for chat_id in selected)
        )
        lines = [self.strings["list_header"].format(count=len(chats)), ""]
        lines.extend(
            f"{offset + index}. <b>{name}</b> — <code>{chat_id}</code>"
            for index, (chat_id, name) in enumerate(zip(selected, names), start=1)
        )
        if pages > 1:
            lines.extend((
                "",
                self.strings["list_page"].format(page=page, pages=pages, prefix=prefix),
            ))
        await utils.answer(message, "\n".join(lines), parse_mode="HTML", link_preview=False)

    @loader.command()
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
            await utils.answer(
                message,
                self.strings["key_usage"].format(prefix=utils.escape_html(self.get_prefix())),
            )
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
