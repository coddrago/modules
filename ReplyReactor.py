# ---------------------------------------------------------------------------------
# ░█▀▄░▄▀▀▄░█▀▄░█▀▀▄░█▀▀▄░█▀▀▀░▄▀▀▄░░░█▀▄▀█
# ░█░░░█░░█░█░█░█▄▄▀░█▄▄█░█░▀▄░█░░█░░░█░▀░█
# ░▀▀▀░░▀▀░░▀▀░░▀░▀▀░▀░░▀░▀▀▀▀░░▀▀░░░░▀░░▒▀
# Name: ReplyReactor
# Description: React to the latest messages of a replied-to user from your account
# Author: @codrago_m
# ---------------------------------------------------------------------------------
# 🔒    Licensed under the GNU AGPLv3
# 🌐 https://www.gnu.org/licenses/agpl-3.0.html
# ---------------------------------------------------------------------------------
# Commands: rreact, rreactstop
# scope: heroku_only
# meta developer: @codrago_m
# ---------------------------------------------------------------------------------

import asyncio
import html
import re

from herokutl.errors import FloodWaitError, MessageNotModifiedError, RPCError
from herokutl.tl.functions.messages import GetAvailableReactionsRequest, SendReactionRequest
from herokutl.tl.types import Message, MessageEntityCustomEmoji, ReactionCustomEmoji, ReactionEmoji, User

from .. import loader, utils

__version__ = (1, 0, 2)

SCAN_LIMIT = 10000
PAUSE = 0.8

# UnigramIcons — https://t.me/addemoji/UnigramIcons
GEAR = '<tg-emoji emoji-id="5870982283724328568">⚙</tg-emoji>'
CHECK = '<tg-emoji emoji-id="5870633910337015697">✅</tg-emoji>'
WARN = '<tg-emoji emoji-id="5870931487146119264">❗️</tg-emoji>'
CROSS = '<tg-emoji emoji-id="5870657884844462243">❌</tg-emoji>'
CLOCK = '<tg-emoji emoji-id="5870496192210669260">⏲</tg-emoji>'
STOP = '<tg-emoji emoji-id="5872988737826197458">⛔️</tg-emoji>'
INFO = '<tg-emoji emoji-id="5870609858520158157">ℹ️</tg-emoji>'


class ReactorError(Exception):
    def __init__(self, key, **values):
        self.key = key
        self.values = values
        super().__init__(key)


@loader.tds
class ReplyReactorMod(loader.Module):
    """Reacts to a user's latest messages in this chat from your account."""

    strings = {
        "name": "ReplyReactor",
        "usage": (
            WARN + " Reply to a user: {prefix}rreact &lt;emoji or custom emoji ID&gt; "
            "&lt;1–1000&gt;. Reactions are placed from your account. Stop: {prefix}rreactstop"
        ),
        "reply": WARN + " Reply to a regular message sent by a user, not an anonymous channel.",
        "emoji": WARN + " Unknown reaction. Insert one supported emoji, one custom emoji, or its positive numeric ID.",
        "busy": CLOCK + " A reaction job is already running. Stop it in its chat with {prefix}rreactstop.",
        "start": GEAR + " Reacting to up to {count} latest messages by {name} from your account. Stop: {prefix}rreactstop",
        "result": CHECK + " Messages reacted to: {done}/{count}. Skipped: {skipped}. Checked: {scanned}.",
        "stopped": STOP + " Stopped; existing reactions remain.",
        "limit": INFO + " The scan limit of 10000 messages was reached.",
        "flood": CLOCK + " Telegram requested a pause of {seconds} seconds; the job stopped.",
        "error": CROSS + " Stopped: {error}. Check chat access, allowed reactions, and Premium for custom emoji.",
        "idle": INFO + " No reaction job is running in this chat.",
        "stopping": STOP + " Stopping after the current reaction.",
        "_cls_doc": "Reacts to a user's latest messages in this chat from your account.",
        "_cmd_doc_rreact": "<emoji/ID> <count>, reply to a user; latest messages, reactions from your account",
        "_cmd_doc_rreactstop": "Stop the reaction job in this chat; keep reactions already placed",
    }
    strings_ru = {
        "usage": (
            WARN + " Ответом пользователю: {prefix}rreact &lt;эмодзи или ID премиум-эмодзи&gt; "
            "&lt;1–1000&gt;. Реакции ставятся с твоего аккаунта. Стоп: {prefix}rreactstop"
        ),
        "reply": WARN + " Ответь на обычное сообщение пользователя, а не анонимного канала.",
        "emoji": WARN + " Неизвестная реакция. Вставь один поддерживаемый эмодзи, один премиум-эмодзи или его положительный числовой ID.",
        "busy": CLOCK + " Расстановка уже идёт. Остановить её можно в исходном чате: {prefix}rreactstop.",
        "start": GEAR + " Ставлю реакции на последние сообщения {name}, до {count} шт., с твоего аккаунта. Стоп: {prefix}rreactstop",
        "result": CHECK + " Сообщений с реакцией: {done}/{count}. Пропущено: {skipped}. Проверено: {scanned}.",
        "stopped": STOP + " Остановлено; уже поставленные реакции сохранены.",
        "limit": INFO + " Достигнут предел просмотра: 10000 сообщений.",
        "flood": CLOCK + " Telegram просит подождать {seconds} с; расстановка остановлена.",
        "error": CROSS + " Остановлено: {error}. Проверь доступ к чату, разрешённые реакции и Premium для кастомных эмодзи.",
        "idle": INFO + " В этом чате расстановка не запущена.",
        "stopping": STOP + " Остановлюсь после текущей реакции.",
        "_cls_doc": "Ставит реакции на последние сообщения пользователя в чате с твоего аккаунта.",
        "_cmd_doc_rreact": "<эмодзи/ID> <число>, ответом пользователю; последние сообщения, реакции с твоего аккаунта",
        "_cmd_doc_rreactstop": "Остановить расстановку в этом чате; уже поставленные реакции останутся",
    }
    strings_ua = {
        "usage": (
            WARN + " Відповіддю користувачу: {prefix}rreact &lt;емодзі або ID власного емодзі&gt; "
            "&lt;1–1000&gt;. Реакції ставляться з твого акаунта. Стоп: {prefix}rreactstop"
        ),
        "reply": WARN + " Відповідай на звичайне повідомлення користувача, а не анонімного каналу.",
        "emoji": WARN + " Невідома реакція. Встав один підтримуваний емодзі, власний емодзі або його додатний числовий ID.",
        "busy": CLOCK + " Реакції вже розставляються. Зупини в початковому чаті: {prefix}rreactstop.",
        "start": GEAR + " Ставлю реакції на останні повідомлення {name}, до {count} шт., з твого акаунта. Стоп: {prefix}rreactstop",
        "result": CHECK + " Повідомлень із реакцією: {done}/{count}. Пропущено: {skipped}. Перевірено: {scanned}.",
        "stopped": STOP + " Зупинено; поставлені реакції збережено.",
        "limit": INFO + " Досягнуто межі перегляду: 10000 повідомлень.",
        "flood": CLOCK + " Telegram просить зачекати {seconds} с; розстановку зупинено.",
        "error": CROSS + " Зупинено: {error}. Перевір доступ до чату, дозволені реакції та Premium для власних емодзі.",
        "idle": INFO + " У цьому чаті розстановку не запущено.",
        "stopping": STOP + " Зупинюся після поточної реакції.",
        "_cls_doc": "Ставить реакції на останні повідомлення користувача з твого акаунта.",
        "_cmd_doc_rreact": "<емодзі/ID> <число>, відповіддю користувачу; останні повідомлення, реакції з твого акаунта",
        "_cmd_doc_rreactstop": "Зупинити розстановку в цьому чаті; поставлені реакції залишаться",
    }
    strings_de = {
        "usage": (
            WARN + " Auf einen Nutzer antworten: {prefix}rreact &lt;Emoji oder eigene Emoji-ID&gt; "
            "&lt;1–1000&gt;. Reaktionen kommen von deinem Konto. Stopp: {prefix}rreactstop"
        ),
        "reply": WARN + " Antworte auf eine normale Nutzernachricht, nicht auf einen anonymen Kanal.",
        "emoji": WARN + " Unbekannte Reaktion. Ein unterstütztes Emoji, eigenes Emoji oder dessen positive numerische ID eingeben.",
        "busy": CLOCK + " Ein Auftrag läuft bereits. Im ursprünglichen Chat stoppen: {prefix}rreactstop.",
        "start": GEAR + " Reagiere auf bis zu {count} neueste Nachrichten von {name}, von deinem Konto. Stopp: {prefix}rreactstop",
        "result": CHECK + " Nachrichten mit Reaktion: {done}/{count}. Übersprungen: {skipped}. Geprüft: {scanned}.",
        "stopped": STOP + " Gestoppt; gesetzte Reaktionen bleiben erhalten.",
        "limit": INFO + " Suchgrenze von 10000 Nachrichten erreicht.",
        "flood": CLOCK + " Telegram verlangt {seconds} Sekunden Pause; Auftrag gestoppt.",
        "error": CROSS + " Gestoppt: {error}. Chat-Zugriff, erlaubte Reaktionen und Premium für eigene Emojis prüfen.",
        "idle": INFO + " In diesem Chat läuft kein Auftrag.",
        "stopping": STOP + " Stoppe nach der aktuellen Reaktion.",
        "_cls_doc": "Reagiert auf die neuesten Nutzernachrichten von deinem Konto.",
        "_cmd_doc_rreact": "<Emoji/ID> <Anzahl>, als Antwort auf einen Nutzer; neueste Nachrichten, von deinem Konto",
        "_cmd_doc_rreactstop": "Auftrag in diesem Chat stoppen; gesetzte Reaktionen bleiben erhalten",
    }
    strings_jp = {
        "usage": (
            WARN + " ユーザーに返信: {prefix}rreact &lt;絵文字またはカスタム絵文字ID&gt; "
            "&lt;1–1000&gt;。リアクションは自分のアカウントから付きます。停止: {prefix}rreactstop"
        ),
        "reply": WARN + " 匿名チャンネルではなく、ユーザーの通常メッセージに返信してください。",
        "emoji": WARN + " 無効なリアクションです。対応する絵文字、カスタム絵文字、または正の数値IDを1つ指定してください。",
        "busy": CLOCK + " 処理が進行中です。元のチャットで停止: {prefix}rreactstop。",
        "start": GEAR + " {name} の最新メッセージ最大 {count} 件に、自分のアカウントからリアクションします。停止: {prefix}rreactstop",
        "result": CHECK + " リアクション済み: {done}/{count}。スキップ: {skipped}。確認済み: {scanned}。",
        "stopped": STOP + " 停止しました。追加済みのリアクションは残ります。",
        "limit": INFO + " 確認上限の10000件に達しました。",
        "flood": CLOCK + " Telegramが {seconds} 秒の待機を要求しました。処理を停止しました。",
        "error": CROSS + " 停止: {error}。チャット権限、許可されたリアクション、カスタム絵文字用のPremiumを確認してください。",
        "idle": INFO + " このチャットで実行中の処理はありません。",
        "stopping": STOP + " 現在のリアクションが完了したら停止します。",
        "_cls_doc": "自分のアカウントでユーザーの最新メッセージにリアクションします。",
        "_cmd_doc_rreact": "<絵文字/ID> <件数>、ユーザーに返信。最新メッセージ、自分のアカウントから",
        "_cmd_doc_rreactstop": "このチャットの処理を停止。追加済みのリアクションは残ります",
    }
    strings_neofit = {
        "usage": WARN + " Input: {prefix}rreact &lt;emoji/custom_id&gt; &lt;1–1000&gt;, as a reply. Actor: user_account. Cancel: {prefix}rreactstop",
        "reply": WARN + " InputError: reply to a user message, not an anonymous channel.",
        "emoji": WARN + " ReactionError: expected one supported emoji, custom emoji entity, or positive document ID.",
        "busy": CLOCK + " JobBusy: cancel in the original chat with {prefix}rreactstop.",
        "start": GEAR + " Job started: user={name}, latest={count}, actor=user_account. Cancel: {prefix}rreactstop",
        "result": CHECK + " Reactions: {done}/{count}; skipped={skipped}; scanned={scanned}.",
        "stopped": STOP + " Job cancelled; completed reactions retained.",
        "limit": INFO + " ScanLimit: 10000 messages reached.",
        "flood": CLOCK + " FloodWait: {seconds}s; job stopped.",
        "error": CROSS + " JobError: {error}. Verify chat access, allowed reactions, and custom emoji Premium access.",
        "idle": INFO + " No active job for this chat.",
        "stopping": STOP + " Cancellation queued; finishing the current reaction.",
        "_cls_doc": "Batch reaction pipeline for a replied-to user's latest messages, sent from the user account.",
        "_cmd_doc_rreact": "<emoji/ID> <count>, reply required; latest messages, actor=user_account",
        "_cmd_doc_rreactstop": "Cancel this chat's job; retain completed reactions",
    }
    strings_tiktok = {
        "usage": WARN + " Реплай юзеру: {prefix}rreact &lt;эмодзи или ID&gt; &lt;1–1000&gt;. Реакции летят с твоего акка. Стоп: {prefix}rreactstop",
        "reply": WARN + " Нужен реплай на сообщение юзера, а не анонимного канала.",
        "emoji": WARN + " Эту реакцию не понял. Вставь один обычный или премиум-эмодзи либо его числовой ID больше нуля.",
        "busy": CLOCK + " Реакции уже летят. Стоп в исходном чате: {prefix}rreactstop.",
        "start": GEAR + " Реакции на последние сообщения {name}, до {count} штук, с твоего акка. Стоп: {prefix}rreactstop",
        "result": CHECK + " С реакцией: {done}/{count}. Скип: {skipped}. Проверено: {scanned}.",
        "stopped": STOP + " Стоп, уже поставленное осталось.",
        "limit": INFO + " 10000 сообщений просмотрено, это лимит.",
        "flood": CLOCK + " Telegram просит паузу {seconds} с, расстановка на стопе.",
        "error": CROSS + " Стоп: {error}. Чекни доступ, разрешённые реакции и Premium для кастомок.",
        "idle": INFO + " Тут сейчас ничего не ставится.",
        "stopping": STOP + " Закончим текущую реакцию и стоп.",
        "_cls_doc": "Ставит реакции на последние сообщения юзера с твоего акка.",
        "_cmd_doc_rreact": "<эмодзи/ID> <число>, реплаем юзеру; последние сообщения, с твоего акка",
        "_cmd_doc_rreactstop": "Стопнуть расстановку тут; готовые реакции останутся",
    }
    strings_uwu = {
        "usage": WARN + " Ответь пользователю: {prefix}rreact &lt;эмодзи или ID&gt; &lt;1–1000&gt;. Реакции с твоего аккаунта, ня. Стоп: {prefix}rreactstop",
        "reply": WARN + " Нужен ответ на обычное сообщение пользователя, не анонимного канала, ня.",
        "emoji": WARN + " Не узнал реакцию. Вставь один доступный эмодзи, премиум-эмодзи или его положительный числовой ID.",
        "busy": CLOCK + " Уже расставляю реакции, ня. Стоп в исходном чате: {prefix}rreactstop.",
        "start": GEAR + " Украшаю последние сообщения {name}, до {count} шт., с твоего аккаунта. Стоп: {prefix}rreactstop",
        "result": CHECK + " С реакцией: {done}/{count}. Пропущено: {skipped}. Проверено: {scanned}, ня.",
        "stopped": STOP + " Остановился, уже поставленные реакции остались.",
        "limit": INFO + " Просмотрел 10000 сообщений, это предел, ня.",
        "flood": CLOCK + " Telegram просит {seconds} с отдыха; расстановка остановлена.",
        "error": CROSS + " Остановился: {error}. Проверь доступ, разрешённые реакции и Premium для кастомных эмодзи.",
        "idle": INFO + " В этом чате сейчас отдыхаю, ня.",
        "stopping": STOP + " Закончу текущую реакцию и остановлюсь.",
        "_cls_doc": "Украшает реакциями последние сообщения пользователя с твоего аккаунта.",
        "_cmd_doc_rreact": "<эмодзи/ID> <число>, ответом пользователю; последние сообщения, с твоего аккаунта",
        "_cmd_doc_rreactstop": "Остановить расстановку в чате; готовые реакции останутся, ня",
    }
    strings_leet = {
        "usage": WARN + " 1nput: {prefix}rreact &lt;emoji/ID&gt; &lt;1–1000&gt;, reply required. Actor: your_4ccount. St0p: {prefix}rreactstop",
        "reply": WARN + " R3ply to a user's regular message, not an anonymous channel.",
        "emoji": WARN + " B4d reaction: one supported emoji, custom emoji, or positive numeric ID required.",
        "busy": CLOCK + " J0b busy. St0p in its chat: {prefix}rreactstop.",
        "start": GEAR + " R3acting: user={name}, latest={count}, actor=your_4ccount. St0p: {prefix}rreactstop",
        "result": CHECK + " D0ne: {done}/{count}. Skipped: {skipped}. Scanned: {scanned}.",
        "stopped": STOP + " St0pped; completed reactions retained.",
        "limit": INFO + " Sc4n limit: 10000 messages.",
        "flood": CLOCK + " Fl00dWait: {seconds}s; job halted.",
        "error": CROSS + " H4lted: {error}. Check chat access, allowed reactions and Premium for custom emoji.",
        "idle": INFO + " N0 active job in this chat.",
        "stopping": STOP + " St0pping after the current reaction.",
        "_cls_doc": "B4tch reactions to a replied-to user's latest messages from your_4ccount.",
        "_cmd_doc_rreact": "<emoji/ID> <count>, reply required; latest messages, actor=your_4ccount",
        "_cmd_doc_rreactstop": "St0p this chat's reaction job; keep completed reactions",
    }

    def __init__(self):
        self._job = None
        self._available = None

    def _text(self, key, **values):
        return self.strings(key).format(**{k: html.escape(str(v)) for k, v in values.items()})

    def _parse(self, message):
        raw = message.raw_text or ""
        match = re.fullmatch(r"\S+\s+(\S+)\s+([0-9]{1,4})\s*", raw)
        if not match or not 1 <= int(match[2]) <= 1000:
            raise ReactorError("usage")
        token = match[1]
        offset = len(raw[: match.start(1)].encode("utf-16-le")) // 2
        length = len(token.encode("utf-16-le")) // 2
        entities = [
            entity
            for entity in message.entities or []
            if isinstance(entity, MessageEntityCustomEmoji)
            and entity.offset < offset + length
            and entity.offset + entity.length > offset
        ]
        if entities:
            entity = entities[0]
            if len(entities) != 1 or entity.offset != offset or entity.length != length:
                raise ReactorError("emoji")
            return ReactionCustomEmoji(entity.document_id), int(match[2])
        custom = re.fullmatch(r"(?:tg://emoji\?id=)?([0-9]{1,19})", token)
        if custom:
            doc_id = int(custom[1])
            if not 0 < doc_id < 2**63:
                raise ReactorError("emoji")
            return ReactionCustomEmoji(doc_id), int(match[2])
        return ReactionEmoji(token), int(match[2])

    def _same(self, left, right):
        if type(left) is not type(right):
            return False
        if isinstance(left, ReactionCustomEmoji):
            return left.document_id == right.document_id
        return left.emoticon == right.emoticon

    def _chosen(self, message):
        results = getattr(getattr(message, "reactions", None), "results", None) or []
        chosen = [
            item
            for item in results
            if item.chosen_order is not None
            and isinstance(item.reaction, (ReactionCustomEmoji, ReactionEmoji))
        ]
        return [item.reaction for item in sorted(chosen, key=lambda item: item.chosen_order)]

    async def _validate(self, reaction):
        if isinstance(reaction, ReactionCustomEmoji):
            return reaction
        if self._available is None:
            result = await self._client(GetAvailableReactionsRequest(hash=0))
            self._available = [item.reaction for item in result.reactions if not item.inactive]
        wanted = reaction.emoticon.replace("\ufe0f", "")
        for emoji in self._available:
            if emoji.replace("\ufe0f", "") == wanted:
                return ReactionEmoji(emoji)
        raise ReactorError("emoji")

    async def _send(self, peer, mid, reactions):
        try:
            await self._client(SendReactionRequest(peer=peer, msg_id=mid, reaction=reactions))
        except MessageNotModifiedError:
            pass

    async def _apply(self, message, peer, reaction):
        previous = self._chosen(message)
        if any(self._same(item, reaction) for item in previous):
            return
        await self._send(peer, message.id, previous + [reaction])

    async def _walk(self, command, sender, reaction, count, job):
        peer = await command.get_input_chat()
        albums = set()
        async for msg in self._client.iter_messages(
            peer, from_user=sender, limit=SCAN_LIMIT, max_id=command.id
        ):
            if job["stop"].is_set() or job["done"] >= count:
                break
            job["scanned"] += 1
            grouped = msg.grouped_id
            if (
                not isinstance(msg, Message)
                or msg.sender_id != sender.id
                or msg.id >= command.id
                or (grouped and grouped in albums)
            ):
                job["skipped"] += 1
                continue
            try:
                await self._apply(msg, peer, reaction)
            except RPCError as exc:
                if type(exc).__name__ not in {"MessageIdInvalidError", "MsgIdInvalidError"}:
                    raise
                job["skipped"] += 1
                continue
            job["done"] += 1
            if grouped:
                albums.add(grouped)
            if job["done"] >= count:
                break
            try:
                await asyncio.wait_for(job["stop"].wait(), timeout=PAUSE)
            except asyncio.TimeoutError:
                pass

    @loader.command(
        ru_doc="<эмодзи/ID> <число>, ответом пользователю; последние сообщения, реакции с твоего аккаунта",
        ua_doc="<емодзі/ID> <число>, відповіддю користувачу; останні повідомлення, реакції з твого акаунта",
        de_doc="<Emoji/ID> <Anzahl>, als Antwort auf einen Nutzer; neueste Nachrichten, von deinem Konto",
        jp_doc="<絵文字/ID> <件数>、ユーザーに返信。最新メッセージ、自分のアカウントから",
        neofit_doc="<emoji/ID> <count>, reply required; latest messages, actor=user_account",
        tiktok_doc="<эмодзи/ID> <число>, реплаем юзеру; последние сообщения, с твоего акка",
        uwu_doc="<эмодзи/ID> <число>, ответом пользователю; последние сообщения, с твоего аккаунта",
        leet_doc="<emoji/ID> <count>, reply required; latest messages, actor=your_4ccount",
        en_doc="<emoji/ID> <count>, reply to a user; latest messages, reactions from your account",
    )
    async def rreact(self, message: Message):
        """<emoji/ID> <count>, reply to a user; latest messages, reactions from your account"""
        prefix = self.get_prefix()
        if self._job is not None:
            await utils.answer(message, self._text("busy", prefix=prefix))
            return
        job = {
            "chat": message.chat_id,
            "stop": asyncio.Event(),
            "done": 0,
            "skipped": 0,
            "scanned": 0,
        }
        self._job = job
        status = message
        count = 0
        started = False
        reason = ""
        try:
            reaction, count = self._parse(message)
            reply = await message.get_reply_message()
            if not isinstance(reply, Message) or reply.chat_id != message.chat_id:
                raise ReactorError("reply")
            sender = await reply.get_sender()
            if not isinstance(sender, User):
                raise ReactorError("reply")
            reaction = await self._validate(reaction)
            name = " ".join(part for part in (sender.first_name, sender.last_name) if part) or str(sender.id)
            status = await utils.answer(
                message,
                self._text("start", count=count, name=name, prefix=prefix),
            )
            started = True
            await self._walk(message, sender, reaction, count, job)
            if job["stop"].is_set():
                reason = self.strings("stopped")
            elif job["scanned"] >= SCAN_LIMIT and job["done"] < count:
                reason = self.strings("limit")
        except ReactorError as exc:
            reason = self._text(exc.key, prefix=prefix, **exc.values)
        except FloodWaitError as exc:
            reason = self._text("flood", seconds=exc.seconds)
        except Exception as exc:
            reason = self._text("error", error=type(exc).__name__)
        finally:
            if self._job is job:
                self._job = None
        text = (
            self._text("result", count=count, **{key: job[key] for key in ("done", "skipped", "scanned")})
            if started
            else ""
        )
        text = "\n".join(part for part in (text, reason) if part)
        await utils.answer(status or message, text)

    @loader.command(
        ru_doc="Остановить расстановку в этом чате; уже поставленные реакции останутся",
        ua_doc="Зупинити розстановку в цьому чаті; поставлені реакції залишаться",
        de_doc="Auftrag in diesem Chat stoppen; gesetzte Reaktionen bleiben erhalten",
        jp_doc="このチャットの処理を停止。追加済みのリアクションは残ります",
        neofit_doc="Cancel this chat's job; retain completed reactions",
        tiktok_doc="Стопнуть расстановку тут; готовые реакции останутся",
        uwu_doc="Остановить расстановку в чате; готовые реакции останутся, ня",
        leet_doc="St0p this chat's reaction job; keep completed reactions",
        en_doc="Stop the reaction job in this chat; keep reactions already placed",
    )
    async def rreactstop(self, message: Message):
        """Stop the reaction job in this chat; keep reactions already placed"""
        if self._job is None or self._job["chat"] != message.chat_id:
            await utils.answer(message, self.strings("idle"))
            return
        self._job["stop"].set()
        await utils.answer(message, self.strings("stopping"))

    async def on_unload(self):
        if self._job is not None:
            self._job["stop"].set()
