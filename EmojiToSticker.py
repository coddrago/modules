# ---------------------------------------------------------------------------------
# ░█▀▄░▄▀▀▄░█▀▄░█▀▀▄░█▀▀▄░█▀▀▀░▄▀▀▄░░░█▀▄▀█
# ░█░░░█░░█░█░█░█▄▄▀░█▄▄█░█░▀▄░█░░█░░░█░▀░█
# ░▀▀▀░░▀▀░░▀▀░░▀░▀▀░▀░░▀░▀▀▀▀░░▀▀░░░░▀░░▒▀
# Name: EmojiToSticker
# Description: Convert custom emoji and emoji packs into sticker packs at native sticker resolution via Telegram API
# Author: @codrago_m
# ---------------------------------------------------------------------------------
# 🔒    Licensed under the GNU AGPLv3
# 🌐 https://www.gnu.org/licenses/agpl-3.0.html
# ---------------------------------------------------------------------------------
# Commands: e2s, e1s
# scope: heroku_only
# scope: ffmpeg
# meta developer: @codrago_m
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

from herokutl.errors import FloodWaitError
from herokutl.tl import functions
from herokutl.tl.functions.messages import (
    GetCustomEmojiDocumentsRequest,
    GetStickerSetRequest,
    UploadMediaRequest,
)
from herokutl.tl.types import (
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
    MessageEntityCustomEmoji,
)

from .. import loader, utils

STICKER_SIDE = 512
MAX_STATIC_BYTES = 512 * 1024
MAX_VIDEO_BYTES = 256 * 1024
MAX_PACK = 120


@loader.tds
class EmojiToStickerMod(loader.Module):
    """Converts custom emoji and emoji packs into sticker packs at native sticker resolution."""

    strings = {
        "name": "EmojiToSticker",
        "no_args": (
            "<tg-emoji emoji-id=5253864872780769235>❗️</tg-emoji> "
            "Reply to a custom emoji or provide an emoji pack link/shortname."
        ),
        "no_reply": (
            "<tg-emoji emoji-id=5253864872780769235>❗️</tg-emoji> "
            "Reply to a message with a custom emoji."
        ),
        "fetch_err": (
            "<tg-emoji emoji-id=5253864872780769235>❗️</tg-emoji> "
            "Failed to fetch emoji pack: <code>{}</code>"
        ),
        "empty_pack": (
            "<tg-emoji emoji-id=5253864872780769235>❗️</tg-emoji> "
            "Emoji pack is empty."
        ),
        "no_stickers": (
            "<tg-emoji emoji-id=5253864872780769235>❗️</tg-emoji> "
            "Nothing to convert for type <code>{}</code>."
        ),
        "unsupported": (
            "<tg-emoji emoji-id=5253864872780769235>❗️</tg-emoji> "
            "Unsupported emoji format."
        ),
        "no_ffmpeg": (
            "<tg-emoji emoji-id=5253864872780769235>❗️</tg-emoji> "
            "FFmpeg is required on the server to convert video emoji."
        ),
        "loading": (
            "<tg-emoji emoji-id=4911656069207426158>💘</tg-emoji> "
            "<i>Fetching emoji info...</i>"
        ),
        "processing": (
            "<tg-emoji emoji-id=4911656069207426158>💘</tg-emoji> "
            "Creating <b>{}</b> stickers «<b>{}</b>»\n"
            "<b>Progress:</b> <code>{}/{}</code>"
        ),
        "success": (
            "<tg-emoji emoji-id=4911656069207426158>💘</tg-emoji> "
            "Sticker pack created!\n\n"
            "<b>Title:</b> <code>{}</code>\n"
            "<b>Type:</b> <code>{}</code>\n"
            "<b>Link:</b> <a href='{}'>Add Sticker Pack</a>"
        ),
        "btn_add": "Add Pack",
        "error": (
            "<tg-emoji emoji-id=5253864872780769235>❗️</tg-emoji> "
            "Error: <code>{}</code>"
        ),
        "_cls_doc": "Converts custom emoji and emoji packs into sticker packs at native sticker resolution.",
        "_cmd_doc_e2s": "<pack / reply> — convert an emoji pack into a sticker pack via API",
        "_cmd_doc_e1s": "<reply to emoji> [title] — one custom emoji into a sticker pack",
    }

    strings_ru = {
        "no_args": (
            "<tg-emoji emoji-id=5253864872780769235>❗️</tg-emoji> "
            "Ответьте на кастомное эмодзи или укажите ссылку/шортнейм эмодзи-пака."
        ),
        "no_reply": (
            "<tg-emoji emoji-id=5253864872780769235>❗️</tg-emoji> "
            "Ответьте на сообщение с кастомным эмодзи."
        ),
        "fetch_err": (
            "<tg-emoji emoji-id=5253864872780769235>❗️</tg-emoji> "
            "Не удалось найти эмодзи-пак: <code>{}</code>"
        ),
        "empty_pack": (
            "<tg-emoji emoji-id=5253864872780769235>❗️</tg-emoji> "
            "Эмодзи-пак пуст."
        ),
        "no_stickers": (
            "<tg-emoji emoji-id=5253864872780769235>❗️</tg-emoji> "
            "Нечего конвертировать для типа <code>{}</code>."
        ),
        "unsupported": (
            "<tg-emoji emoji-id=5253864872780769235>❗️</tg-emoji> "
            "Неподдерживаемый формат эмодзи."
        ),
        "no_ffmpeg": (
            "<tg-emoji emoji-id=5253864872780769235>❗️</tg-emoji> "
            "Для видео-эмодзи нужен FFmpeg на сервере."
        ),
        "loading": (
            "<tg-emoji emoji-id=4911656069207426158>💘</tg-emoji> "
            "<i>Получаю информацию об эмодзи...</i>"
        ),
        "processing": (
            "<tg-emoji emoji-id=4911656069207426158>💘</tg-emoji> "
            "Создаю <b>{}</b> стикеры «<b>{}</b>»\n"
            "<b>Прогресс:</b> <code>{}/{}</code>"
        ),
        "success": (
            "<tg-emoji emoji-id=4911656069207426158>💘</tg-emoji> "
            "Стикерпак создан!\n\n"
            "<b>Название:</b> <code>{}</code>\n"
            "<b>Тип:</b> <code>{}</code>\n"
            "<b>Ссылка:</b> <a href='{}'>Добавить стикерпак</a>"
        ),
        "btn_add": "Добавить пак",
        "error": (
            "<tg-emoji emoji-id=5253864872780769235>❗️</tg-emoji> "
            "Ошибка: <code>{}</code>"
        ),
        "_cls_doc": "Конвертирует кастомные эмодзи и эмодзи-паки в стикерпаки в родном разрешении стикера.",
        "_cmd_doc_e2s": "<пак / реплай> — конвертировать эмодзи-пак в стикерпак через API",
        "_cmd_doc_e1s": "<реплай на эмодзи> [название] — одно кастомное эмодзи в стикерпак",
    }

    strings_ua = {
        "no_args": (
            "<tg-emoji emoji-id=5253864872780769235>❗️</tg-emoji> "
            "Відповідайте на кастомне емодзі або вкажіть посилання/коротку назву емодзі-паку."
        ),
        "no_reply": (
            "<tg-emoji emoji-id=5253864872780769235>❗️</tg-emoji> "
            "Відповідайте на повідомлення з кастомним емодзі."
        ),
        "fetch_err": (
            "<tg-emoji emoji-id=5253864872780769235>❗️</tg-emoji> "
            "Не вдалося знайти емодзі-пак: <code>{}</code>"
        ),
        "empty_pack": (
            "<tg-emoji emoji-id=5253864872780769235>❗️</tg-emoji> "
            "Емодзі-пак порожній."
        ),
        "no_stickers": (
            "<tg-emoji emoji-id=5253864872780769235>❗️</tg-emoji> "
            "Немає що конвертувати для типу <code>{}</code>."
        ),
        "unsupported": (
            "<tg-emoji emoji-id=5253864872780769235>❗️</tg-emoji> "
            "Непідтримуваний формат емодзі."
        ),
        "no_ffmpeg": (
            "<tg-emoji emoji-id=5253864872780769235>❗️</tg-emoji> "
            "Для відеоемодзі потрібен FFmpeg на сервері."
        ),
        "loading": (
            "<tg-emoji emoji-id=4911656069207426158>💘</tg-emoji> "
            "<i>Отримую інформацію про емодзі...</i>"
        ),
        "processing": (
            "<tg-emoji emoji-id=4911656069207426158>💘</tg-emoji> "
            "Створюю <b>{}</b> стікери «<b>{}</b>»\n"
            "<b>Прогрес:</b> <code>{}/{}</code>"
        ),
        "success": (
            "<tg-emoji emoji-id=4911656069207426158>💘</tg-emoji> "
            "Стікерпак створено!\n\n"
            "<b>Назва:</b> <code>{}</code>\n"
            "<b>Тип:</b> <code>{}</code>\n"
            "<b>Посилання:</b> <a href='{}'>Додати стікерпак</a>"
        ),
        "btn_add": "Додати пак",
        "error": (
            "<tg-emoji emoji-id=5253864872780769235>❗️</tg-emoji> "
            "Помилка: <code>{}</code>"
        ),
        "_cls_doc": "Конвертує кастомні емодзі та емодзі-паки в стікерпаки в рідній роздільності стікера.",
        "_cmd_doc_e2s": "<пак / відповідь> — конвертувати емодзі-пак у стікерпак через API",
        "_cmd_doc_e1s": "<відповідь на емодзі> [назва] — одне кастомне емодзі в стікерпак",
    }

    strings_de = {
        "no_args": (
            "<tg-emoji emoji-id=5253864872780769235>❗️</tg-emoji> "
            "Antworte auf ein Custom-Emoji oder gib einen Emoji-Pack-Link bzw. Shortname an."
        ),
        "no_reply": (
            "<tg-emoji emoji-id=5253864872780769235>❗️</tg-emoji> "
            "Antworte auf eine Nachricht mit einem Custom-Emoji."
        ),
        "fetch_err": (
            "<tg-emoji emoji-id=5253864872780769235>❗️</tg-emoji> "
            "Emoji-Pack konnte nicht geladen werden: <code>{}</code>"
        ),
        "empty_pack": (
            "<tg-emoji emoji-id=5253864872780769235>❗️</tg-emoji> "
            "Das Emoji-Pack ist leer."
        ),
        "no_stickers": (
            "<tg-emoji emoji-id=5253864872780769235>❗️</tg-emoji> "
            "Nichts zu konvertieren für den Typ <code>{}</code>."
        ),
        "unsupported": (
            "<tg-emoji emoji-id=5253864872780769235>❗️</tg-emoji> "
            "Nicht unterstütztes Emoji-Format."
        ),
        "no_ffmpeg": (
            "<tg-emoji emoji-id=5253864872780769235>❗️</tg-emoji> "
            "Für Video-Emojis wird FFmpeg auf dem Server benötigt."
        ),
        "loading": (
            "<tg-emoji emoji-id=4911656069207426158>💘</tg-emoji> "
            "<i>Emoji-Infos werden geladen...</i>"
        ),
        "processing": (
            "<tg-emoji emoji-id=4911656069207426158>💘</tg-emoji> "
            "Erstelle <b>{}</b>-Sticker «<b>{}</b>»\n"
            "<b>Fortschritt:</b> <code>{}/{}</code>"
        ),
        "success": (
            "<tg-emoji emoji-id=4911656069207426158>💘</tg-emoji> "
            "Stickerpack erstellt!\n\n"
            "<b>Titel:</b> <code>{}</code>\n"
            "<b>Typ:</b> <code>{}</code>\n"
            "<b>Link:</b> <a href='{}'>Stickerpack hinzufügen</a>"
        ),
        "btn_add": "Pack hinzufügen",
        "error": (
            "<tg-emoji emoji-id=5253864872780769235>❗️</tg-emoji> "
            "Fehler: <code>{}</code>"
        ),
        "_cls_doc": "Wandelt Custom-Emojis und Emoji-Packs in Stickerpacks in nativer Stickerauflösung um.",
        "_cmd_doc_e2s": "<Pack / Antwort> — Emoji-Pack über die API in ein Stickerpack umwandeln",
        "_cmd_doc_e1s": "<Antwort auf Emoji> [Titel] — ein Custom-Emoji in ein Stickerpack",
    }

    strings_jp = {
        "no_args": (
            "<tg-emoji emoji-id=5253864872780769235>❗️</tg-emoji> "
            "カスタム絵文字に返信するか、絵文字パックのリンクかショートネームを指定してください。"
        ),
        "no_reply": (
            "<tg-emoji emoji-id=5253864872780769235>❗️</tg-emoji> "
            "カスタム絵文字のあるメッセージに返信してください。"
        ),
        "fetch_err": (
            "<tg-emoji emoji-id=5253864872780769235>❗️</tg-emoji> "
            "絵文字パックを取得できませんでした: <code>{}</code>"
        ),
        "empty_pack": (
            "<tg-emoji emoji-id=5253864872780769235>❗️</tg-emoji> "
            "絵文字パックは空です。"
        ),
        "no_stickers": (
            "<tg-emoji emoji-id=5253864872780769235>❗️</tg-emoji> "
            "タイプ <code>{}</code> で変換できるものがありません。"
        ),
        "unsupported": (
            "<tg-emoji emoji-id=5253864872780769235>❗️</tg-emoji> "
            "未対応の絵文字形式です。"
        ),
        "no_ffmpeg": (
            "<tg-emoji emoji-id=5253864872780769235>❗️</tg-emoji> "
            "動画絵文字の変換にはサーバーに FFmpeg が必要です。"
        ),
        "loading": (
            "<tg-emoji emoji-id=4911656069207426158>💘</tg-emoji> "
            "<i>絵文字情報を取得しています...</i>"
        ),
        "processing": (
            "<tg-emoji emoji-id=4911656069207426158>💘</tg-emoji> "
            "<b>{}</b> ステッカー「<b>{}</b>」を作成中\n"
            "<b>進捗:</b> <code>{}/{}</code>"
        ),
        "success": (
            "<tg-emoji emoji-id=4911656069207426158>💘</tg-emoji> "
            "ステッカーパックを作成しました！\n\n"
            "<b>タイトル:</b> <code>{}</code>\n"
            "<b>種類:</b> <code>{}</code>\n"
            "<b>リンク:</b> <a href='{}'>ステッカーパックを追加</a>"
        ),
        "btn_add": "パックを追加",
        "error": (
            "<tg-emoji emoji-id=5253864872780769235>❗️</tg-emoji> "
            "エラー: <code>{}</code>"
        ),
        "_cls_doc": "カスタム絵文字と絵文字パックを、ステッカー本来の解像度のステッカーパックに変換します。",
        "_cmd_doc_e2s": "<パック / 返信> — 絵文字パックを API 経由でステッカーパックに変換",
        "_cmd_doc_e1s": "<絵文字への返信> [タイトル] — カスタム絵文字1つをステッカーパックに",
    }

    strings_leet = {
        "no_args": (
            "<tg-emoji emoji-id=5253864872780769235>❗️</tg-emoji> "
            "R3ply 70 4 cu570m 3m0j1 0r g1v3 4n 3m0j1 p4ck l1nk/5h0r7n4m3."
        ),
        "no_reply": (
            "<tg-emoji emoji-id=5253864872780769235>❗️</tg-emoji> "
            "R3ply 70 4 m355463 w17h 4 cu570m 3m0j1."
        ),
        "fetch_err": (
            "<tg-emoji emoji-id=5253864872780769235>❗️</tg-emoji> "
            "F41l3d 70 f37ch 3m0j1 p4ck: <code>{}</code>"
        ),
        "empty_pack": (
            "<tg-emoji emoji-id=5253864872780769235>❗️</tg-emoji> "
            "3m0j1 p4ck 15 3mp7y."
        ),
        "no_stickers": (
            "<tg-emoji emoji-id=5253864872780769235>❗️</tg-emoji> "
            "N07h1ng 70 c0nv3r7 f0r 7yp3 <code>{}</code>."
        ),
        "unsupported": (
            "<tg-emoji emoji-id=5253864872780769235>❗️</tg-emoji> "
            "Un5upp0r73d 3m0j1 f0rm47."
        ),
        "no_ffmpeg": (
            "<tg-emoji emoji-id=5253864872780769235>❗️</tg-emoji> "
            "FFmP36 15 r3qu1r3d 0n 7h3 53rv3r 70 c0nv3r7 v1d30 3m0j1."
        ),
        "loading": (
            "<tg-emoji emoji-id=4911656069207426158>💘</tg-emoji> "
            "<i>F37ch1ng 3m0j1 1nf0...</i>"
        ),
        "processing": (
            "<tg-emoji emoji-id=4911656069207426158>💘</tg-emoji> "
            "Cr3471ng <b>{}</b> 571ck3r5 «<b>{}</b>»\n"
            "<b>Pr0gr355:</b> <code>{}/{}</code>"
        ),
        "success": (
            "<tg-emoji emoji-id=4911656069207426158>💘</tg-emoji> "
            "571ck3r p4ck cr3473d!\n\n"
            "<b>T17l3:</b> <code>{}</code>\n"
            "<b>Typ3:</b> <code>{}</code>\n"
            "<b>L1nk:</b> <a href='{}'>4dd 571ck3r P4ck</a>"
        ),
        "btn_add": "4dd P4ck",
        "error": (
            "<tg-emoji emoji-id=5253864872780769235>❗️</tg-emoji> "
            "3rr0r: <code>{}</code>"
        ),
        "_cls_doc": "C0nv3r75 cu570m 3m0j1 4nd 3m0j1 p4ck5 1n70 571ck3r p4ck5 47 n471v3 571ck3r r350lu710n.",
        "_cmd_doc_e2s": "<p4ck / r3ply> — c0nv3r7 4n 3m0j1 p4ck 1n70 4 571ck3r p4ck v14 4P1",
        "_cmd_doc_e1s": "<r3ply 70 3m0j1> [717l3] — 0n3 cu570m 3m0j1 1n70 4 571ck3r p4ck",
    }

    strings_uwu = {
        "no_args": (
            "<tg-emoji emoji-id=5253864872780769235>❗️</tg-emoji> "
            "Wepwy to a custom emoji ow give an emoji pack wink/showtname."
        ),
        "no_reply": (
            "<tg-emoji emoji-id=5253864872780769235>❗️</tg-emoji> "
            "Wepwy to a message with a custom emoji, pwease."
        ),
        "fetch_err": (
            "<tg-emoji emoji-id=5253864872780769235>❗️</tg-emoji> "
            "Faiwed to fetch emoji pack: <code>{}</code>"
        ),
        "empty_pack": (
            "<tg-emoji emoji-id=5253864872780769235>❗️</tg-emoji> "
            "Emoji pack is empty, uwu."
        ),
        "no_stickers": (
            "<tg-emoji emoji-id=5253864872780769235>❗️</tg-emoji> "
            "Nothing to convewt fow type <code>{}</code>."
        ),
        "unsupported": (
            "<tg-emoji emoji-id=5253864872780769235>❗️</tg-emoji> "
            "Unsuppowted emoji fowmat."
        ),
        "no_ffmpeg": (
            "<tg-emoji emoji-id=5253864872780769235>❗️</tg-emoji> "
            "FFmpeg is wequiwed on the sewvew to convewt video emoji."
        ),
        "loading": (
            "<tg-emoji emoji-id=4911656069207426158>💘</tg-emoji> "
            "<i>Fetching emoji infowo...</i>"
        ),
        "processing": (
            "<tg-emoji emoji-id=4911656069207426158>💘</tg-emoji> "
            "Cweating <b>{}</b> stickews «<b>{}</b>»\n"
            "<b>PwoGwess:</b> <code>{}/{}</code>"
        ),
        "success": (
            "<tg-emoji emoji-id=4911656069207426158>💘</tg-emoji> "
            "Stickew pack cweated!\n\n"
            "<b>Titwe:</b> <code>{}</code>\n"
            "<b>Type:</b> <code>{}</code>\n"
            "<b>Wink:</b> <a href='{}'>Add Stickew Pack</a>"
        ),
        "btn_add": "Add Pack",
        "error": (
            "<tg-emoji emoji-id=5253864872780769235>❗️</tg-emoji> "
            "Ewwow: <code>{}</code>"
        ),
        "_cls_doc": "Convewts custom emoji and emoji packs into stickew packs at native stickew wesowution.",
        "_cmd_doc_e2s": "<pack / wepwy> — convewt an emoji pack into a stickew pack via API",
        "_cmd_doc_e1s": "<wepwy to emoji> [titwe] — one custom emoji into a stickew pack",
    }

    strings_tiktok = {
        "no_args": (
            "<tg-emoji emoji-id=5253864872780769235>❗️</tg-emoji> "
            "Бро, ответь на кастомку или кинь ссылку/шортнейм эмодзи-пака."
        ),
        "no_reply": (
            "<tg-emoji emoji-id=5253864872780769235>❗️</tg-emoji> "
            "Ответь на сообщение с кастомным эмодзи, это база."
        ),
        "fetch_err": (
            "<tg-emoji emoji-id=5253864872780769235>❗️</tg-emoji> "
            "Эмодзи-пак не нашёлся, кринж: <code>{}</code>"
        ),
        "empty_pack": (
            "<tg-emoji emoji-id=5253864872780769235>❗️</tg-emoji> "
            "Эмодзи-пак пустой, вайб не тот."
        ),
        "no_stickers": (
            "<tg-emoji emoji-id=5253864872780769235>❗️</tg-emoji> "
            "Для типа <code>{}</code> конвертить нечего."
        ),
        "unsupported": (
            "<tg-emoji emoji-id=5253864872780769235>❗️</tg-emoji> "
            "Формат эмодзи не зашёл, не поддерживается."
        ),
        "no_ffmpeg": (
            "<tg-emoji emoji-id=5253864872780769235>❗️</tg-emoji> "
            "Для видео-эмодзи на сервере нужен FFmpeg, без него никак."
        ),
        "loading": (
            "<tg-emoji emoji-id=4911656069207426158>💘</tg-emoji> "
            "<i>Ловлю инфу по эмодзи...</i>"
        ),
        "processing": (
            "<tg-emoji emoji-id=4911656069207426158>💘</tg-emoji> "
            "Делаю <b>{}</b> стикеры «<b>{}</b>»\n"
            "<b>Прогресс:</b> <code>{}/{}</code>"
        ),
        "success": (
            "<tg-emoji emoji-id=4911656069207426158>💘</tg-emoji> "
            "Стикерпак готов, это имба!\n\n"
            "<b>Название:</b> <code>{}</code>\n"
            "<b>Тип:</b> <code>{}</code>\n"
            "<b>Ссылка:</b> <a href='{}'>Добавить стикерпак</a>"
        ),
        "btn_add": "Кинуть пак",
        "error": (
            "<tg-emoji emoji-id=5253864872780769235>❗️</tg-emoji> "
            "Ошибка, не фортануло: <code>{}</code>"
        ),
        "_cls_doc": "Конвертит кастомные эмодзи и эмодзи-паки в стикерпаки в родном разрешении стикера.",
        "_cmd_doc_e2s": "<пак / реплай> — конвертнуть эмодзи-пак в стикерпак через API",
        "_cmd_doc_e1s": "<реплай на эмодзи> [название] — одну кастомку в стикерпак",
    }

    strings_neofit = {
        "no_args": (
            "<tg-emoji emoji-id=5253864872780769235>❗️</tg-emoji> "
            "ValueError: reply target or emoji pack shortname/url is required."
        ),
        "no_reply": (
            "<tg-emoji emoji-id=5253864872780769235>❗️</tg-emoji> "
            "TypeError: expected a reply containing MessageEntityCustomEmoji."
        ),
        "fetch_err": (
            "<tg-emoji emoji-id=5253864872780769235>❗️</tg-emoji> "
            "GetStickerSetRequest failed: <code>{}</code>"
        ),
        "empty_pack": (
            "<tg-emoji emoji-id=5253864872780769235>❗️</tg-emoji> "
            "documents[] is empty."
        ),
        "no_stickers": (
            "<tg-emoji emoji-id=5253864872780769235>❗️</tg-emoji> "
            "No documents matched mime filter for type <code>{}</code>."
        ),
        "unsupported": (
            "<tg-emoji emoji-id=5253864872780769235>❗️</tg-emoji> "
            "Unsupported mime_type."
        ),
        "no_ffmpeg": (
            "<tg-emoji emoji-id=5253864872780769235>❗️</tg-emoji> "
            "DependencyMissing: ffmpeg binary not found in PATH."
        ),
        "loading": (
            "<tg-emoji emoji-id=4911656069207426158>💘</tg-emoji> "
            "<i>await GetStickerSetRequest(...)</i>"
        ),
        "processing": (
            "<tg-emoji emoji-id=4911656069207426158>💘</tg-emoji> "
            "CreateStickerSetRequest type=<b>{}</b> title=«<b>{}</b>»\n"
            "<b>progress:</b> <code>{}/{}</code>"
        ),
        "success": (
            "<tg-emoji emoji-id=4911656069207426158>💘</tg-emoji> "
            "stickerSet created.\n\n"
            "<b>title:</b> <code>{}</code>\n"
            "<b>type:</b> <code>{}</code>\n"
            "<b>link:</b> <a href='{}'>t.me/addstickers</a>"
        ),
        "btn_add": "addstickers",
        "error": (
            "<tg-emoji emoji-id=5253864872780769235>❗️</tg-emoji> "
            "Exception: <code>{}</code>"
        ),
        "_cls_doc": "Converts custom emoji documents into a sticker set at native 512px sticker resolution.",
        "_cmd_doc_e2s": "<pack / reply> — convert an emoji set into a sticker set via API",
        "_cmd_doc_e1s": "<reply to emoji> [title] — wrap one custom emoji document into a sticker set",
    }

    @staticmethod
    def _clean_short_name(raw_name: str) -> str:
        name = re.sub(r"_by_.*$", "", raw_name, flags=re.IGNORECASE)
        name = re.sub(r"[^a-zA-Z0-9_]", "", name)
        name = re.sub(r"_+", "_", name).strip("_")
        name = name[:16].rstrip("_")
        return name or "pack"

    @staticmethod
    def _pack_from_arg(raw: str):
        text = (raw or "").strip()
        if not text:
            return None
        match = re.search(r"(?:addemoji|addstickers)/([A-Za-z0-9_]+)", text)
        short = match.group(1) if match else text.split("/")[-1].split()[0]
        short = re.sub(r"[^A-Za-z0-9_]", "", short)
        if not short:
            return None
        return InputStickerSetShortName(short_name=short)

    def _set_from_document(self, document):
        for attr in document.attributes:
            if isinstance(attr, (DocumentAttributeCustomEmoji, DocumentAttributeSticker)):
                stickerset = getattr(attr, "stickerset", None)
                if isinstance(stickerset, InputStickerSetShortName):
                    return stickerset
                if isinstance(stickerset, InputStickerSetID):
                    return InputStickerSetID(
                        id=stickerset.id,
                        access_hash=stickerset.access_hash,
                    )
        return None

    def _custom_ids(self, message: Message):
        found = []
        seen = set()
        for entity in message.entities or []:
            if isinstance(entity, MessageEntityCustomEmoji) and entity.document_id not in seen:
                seen.add(entity.document_id)
                found.append(entity.document_id)
        return found

    @loader.command(
        ru_doc="<пак / реплай> — конвертировать эмодзи-пак в стикерпак через API",
        ua_doc="<пак / відповідь> — конвертувати емодзі-пак у стікерпак через API",
        de_doc="<Pack / Antwort> — Emoji-Pack über die API in ein Stickerpack umwandeln",
        jp_doc="<パック / 返信> — 絵文字パックを API 経由でステッカーパックに変換",
        leet_doc="<p4ck / r3ply> — c0nv3r7 4n 3m0j1 p4ck 1n70 4 571ck3r p4ck v14 4P1",
        uwu_doc="<pack / wepwy> — convewt an emoji pack into a stickew pack via API",
        tiktok_doc="<пак / реплай> — конвертнуть эмодзи-пак в стикерпак через API",
        neofit_doc="<pack / reply> — convert an emoji set into a sticker set via API",
        en_doc="<pack / reply> — convert an emoji pack into a sticker pack via API",
    )
    async def e2scmd(self, message: Message):
        """<pack / reply> — convert an emoji pack into a sticker pack via API"""
        reply = await message.get_reply_message()
        args = utils.get_args_raw(message)
        sticker_set = None

        if reply and reply.document:
            sticker_set = self._set_from_document(reply.document)

        if not sticker_set and reply:
            ids = self._custom_ids(reply)
            if ids:
                await self._from_ids(message, ids)
                return

        if not sticker_set and args:
            sticker_set = self._pack_from_arg(args)

        if not sticker_set:
            own_ids = self._custom_ids(message)
            if own_ids:
                await self._from_ids(message, own_ids)
                return
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

        docs = list(full_set.documents or [])
        if not docs:
            with contextlib.suppress(Exception):
                await form.edit(
                    text=self.strings("empty_pack", message),
                    reply_markup=None,
                )
            return

        pack_type = self._detect_type(docs, full_set.set)
        if pack_type == "video" and not shutil.which("ffmpeg"):
            with contextlib.suppress(Exception):
                await form.edit(
                    text=self.strings("no_ffmpeg", message),
                    reply_markup=None,
                )
            return

        docs = self._filter_docs(docs, pack_type)[:MAX_PACK]
        if not docs:
            with contextlib.suppress(Exception):
                await form.edit(
                    text=self.strings("no_stickers", message).format(pack_type),
                    reply_markup=None,
                )
            return

        raw_short = getattr(full_set.set, "short_name", "") or "pack"
        title = f"{full_set.set.title[:50]} Stickers"
        await self._create_pack(
            message=message,
            form=form,
            docs=docs,
            pack_type=pack_type,
            title=title,
            clean_name=self._clean_short_name(raw_short),
        )

    @loader.command(
        ru_doc="<реплай на эмодзи> [название] — одно кастомное эмодзи в стикерпак",
        ua_doc="<відповідь на емодзі> [назва] — одне кастомне емодзі в стікерпак",
        de_doc="<Antwort auf Emoji> [Titel] — ein Custom-Emoji in ein Stickerpack",
        jp_doc="<絵文字への返信> [タイトル] — カスタム絵文字1つをステッカーパックに",
        leet_doc="<r3ply 70 3m0j1> [717l3] — 0n3 cu570m 3m0j1 1n70 4 571ck3r p4ck",
        uwu_doc="<wepwy to emoji> [titwe] — one custom emoji into a stickew pack",
        tiktok_doc="<реплай на эмодзи> [название] — одну кастомку в стикерпак",
        neofit_doc="<reply to emoji> [title] — wrap one custom emoji document into a sticker set",
        en_doc="<reply to emoji> [title] — one custom emoji into a sticker pack",
    )
    async def e1scmd(self, message: Message):
        """<reply to emoji> [title] — one custom emoji into a sticker pack"""
        reply = await message.get_reply_message()
        ids = self._custom_ids(reply) if reply else []
        if not ids:
            ids = self._custom_ids(message)
        if not ids and reply and reply.document:
            doc = reply.document
            if any(isinstance(a, DocumentAttributeCustomEmoji) for a in doc.attributes):
                await self._create_single(message, [doc])
                return
        if not ids:
            await self.inline.form(
                text=self.strings("no_reply", message),
                message=message,
                silent=True,
            )
            return
        await self._from_ids(message, ids[:1], single_title=True)

    async def _from_ids(self, message: Message, document_ids: list, single_title: bool = False):
        form = await self.inline.form(
            text=self.strings("loading", message),
            message=message,
            silent=True,
        )
        try:
            docs = await message.client(
                GetCustomEmojiDocumentsRequest(document_id=document_ids)
            )
        except Exception as exc:
            with contextlib.suppress(Exception):
                await form.edit(
                    text=self.strings("fetch_err", message).format(exc),
                    reply_markup=None,
                )
            return
        docs = [doc for doc in docs if getattr(doc, "mime_type", None)]
        if not docs:
            with contextlib.suppress(Exception):
                await form.edit(
                    text=self.strings("unsupported", message),
                    reply_markup=None,
                )
            return
        if len(docs) == 1 or single_title:
            await self._create_single(message, docs[:1], form)
            return

        pack_type = self._detect_type(docs, None)
        if pack_type == "video" and not shutil.which("ffmpeg"):
            with contextlib.suppress(Exception):
                await form.edit(
                    text=self.strings("no_ffmpeg", message),
                    reply_markup=None,
                )
            return
        docs = self._filter_docs(docs, pack_type)[:MAX_PACK]
        rnd = "".join(random.choices(string.ascii_lowercase + string.digits, k=6))
        await self._create_pack(
            message=message,
            form=form,
            docs=docs,
            pack_type=pack_type,
            title=f"Emoji {rnd.upper()}",
            clean_name=f"e_{rnd}",
        )

    async def _create_single(self, message: Message, docs: list, form=None):
        if form is None:
            form = await self.inline.form(
                text=self.strings("loading", message),
                message=message,
                silent=True,
            )
        pack_type = self._detect_type(docs, None)
        if pack_type == "video" and not shutil.which("ffmpeg"):
            with contextlib.suppress(Exception):
                await form.edit(
                    text=self.strings("no_ffmpeg", message),
                    reply_markup=None,
                )
            return
        args = utils.get_args_raw(message)
        rnd = "".join(random.choices(string.ascii_lowercase + string.digits, k=6))
        title = args.strip()[:50] if args else f"Sticker {rnd.upper()}"
        await self._create_pack(
            message=message,
            form=form,
            docs=docs[:1],
            pack_type=pack_type,
            title=title,
            clean_name=f"s_{rnd}",
        )

    @staticmethod
    def _detect_type(docs: list, sticker_set) -> str:
        sample = docs[:3]
        if getattr(sticker_set, "animated", False) or any(
            doc.mime_type == "application/x-tgsticker" for doc in sample
        ):
            return "animated"
        if getattr(sticker_set, "videos", False) or any(
            doc.mime_type in ("video/webm", "video/mp4") for doc in sample
        ):
            return "video"
        return "static"

    @staticmethod
    def _filter_docs(docs: list, pack_type: str) -> list:
        if pack_type == "animated":
            return [doc for doc in docs if doc.mime_type == "application/x-tgsticker"]
        if pack_type == "video":
            return [doc for doc in docs if doc.mime_type in ("video/webm", "video/mp4")]
        return [
            doc
            for doc in docs
            if doc.mime_type in ("image/webp", "image/png", "image/jpeg")
        ]

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
        short_name = f"s_{rnd_hash}_{clean_base}_by_{my_name}"[:64].rstrip("_")

        with contextlib.suppress(Exception):
            await form.edit(
                text=self.strings("processing", message).format(pack_type, title, 0, total),
                reply_markup=None,
            )

        sem = asyncio.Semaphore(3)
        progress = [0]
        last_edit = [0.0]
        lock = asyncio.Lock()

        async def _update_progress():
            now = asyncio.get_event_loop().time()
            if now - last_edit[0] < 2.0:
                return
            last_edit[0] = now
            done = progress[0]
            bar_len = 12
            filled = int(done / total * bar_len)
            bar = "█" * filled + "░" * (bar_len - filled)
            with contextlib.suppress(Exception):
                await form.edit(
                    text=(
                        f"{self.strings('processing', message).format(pack_type, title, done, total)}\n"
                        f"<code>[{bar}]</code> {int(done / total * 100)}%"
                    ),
                    reply_markup=None,
                )

        async def _worker(idx: int, doc):
            emoji = "⭐"
            for attr in doc.attributes:
                if (
                    isinstance(attr, (DocumentAttributeCustomEmoji, DocumentAttributeSticker))
                    and getattr(attr, "alt", None)
                ):
                    emoji = attr.alt
                    break
            raw = await message.client.download_media(doc, bytes)
            loop = asyncio.get_running_loop()
            if pack_type == "animated":
                file_obj = io.BytesIO(raw)
                file_obj.name = "sticker.tgs"
                mime = "application/x-tgsticker"
            elif pack_type == "video":
                file_obj = await self._upscale_video(raw)
                mime = "video/webm"
            else:
                file_obj = await loop.run_in_executor(None, self._upscale_static, raw)
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
                    return idx, item
                except FloodWaitError as exc:
                    await asyncio.sleep(exc.seconds + 1)
                except Exception:
                    if attempt == 2:
                        return None
                    await asyncio.sleep(1)
            return None

        try:
            results = await asyncio.gather(*[_worker(i, doc) for i, doc in enumerate(docs)])
            items = [item for _, item in sorted(row for row in results if row)]
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
            link = f"https://t.me/addstickers/{final_sn}"
            with contextlib.suppress(Exception):
                await form.edit(
                    text=self.strings("success", message).format(title, pack_type, link),
                    reply_markup=[[{"text": self.strings("btn_add", message), "url": link}]],
                )
        except Exception as exc:
            with contextlib.suppress(Exception):
                await form.edit(
                    text=self.strings("error", message).format(exc),
                    reply_markup=None,
                )

    async def _safe_create_set(self, client, title: str, short_name: str, stickers: list, retries: int = 3):
        for index in range(retries):
            short = short_name if index == 0 else f"{short_name}_{index + 1}"
            short = short[:64]
            try:
                await client(
                    functions.stickers.CreateStickerSetRequest(
                        user_id=InputUserSelf(),
                        title=title,
                        short_name=short,
                        stickers=stickers,
                    )
                )
                return short, None
            except Exception as exc:
                err = str(exc)
                occupied = (
                    "SHORT_NAME_OCCUPIED" in err
                    or "already exists" in err.lower()
                    or "STICKERSET_INVALID" in err
                )
                if occupied and index < retries - 1:
                    continue
                return None, err
        return None, "SHORT_NAME_OCCUPIED"

    @staticmethod
    async def _upload_item(client, file_obj: io.BytesIO, mime: str, emoji_str: str, pack_type: str):
        attr_sticker = DocumentAttributeSticker(
            alt=emoji_str or "⭐",
            stickerset=InputStickerSetEmpty(),
        )
        if pack_type == "animated":
            mt = "application/x-tgsticker"
            filename = "sticker.tgs"
            extra = []
        elif pack_type == "video":
            mt = "video/webm"
            filename = "sticker.webm"
            extra = [DocumentAttributeVideo(duration=3, w=STICKER_SIDE, h=STICKER_SIDE, nosound=True)]
        else:
            mt = "image/webp"
            filename = "sticker.webp"
            extra = [DocumentAttributeImageSize(w=STICKER_SIDE, h=STICKER_SIDE)]

        file_obj.seek(0)
        uploaded = await client.upload_file(file_obj, file_name=filename)
        media = InputMediaUploadedDocument(
            file=uploaded,
            mime_type=mt,
            attributes=[DocumentAttributeFilename(file_name=filename), attr_sticker, *extra],
        )
        result = await client(UploadMediaRequest(peer=InputPeerSelf(), media=media))
        doc = result.document
        return InputStickerSetItem(
            document=InputDocument(
                id=doc.id,
                access_hash=doc.access_hash,
                file_reference=doc.file_reference,
            ),
            emoji=emoji_str or "⭐",
        )

    @staticmethod
    def _upscale_static(image_bytes: bytes) -> io.BytesIO:
        image = Image.open(io.BytesIO(image_bytes)).convert("RGBA")
        side = STICKER_SIDE
        if image.width != side or image.height != side:
            scale = min(side / image.width, side / image.height)
            resized = image.resize(
                (max(1, round(image.width * scale)), max(1, round(image.height * scale))),
                Image.Resampling.LANCZOS,
            )
            canvas = Image.new("RGBA", (side, side), (0, 0, 0, 0))
            canvas.alpha_composite(
                resized,
                dest=((side - resized.width) // 2, (side - resized.height) // 2),
            )
            image = canvas

        output = io.BytesIO()
        output.name = "sticker.webp"
        image.save(output, format="WEBP", lossless=True, quality=100, method=6)
        if output.tell() > MAX_STATIC_BYTES:
            output = io.BytesIO()
            output.name = "sticker.webp"
            image.save(output, format="WEBP", lossless=False, quality=95, method=6)
        output.seek(0)
        return output

    @staticmethod
    async def _upscale_video(video_bytes: bytes) -> io.BytesIO:
        with tempfile.NamedTemporaryFile(suffix=".webm", delete=False) as source:
            source_path = source.name
            source.write(video_bytes)
        out_path = source_path + "_out.webm"
        try:
            vf = (
                "format=rgba,"
                f"scale={STICKER_SIDE}:{STICKER_SIDE}:force_original_aspect_ratio=decrease:flags=lanczos,"
                f"pad={STICKER_SIDE}:{STICKER_SIDE}:(ow-iw)/2:(oh-ih)/2:color=0x00000000,"
                "format=yuva420p"
            )
            presets = (
                {"crf": "18", "bitrate": "900k", "maxrate": "1100k", "bufsize": "1500k"},
                {"crf": "24", "bitrate": "600k", "maxrate": "800k", "bufsize": "1000k"},
                {"crf": "32", "bitrate": "350k", "maxrate": "450k", "bufsize": "600k"},
                {"crf": "40", "bitrate": "180k", "maxrate": "240k", "bufsize": "320k"},
            )
            written = False
            for preset in presets:
                if os.path.exists(out_path):
                    os.remove(out_path)
                cmd = [
                    "ffmpeg", "-y",
                    "-c:v", "libvpx-vp9",
                    "-i", source_path,
                    "-t", "2.99",
                    "-vf", vf,
                    "-c:v", "libvpx-vp9",
                    "-pix_fmt", "yuva420p",
                    "-auto-alt-ref", "0",
                    "-metadata:s:v:0", "alpha_mode=1",
                    "-crf", preset["crf"],
                    "-b:v", preset["bitrate"],
                    "-maxrate", preset["maxrate"],
                    "-bufsize", preset["bufsize"],
                    "-r", "30",
                    "-an",
                    out_path,
                ]
                proc = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.DEVNULL,
                    stderr=asyncio.subprocess.PIPE,
                )
                _, stderr = await proc.communicate()
                if proc.returncode != 0 or not os.path.exists(out_path):
                    if not written:
                        raise RuntimeError(
                            (stderr or b"ffmpeg failed").decode("utf-8", "replace")[-300:]
                        )
                    break
                written = True
                if os.path.getsize(out_path) <= MAX_VIDEO_BYTES:
                    break
            if not written:
                raise RuntimeError("Failed to upscale video emoji")
            with open(out_path, "rb") as handle:
                output = io.BytesIO(handle.read())
            output.name = "sticker.webm"
            output.seek(0)
            return output
        finally:
            if os.path.exists(source_path):
                os.remove(source_path)
            if os.path.exists(out_path):
                os.remove(out_path)
