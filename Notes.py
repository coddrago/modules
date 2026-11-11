# ---------------------------------------------------------------------------------
#░█▀▄░▄▀▀▄░█▀▄░█▀▀▄░█▀▀▄░█▀▀▀░▄▀▀▄░░░█▀▄▀█
#░█░░░█░░█░█░█░█▄▄▀░█▄▄█░█░▀▄░█░░█░░░█░▀░█
#░▀▀▀░░▀▀░░▀▀░░▀░▀▀░▀░░▀░▀▀▀▀░░▀▀░░░░▀░░▒▀
# Name: Notes
# Description: Advanced notes module with folders and other features
# Author: @codrago
# ---------------------------------------------------------------------------------
# 🔒    Licensed under the GNU AGPLv3
# 🌐 https://www.gnu.org/licenses/agpl-3.0.html
# ---------------------------------------------------------------------------------
# Commands: hsave, hget, hdel, hlist
# scope: heroku_only
# meta developer: @codrago_m
# meta banner: https://raw.githubusercontent.com/coddrago/modules/refs/heads/main/banner.png
# ---------------------------------------------------------------------------------

__version__ = (1, 0, 0)

import logging

from herokutl.tl.types import Message

from heroku import loader, utils

logger = logging.getLogger(__name__)

DEFAULT_FOLDER = "global"


@loader.tds
class NotesMod(loader.Module):
    """Advanced notes module with folders and other features"""

    strings = {
        "name": "Notes",
        "saved": (
            "💾 <b>Note</b> <code>{}</code> <b>saved</b>.\n"
            "📁 <b>Folder:</b> <code>{}</code>"
        ),
        "no_reply": "🚫 <b>Reply and note name are required.</b>",
        "no_name": "🚫 <b>Specify note name.</b>",
        "no_note": "🚫 <b>Note not found.</b>",
        "available_notes": "💾 <b>Current notes:</b>",
        "no_notes": "😔 <b>You have no notes yet</b>",
        "deleted": "🙂 <b>Deleted note </b><code>{}</code>",
        "_cmd_doc_hsave": "[folder] <name> - Save new note",
        "_cmd_doc_hget": "<name> - Show specified note",
        "_cmd_doc_hdel": "<name> - Delete specified note",
        "_cmd_doc_hlist": "[folder] - List all notes",
        "_cls_doc": "Notes module with folders and categories",
    }

    strings_ru = {
        "saved": (
            "💾 <b>Заметка</b> <code>{}</code> <b>сохранена</b>.\n"
            "📁 <b>Папка:</b> <code>{}</code>"
        ),
        "no_reply": "🚫 <b>Требуется реплай на контент заметки.</b>",
        "no_name": "🚫 <b>Укажи имя заметки.</b>",
        "no_note": "🚫 <b>Заметка не найдена.</b>",
        "available_notes": "💾 <b>Текущие заметки:</b>",
        "no_notes": "😔 <b>У тебя пока что нет заметок</b>",
        "deleted": "🙂 <b>Заметка с именем </b><code>{}</code> <b>удалена</b>",
        "_cmd_doc_hsave": "[папка] <имя> - Сохранить заметку",
        "_cmd_doc_hget": "<имя> - Показать заметку",
        "_cmd_doc_hdel": "<имя> - Удалить заметку",
        "_cmd_doc_hlist": "[папка] - Показать все заметки",
        "_cls_doc": "Модуль заметок с расширенным функционалом. Папки и категории",
    }

    strings_de = {
        "saved": (
            "💾 <b>Notiz</b> <code>{}</code> <b>gespeichert</b>.\n"
            "📁 <b>Ordner:</b> <code>{}</code>"
        ),
        "no_reply": "🚫 <b>Antworte auf den Inhalt der Notiz.</b>",
        "no_name": "🚫 <b>Gib einen Namen für die Notiz an.</b>",
        "no_note": "🚫 <b>Notiz nicht gefunden.</b>",
        "available_notes": "💾 <b>Aktuelle Notizen:</b>",
        "no_notes": "😔 <b>Du hast noch keine Notizen</b>",
        "deleted": "🙂 <b>Notiz mit dem Namen </b><code>{}</code> <b>gelöscht</b>",
        "_cmd_doc_hsave": "[Ordner] <Name> - Speichert eine neue Notiz",
        "_cmd_doc_hget": "<Name> - Zeigt eine Notiz an",
        "_cmd_doc_hdel": "<Name> - Löscht eine Notiz",
        "_cmd_doc_hlist": "[Ordner] - Zeigt alle Notizen an",
        "_cls_doc": "Notizenmodul mit erweiterten Funktionen. Ordner und Kategorien",
    }

    strings_tr = {
        "saved": (
            "💾 <b>Not</b> <code>{}</code> <b>kaydedildi</b>.\n"
            "📁 <b>Klasör:</b> <code>{}</code>"
        ),
        "no_reply": "🚫 <b>Not içeriğine yanıt verin.</b>",
        "no_name": "🚫 <b>Bir not adı belirtin.</b>",
        "no_note": "🚫 <b>Not bulunamadı.</b>",
        "available_notes": "💾 <b>Mevcut notlar:</b>",
        "no_notes": "😔 <b>Henüz notunuz yok</b>",
        "deleted": "🙂 <b>Not adı </b><code>{}</code> <b>silindi</b>",
        "_cmd_doc_hsave": "[Klasör] <Ad> - Yeni bir not kaydedin",
        "_cmd_doc_hget": "<Ad> - Bir notu göster",
        "_cmd_doc_hdel": "<Ad> - Bir notu sil",
        "_cmd_doc_hlist": "[Klasör] - Tüm notları göster",
        "_cls_doc": "Gelişmiş not modülü. Klasörler ve diğer özellikler",
    }

    strings_uz = {
        "saved": (
            "💾 <b>Qayd</b> <code>{}</code> <b>saqlandi</b>.\n"
            "📁 <b>Jild:</b> <code>{}</code>"
        ),
        "no_reply": "🚫 <b>Qayd tarkibiga javob bering.</b>",
        "no_name": "🚫 <b>Qayd nomini kiriting.</b>",
        "no_note": "🚫 <b>Qayd topilmadi.</b>",
        "available_notes": "💾 <b>Mavjud qaydlar:</b>",
        "no_notes": "😔 <b>Hozircha sizda qayd yo'q</b>",
        "deleted": "🙂 <b>Qayd nomi </b><code>{}</code> <b>o'chirildi</b>",
        "_cmd_doc_hsave": "[Jild] <Nomi> - Yangi qayd saqlash",
        "_cmd_doc_hget": "<Nomi> - Qaydni ko'rsatish",
        "_cmd_doc_hdel": "<Nomi> - Qaydni o'chirish",
        "_cmd_doc_hlist": "[Jild] - Barcha qaydlarni ko'rsatish",
        "_cls_doc": "Kengaytirilgan qayd moduli. Jildlar va kategoriyalar",
    }

    strings_hi = {
        "saved": (
            "💾 <b>नोट</b> <code>{}</code> <b>सहेजा गया</b>.\n"
            "📁 <b>फ़ोल्डर:</b> <code>{}</code>"
        ),
        "no_reply": "🚫 <b>नोट की अंतर्दृष्टि पर जवाब दें।</b>",
        "no_name": "🚫 <b>एक नोट नाम दर्ज करें।</b>",
        "no_note": "🚫 <b>नोट नहीं मिला।</b>",
        "available_notes": "💾 <b>उपलब्ध नोट्स:</b>",
        "no_notes": "😔 <b>आपके पास अभी तक कोई नोट नहीं है</b>",
        "deleted": "🙂 <b>नोट नाम </b><code>{}</code> <b>हटा दिया गया</b>",
        "_cmd_doc_hsave": "[फ़ोल्डर] <नाम> - एक नया नोट सहेजें",
        "_cmd_doc_hget": "<नाम> - एक नोट दिखाएं",
        "_cmd_doc_hdel": "<नाम> - एक नोट हटाएं",
        "_cmd_doc_hlist": "[फ़ोल्डर] - सभी नोट्स दिखाएं",
        "_cls_doc": "उन्नत नोट्स मॉड्यूल। फ़ोल्डर और श्रेणियाँ",
    }

    async def client_ready(self):
        self._notes = self.get("notes", {})

    @staticmethod
    def _parse_note_args(args: str) -> tuple[str, str]:
        """Split raw args into (folder, name)"""
        parts = args.split(maxsplit=1)
        match parts:
            case [folder, name]:
                return folder, name
            case _:
                return DEFAULT_FOLDER, args

    @staticmethod
    def _get_note_emoji(reply: Message) -> str:
        """Get emoji, which describes note media type"""
        match reply:
            case Message(video=video) if video:
                return "🎞"
            case Message(photo=photo) if photo:
                return "🖼"
            case Message(voice=voice) if voice:
                return "🗣"
            case Message(audio=audio) if audio:
                return "🎧"
            case Message(file=file) if file:
                return "📝"
            case _:
                return "🔹"

    def _find_note(self, name: str) -> tuple[str | None, dict | None]:
        """Find note by its name. Returns (folder, note)"""
        for folder, notes in self._notes.items():
            if name in notes:
                return folder, notes[name]

        return None, None

    async def _send_note_as_reply(self, message: Message, asset: Message) -> None:
        """Send note as a new message and remove command message"""
        await self._client.send_message(
            message.peer_id,
            asset,
            reply_to=getattr(message, "reply_to_msg_id", None),
        )

        if message.out:
            await message.delete()

    async def hsavecmd(self, message: Message):
        """[folder] <name> - Save new note"""
        args = utils.get_args_raw(message)
        reply = await message.get_reply_message()

        if not (reply and args):
            await utils.answer(message, self.strings["no_reply"])
            return

        folder, name = self._parse_note_args(args)

        if folder not in self._notes:
            logger.warning("Created new folder %s", folder)

        self._notes.setdefault(folder, {})[name] = {
            "id": await self._db.store_asset(reply),
            "type": self._get_note_emoji(reply),
        }

        self.set("notes", self._notes)

        await utils.answer(message, self.strings["saved"].format(name, folder))

    async def hgetcmd(self, message: Message):
        """<name> - Show specified note"""
        name = utils.get_args_raw(message)

        if not name:
            await utils.answer(message, self.strings["no_name"])
            return

        _, note = self._find_note(name)

        if not note:
            await utils.answer(message, self.strings["no_note"])
            return

        asset = await self._db.fetch_asset(note["id"])

        match asset:
            # Voice messages and round video messages
            # can't be set via edit, so send them as new messages
            case Message(voice=voice) if voice:
                await self._send_note_as_reply(message, asset)
            case Message(video_note=video_note) if video_note:
                await self._send_note_as_reply(message, asset)
            # Any other note type just replaces the command message
            case _ if message.out:
                await message.edit(
                    asset.message or " ",
                    file=asset.media,
                    parse_mode=lambda t: (t, asset.entities or []),
                )
            case _:
                await self._send_note_as_reply(message, asset)

    async def hdelcmd(self, message: Message):
        """<name> - Delete specified note"""
        name = utils.get_args_raw(message)

        if not name:
            await utils.answer(message, self.strings["no_name"])
            return

        folder, note = self._find_note(name)

        if not note:
            await utils.answer(message, self.strings["no_note"])
            return

        try:
            if asset := await self._db.fetch_asset(note["id"]):
                await asset.delete()
        except Exception:
            logger.debug("Failed to delete note asset", exc_info=True)

        del self._notes[folder][name]

        if not self._notes[folder]:
            del self._notes[folder]

        self.set("notes", self._notes)

        await utils.answer(message, self.strings["deleted"].format(name))

    async def hlistcmd(self, message: Message):
        """[folder] - List all notes"""
        args = utils.get_args_raw(message)

        if not self._notes:
            await utils.answer(message, self.strings["no_notes"])
            return

        match args:
            case str() if args in self._notes:
                result = "\n".join(
                    f"{asset['type']} <code>{note}</code>"
                    for note, asset in self._notes[args].items()
                )
            case _:
                result = "\n\n".join(
                    f"🔸 <b>{folder}</b>\n"
                    + "\n".join(
                        f"    {asset['type']} <code>{note}</code>"
                        for note, asset in notes.items()
                    )
                    for folder, notes in self._notes.items()
                )

        await utils.answer(
            message,
            f"{self.strings['available_notes']}\n{result}",
        )
