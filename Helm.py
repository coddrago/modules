# ---------------------------------------------------------------------------------
#░█▀▄░▄▀▀▄░█▀▄░█▀▀▄░█▀▀▄░█▀▀▀░▄▀▀▄░░░█▀▄▀█
#░█░░░█░░█░█░█░█▄▄▀░█▄▄█░█░▀▄░█░░█░░░█░▀░█
#░▀▀▀░░▀▀░░▀▀░░▀░▀▀░▀░░▀░▀▀▀▀░░▀▀░░░░▀░░▒▀
# Name: Helm
# Description: Group moderation: warns, mutes, bans, member lists.
# Author: @codrago_m
# Commands: warn, unwarn, mute, unmute, ban, unban, kick, gban, ungban, promote, fullrights, demote, settag, rights, slow, setabout, setphoto, setusername, sign, forum, antispam, hidemembers, history, joinreq, link, d
# scope: heroku_only
# scope: disable_onload_docs
# meta developer: @codrago_m
# ---------------------------------------------------------------------------------
# 🔒    Licensed under the GNU AGPLv3
# 🌐 https://www.gnu.org/licenses/agpl-3.0.html
# ---------------------------------------------------------------------------------

__version__ = (2, 7, 2)

import asyncio
import io
import logging
import time
import typing
from datetime import datetime, timedelta, timezone
from html import escape as es
from re import findall, fullmatch, sub

import humanize
from herokutl import TelegramClient, errors
from herokutl.errors import ChatAdminRequiredError, UserAdminInvalidError
from herokutl.tl import types
from herokutl.tl.functions import channels, messages
from herokutl.tl.functions.channels import EditAdminRequest, LeaveChannelRequest
from herokutl.tl.functions.messages import EditChatParticipantRankRequest
from herokutl.tl.functions.contacts import BlockRequest, UnblockRequest
from herokutl.tl.functions.messages import DeleteHistoryRequest
from herokutl.tl.patched import Message, MessageService
from herokutl.tl.types import (
    Channel,
    ChannelAdminLogEventActionParticipantToggleBan,
    ChannelAdminLogEventsFilter,
    ChannelForbidden,
    ChannelParticipantBanned,
    Chat,
    ChatForbidden,
    InputPeerChannel,
    InputPeerChat,
    InputPeerUser,
    User,
)

from .. import loader, utils

log = logging.getLogger(__name__)

QUANTIFIERS = ["*", "+", "?", "{", "}", "|", "(", ")", "[", "]", "^", "$"]

_HUMANIZE_LANGS = {
    "en_US",
    "ru_RU",
    "de_DE",
    "fr_FR",
    "it_IT",
    "tr_TR",
    "es_ES",
    "sv_SE",
}


def convert_timespan(timespan: str) -> timedelta:
    """1y, 1w, 1d, 1h, 1m. Seconds are ignored: Telegram doesn't take them."""
    result = timedelta()

    for span in timespan.lower().split():
        value = span[:-1]
        if not value:
            value = 1
        try:
            value = int(value)
        except ValueError:
            value = 0

        match span[-1:]:
            case "y":
                result += timedelta(days=value * 365)
            case "w":
                result += timedelta(weeks=value)
            case "d":
                result += timedelta(days=value)
            case "h":
                result += timedelta(hours=value)
            case "m":
                result += timedelta(minutes=value)
            case "s":
                log.warning("Telegram doesn't support seconds, skipping")
            case _:
                raise ValueError(f"Unknown unit in `{span}`")

    return result or timedelta(days=365)


def action_user_id(participant) -> int:
    peer = getattr(participant, "peer", None)
    return getattr(peer, "user_id", 0) or getattr(participant, "user_id", 0)


def humanize_timespan(timespan: timedelta, language: str = "en_US") -> str:
    language = language if language in _HUMANIZE_LANGS else "en_US"
    if language == "en_US":
        humanize.i18n.deactivate()
    else:
        humanize.i18n.activate(language)
    return humanize.precisedelta(timespan)


def seq_rights(sequence: str, inv: bool = False) -> typing.Union[dict, None]:
    """
    0 view, 1 send, 2 media, 3 stickers, 4 gifs, 5 games, 6 inline,
    7 link previews, 8 polls, 9 change info, a invite, b pin.
    """
    if not sequence:
        return None

    result = {}
    for right in sequence:
        match right:
            case "0":
                result["view_messages"] = not inv
            case "1":
                result["send_messages"] = not inv
                result["send_plain"] = not inv
                result["send_reactions"] = not inv
            case "2":
                result["send_media"] = not inv
            case "3":
                result["send_stickers"] = not inv
            case "4":
                result["send_gifs"] = not inv
            case "5":
                result["send_games"] = not inv
            case "6":
                result["send_inline"] = not inv
            case "7":
                result["embed_link_previews"] = not inv
            case "8":
                result["send_polls"] = not inv
            case "9":
                result["change_info"] = not inv
            case "a":
                result["invite_users"] = not inv
            case "b":
                result["pin_messages"] = not inv
            case _:
                raise ValueError(f"Unknown right: {right}")
    return result


_EDIT_PERMISSION_DEFAULTS = {
    "view_messages": True,
    "send_messages": True,
    "send_media": True,
    "send_stickers": True,
    "send_gifs": True,
    "send_games": True,
    "send_inline": True,
    "embed_link_previews": True,
    "send_polls": True,
    "change_info": True,
    "invite_users": True,
    "pin_messages": True,
    "send_plain": True,
    "manage_topics": True,
    "send_photos": True,
    "send_videos": True,
    "send_roundvideos": True,
    "send_audios": True,
    "send_voices": True,
    "send_docs": True,
    "edit_rank": True,
    "send_reactions": True,
}

_CHAT_BANNED_RIGHT_FIELDS = set(types.ChatBannedRights.__init__.__annotations__) | {
    "until_date",
    "view_messages",
    "send_messages",
    "send_media",
    "send_stickers",
    "send_gifs",
    "send_games",
    "send_inline",
    "embed_links",
    "send_polls",
    "change_info",
    "invite_users",
    "pin_messages",
    "manage_topics",
    "send_photos",
    "send_videos",
    "send_roundvideos",
    "send_audios",
    "send_voices",
    "send_docs",
    "send_plain",
    "edit_rank",
}


def _make_chat_banned_rights(**rights):
    return types.ChatBannedRights(
        **{key: value for key, value in rights.items() if key in _CHAT_BANNED_RIGHT_FIELDS}
    )


async def edit_permissions(client: TelegramClient, entity, user=None, until_date=None, **permissions):
    if not any(
        key in permissions
        for key in (
            "send_plain",
            "manage_topics",
            "send_photos",
            "send_videos",
            "send_roundvideos",
            "send_audios",
            "send_voices",
            "send_docs",
            "edit_rank",
            "send_reactions",
        )
    ):
        return await client.edit_permissions(entity, user, until_date, **permissions)

    permissions = {**_EDIT_PERMISSION_DEFAULTS, **permissions}
    if permissions.get("send_media") is False:
        for key in (
            "send_photos",
            "send_videos",
            "send_roundvideos",
            "send_audios",
            "send_voices",
            "send_docs",
        ):
            permissions[key] = False

    entity = await client.get_input_entity(entity)
    rights = _make_chat_banned_rights(
        until_date=until_date,
        view_messages=not permissions["view_messages"],
        send_messages=not permissions["send_messages"],
        send_media=not permissions["send_media"],
        send_stickers=not permissions["send_stickers"],
        send_gifs=not permissions["send_gifs"],
        send_games=not permissions["send_games"],
        send_inline=not permissions["send_inline"],
        embed_links=not permissions["embed_link_previews"],
        send_polls=not permissions["send_polls"],
        change_info=not permissions["change_info"],
        invite_users=not permissions["invite_users"],
        pin_messages=not permissions["pin_messages"],
        manage_topics=not permissions["manage_topics"],
        send_photos=not permissions["send_photos"],
        send_videos=not permissions["send_videos"],
        send_roundvideos=not permissions["send_roundvideos"],
        send_audios=not permissions["send_audios"],
        send_voices=not permissions["send_voices"],
        send_docs=not permissions["send_docs"],
        send_reactions=not permissions["send_reactions"],
        send_plain=not permissions["send_plain"],
        edit_rank=not permissions["edit_rank"],
    )

    if user is None:
        return await client(
            messages.EditChatDefaultBannedRightsRequest(peer=entity, banned_rights=rights)
        )

    user = await client.get_input_entity(user)
    return await client(
        channels.EditBannedRequest(channel=entity, participant=user, banned_rights=rights)
    )


class TimespanValidator(loader.validators.Validator):
    def __init__(self):
        super().__init__(
            self._validate,
            doc={
                "en": "a timespan like 2d 3h (y, w, d, h, m)",
                "ru": "срок вроде 2d 3h (y, w, d, h, m)",
                "ua": "термін на кшталт 2d 3h (y, w, d, h, m)",
                "de": "eine Dauer wie 2d 3h (y, w, d, h, m)",
                "ja": "2d 3h のような期間 (y, w, d, h, m)",
            },
        )

    @staticmethod
    def _validate(value: str) -> typing.Union[str, None]:
        try:
            convert_timespan(value)
        except ValueError as e:
            raise loader.validators.ValidationError(str(e)) from e
        return value


@loader.tds
class HelmMod(loader.Module):
    """Group moderation: warns, mutes, bans, member lists."""

    def __init__(self):
        self.config = loader.ModuleConfig(
            loader.ConfigValue(
                "warnlimit",
                3,
                lambda: self.strings["cfg.warnlimit"],
                validator=loader.validators.Integer(minimum=1, maximum=10),
            ),
            loader.ConfigValue(
                "default_ptime",
                "y",
                lambda: self.strings["cfg.ptime"],
                validator=TimespanValidator(),
            ),
            loader.ConfigValue(
                "wl_punishment",
                "mute",
                lambda: self.strings["cfg.wl_punishment"],
                validator=loader.validators.Choice(["mute", "ban"]),
            ),
            loader.ConfigValue(
                "wl_reason",
                "Warn limit exceeded",
                lambda: self.strings["cfg.wl_reason"],
                validator=loader.validators.String(),
            ),
            loader.ConfigValue(
                "wl_timespan",
                "7d",
                lambda: self.strings["cfg.wl_timespan"],
                validator=TimespanValidator(),
            ),
            loader.ConfigValue(
                "gban_except",
                [1846422780, 2685666919, 2375266505],
                lambda: self.strings["cfg.gban_except"],
                validator=loader.validators.Series(validator=loader.validators.Integer()),
            ),
            loader.ConfigValue(
                "gban_pm_block",
                True,
                lambda: self.strings["cfg.gban_pm_block"],
                validator=loader.validators.Boolean(),
            ),
            loader.ConfigValue(
                "gban_pm_del_history",
                False,
                lambda: self.strings["cfg.gban_pm_del_history"],
                validator=loader.validators.Boolean(),
            ),
            loader.ConfigValue(
                "gban_pm_except",
                [],
                lambda: self.strings["cfg.gban_pm_except"],
                validator=loader.validators.Series(validator=loader.validators.Integer()),
            ),
            loader.ConfigValue(
                "global_logs",
                True,
                lambda: self.strings["cfg.global_logs"],
                validator=loader.validators.Boolean(),
            ),
        )
        self._gban_cache = {}
        self._temp_tasks = {}

    async def client_ready(self):
        if not self.get("warns", None):
            self.set("warns", {})
        if not self.get("chat_properties", None):
            self.set("chat_properties", {})

        await self._resume_temp_chats()

        self.client: TelegramClient = self.client
        self.xdlib = await self.import_lib(
            "https://raw.githubusercontent.com/coddrago/modules/refs/heads/main/libs/xdlib.py",
            suspend_on_error=True,
        )

        self.asset_channel = self._db.get("heroku.forums", "channel_id", 0)
        self._log_topic = await utils.asset_forum_topic(
            self.client,
            self._db,
            self.asset_channel,
            "Helm",
            description="Moderation log.",
            icon_emoji_id=5409025823388741707,
            invite_bot=True,
        )
        self._me_id = (await self.client.get_me()).id
        self._admin_chats = []
        self.modlog.start()

    def _span(self, timespan: timedelta) -> str:
        if timespan >= timedelta(days=365):
            return self.strings["sys.forever"]
        return humanize_timespan(timespan, self.strings["sys.LANG"])


    strings = {
        'name': 'Helm',
        'cfg.warnlimit': 'Warns before a user is restricted',
        'cfg.ptime': 'Default punishment length',
        'cfg.wl_punishment': 'What happens when the warn limit is hit',
        'cfg.wl_reason': 'Reason used for the warn-limit punishment',
        'cfg.wl_timespan': 'How long the warn-limit punishment lasts',
        'error.wrongchattype.pm': '<tg-emoji emoji-id="5870563425628721113">📧</tg-emoji> <b>This only works in groups.</b>',
        'error.wrongchattype.channel': '<tg-emoji emoji-id="5870693687691841267">📣</tg-emoji> <b>This only works in groups, not channels.</b>',
        'error.no_args.user': '<tg-emoji emoji-id="5870994129244131212">👤</tg-emoji> <b>Specify a user.</b>\nReply, or pass a username or ID.',
        'error.locate_user': '<tg-emoji emoji-id="5870974879200711167">🔎</tg-emoji> <b>User not found.</b>\nCheck the username or ID.',
        'error.can_not_restrict': '<tg-emoji emoji-id="5870704313440932932">🔓</tg-emoji> <b>Couldn\'t restrict them.</b>\nYou may lack the rights, or they were promoted by someone else.',
        'error.reply_is_service': '<tg-emoji emoji-id="5870982283724328568">⚙️</tg-emoji> <b>That\'s a service message.</b>\nReply to a normal message.',
        'error.self': '<tg-emoji emoji-id="5872988737826197458">🔫</tg-emoji> <b>You can\'t restrict yourself.</b>',
        'error.warn_self': '<tg-emoji emoji-id="5870948572526022116">☝🏻</tg-emoji> <b>You can\'t warn yourself.</b>',
        'error.no_args.rights': '<tg-emoji emoji-id="5872996816659681395">❓</tg-emoji> <b>Specify the rights.</b>\nA sequence like <code>123456789ab</code>. Put <code>r</code> in front to take those rights away.',
        'error.no_user': '<tg-emoji emoji-id="5870994129244131212">👤</tg-emoji> <b>Specify a user.</b>\nReply, or pass a username or ID.',
        'error.no_reply': '<tg-emoji emoji-id="5872886929921413168">💬</tg-emoji> <b>Reply to a message.</b>',
        'error.invalid_args': '<tg-emoji emoji-id="5872996816659681395">❓</tg-emoji> <b>Usage:</b> <code>g</code> or <code>c</code>, then a title. A trailing <code>30m</code>, <code>2h</code> or <code>1d</code> deletes it later.',
        'error.too_much': '<tg-emoji emoji-id="5870657884844462243">❌</tg-emoji> <b>Bad count.</b>\nUse a number from 1 to 100.',
        'error.insufficient_rights': '<tg-emoji emoji-id="5870704313440932932">🔓</tg-emoji> <b>Not enough rights.</b>',
        'error.unknown': '<tg-emoji emoji-id="5870657884844462243">🙅🏻\u200d♂️</tg-emoji> <b>Unknown error.</b>',
        'error': '<b>Error:</b> <code>{error}</code>',
        'done.muted.f': '<tg-emoji emoji-id="5870681133502435302">🔇</tg-emoji> <b>{user} is muted forever</b>',
        'done.muted': '<tg-emoji emoji-id="5870681133502435302">🔇</tg-emoji> <b>{user} is muted for {timespan}</b>',
        'done.warned': '<tg-emoji emoji-id="5870931487146119264">⚠️</tg-emoji> <b>{user} has been warned</b>',
        'done.banned.f': '<tg-emoji emoji-id="5872988737826197458">⛔</tg-emoji> <b>{user} is banned forever</b>',
        'done.banned': '<tg-emoji emoji-id="5872988737826197458">⛔</tg-emoji> <b>{user} is banned for {timespan}</b>',
        'done.kicked': '<tg-emoji emoji-id="5870778972857438051">🍃</tg-emoji> <b>{user} has been kicked</b>',
        'done.nomedia': '<tg-emoji emoji-id="5870782662234346251">🖼️</tg-emoji> <b>{user} can\'t send media for {timespan}</b>',
        'done.nomedia.f': '<tg-emoji emoji-id="5870782662234346251">🖼️</tg-emoji> <b>{user} can\'t send media anymore</b>',
        'done.allowmedia': '<tg-emoji emoji-id="5870782662234346251">🖼️</tg-emoji> <b>{user} can send media again</b>',
        'done.setrights.f': '<tg-emoji emoji-id="5870982283724328568">🔧</tg-emoji> <b>Rights for <code>{user}</code> set to {rights}</b>',
        'done.setrights': '<tg-emoji emoji-id="5870982283724328568">🔧</tg-emoji> <b>Rights for <code>{user}</code> set to {rights}</b> for {timespan}',
        'done.unmuted': '<tg-emoji emoji-id="5870693687691841267">🔊</tg-emoji> <b>{user} can write again</b>',
        'done.unbanned': '<tg-emoji emoji-id="5870948572526022116">👋🏻</tg-emoji> <b>{user} is unbanned</b>',
        'done.unwarned.one': '<tg-emoji emoji-id="5870930636742595124">⚖️</tg-emoji> <b>One warn taken off {user}</b>',
        'done.unwarned.all': '<tg-emoji emoji-id="5870930636742595124">⚖️</tg-emoji> <b>All warns taken off <code>{user}</code></b>',
        'done.da_kicked': '<tg-emoji emoji-id="5870778972857438051">🍃</tg-emoji> <b>Kicked <code>{amount}</code> deleted accounts</b>',
        'done.pin': '<tg-emoji emoji-id="5870930744116776638">📌</tg-emoji> <b>Pinned.</b>',
        'done.unpin': '<tg-emoji emoji-id="5870930744116776638">📌</tg-emoji> <b>Unpinned.</b>',
        'done.channel_ban.on': '<tg-emoji emoji-id="5870704313440932932">🔒</tg-emoji> <b>Messages sent as a channel will be banned.</b>',
        'done.channel_ban.off': '<tg-emoji emoji-id="5870704313440932932">🔓</tg-emoji> <b>Messages sent as a channel are allowed again.</b>',
        'done.channel_ban.action': '<tg-emoji emoji-id="5872988737826197458">⛔</tg-emoji> <b>{user} is banned forever</b>\n<b>Reason:</b> posting as a channel',
        'done.flushda': '<tg-emoji emoji-id="5870778972857438051">🍃</tg-emoji> <b>Removed <code>{amt}</code> deleted accounts</b>',
        'done.glban.f': '<tg-emoji emoji-id="5870718740236079262">🌍</tg-emoji> <b>{user} is banned in {count} chats forever</b>',
        'done.glban': '<tg-emoji emoji-id="5870718740236079262">🌍</tg-emoji> <b>{user} is banned in {count} chats for {timespan}</b>',
        'done.glunban': '<tg-emoji emoji-id="5870718740236079262">🌍</tg-emoji> <b>{user} is unbanned in {count} chats</b>',
        'done.leave': '<tg-emoji emoji-id="5870764288364252592">😶</tg-emoji> <b>Leaving.</b>',
        'done.leave.reason': '<tg-emoji emoji-id="5870764288364252592">😶</tg-emoji> <b>Leaving.</b>\n<b>Reason:</b> <i>{reason}</i>',
        'reason': '\n<b>Reason:</b> <i>{0}</i>',
        'chat_id': '<tg-emoji emoji-id="5870772616305839506">👥</tg-emoji> <b>Chat ID:</b> <code>{chat_id}</code>{additional}\n<tg-emoji emoji-id="5870994129244131212">👤</tg-emoji> <b>Your ID:</b> <code>{my_id}</code>',
        'person_in_reply_id': '<tg-emoji emoji-id="5870772616305839506">🫂</tg-emoji> <b>Reply ID:</b> <code>{reply_id}</code>',
        'sys.DA': 'Deleted account',
        'sys.LANG': 'en_US',
        'sys.forever': 'forever',
        'of_chat': 'group',
        'of_channel': 'channel',
        'loading': '<tg-emoji emoji-id="5870813306826002498">🟡</tg-emoji> <b>Loading…</b>',
        'own_list': '<b>Chats you run ({count}):</b>\n\n{msg}',
        'no_ownerships': '<tg-emoji emoji-id="5870657884844462243">❌</tg-emoji> <b>You don\'t run any chats.</b>',
        'not_a_chat': '<tg-emoji emoji-id="5870931487146119264">⚠️</tg-emoji> <b>Groups only.</b>',
        'admins_in_chat': '<tg-emoji emoji-id="5870684638195748414">👑</tg-emoji> <b>Admins in <code>{title}</code> ({count}):</b>\n\n',
        'admins_in_chat_caption': '<b>Admins in {}:</b>',
        'too_many_admins': 'Too many admins. Sending the list as a file…',
        'no_admins_in_chat': '<b>No admins here.</b>',
        'bots_in_chat': '<tg-emoji emoji-id="5870531058755178453">🤖</tg-emoji> <b>Bots in <code>{title}</code> ({count}):</b>\n\n',
        'bots_in_chat_caption': '<b>Bots in <code>{}</code>:</b>',
        'too_many_bots': 'Too many bots. Sending the list as a file…',
        'no_bots_in_chat': '<b>No bots here.</b>',
        'users_in_chat': '<tg-emoji emoji-id="5870994129244131212">👤</tg-emoji> <b>Members in <code>{title}</code> ({count}):</b>\n\n',
        'users_in_chat_caption': '<b>Members in <code>{}</code>:</b>',
        'no_user_in_chat': '<b>No members here.</b>',
        'too_many_users': 'Too many members. Sending the list as a file…',
        'chat_muted': '<tg-emoji emoji-id="5870681133502435302">🔇</tg-emoji> <b>Members can no longer write.</b>',
        'chat_unmuted': '<tg-emoji emoji-id="5870633910337015697">✅</tg-emoji> <b>Members can write again.</b>',
        'title_changed': '<b>{type_of} renamed from <code>{old_title}</code> to <code>{new_title}</code>.</b>',
        'user_invited': '<tg-emoji emoji-id="5870633910337015697">✅</tg-emoji> <b><a href=\'tg://user?id={id}\'>{user}</a> invited.</b>',
        'creator': '<tg-emoji emoji-id="5870684638195748414">👑</tg-emoji> <b>Owner: <a href=\'tg://user?id={id}\'>{creator}</a>.</b>',
        'no_creator': '<tg-emoji emoji-id="5870657884844462243">❌</tg-emoji> <b>No owner found.</b>',
        'channel_created': '<tg-emoji emoji-id="5870633910337015697">✅</tg-emoji> <b>Channel <code>{title}</code> created.</b>\n<tg-emoji emoji-id="5870527201874546272">🔗</tg-emoji> <b>Invite: {link}</b>',
        'group_created': '<tg-emoji emoji-id="5870633910337015697">✅</tg-emoji> <b>Group <code>{title}</code> created.</b>\n<tg-emoji emoji-id="5870527201874546272">🔗</tg-emoji> <b>Invite: {link}</b>',
        'temp_chat': '\n<tg-emoji emoji-id="5870875489362513438">🗑</tg-emoji> <b>Deletes itself in {timespan}.</b>',
        'type_group': 'Group',
        'type_channel': 'Channel',
        'type_unknown': 'Unknown',
        'yes': '<tg-emoji emoji-id="5870633910337015697">✅</tg-emoji> Yes',
        'no': '<tg-emoji emoji-id="5870657884844462243">✖️</tg-emoji> No',
        'all_approved': '<tg-emoji emoji-id="5870633910337015697">✅</tg-emoji> <b>Requests approved</b>',
        'all_dismissed': '<tg-emoji emoji-id="5870657884844462243">✖️</tg-emoji> <b>Requests declined</b>',
        'log_text': '<tg-emoji emoji-id="5870994129244131212">👤</tg-emoji> <b>User:</b> {user}\n<tg-emoji emoji-id="5870704313440932932">🔒</tg-emoji> <b>Admin:</b> {admin}\n<tg-emoji emoji-id="5872988737826197458">⛔️</tg-emoji> <b>Action:</b> {punishment}{reason}{time}{chat}',
        'log_chat': '\n<tg-emoji emoji-id="5872886929921413168">💬</tg-emoji> <b>Chat:</b> {chat}',
        'log_reason': '\n<tg-emoji emoji-id="5870676941614354370">🖋</tg-emoji> <b>Reason:</b> {reason}',
        'log_time': '\n<tg-emoji emoji-id="5870729937215819584">⏰️</tg-emoji> <b>Time:</b> {time}',
        'act.mute': 'Mute',
        'act.ban': 'Ban',
        'act.kick': 'Kick',
        'act.unmute': 'Unmute',
        'act.unban': 'Unban',
        'act.warn': 'Warn',
        'act.nomedia': 'Media restricted',
        'act.allowmedia': 'Media allowed',
        'act.rights': 'Rights changed',
        'flushda.loading': '<tg-emoji emoji-id="5870813306826002498">🟡</tg-emoji> <b>Removing deleted accounts…</b>',
        'flushda.loading.chat': '<tg-emoji emoji-id="5870813306826002498">🟡</tg-emoji> <b>Removing deleted accounts from this chat…</b>',
        'flushda.loading.channels': '<tg-emoji emoji-id="5870813306826002498">🟡</tg-emoji> <b>Removing deleted accounts from channels…</b>',
        'monday': 'Monday',
        'tuesday': 'Tuesday',
        'wednesday': 'Wednesday',
        'thursday': 'Thursday',
        'friday': 'Friday',
        'saturday': 'Saturday',
        'sunday': 'Sunday',
        'cfg.gban_except': 'Chat IDs left out of .gban and .ungban',
        'cfg.gban_pm_block': 'Block the user in PM on .gban, and unblock on .ungban',
        'cfg.gban_pm_del_history': 'Also delete the PM history when blocking',
        'cfg.gban_pm_except': 'User IDs that are never blocked in PM',
        'cfg.global_logs': 'Log restrictions from every admin chat, not only your own commands',
        'gban.no_reason': 'Not specified',
        'gban.args': '<tg-emoji emoji-id="5870994129244131212">👤</tg-emoji> <b>Specify a user.</b>\nReply, or pass a username or ID.',
        'gban.working': '<tg-emoji emoji-id="5870718740236079262">🌍</tg-emoji> <b>Banning <a href="{url}">{name}</a> everywhere…</b>',
        'gban.unworking': '<tg-emoji emoji-id="5870718740236079262">🌍</tg-emoji> <b>Unbanning <a href="{url}">{name}</a> everywhere…</b>',
        'gban.done': '<tg-emoji emoji-id="5872988737826197458">⛔</tg-emoji> <b><a href="{url}">{name}</a> is banned in {count} chats</b>\n<b>Reason:</b> <i>{reason}</i>',
        'gban.undone': '<tg-emoji emoji-id="5870948572526022116">👋🏻</tg-emoji> <b><a href="{url}">{name}</a> is unbanned in {count} chats</b>',
        'gban.chats': '\n{chats}',
        'gban.pm_blocked': '\n<tg-emoji emoji-id="5872988737826197458">🚫</tg-emoji> <b>Blocked in PM</b>',
        'gban.pm_unblocked': '\n<tg-emoji emoji-id="5870948572526022116">👋🏻</tg-emoji> <b>Unblocked in PM</b>',
        'gban.pm_failed': '\n<tg-emoji emoji-id="5870704313440932932">🔓</tg-emoji> <b>Couldn\'t block in PM</b>',
        'gban.pm_cleared': ' · <b>PM history deleted</b>',
        'chatinfo': '<tg-emoji emoji-id="5870704313440932932">🔒</tg-emoji><b> Type: {type_of}\n</b><tg-emoji emoji-id="5870495350397079101">#️⃣</tg-emoji><b> Chat ID: </b><code>{id}</code><b>\n</b><tg-emoji emoji-id="5873225338984599714">🔥</tg-emoji><b> Title: {title}\n\n</b><tg-emoji emoji-id="5870676941614354370">🖋</tg-emoji><b> About: {about}\n\n</b><tg-emoji emoji-id="5870684638195748414">👑</tg-emoji><b> Admins: {admins_count}\n</b><tg-emoji emoji-id="5870633910337015697">✅</tg-emoji><b> Online: {online_count}\n</b><tg-emoji emoji-id="5870994129244131212">👤</tg-emoji><b> Members: {participants_count}\n</b><tg-emoji emoji-id="5872988737826197458">🚫</tg-emoji><b> Kicked: {kicked_count}\n</b><tg-emoji emoji-id="5870892901159932239">🔀</tg-emoji><b> Pending requests: {requests_pending}\n\n</b><tg-emoji emoji-id="5870729937215819584">🕐</tg-emoji><b> Slow mode: {slowmode_seconds}\n</b><tg-emoji emoji-id="5872980989705196227">📞</tg-emoji><b> Call: {call}\n</b><tg-emoji emoji-id="5870875489362513438">🗑</tg-emoji><b> TTL: {ttl_period}\n</b><tg-emoji emoji-id="5870994129244131212">👤</tg-emoji><b> Recent requesters: {recent_requesters}\n\n</b><tg-emoji emoji-id="5870772616305839506">👥</tg-emoji><b> Linked chat: {linked_chat_id}\n</b><tg-emoji emoji-id="5870704313440932932">🛡</tg-emoji><b> Antispam: {antispam}\n</b><tg-emoji emoji-id="5870542612217204751">👁</tg-emoji><b> Members hidden: {participants_hidden}\n\n</b><tg-emoji emoji-id="5870527201874546272">🔗</tg-emoji><b> Link: {link}</b>',
        'userinfo': '<blockquote><tg-emoji emoji-id="5870495350397079101">#️⃣</tg-emoji><b> ID: {user_id}\n</b><tg-emoji emoji-id="5873225338984599714">🔥</tg-emoji><b> First name: {first_name}\n</b><tg-emoji emoji-id="5873225338984599714">🔥</tg-emoji><b> Last name: {last_name}\n</b><tg-emoji emoji-id="5872980989705196227">📞</tg-emoji><b> Phone: {phone}\n</b><tg-emoji emoji-id="5870998024779468554">🐶</tg-emoji><b> Usernames: {usernames}</b></blockquote><b>\n</b><blockquote><tg-emoji emoji-id="5870609858520158157">ℹ️</tg-emoji><b> About: {about}</b></blockquote><b>\n</b><blockquote><tg-emoji emoji-id="5870729937215819584">🕐</tg-emoji><b> Hours: </b>{business_work_hours}\n<tg-emoji emoji-id="5870450871715761518">❤️</tg-emoji><b> Emoji status: {emoji_status}</b></blockquote><b>\n</b><blockquote><tg-emoji emoji-id="5870693687691841267">🔉</tg-emoji><b> Channel: {personal_channel}\n</b><tg-emoji emoji-id="5870847962917113498">🎂</tg-emoji><b> Birthday: {birthday}\n</b><tg-emoji emoji-id="5870478797593120516">🎁</tg-emoji><b> Gifts: {stargifts_count}</b></blockquote><b>\n</b><blockquote><tg-emoji emoji-id="5870931487146119264">🚨</tg-emoji><b> Chats in common: {common_chats_count}\n</b><tg-emoji emoji-id="5870772616305839506">👥</tg-emoji><b> Common chats: {common_chats}</b></blockquote>',
        'promote.no_rights': '<tg-emoji emoji-id="5870704313440932932">🔓</tg-emoji> <b>Not enough rights to change admins.</b>',
        'promote.no_user': '<tg-emoji emoji-id="5870994129244131212">👤</tg-emoji> <b>Specify a user.</b>\nReply, or pass a username or ID.',
        'promote.demoted': '<tg-emoji emoji-id="5870948572526022116">👋🏻</tg-emoji> <b>{name}</b> [<code>{user_id}</code>] <b>is no longer an admin.</b>',
        'promote.promoted_full': '<tg-emoji emoji-id="5870684638195748414">👑</tg-emoji> <b>{name}</b> [<code>{user_id}</code>] <b>is an admin with full rights.</b>\n<b>Rank:</b> {rank}',
        'promote.promoted': '<tg-emoji emoji-id="5870684638195748414">👑</tg-emoji> <b>{name}</b> [<code>{user_id}</code>] <b>is an admin.</b>\n<b>Rank:</b> {rank}',
        'promote.choose': '<tg-emoji emoji-id="5870684638195748414">👑</tg-emoji> <b>Admin rights for {name}</b> [<code>{user_id}</code>]\n<b>Rank:</b> {rank}',
        'promote.confirm': 'Confirm',
        'promote.default_rank': 'Admin',
        'promote.tag_group_only': '<tg-emoji emoji-id="5870931487146119264">⚠️</tg-emoji> <b>Member tags only work in groups.</b>',
        'promote.tag_usage': '<b>Usage:</b> <code>{prefix}settag @user tag</code> or reply with <code>{prefix}settag tag</code>. No tag or <code>-</code> removes it.',
        'promote.tag_invalid': '<tg-emoji emoji-id="5870657884844462243">❌</tg-emoji> <b>A member tag is at most 16 characters, with no emoji.</b>',
        'promote.tag_no_rights': '<tg-emoji emoji-id="5870704313440932932">🔓</tg-emoji> <b>You need Manage member tags to change someone else\'s tag.</b>',
        'promote.tag_updated': '<tg-emoji emoji-id="5870676941614354370">🖋</tg-emoji> <b>Member tag for {name}:</b> <code>{rank}</code>',
        'promote.tag_removed': '<tg-emoji emoji-id="5255831443816327915">🗑</tg-emoji> <b>Member tag removed for {name}.</b>',
        'promote.rpc_error': '<tg-emoji emoji-id="5870657884844462243">❌</tg-emoji> <b>Telegram error:</b> <code>{error}</code>',
        'promote.right.change_info': '{emoji} Change {where} info',
        'promote.right.post_messages': '{emoji} Post messages',
        'promote.right.edit_messages': '{emoji} Edit posts',
        'promote.right.delete_messages': '{emoji} Delete messages',
        'promote.right.ban_users': '{emoji} Restrict users',
        'promote.right.invite_users': '{emoji} Invite users',
        'promote.right.pin_messages': '{emoji} Pin messages',
        'promote.right.add_admins': '{emoji} Add admins',
        'promote.right.anonymous': '{emoji} Anonymous',
        'promote.right.manage_call': '{emoji} Manage calls',
        'promote.right.manage_topics': '{emoji} Manage topics',
        'promote.right.post_stories': '{emoji} Post stories',
        'promote.right.edit_stories': '{emoji} Edit stories',
        'promote.right.delete_stories': '{emoji} Delete stories',
        'promote.right.manage_direct_messages': '{emoji} Manage direct messages',
        'promote.right.manage_ranks': '{emoji} Manage member tags',
        'promote.right.manage_linked_peers': '{emoji} Manage linked chats',
        'promote.right.manage_welcome_messages': '{emoji} Manage welcome messages',
        'promote.right.other': '{emoji} Other rights',
        'chat.not_channel': '<tg-emoji emoji-id="5870693687691841267">📣</tg-emoji> <b>This only works in supergroups and channels.</b>',
        'chat.no_rights': '<tg-emoji emoji-id="5870704313440932932">🔓</tg-emoji> <b>Not enough rights to change this chat.</b>',
        'chat.usage.slow': '<b>Usage:</b> <code>{prefix}slow</code> off, or <code>30</code>, <code>1m</code>, <code>5m</code>, <code>1h</code>.',
        'chat.usage.about': '<b>Usage:</b> <code>{prefix}setabout text</code>. <code>-</code> clears it.',
        'chat.usage.photo': '<b>Usage:</b> reply to a photo with <code>{prefix}setphoto</code>. <code>-</code> removes it.',
        'chat.usage.username': '<b>Usage:</b> <code>{prefix}setusername name</code>. <code>-</code> removes it.',
        'chat.usage.link': '<b>Usage:</b> <code>{prefix}link</code>, <code>new</code>, <code>revoke</code>, or <code>title</code>.',
        'chat.slow_off': '<tg-emoji emoji-id="5870729937215819584">🕐</tg-emoji> <b>Slow mode is off.</b>',
        'chat.slow_on': '<tg-emoji emoji-id="5870729937215819584">🕐</tg-emoji> <b>Slow mode:</b> <code>{seconds}</code>s',
        'chat.about_set': '<tg-emoji emoji-id="5870676941614354370">🖋</tg-emoji> <b>Description updated.</b>',
        'chat.about_cleared': '<tg-emoji emoji-id="5255831443816327915">🗑</tg-emoji> <b>Description cleared.</b>',
        'chat.photo_set': '<tg-emoji emoji-id="5870782662234346251">🖼️</tg-emoji> <b>Chat photo updated.</b>',
        'chat.photo_cleared': '<tg-emoji emoji-id="5255831443816327915">🗑</tg-emoji> <b>Chat photo removed.</b>',
        'chat.username_set': '<tg-emoji emoji-id="5870527201874546272">🔗</tg-emoji> <b>Username:</b> @{username}',
        'chat.username_cleared': '<tg-emoji emoji-id="5255831443816327915">🗑</tg-emoji> <b>Username removed.</b>',
        'chat.sign_on': '<tg-emoji emoji-id="5870676941614354370">🖋</tg-emoji> <b>Author signatures are on.</b>',
        'chat.sign_off': '<tg-emoji emoji-id="5870676941614354370">🖋</tg-emoji> <b>Author signatures are off.</b>',
        'chat.forum_on': '<tg-emoji emoji-id="5872886929921413168">💬</tg-emoji> <b>Topics are on.</b>',
        'chat.forum_off': '<tg-emoji emoji-id="5872886929921413168">💬</tg-emoji> <b>Topics are off.</b>',
        'chat.spam_on': '<tg-emoji emoji-id="5870704313440932932">🛡</tg-emoji> <b>Aggressive antispam is on.</b>',
        'chat.spam_off': '<tg-emoji emoji-id="5870704313440932932">🛡</tg-emoji> <b>Aggressive antispam is off.</b>',
        'chat.hidden_on': '<tg-emoji emoji-id="5870542612217204751">👁</tg-emoji> <b>The member list is hidden.</b>',
        'chat.hidden_off': '<tg-emoji emoji-id="5870542612217204751">👁</tg-emoji> <b>The member list is visible.</b>',
        'chat.history_on': '<tg-emoji emoji-id="5870729937215819584">🕐</tg-emoji> <b>New members can see the history.</b>',
        'chat.history_off': '<tg-emoji emoji-id="5870729937215819584">🕐</tg-emoji> <b>History is hidden from new members.</b>',
        'chat.join_on': '<tg-emoji emoji-id="5870892901159932239">🔀</tg-emoji> <b>Join requests are on.</b>',
        'chat.join_off': '<tg-emoji emoji-id="5870892901159932239">🔀</tg-emoji> <b>Join requests are off.</b>',
        'chat.link_none': '<tg-emoji emoji-id="5870527201874546272">🔗</tg-emoji> <b>No invite link yet.</b>',
        'chat.link': '<tg-emoji emoji-id="5870527201874546272">🔗</tg-emoji> <b>Invite:</b> {link}',
        'chat.link_revoked': '<tg-emoji emoji-id="5255831443816327915">🗑</tg-emoji> <b>Invite revoked.</b>\n<tg-emoji emoji-id="5870527201874546272">🔗</tg-emoji> <b>New:</b> {link}',
        'chat.link_created': '<tg-emoji emoji-id="5870633910337015697">✅</tg-emoji> <b>Invite created.</b>\n<tg-emoji emoji-id="5870527201874546272">🔗</tg-emoji> {link}',
        'rights.header': '<tg-emoji emoji-id="5870684638195748414">👑</tg-emoji> <b>{name}</b> [<code>{user_id}</code>]\n<b>Role:</b> {role}\n<b>Rank:</b> {rank}',
        'rights.owner': 'Owner',
        'rights.admin': 'Admin',
        'rights.member': 'Member',
        'rights.none': '<tg-emoji emoji-id="5870657884844462243">✖️</tg-emoji> <b>{name}</b> [<code>{user_id}</code>] <b>is not an admin.</b>',
        'rights.empty': '<i>No rights.</i>',
    }

    strings_ru = {
        'name': 'Helm',
        'cfg.warnlimit': 'Сколько варнов до ограничения',
        'cfg.ptime': 'Срок наказания по умолчанию',
        'cfg.wl_punishment': 'Что делать при достижении лимита варнов',
        'cfg.wl_reason': 'Причина наказания за лимит варнов',
        'cfg.wl_timespan': 'На сколько наказывать за лимит варнов',
        'error.wrongchattype.pm': '<tg-emoji emoji-id="5870563425628721113">📧</tg-emoji> <b>Это только для групп.</b>',
        'error.wrongchattype.channel': '<tg-emoji emoji-id="5870693687691841267">📣</tg-emoji> <b>Это для групп, не для каналов.</b>',
        'error.no_args.user': '<tg-emoji emoji-id="5870994129244131212">👤</tg-emoji> <b>Укажи пользователя.</b>\nОтветом, юзернеймом или ID.',
        'error.locate_user': '<tg-emoji emoji-id="5870974879200711167">🔎</tg-emoji> <b>Пользователь не найден.</b>\nПроверь юзернейм или ID.',
        'error.can_not_restrict': '<tg-emoji emoji-id="5870704313440932932">🔓</tg-emoji> <b>Не вышло ограничить.</b>\nНе хватает прав или его повысил не ты.',
        'error.reply_is_service': '<tg-emoji emoji-id="5870982283724328568">⚙️</tg-emoji> <b>Это служебное сообщение.</b>\nОтветь на обычное.',
        'error.self': '<tg-emoji emoji-id="5872988737826197458">🔫</tg-emoji> <b>Себя ограничить нельзя.</b>',
        'error.warn_self': '<tg-emoji emoji-id="5870948572526022116">☝🏻</tg-emoji> <b>Себя варнить нельзя.</b>',
        'error.no_args.rights': '<tg-emoji emoji-id="5872996816659681395">❓</tg-emoji> <b>Укажи права.</b>\nПоследовательность вроде <code>123456789ab</code>. <code>r</code> в начале забирает эти права.',
        'error.no_user': '<tg-emoji emoji-id="5870994129244131212">👤</tg-emoji> <b>Укажи пользователя.</b>\nОтветом, юзернеймом или ID.',
        'error.no_reply': '<tg-emoji emoji-id="5872886929921413168">💬</tg-emoji> <b>Ответь на сообщение.</b>',
        'error.invalid_args': '<tg-emoji emoji-id="5872996816659681395">❓</tg-emoji> <b>Формат:</b> <code>g</code> или <code>c</code>, затем название. В конце <code>30m</code>, <code>2h</code> или <code>1d</code> — чат удалится сам.',
        'error.too_much': '<tg-emoji emoji-id="5870657884844462243">❌</tg-emoji> <b>Неверное число.</b>\nОт 1 до 100.',
        'error.insufficient_rights': '<tg-emoji emoji-id="5870704313440932932">🔓</tg-emoji> <b>Не хватает прав.</b>',
        'error.unknown': '<tg-emoji emoji-id="5870657884844462243">🙅🏻\u200d♂️</tg-emoji> <b>Неизвестная ошибка.</b>',
        'error': '<b>Ошибка:</b> <code>{error}</code>',
        'done.muted.f': '<tg-emoji emoji-id="5870681133502435302">🔇</tg-emoji> <b>{user} в муте навсегда</b>',
        'done.muted': '<tg-emoji emoji-id="5870681133502435302">🔇</tg-emoji> <b>{user} в муте на {timespan}</b>',
        'done.warned': '<tg-emoji emoji-id="5870931487146119264">⚠️</tg-emoji> <b>{user} получил варн</b>',
        'done.banned.f': '<tg-emoji emoji-id="5872988737826197458">⛔</tg-emoji> <b>{user} забанен навсегда</b>',
        'done.banned': '<tg-emoji emoji-id="5872988737826197458">⛔</tg-emoji> <b>{user} забанен на {timespan}</b>',
        'done.kicked': '<tg-emoji emoji-id="5870778972857438051">🍃</tg-emoji> <b>{user} кикнут</b>',
        'done.nomedia': '<tg-emoji emoji-id="5870782662234346251">🖼️</tg-emoji> <b>{user} не может слать медиа {timespan}</b>',
        'done.nomedia.f': '<tg-emoji emoji-id="5870782662234346251">🖼️</tg-emoji> <b>{user} больше не может слать медиа</b>',
        'done.allowmedia': '<tg-emoji emoji-id="5870782662234346251">🖼️</tg-emoji> <b>{user} снова может слать медиа</b>',
        'done.setrights.f': '<tg-emoji emoji-id="5870982283724328568">🔧</tg-emoji> <b>Права <code>{user}</code> выставлены: {rights}</b>',
        'done.setrights': '<tg-emoji emoji-id="5870982283724328568">🔧</tg-emoji> <b>Права <code>{user}</code> выставлены: {rights}</b> на {timespan}',
        'done.unmuted': '<tg-emoji emoji-id="5870693687691841267">🔊</tg-emoji> <b>{user} снова может писать</b>',
        'done.unbanned': '<tg-emoji emoji-id="5870948572526022116">👋🏻</tg-emoji> <b>{user} разбанен</b>',
        'done.unwarned.one': '<tg-emoji emoji-id="5870930636742595124">⚖️</tg-emoji> <b>С {user} снят один варн</b>',
        'done.unwarned.all': '<tg-emoji emoji-id="5870930636742595124">⚖️</tg-emoji> <b>С <code>{user}</code> сняты все варны</b>',
        'done.da_kicked': '<tg-emoji emoji-id="5870778972857438051">🍃</tg-emoji> <b>Кикнуто удалённых аккаунтов: <code>{amount}</code></b>',
        'done.pin': '<tg-emoji emoji-id="5870930744116776638">📌</tg-emoji> <b>Закреплено.</b>',
        'done.unpin': '<tg-emoji emoji-id="5870930744116776638">📌</tg-emoji> <b>Откреплено.</b>',
        'done.channel_ban.on': '<tg-emoji emoji-id="5870704313440932932">🔒</tg-emoji> <b>Сообщения от имени канала будут баниться.</b>',
        'done.channel_ban.off': '<tg-emoji emoji-id="5870704313440932932">🔓</tg-emoji> <b>Сообщения от имени канала снова разрешены.</b>',
        'done.channel_ban.action': '<tg-emoji emoji-id="5872988737826197458">⛔</tg-emoji> <b>{user} забанен навсегда</b>\n<b>Причина:</b> писал от имени канала',
        'done.flushda': '<tg-emoji emoji-id="5870778972857438051">🍃</tg-emoji> <b>Убрано удалённых аккаунтов: <code>{amt}</code></b>',
        'done.glban.f': '<tg-emoji emoji-id="5870718740236079262">🌍</tg-emoji> <b>{user} забанен в {count} чатах навсегда</b>',
        'done.glban': '<tg-emoji emoji-id="5870718740236079262">🌍</tg-emoji> <b>{user} забанен в {count} чатах на {timespan}</b>',
        'done.glunban': '<tg-emoji emoji-id="5870718740236079262">🌍</tg-emoji> <b>{user} разбанен в {count} чатах</b>',
        'done.leave': '<tg-emoji emoji-id="5870764288364252592">😶</tg-emoji> <b>Выхожу.</b>',
        'done.leave.reason': '<tg-emoji emoji-id="5870764288364252592">😶</tg-emoji> <b>Выхожу.</b>\n<b>Причина:</b> <i>{reason}</i>',
        'reason': '\n<b>Причина:</b> <i>{0}</i>',
        'chat_id': '<tg-emoji emoji-id="5870772616305839506">👥</tg-emoji> <b>ID чата:</b> <code>{chat_id}</code>{additional}\n<tg-emoji emoji-id="5870994129244131212">👤</tg-emoji> <b>Твой ID:</b> <code>{my_id}</code>',
        'person_in_reply_id': '<tg-emoji emoji-id="5870772616305839506">🫂</tg-emoji> <b>ID в ответе:</b> <code>{reply_id}</code>',
        'sys.DA': 'Удалённый аккаунт',
        'sys.LANG': 'ru_RU',
        'sys.forever': 'навсегда',
        'of_chat': 'группы',
        'of_channel': 'канала',
        'loading': '<tg-emoji emoji-id="5870813306826002498">🟡</tg-emoji> <b>Гружу…</b>',
        'own_list': '<b>Чаты, где ты админ ({count}):</b>\n\n{msg}',
        'no_ownerships': '<tg-emoji emoji-id="5870657884844462243">❌</tg-emoji> <b>Таких чатов нет.</b>',
        'not_a_chat': '<tg-emoji emoji-id="5870931487146119264">⚠️</tg-emoji> <b>Только в группах.</b>',
        'admins_in_chat': '<tg-emoji emoji-id="5870684638195748414">👑</tg-emoji> <b>Админы в <code>{title}</code> ({count}):</b>\n\n',
        'admins_in_chat_caption': '<b>Админы в {}:</b>',
        'too_many_admins': 'Админов слишком много. Шлю списком в файле…',
        'no_admins_in_chat': '<b>Админов нет.</b>',
        'bots_in_chat': '<tg-emoji emoji-id="5870531058755178453">🤖</tg-emoji> <b>Боты в <code>{title}</code> ({count}):</b>\n\n',
        'bots_in_chat_caption': '<b>Боты в <code>{}</code>:</b>',
        'too_many_bots': 'Ботов слишком много. Шлю списком в файле…',
        'no_bots_in_chat': '<b>Ботов нет.</b>',
        'users_in_chat': '<tg-emoji emoji-id="5870994129244131212">👤</tg-emoji> <b>Участники в <code>{title}</code> ({count}):</b>\n\n',
        'users_in_chat_caption': '<b>Участники в <code>{}</code>:</b>',
        'no_user_in_chat': '<b>Участников нет.</b>',
        'too_many_users': 'Участников слишком много. Шлю списком в файле…',
        'chat_muted': '<tg-emoji emoji-id="5870681133502435302">🔇</tg-emoji> <b>Участники больше не могут писать.</b>',
        'chat_unmuted': '<tg-emoji emoji-id="5870633910337015697">✅</tg-emoji> <b>Участники снова могут писать.</b>',
        'title_changed': '<b>Название {type_of} сменено с <code>{old_title}</code> на <code>{new_title}</code>.</b>',
        'user_invited': '<tg-emoji emoji-id="5870633910337015697">✅</tg-emoji> <b><a href=\'tg://user?id={id}\'>{user}</a> приглашён.</b>',
        'creator': '<tg-emoji emoji-id="5870684638195748414">👑</tg-emoji> <b>Владелец: <a href=\'tg://user?id={id}\'>{creator}</a>.</b>',
        'no_creator': '<tg-emoji emoji-id="5870657884844462243">❌</tg-emoji> <b>Владелец не найден.</b>',
        'channel_created': '<tg-emoji emoji-id="5870633910337015697">✅</tg-emoji> <b>Канал <code>{title}</code> создан.</b>\n<tg-emoji emoji-id="5870527201874546272">🔗</tg-emoji> <b>Ссылка: {link}</b>',
        'group_created': '<tg-emoji emoji-id="5870633910337015697">✅</tg-emoji> <b>Группа <code>{title}</code> создана.</b>\n<tg-emoji emoji-id="5870527201874546272">🔗</tg-emoji> <b>Ссылка: {link}</b>',
        'temp_chat': '\n<tg-emoji emoji-id="5870875489362513438">🗑</tg-emoji> <b>Удалится сам через {timespan}.</b>',
        'type_group': 'Группа',
        'type_channel': 'Канал',
        'type_unknown': 'Неизвестно',
        'yes': '<tg-emoji emoji-id="5870633910337015697">✅</tg-emoji> Да',
        'no': '<tg-emoji emoji-id="5870657884844462243">✖️</tg-emoji> Нет',
        'all_approved': '<tg-emoji emoji-id="5870633910337015697">✅</tg-emoji> <b>Заявки приняты</b>',
        'all_dismissed': '<tg-emoji emoji-id="5870657884844462243">✖️</tg-emoji> <b>Заявки отклонены</b>',
        'log_text': '<tg-emoji emoji-id="5870994129244131212">👤</tg-emoji> <b>Кто:</b> {user}\n<tg-emoji emoji-id="5870704313440932932">🔒</tg-emoji> <b>Кто наказал:</b> {admin}\n<tg-emoji emoji-id="5872988737826197458">⛔️</tg-emoji> <b>Что:</b> {punishment}{reason}{time}{chat}',
        'log_chat': '\n<tg-emoji emoji-id="5872886929921413168">💬</tg-emoji> <b>Чат:</b> {chat}',
        'log_reason': '\n<tg-emoji emoji-id="5870676941614354370">🖋</tg-emoji> <b>Причина:</b> {reason}',
        'log_time': '\n<tg-emoji emoji-id="5870729937215819584">⏰️</tg-emoji> <b>Срок:</b> {time}',
        'act.mute': 'Мут',
        'act.ban': 'Бан',
        'act.kick': 'Кик',
        'act.unmute': 'Размут',
        'act.unban': 'Разбан',
        'act.warn': 'Варн',
        'act.nomedia': 'Запрет медиа',
        'act.allowmedia': 'Медиа разрешены',
        'act.rights': 'Права изменены',
        'flushda.loading': '<tg-emoji emoji-id="5870813306826002498">🟡</tg-emoji> <b>Убираю удалённые аккаунты…</b>',
        'flushda.loading.chat': '<tg-emoji emoji-id="5870813306826002498">🟡</tg-emoji> <b>Убираю удалённые аккаунты из этого чата…</b>',
        'flushda.loading.channels': '<tg-emoji emoji-id="5870813306826002498">🟡</tg-emoji> <b>Убираю удалённые аккаунты из каналов…</b>',
        'monday': 'Понедельник',
        'tuesday': 'Вторник',
        'wednesday': 'Среда',
        'thursday': 'Четверг',
        'friday': 'Пятница',
        'saturday': 'Суббота',
        'sunday': 'Воскресенье',
        'cfg.gban_except': 'ID чатов, которые .gban и .ungban не трогают',
        'cfg.gban_pm_block': 'Блокировать в ЛС при .gban и разблокировать при .ungban',
        'cfg.gban_pm_del_history': 'Вместе с блокировкой удалять переписку в ЛС',
        'cfg.gban_pm_except': 'ID пользователей, которых в ЛС не блокировать',
        'cfg.global_logs': 'Логировать ограничения из всех чатов, где вы админ, а не только свои команды',
        'gban.no_reason': 'Не указана',
        'gban.args': '<tg-emoji emoji-id="5870994129244131212">👤</tg-emoji> <b>Укажи пользователя.</b>\nОтветь на сообщение или передай юзернейм или ID.',
        'gban.working': '<tg-emoji emoji-id="5870718740236079262">🌍</tg-emoji> <b>Баню <a href="{url}">{name}</a> везде…</b>',
        'gban.unworking': '<tg-emoji emoji-id="5870718740236079262">🌍</tg-emoji> <b>Разбаниваю <a href="{url}">{name}</a> везде…</b>',
        'gban.done': '<tg-emoji emoji-id="5872988737826197458">⛔</tg-emoji> <b><a href="{url}">{name}</a> забанен в {count} чатах</b>\n<b>Причина:</b> <i>{reason}</i>',
        'gban.undone': '<tg-emoji emoji-id="5870948572526022116">👋🏻</tg-emoji> <b><a href="{url}">{name}</a> разбанен в {count} чатах</b>',
        'gban.chats': '\n{chats}',
        'gban.pm_blocked': '\n<tg-emoji emoji-id="5872988737826197458">🚫</tg-emoji> <b>Заблокирован в ЛС</b>',
        'gban.pm_unblocked': '\n<tg-emoji emoji-id="5870948572526022116">👋🏻</tg-emoji> <b>Разблокирован в ЛС</b>',
        'gban.pm_failed': '\n<tg-emoji emoji-id="5870704313440932932">🔓</tg-emoji> <b>Не удалось заблокировать в ЛС</b>',
        'gban.pm_cleared': ' · <b>Переписка в ЛС удалена</b>',
        'chatinfo': '<tg-emoji emoji-id="5870704313440932932">🔒</tg-emoji><b> Тип: {type_of}\n</b><tg-emoji emoji-id="5870495350397079101">#️⃣</tg-emoji><b> ID чата: </b><code>{id}</code><b>\n</b><tg-emoji emoji-id="5873225338984599714">🔥</tg-emoji><b> Название: {title}\n\n</b><tg-emoji emoji-id="5870676941614354370">🖋</tg-emoji><b> Описание: {about}\n\n</b><tg-emoji emoji-id="5870684638195748414">👑</tg-emoji><b> Админы: {admins_count}\n</b><tg-emoji emoji-id="5870633910337015697">✅</tg-emoji><b> Онлайн: {online_count}\n</b><tg-emoji emoji-id="5870994129244131212">👤</tg-emoji><b> Участники: {participants_count}\n</b><tg-emoji emoji-id="5872988737826197458">🚫</tg-emoji><b> Кикнутые: {kicked_count}\n</b><tg-emoji emoji-id="5870892901159932239">🔀</tg-emoji><b> Заявки: {requests_pending}\n\n</b><tg-emoji emoji-id="5870729937215819584">🕐</tg-emoji><b> Медленный режим: {slowmode_seconds}\n</b><tg-emoji emoji-id="5872980989705196227">📞</tg-emoji><b> Звонок: {call}\n</b><tg-emoji emoji-id="5870875489362513438">🗑</tg-emoji><b> TTL: {ttl_period}\n</b><tg-emoji emoji-id="5870994129244131212">👤</tg-emoji><b> Недавние заявки: {recent_requesters}\n\n</b><tg-emoji emoji-id="5870772616305839506">👥</tg-emoji><b> Связанный чат: {linked_chat_id}\n</b><tg-emoji emoji-id="5870704313440932932">🛡</tg-emoji><b> Антиспам: {antispam}\n</b><tg-emoji emoji-id="5870542612217204751">👁</tg-emoji><b> Список скрыт: {participants_hidden}\n\n</b><tg-emoji emoji-id="5870527201874546272">🔗</tg-emoji><b> Ссылка: {link}</b>',
        'userinfo': '<blockquote><tg-emoji emoji-id="5870495350397079101">#️⃣</tg-emoji><b> ID: {user_id}\n</b><tg-emoji emoji-id="5873225338984599714">🔥</tg-emoji><b> Имя: {first_name}\n</b><tg-emoji emoji-id="5873225338984599714">🔥</tg-emoji><b> Фамилия: {last_name}\n</b><tg-emoji emoji-id="5872980989705196227">📞</tg-emoji><b> Телефон: {phone}\n</b><tg-emoji emoji-id="5870998024779468554">🐶</tg-emoji><b> Юзернеймы: {usernames}</b></blockquote><b>\n</b><blockquote><tg-emoji emoji-id="5870609858520158157">ℹ️</tg-emoji><b> О себе: {about}</b></blockquote><b>\n</b><blockquote><tg-emoji emoji-id="5870729937215819584">🕐</tg-emoji><b> Часы: </b>{business_work_hours}\n<tg-emoji emoji-id="5870450871715761518">❤️</tg-emoji><b> Эмодзи-статус: {emoji_status}</b></blockquote><b>\n</b><blockquote><tg-emoji emoji-id="5870693687691841267">🔉</tg-emoji><b> Канал: {personal_channel}\n</b><tg-emoji emoji-id="5870847962917113498">🎂</tg-emoji><b> День рождения: {birthday}\n</b><tg-emoji emoji-id="5870478797593120516">🎁</tg-emoji><b> Подарки: {stargifts_count}</b></blockquote><b>\n</b><blockquote><tg-emoji emoji-id="5870931487146119264">🚨</tg-emoji><b> Общих чатов: {common_chats_count}\n</b><tg-emoji emoji-id="5870772616305839506">👥</tg-emoji><b> Общие чаты: {common_chats}</b></blockquote>',
        'promote.no_rights': '<tg-emoji emoji-id="5870704313440932932">🔓</tg-emoji> <b>Не хватает прав, чтобы менять админов.</b>',
        'promote.no_user': '<tg-emoji emoji-id="5870994129244131212">👤</tg-emoji> <b>Укажи пользователя.</b>\nОтветь на сообщение или передай юзернейм или ID.',
        'promote.demoted': '<tg-emoji emoji-id="5870948572526022116">👋🏻</tg-emoji> <b>С {name}</b> [<code>{user_id}</code>] <b>сняты права админа.</b>',
        'promote.promoted_full': '<tg-emoji emoji-id="5870684638195748414">👑</tg-emoji> <b>{name}</b> [<code>{user_id}</code>] <b>повышен с полными правами.</b>\n<b>Должность:</b> {rank}',
        'promote.promoted': '<tg-emoji emoji-id="5870684638195748414">👑</tg-emoji> <b>{name}</b> [<code>{user_id}</code>] <b>повышен до админа.</b>\n<b>Должность:</b> {rank}',
        'promote.choose': '<tg-emoji emoji-id="5870684638195748414">👑</tg-emoji> <b>Права для {name}</b> [<code>{user_id}</code>]\n<b>Должность:</b> {rank}',
        'promote.confirm': 'Подтвердить',
        'promote.default_rank': 'Админ',
        'promote.tag_group_only': '<tg-emoji emoji-id="5870931487146119264">⚠️</tg-emoji> <b>Теги участников есть только в группах.</b>',
        'promote.tag_usage': '<b>Использование:</b> <code>{prefix}settag @user тег</code> или ответом <code>{prefix}settag тег</code>. Без тега или <code>-</code> снимает его.',
        'promote.tag_invalid': '<tg-emoji emoji-id="5870657884844462243">❌</tg-emoji> <b>Тег — максимум 16 символов, без эмодзи.</b>',
        'promote.tag_no_rights': '<tg-emoji emoji-id="5870704313440932932">🔓</tg-emoji> <b>Чтобы менять чужой тег, нужно право «Управление тегами участников».</b>',
        'promote.tag_updated': '<tg-emoji emoji-id="5870676941614354370">🖋</tg-emoji> <b>Тег {name}:</b> <code>{rank}</code>',
        'promote.tag_removed': '<tg-emoji emoji-id="5255831443816327915">🗑</tg-emoji> <b>Тег {name} снят.</b>',
        'promote.rpc_error': '<tg-emoji emoji-id="5870657884844462243">❌</tg-emoji> <b>Ошибка Telegram:</b> <code>{error}</code>',
        'promote.right.change_info': '{emoji} Изменение профиля {where}',
        'promote.right.post_messages': '{emoji} Публиковать посты',
        'promote.right.edit_messages': '{emoji} Изменять посты',
        'promote.right.delete_messages': '{emoji} Удалять сообщения',
        'promote.right.ban_users': '{emoji} Ограничивать пользователей',
        'promote.right.invite_users': '{emoji} Добавлять пользователей',
        'promote.right.pin_messages': '{emoji} Закреплять сообщения',
        'promote.right.add_admins': '{emoji} Назначать админов',
        'promote.right.anonymous': '{emoji} Анонимность',
        'promote.right.manage_call': '{emoji} Управление звонками',
        'promote.right.manage_topics': '{emoji} Управление темами',
        'promote.right.post_stories': '{emoji} Публиковать истории',
        'promote.right.edit_stories': '{emoji} Изменять истории',
        'promote.right.delete_stories': '{emoji} Удалять истории',
        'promote.right.manage_direct_messages': '{emoji} Управление ЛС канала',
        'promote.right.manage_ranks': '{emoji} Управление тегами участников',
        'promote.right.manage_linked_peers': '{emoji} Управление связанными чатами',
        'promote.right.manage_welcome_messages': '{emoji} Управление приветствиями',
        'promote.right.other': '{emoji} Прочие права',
        'chat.not_channel': '<tg-emoji emoji-id="5870693687691841267">📣</tg-emoji> <b>Это только для супергрупп и каналов.</b>',
        'chat.no_rights': '<tg-emoji emoji-id="5870704313440932932">🔓</tg-emoji> <b>Не хватает прав, чтобы менять этот чат.</b>',
        'chat.usage.slow': '<b>Использование:</b> <code>{prefix}slow</code> off, либо <code>30</code>, <code>1m</code>, <code>5m</code>, <code>1h</code>.',
        'chat.usage.about': '<b>Использование:</b> <code>{prefix}setabout текст</code>. <code>-</code> очищает.',
        'chat.usage.photo': '<b>Использование:</b> ответом на фото <code>{prefix}setphoto</code>. <code>-</code> убирает.',
        'chat.usage.username': '<b>Использование:</b> <code>{prefix}setusername имя</code>. <code>-</code> убирает.',
        'chat.usage.link': '<b>Использование:</b> <code>{prefix}link</code>, <code>new</code>, <code>revoke</code> или <code>название</code>.',
        'chat.slow_off': '<tg-emoji emoji-id="5870729937215819584">🕐</tg-emoji> <b>Медленный режим выключен.</b>',
        'chat.slow_on': '<tg-emoji emoji-id="5870729937215819584">🕐</tg-emoji> <b>Медленный режим:</b> <code>{seconds}</code> с',
        'chat.about_set': '<tg-emoji emoji-id="5870676941614354370">🖋</tg-emoji> <b>Описание обновлено.</b>',
        'chat.about_cleared': '<tg-emoji emoji-id="5255831443816327915">🗑</tg-emoji> <b>Описание очищено.</b>',
        'chat.photo_set': '<tg-emoji emoji-id="5870782662234346251">🖼️</tg-emoji> <b>Фото чата обновлено.</b>',
        'chat.photo_cleared': '<tg-emoji emoji-id="5255831443816327915">🗑</tg-emoji> <b>Фото чата убрано.</b>',
        'chat.username_set': '<tg-emoji emoji-id="5870527201874546272">🔗</tg-emoji> <b>Юзернейм:</b> @{username}',
        'chat.username_cleared': '<tg-emoji emoji-id="5255831443816327915">🗑</tg-emoji> <b>Юзернейм убран.</b>',
        'chat.sign_on': '<tg-emoji emoji-id="5870676941614354370">🖋</tg-emoji> <b>Подписи авторов включены.</b>',
        'chat.sign_off': '<tg-emoji emoji-id="5870676941614354370">🖋</tg-emoji> <b>Подписи авторов выключены.</b>',
        'chat.forum_on': '<tg-emoji emoji-id="5872886929921413168">💬</tg-emoji> <b>Темы включены.</b>',
        'chat.forum_off': '<tg-emoji emoji-id="5872886929921413168">💬</tg-emoji> <b>Темы выключены.</b>',
        'chat.spam_on': '<tg-emoji emoji-id="5870704313440932932">🛡</tg-emoji> <b>Агрессивный антиспам включён.</b>',
        'chat.spam_off': '<tg-emoji emoji-id="5870704313440932932">🛡</tg-emoji> <b>Агрессивный антиспам выключен.</b>',
        'chat.hidden_on': '<tg-emoji emoji-id="5870542612217204751">👁</tg-emoji> <b>Список участников скрыт.</b>',
        'chat.hidden_off': '<tg-emoji emoji-id="5870542612217204751">👁</tg-emoji> <b>Список участников виден.</b>',
        'chat.history_on': '<tg-emoji emoji-id="5870729937215819584">🕐</tg-emoji> <b>Новые участники видят историю.</b>',
        'chat.history_off': '<tg-emoji emoji-id="5870729937215819584">🕐</tg-emoji> <b>История скрыта от новых участников.</b>',
        'chat.join_on': '<tg-emoji emoji-id="5870892901159932239">🔀</tg-emoji> <b>Заявки на вступление включены.</b>',
        'chat.join_off': '<tg-emoji emoji-id="5870892901159932239">🔀</tg-emoji> <b>Заявки на вступление выключены.</b>',
        'chat.link_none': '<tg-emoji emoji-id="5870527201874546272">🔗</tg-emoji> <b>Инвайта ещё нет.</b>',
        'chat.link': '<tg-emoji emoji-id="5870527201874546272">🔗</tg-emoji> <b>Инвайт:</b> {link}',
        'chat.link_revoked': '<tg-emoji emoji-id="5255831443816327915">🗑</tg-emoji> <b>Инвайт отозван.</b>\n<tg-emoji emoji-id="5870527201874546272">🔗</tg-emoji> <b>Новый:</b> {link}',
        'chat.link_created': '<tg-emoji emoji-id="5870633910337015697">✅</tg-emoji> <b>Инвайт создан.</b>\n<tg-emoji emoji-id="5870527201874546272">🔗</tg-emoji> {link}',
        'rights.header': '<tg-emoji emoji-id="5870684638195748414">👑</tg-emoji> <b>{name}</b> [<code>{user_id}</code>]\n<b>Роль:</b> {role}\n<b>Должность:</b> {rank}',
        'rights.owner': 'Владелец',
        'rights.admin': 'Админ',
        'rights.member': 'Участник',
        'rights.none': '<tg-emoji emoji-id="5870657884844462243">✖️</tg-emoji> <b>{name}</b> [<code>{user_id}</code>] <b>не админ.</b>',
        'rights.empty': '<i>Прав нет.</i>',
    }

    strings_de = {
        'name': 'Helm',
        'cfg.warnlimit': 'Verwarnungen, bevor ein Nutzer eingeschränkt wird',
        'cfg.ptime': 'Standarddauer der Strafe',
        'cfg.wl_punishment': 'Strafe beim Erreichen des Verwarnungslimits',
        'cfg.wl_reason': 'Grund für die Limit-Strafe',
        'cfg.wl_timespan': 'Dauer der Limit-Strafe',
        'error.wrongchattype.pm': '<tg-emoji emoji-id="5870563425628721113">📧</tg-emoji> <b>Sie können dieses Modul nicht in PM verwenden.</b>\nDieses Modul ist für Gruppen gedacht.',
        'error.wrongchattype.channel': '<tg-emoji emoji-id="5870693687691841267">📣</tg-emoji> <b>Sie können dieses Modul nicht in Kanälen verwenden.</b>\nDieses Modul ist für Gruppen gedacht.',
        'error.no_args.user': '<tg-emoji emoji-id="5870994129244131212">👤</tg-emoji> <b>Sie müssen einen Benutzer angeben.</b>\nSie können einen Benutzernamen, eine ID oder eine Antwort auf eine Nachricht verwenden.',
        'error.locate_user': '<tg-emoji emoji-id="5870974879200711167">🔎</tg-emoji> <b>Kein Benutzer gefunden.</b>\nÜberprüfen Sie den Benutzernamen oder die ID.',
        'error.can_not_restrict': '<tg-emoji emoji-id="5870704313440932932">🔓</tg-emoji> <b>Benutzer konnte nicht eingeschränkt werden.</b>\nSie haben möglicherweise nicht die erforderlichen Berechtigungen oder versuchen, einen Administrator zu verbannen, den Sie nicht befördert haben.',
        'error.reply_is_service': '<tg-emoji emoji-id="5870982283724328568">⚙️</tg-emoji> <b>Sie können einen Benutzer nicht einschränken, indem Sie auf eine Servicemeldung antworten.</b>\nAntworten Sie stattdessen auf eine Benutzermeldung — dies kann z. B. auftreten, wenn Sie in einem Thema schreiben.',
        'error.self': '<tg-emoji emoji-id="5872988737826197458">🔫</tg-emoji> <b>Sie können sich nicht einschränken.</b>\nSeien Sie nicht so selbstkritisch.',
        'error.warn_self': '<tg-emoji emoji-id="5870948572526022116">☝🏻</tg-emoji> <b>So ein böser Junge.</b>\nHör auf herumzuspielen und mach etwas Moderationskram.',
        'error.no_args.rights': '<tg-emoji emoji-id="5872996816659681395">❓</tg-emoji> <b>Sie müssen die Rechte angeben.</b>\nRechte sind eine Sequenz von Rechten (z. B. `123456789ab` um alle Rechte zu setzen). Fügen Sie ein `r` vor der Zeichenfolge hinzu, um die Rechte zu invertieren.',
        'error.no_user': '<tg-emoji emoji-id="5870994129244131212">👤</tg-emoji> <b>Nutzer angeben.</b>\nAntwort, Nutzername oder ID.',
        'error.no_reply': '<tg-emoji emoji-id="5872886929921413168">💬</tg-emoji> <b>Antworte auf eine Nachricht.</b>',
        'error.invalid_args': '<tg-emoji emoji-id="5872996816659681395">❓</tg-emoji> <b>Format:</b> <code>g</code> oder <code>c</code>, dann ein Titel. <code>30m</code>, <code>2h</code> oder <code>1d</code> am Ende löscht ihn später.',
        'error.too_much': '<tg-emoji emoji-id="5870657884844462243">❌</tg-emoji> <b>Falsche Anzahl</b>\nVerwenden Sie eine Zahl von 1 bis 100.',
        'error.insufficient_rights': '<tg-emoji emoji-id="5870704313440932932">🔓</tg-emoji> <b>Nicht genug Rechte.</b>',
        'error.unknown': '<tg-emoji emoji-id="5870657884844462243">🙅🏻\u200d♂️</tg-emoji> <b>Unbekannter Fehler</b>',
        'error': '<b>Fehler:</b> <code>{error}</code>',
        'done.muted.f': '<tg-emoji emoji-id="5870681133502435302">🔇</tg-emoji> <b>{user} wurde für ewig stummgeschaltet</b>',
        'done.muted': '<tg-emoji emoji-id="5870681133502435302">🔇</tg-emoji> <b>{user} wurde für {timespan} stummgeschaltet</b>',
        'done.warned': '<tg-emoji emoji-id="5870931487146119264">⚠</tg-emoji> <b>{user} wurde gewarnt</b>',
        'done.banned.f': '<tg-emoji emoji-id="5872988737826197458">⛔</tg-emoji> <b>{user} wurde für immer gesperrt</b>',
        'done.banned': '<tg-emoji emoji-id="5872988737826197458">⛔</tg-emoji> <b>{user} wurde für {timespan} gesperrt</b>',
        'done.kicked': '<tg-emoji emoji-id="5870778972857438051">🍃</tg-emoji> <b>{user} wurde rausgeworfen</b>',
        'done.nomedia': '<tg-emoji emoji-id="5870782662234346251">🖼️</tg-emoji> <b>{user} kann {timespan} keine Medien senden</b>',
        'done.nomedia.f': '<tg-emoji emoji-id="5870782662234346251">🖼️</tg-emoji> <b>{user} kann keine Medien mehr senden</b>',
        'done.allowmedia': '<tg-emoji emoji-id="5870782662234346251">🖼️</tg-emoji> <b>{user} kann wieder Medien senden</b>',
        'done.setrights.f': '<tg-emoji emoji-id="5870982283724328568">🔧</tg-emoji> <b>Rechte für <code>{user}</code> wurden für immer auf {rights} gesetzt</b>',
        'done.setrights': '<tg-emoji emoji-id="5870982283724328568">🔧</tg-emoji> <b>Rechte für <code>{user}</code> wurden auf {rights} für {timespan} gesetzt</b>',
        'done.unmuted': '<tg-emoji emoji-id="5870693687691841267">🔊</tg-emoji> <b>{user} ist nicht mehr stummgeschaltet</b>',
        'done.unbanned': '<tg-emoji emoji-id="5870948572526022116">👋🏻</tg-emoji> <b>{user} ist nicht mehr gesperrt</b>',
        'done.unwarned.one': '<tg-emoji emoji-id="5870930636742595124">⚖️</tg-emoji> <b>Eine Warnung von <code>{user}</code> wurde zurückgenommen</b>',
        'done.unwarned.all': '<tg-emoji emoji-id="5870930636742595124">⚖️</tg-emoji> <b>Alle Warnungen von <code>{user}</code> wurden zurückgenommen</b>',
        'done.da_kicked': '<tg-emoji emoji-id="5870778972857438051">🍃</tg-emoji> <b><code>{amount}</code> gelöschte Konten wurden rausgeworfen</b>',
        'done.pin': '<tg-emoji emoji-id="5870930744116776638">📌</tg-emoji> <b>Angeheftet</b>',
        'done.unpin': '<tg-emoji emoji-id="5870930744116776638">📌</tg-emoji> <b>Nicht mehr angeheftet</b>',
        'done.channel_ban.on': '<tg-emoji emoji-id="5870704313440932932">🔒</tg-emoji> <b>Okay, Benutzer können nicht mehr im Namen von Kanälen schreiben.</b>',
        'done.channel_ban.off': '<tg-emoji emoji-id="5870704313440932932">🔓</tg-emoji> <b>Okay, Benutzer können wieder im Namen von Kanälen schreiben.</b>',
        'done.channel_ban.action': '<tg-emoji emoji-id="5872988737826197458">⛔</tg-emoji> <b>{user} wurde für immer gesperrt</b>\n<b>Grund:</b>: schrieb im Namen des Kanals',
        'done.flushda': '<tg-emoji emoji-id="5870778972857438051">🍃</tg-emoji> <b>Entfernt <code>{amt}</code> gelöschte Konten</b>',
        'done.glban.f': '<tg-emoji emoji-id="5870718740236079262">🌍</tg-emoji> <b>{user} ist in {count} Chats für immer gesperrt</b>',
        'done.glban': '<tg-emoji emoji-id="5870718740236079262">🌍</tg-emoji> <b>{user} ist in {count} Chats für {timespan} gesperrt</b>',
        'done.glunban': '<tg-emoji emoji-id="5870718740236079262">🌍</tg-emoji> <b>{user} ist in {count} Chats entsperrt</b>',
        'done.leave': '<tg-emoji emoji-id="5870764288364252592">😶</tg-emoji> <b>Ich gehe.</b>',
        'done.leave.reason': '<tg-emoji emoji-id="5870764288364252592">😶</tg-emoji> <b>Ich gehe.</b>\n<b>Grund:</b> <i>{reason}</i>',
        'reason': '\n<b>Grund:</b> <i>{0}</i>',
        'chat_id': '<tg-emoji emoji-id="5870772616305839506">👥</tg-emoji> <b>Chat ID</b>: <code>{chat_id}</code>{additional}\n<tg-emoji emoji-id="5870994129244131212">👤</tg-emoji> <b>Ihre ID</b>: <code>{my_id}</code>',
        'person_in_reply_id': '<tg-emoji emoji-id="5870772616305839506">🫂</tg-emoji> <b>ID der Person in der Antwort</b>: <code>{reply_id}</code>',
        'sys.DA': 'Gelöschtes Konto',
        'sys.LANG': 'de_DE',
        'sys.forever': 'für immer',
        'of_chat': 'Gruppe',
        'of_channel': 'Kanal',
        'loading': '<tg-emoji emoji-id="5870813306826002498">🟡</tg-emoji> <b>Lade Daten ...</b>',
        'own_list': '<b>Meine Besitztümer ({count}):</b>\n\n{msg}',
        'no_ownerships': '<tg-emoji emoji-id="5870657884844462243">❌</tg-emoji> <b>Keine Besitztümer.</b>',
        'not_a_chat': '<tg-emoji emoji-id="5870931487146119264">⚠️</tg-emoji> <b>Funktioniert nur in Gruppen!</b>',
        'admins_in_chat': '<tg-emoji emoji-id="5870684638195748414">👑</tg-emoji> <b>Administratoren in <code>{title}</code> ({count}):</b>\n\n',
        'admins_in_chat_caption': '<b>Administratoren in {}:</b>',
        'too_many_admins': 'Zu viele Admins hier. Lade die Liste der Administratoren in eine Datei...',
        'no_admins_in_chat': '<b>Keine Administratoren in diesem Chat.</b>',
        'bots_in_chat': '<tg-emoji emoji-id="5870531058755178453">🤖</tg-emoji> <b>Bots in <code>{title}</code> ({count}):</b>\n\n',
        'bots_in_chat_caption': '<b>Bots in <code>{}</code>:</b>',
        'too_many_bots': 'Zu viele Bots hier. Lade die Liste der Bots in eine Datei...',
        'no_bots_in_chat': '<b>Keine Bots in diesem Chat.</b>',
        'users_in_chat': '<tg-emoji emoji-id="5870994129244131212">👤</tg-emoji> <b>Benutzer in <code>{title}</code> ({count}):</b>\n\n',
        'users_in_chat_caption': '<b>Benutzer in <code>{}</code>:</b>',
        'no_user_in_chat': '<b>Keine Benutzer in diesem Chat.</b>',
        'too_many_users': 'Zu viele Mitglieder. Die Liste kommt als Datei…',
        'chat_muted': '<tg-emoji emoji-id="5870681133502435302">🔇</tg-emoji> <b>Der Chat ist jetzt für Teilnehmer stummgeschaltet.</b>',
        'chat_unmuted': '<tg-emoji emoji-id="5870633910337015697">✅</tg-emoji> <b>Der Chat ist jetzt für alle Teilnehmer geöffnet.</b>',
        'title_changed': '<b>Der Titel von {type_of} wurde erfolgreich von <code>{old_title}</code> in <code>{new_title}</code> geändert.</b>',
        'user_invited': '<tg-emoji emoji-id="5870633910337015697">✅</tg-emoji> <b>Benutzer <a href=\'tg://user?id={id}\'>{user}</a> wurde in den Chat eingeladen.</b>',
        'creator': '<tg-emoji emoji-id="5870684638195748414">👑</tg-emoji> <b>Der Ersteller ist <a href=\'tg://user?id={id}\'>{creator}</a>.</b>',
        'no_creator': '<tg-emoji emoji-id="5870657884844462243">❌</tg-emoji> <b>Kein Ersteller gefunden.</b>',
        'channel_created': '<tg-emoji emoji-id="5870633910337015697">✅</tg-emoji> <b>Der Kanal <code>{title}</code> wurde erstellt.\n</b><tg-emoji emoji-id="5870527201874546272">🔗</tg-emoji><b> Einladungslink: {link}</b>',
        'group_created': '<tg-emoji emoji-id="5870633910337015697">✅</tg-emoji> <b>Die Gruppe <code>{title}</code> wurde erstellt.\n</b><tg-emoji emoji-id="5870527201874546272">🔗</tg-emoji><b> Einladungslink: {link}</b>',
        'temp_chat': '\n<tg-emoji emoji-id="5870875489362513438">🗑</tg-emoji> <b>Löscht sich in {timespan} selbst.</b>',
        'type_group': 'Gruppe',
        'type_channel': 'Kanal',
        'type_unknown': 'Unbekannt',
        'yes': '<tg-emoji emoji-id="5870633910337015697">✅</tg-emoji> Ja',
        'no': '<tg-emoji emoji-id="5870657884844462243">✖️</tg-emoji> Nein',
        'all_approved': '<tg-emoji emoji-id="5870633910337015697">✅</tg-emoji> <b>Benutzer wurden genehmigt</b>',
        'all_dismissed': '<tg-emoji emoji-id="5870657884844462243">✖️</tg-emoji> <b>Anfragen wurden abgelehnt</b>',
        'log_text': '<tg-emoji emoji-id="5870994129244131212">👤</tg-emoji> <b>Nutzer:</b> {user}\n<tg-emoji emoji-id="5870704313440932932">🔒</tg-emoji> <b>Admin:</b> {admin}\n<tg-emoji emoji-id="5872988737826197458">⛔️</tg-emoji> <b>Aktion:</b> {punishment}{reason}{time}{chat}',
        'log_chat': '\n<tg-emoji emoji-id="5872886929921413168">💬</tg-emoji> <b>Chat:</b> {chat}',
        'log_reason': '\n<tg-emoji emoji-id="5870676941614354370">🖋</tg-emoji> <b>Grund:</b> {reason}',
        'log_time': '\n<tg-emoji emoji-id="5870729937215819584">⏰️</tg-emoji> <b>Dauer:</b> {time}',
        'act.mute': 'Stumm',
        'act.ban': 'Sperre',
        'act.kick': 'Rauswurf',
        'act.unmute': 'Stummschaltung aufgehoben',
        'act.unban': 'Entsperrt',
        'act.warn': 'Verwarnung',
        'act.nomedia': 'Medien gesperrt',
        'act.allowmedia': 'Medien erlaubt',
        'act.rights': 'Rechte geändert',
        'flushda.loading': '<tg-emoji emoji-id="5870813306826002498">🟡</tg-emoji> <b>Gelöschte Konten werden entfernt…</b>',
        'flushda.loading.chat': '<tg-emoji emoji-id="5870813306826002498">🟡</tg-emoji> <b>Gelöschte Konten werden aus diesem Chat entfernt…</b>',
        'flushda.loading.channels': '<tg-emoji emoji-id="5870813306826002498">🟡</tg-emoji> <b>Gelöschte Konten werden aus Kanälen entfernt…</b>',
        'monday': 'Montag',
        'tuesday': 'Dienstag',
        'wednesday': 'Mittwoch',
        'thursday': 'Donnerstag',
        'friday': 'Freitag',
        'saturday': 'Samstag',
        'sunday': 'Sonntag',
        'cfg.gban_except': 'Chat-IDs, die .gban und .ungban auslassen',
        'cfg.gban_pm_block': 'Bei .gban im PM blockieren und bei .ungban wieder freigeben',
        'cfg.gban_pm_del_history': 'Beim Blockieren auch den PM-Verlauf löschen',
        'cfg.gban_pm_except': 'Nutzer-IDs, die im PM nie blockiert werden',
        'cfg.global_logs': 'Einschränkungen aus allen Admin-Chats loggen, nicht nur eigene Befehle',
        'gban.no_reason': 'Nicht angegeben',
        'gban.args': '<tg-emoji emoji-id="5870994129244131212">👤</tg-emoji> <b>Gib einen Nutzer an.</b>\nAntworte oder übergib einen Namen oder eine ID.',
        'gban.working': '<tg-emoji emoji-id="5870718740236079262">🌍</tg-emoji> <b>Sperre <a href="{url}">{name}</a> überall…</b>',
        'gban.unworking': '<tg-emoji emoji-id="5870718740236079262">🌍</tg-emoji> <b>Entsperre <a href="{url}">{name}</a> überall…</b>',
        'gban.done': '<tg-emoji emoji-id="5872988737826197458">⛔</tg-emoji> <b><a href="{url}">{name}</a> ist in {count} Chats gesperrt</b>\n<b>Grund:</b> <i>{reason}</i>',
        'gban.undone': '<tg-emoji emoji-id="5870948572526022116">👋🏻</tg-emoji> <b><a href="{url}">{name}</a> ist in {count} Chats entsperrt</b>',
        'gban.chats': '\n{chats}',
        'gban.pm_blocked': '\n<tg-emoji emoji-id="5872988737826197458">🚫</tg-emoji> <b>Im PM blockiert</b>',
        'gban.pm_unblocked': '\n<tg-emoji emoji-id="5870948572526022116">👋🏻</tg-emoji> <b>Im PM freigegeben</b>',
        'gban.pm_failed': '\n<tg-emoji emoji-id="5870704313440932932">🔓</tg-emoji> <b>Im PM nicht blockiert</b>',
        'gban.pm_cleared': ' · <b>PM-Verlauf gelöscht</b>',
        'chatinfo': '<tg-emoji emoji-id="5870704313440932932">🔒</tg-emoji><b> Typ: {type_of}\n</b><tg-emoji emoji-id="5870495350397079101">#️⃣</tg-emoji><b> Chat-ID: </b><code>{id}</code><b>\n</b><tg-emoji emoji-id="5873225338984599714">🔥</tg-emoji><b> Titel: {title}\n\n</b><tg-emoji emoji-id="5870676941614354370">🖋</tg-emoji><b> Beschreibung: {about}\n\n</b><tg-emoji emoji-id="5870684638195748414">👑</tg-emoji><b> Admins: {admins_count}\n</b><tg-emoji emoji-id="5870633910337015697">✅</tg-emoji><b> Online: {online_count}\n</b><tg-emoji emoji-id="5870994129244131212">👤</tg-emoji><b> Mitglieder: {participants_count}\n</b><tg-emoji emoji-id="5872988737826197458">🚫</tg-emoji><b> Entfernt: {kicked_count}\n</b><tg-emoji emoji-id="5870892901159932239">🔀</tg-emoji><b> Offene Anfragen: {requests_pending}\n\n</b><tg-emoji emoji-id="5870729937215819584">🕐</tg-emoji><b> Slowmode: {slowmode_seconds}\n</b><tg-emoji emoji-id="5872980989705196227">📞</tg-emoji><b> Anruf: {call}\n</b><tg-emoji emoji-id="5870875489362513438">🗑</tg-emoji><b> TTL: {ttl_period}\n</b><tg-emoji emoji-id="5870994129244131212">👤</tg-emoji><b> Letzte Anfragen: {recent_requesters}\n\n</b><tg-emoji emoji-id="5870772616305839506">👥</tg-emoji><b> Verknüpfter Chat: {linked_chat_id}\n</b><tg-emoji emoji-id="5870704313440932932">🛡</tg-emoji><b> Antispam: {antispam}\n</b><tg-emoji emoji-id="5870542612217204751">👁</tg-emoji><b> Liste verborgen: {participants_hidden}\n\n</b><tg-emoji emoji-id="5870527201874546272">🔗</tg-emoji><b> Link: {link}</b>',
        'userinfo': '<blockquote><tg-emoji emoji-id="5870495350397079101">#️⃣</tg-emoji><b> ID: {user_id}\n</b><tg-emoji emoji-id="5873225338984599714">🔥</tg-emoji><b> Vorname: {first_name}\n</b><tg-emoji emoji-id="5873225338984599714">🔥</tg-emoji><b> Nachname: {last_name}\n</b><tg-emoji emoji-id="5872980989705196227">📞</tg-emoji><b> Telefon: {phone}\n</b><tg-emoji emoji-id="5870998024779468554">🐶</tg-emoji><b> Nutzernamen: {usernames}</b></blockquote><b>\n</b><blockquote><tg-emoji emoji-id="5870609858520158157">ℹ️</tg-emoji><b> Über: {about}</b></blockquote><b>\n</b><blockquote><tg-emoji emoji-id="5870729937215819584">🕐</tg-emoji><b> Zeiten: </b>{business_work_hours}\n<tg-emoji emoji-id="5870450871715761518">❤️</tg-emoji><b> Emoji-Status: {emoji_status}</b></blockquote><b>\n</b><blockquote><tg-emoji emoji-id="5870693687691841267">🔉</tg-emoji><b> Kanal: {personal_channel}\n</b><tg-emoji emoji-id="5870847962917113498">🎂</tg-emoji><b> Geburtstag: {birthday}\n</b><tg-emoji emoji-id="5870478797593120516">🎁</tg-emoji><b> Geschenke: {stargifts_count}</b></blockquote><b>\n</b><blockquote><tg-emoji emoji-id="5870931487146119264">🚨</tg-emoji><b> Gemeinsame Chats: {common_chats_count}\n</b><tg-emoji emoji-id="5870772616305839506">👥</tg-emoji><b> Gemeinsame Chats: {common_chats}</b></blockquote>',
        'promote.no_rights': '<tg-emoji emoji-id="5870704313440932932">🔓</tg-emoji> <b>Nicht genug Rechte, um Admins zu ändern.</b>',
        'promote.no_user': '<tg-emoji emoji-id="5870994129244131212">👤</tg-emoji> <b>Geben Sie einen Benutzer an.</b>\nAntworten Sie oder übergeben Sie einen Namen oder eine ID.',
        'promote.demoted': '<tg-emoji emoji-id="5870948572526022116">👋🏻</tg-emoji> <b>{name}</b> [<code>{user_id}</code>] <b>ist kein Admin mehr.</b>',
        'promote.promoted_full': '<tg-emoji emoji-id="5870684638195748414">👑</tg-emoji> <b>{name}</b> [<code>{user_id}</code>] <b>ist Admin mit allen Rechten.</b>\n<b>Rang:</b> {rank}',
        'promote.promoted': '<tg-emoji emoji-id="5870684638195748414">👑</tg-emoji> <b>{name}</b> [<code>{user_id}</code>] <b>ist Admin.</b>\n<b>Rang:</b> {rank}',
        'promote.choose': '<tg-emoji emoji-id="5870684638195748414">👑</tg-emoji> <b>Adminrechte für {name}</b> [<code>{user_id}</code>]\n<b>Rang:</b> {rank}',
        'promote.confirm': 'Bestätigen',
        'promote.default_rank': 'Admin',
        'promote.tag_group_only': '<tg-emoji emoji-id="5870931487146119264">⚠️</tg-emoji> <b>Mitglieder-Tags gibt es nur in Gruppen.</b>',
        'promote.tag_usage': '<b>Nutzung:</b> <code>{prefix}settag @user Tag</code> oder als Antwort <code>{prefix}settag Tag</code>. Ohne Tag oder <code>-</code> wird er entfernt.',
        'promote.tag_invalid': '<tg-emoji emoji-id="5870657884844462243">❌</tg-emoji> <b>Ein Tag hat höchstens 16 Zeichen und kein Emoji.</b>',
        'promote.tag_no_rights': '<tg-emoji emoji-id="5870704313440932932">🔓</tg-emoji> <b>Für fremde Tags brauchen Sie das Recht „Mitglieder-Tags verwalten“.</b>',
        'promote.tag_updated': '<tg-emoji emoji-id="5870676941614354370">🖋</tg-emoji> <b>Tag von {name}:</b> <code>{rank}</code>',
        'promote.tag_removed': '<tg-emoji emoji-id="5255831443816327915">🗑</tg-emoji> <b>Tag von {name} entfernt.</b>',
        'promote.rpc_error': '<tg-emoji emoji-id="5870657884844462243">❌</tg-emoji> <b>Telegram-Fehler:</b> <code>{error}</code>',
        'promote.right.change_info': '{emoji} {where}-Info ändern',
        'promote.right.post_messages': '{emoji} Nachrichten posten',
        'promote.right.edit_messages': '{emoji} Beiträge bearbeiten',
        'promote.right.delete_messages': '{emoji} Nachrichten löschen',
        'promote.right.ban_users': '{emoji} Nutzer einschränken',
        'promote.right.invite_users': '{emoji} Nutzer einladen',
        'promote.right.pin_messages': '{emoji} Nachrichten anheften',
        'promote.right.add_admins': '{emoji} Admins ernennen',
        'promote.right.anonymous': '{emoji} Anonym',
        'promote.right.manage_call': '{emoji} Anrufe verwalten',
        'promote.right.manage_topics': '{emoji} Themen verwalten',
        'promote.right.post_stories': '{emoji} Stories posten',
        'promote.right.edit_stories': '{emoji} Stories bearbeiten',
        'promote.right.delete_stories': '{emoji} Stories löschen',
        'promote.right.manage_direct_messages': '{emoji} Direktnachrichten verwalten',
        'promote.right.manage_ranks': '{emoji} Mitglieder-Tags verwalten',
        'promote.right.manage_linked_peers': '{emoji} Verknüpfte Chats verwalten',
        'promote.right.manage_welcome_messages': '{emoji} Willkommensnachrichten verwalten',
        'promote.right.other': '{emoji} Weitere Rechte',
        'chat.not_channel': '<tg-emoji emoji-id="5870693687691841267">📣</tg-emoji> <b>Das geht nur in Supergruppen und Kanälen.</b>',
        'chat.no_rights': '<tg-emoji emoji-id="5870704313440932932">🔓</tg-emoji> <b>Nicht genug Rechte, um diesen Chat zu ändern.</b>',
        'chat.usage.slow': '<b>Nutzung:</b> <code>{prefix}slow</code> off, oder <code>30</code>, <code>1m</code>, <code>5m</code>, <code>1h</code>.',
        'chat.usage.about': '<b>Nutzung:</b> <code>{prefix}setabout Text</code>. <code>-</code> löscht ihn.',
        'chat.usage.photo': '<b>Nutzung:</b> auf ein Foto antworten mit <code>{prefix}setphoto</code>. <code>-</code> entfernt es.',
        'chat.usage.username': '<b>Nutzung:</b> <code>{prefix}setusername Name</code>. <code>-</code> entfernt ihn.',
        'chat.usage.link': '<b>Nutzung:</b> <code>{prefix}link</code>, <code>new</code>, <code>revoke</code> oder <code>Titel</code>.',
        'chat.slow_off': '<tg-emoji emoji-id="5870729937215819584">🕐</tg-emoji> <b>Slow Mode ist aus.</b>',
        'chat.slow_on': '<tg-emoji emoji-id="5870729937215819584">🕐</tg-emoji> <b>Slow Mode:</b> <code>{seconds}</code> s',
        'chat.about_set': '<tg-emoji emoji-id="5870676941614354370">🖋</tg-emoji> <b>Beschreibung aktualisiert.</b>',
        'chat.about_cleared': '<tg-emoji emoji-id="5255831443816327915">🗑</tg-emoji> <b>Beschreibung gelöscht.</b>',
        'chat.photo_set': '<tg-emoji emoji-id="5870782662234346251">🖼️</tg-emoji> <b>Chatfoto aktualisiert.</b>',
        'chat.photo_cleared': '<tg-emoji emoji-id="5255831443816327915">🗑</tg-emoji> <b>Chatfoto entfernt.</b>',
        'chat.username_set': '<tg-emoji emoji-id="5870527201874546272">🔗</tg-emoji> <b>Benutzername:</b> @{username}',
        'chat.username_cleared': '<tg-emoji emoji-id="5255831443816327915">🗑</tg-emoji> <b>Benutzername entfernt.</b>',
        'chat.sign_on': '<tg-emoji emoji-id="5870676941614354370">🖋</tg-emoji> <b>Autorensignaturen sind an.</b>',
        'chat.sign_off': '<tg-emoji emoji-id="5870676941614354370">🖋</tg-emoji> <b>Autorensignaturen sind aus.</b>',
        'chat.forum_on': '<tg-emoji emoji-id="5872886929921413168">💬</tg-emoji> <b>Themen sind an.</b>',
        'chat.forum_off': '<tg-emoji emoji-id="5872886929921413168">💬</tg-emoji> <b>Themen sind aus.</b>',
        'chat.spam_on': '<tg-emoji emoji-id="5870704313440932932">🛡</tg-emoji> <b>Aggressiver Antispam ist an.</b>',
        'chat.spam_off': '<tg-emoji emoji-id="5870704313440932932">🛡</tg-emoji> <b>Aggressiver Antispam ist aus.</b>',
        'chat.hidden_on': '<tg-emoji emoji-id="5870542612217204751">👁</tg-emoji> <b>Die Mitgliederliste ist verborgen.</b>',
        'chat.hidden_off': '<tg-emoji emoji-id="5870542612217204751">👁</tg-emoji> <b>Die Mitgliederliste ist sichtbar.</b>',
        'chat.history_on': '<tg-emoji emoji-id="5870729937215819584">🕐</tg-emoji> <b>Neue Mitglieder sehen den Verlauf.</b>',
        'chat.history_off': '<tg-emoji emoji-id="5870729937215819584">🕐</tg-emoji> <b>Der Verlauf ist für neue Mitglieder verborgen.</b>',
        'chat.join_on': '<tg-emoji emoji-id="5870892901159932239">🔀</tg-emoji> <b>Beitrittsanfragen sind an.</b>',
        'chat.join_off': '<tg-emoji emoji-id="5870892901159932239">🔀</tg-emoji> <b>Beitrittsanfragen sind aus.</b>',
        'chat.link_none': '<tg-emoji emoji-id="5870527201874546272">🔗</tg-emoji> <b>Noch kein Einladungslink.</b>',
        'chat.link': '<tg-emoji emoji-id="5870527201874546272">🔗</tg-emoji> <b>Einladung:</b> {link}',
        'chat.link_revoked': '<tg-emoji emoji-id="5255831443816327915">🗑</tg-emoji> <b>Einladung widerrufen.</b>\n<tg-emoji emoji-id="5870527201874546272">🔗</tg-emoji> <b>Neu:</b> {link}',
        'chat.link_created': '<tg-emoji emoji-id="5870633910337015697">✅</tg-emoji> <b>Einladung erstellt.</b>\n<tg-emoji emoji-id="5870527201874546272">🔗</tg-emoji> {link}',
        'rights.header': '<tg-emoji emoji-id="5870684638195748414">👑</tg-emoji> <b>{name}</b> [<code>{user_id}</code>]\n<b>Rolle:</b> {role}\n<b>Rang:</b> {rank}',
        'rights.owner': 'Inhaber',
        'rights.admin': 'Admin',
        'rights.member': 'Mitglied',
        'rights.none': '<tg-emoji emoji-id="5870657884844462243">✖️</tg-emoji> <b>{name}</b> [<code>{user_id}</code>] <b>ist kein Admin.</b>',
        'rights.empty': '<i>Keine Rechte.</i>',
    }

    strings_fr = {
        'name': 'Helm',
        'cfg.warnlimit': 'Avertissements avant restriction',
        'cfg.ptime': 'Durée de sanction par défaut',
        'cfg.wl_punishment': "Sanction quand la limite d'avertissements est atteinte",
        'cfg.wl_reason': 'Motif de la sanction de limite',
        'cfg.wl_timespan': 'Durée de la sanction de limite',
        'error.wrongchattype.pm': '<tg-emoji emoji-id="5870563425628721113">📧</tg-emoji> <b>Vous ne pouvez pas utiliser ce module en MP.</b>\nCe module est conçu pour les groupes.',
        'error.wrongchattype.channel': '<tg-emoji emoji-id="5870693687691841267">📣</tg-emoji> <b>Vous ne pouvez pas utiliser ce module dans les canaux.</b>\nCe module est conçu pour les groupes.',
        'error.no_args.user': '<tg-emoji emoji-id="5870994129244131212">👤</tg-emoji> <b>Vous devez spécifier un utilisateur.</b>\nVous pouvez utiliser un nom d\'utilisateur, un ID ou répondre à un message.',
        'error.locate_user': '<tg-emoji emoji-id="5870974879200711167">🔎</tg-emoji> <b>Impossible de trouver l\'utilisateur.</b>\nVérifiez le nom d\'utilisateur ou l\'ID.',
        'error.can_not_restrict': '<tg-emoji emoji-id="5870704313440932932">🔓</tg-emoji> <b>Impossible de restreindre l\'utilisateur.</b>\nVous n\'avez peut-être pas les permissions requises ou essayez de bannir un admin que vous n\'avez pas promu.',
        'error.reply_is_service': '<tg-emoji emoji-id="5870982283724328568">⚙️</tg-emoji> <b>Vous ne pouvez pas restreindre un utilisateur en répondant à un message de service.</b>\nRépondez plutôt à un message d\'utilisateur — cela peut arriver si vous écrivez dans un topic.',
        'error.self': '<tg-emoji emoji-id="5872988737826197458">🔫</tg-emoji> <b>Vous ne pouvez pas vous restreindre vous-même.</b>\nNe soyez pas si autocritique.',
        'error.warn_self': '<tg-emoji emoji-id="5870948572526022116">☝🏻</tg-emoji> <b>Vilain garçon.</b>\nArrêtez de jouer et faites de la modération.',
        'error.no_args.rights': '<tg-emoji emoji-id="5872996816659681395">❓</tg-emoji> <b>Vous devez spécifier les droits.</b>\nLes droits sont une séquence (ex: `123456789ab` pour tous les droits). Ajoutez `r` avant pour inverser les droits.',
        'error.no_user': '<tg-emoji emoji-id="5870994129244131212">👤</tg-emoji> <b>Indique un utilisateur.</b>\nRéponse, pseudo ou ID.',
        'error.no_reply': '<tg-emoji emoji-id="5872886929921413168">💬</tg-emoji> <b>Réponds à un message.</b>',
        'error.invalid_args': '<tg-emoji emoji-id="5872996816659681395">❓</tg-emoji> <b>Format :</b> <code>g</code> ou <code>c</code>, puis un titre. <code>30m</code>, <code>2h</code> ou <code>1d</code> à la fin le supprime plus tard.',
        'error.too_much': '<tg-emoji emoji-id="5870657884844462243">❌</tg-emoji> <b>Quantité incorrecte</b>\nUtilisez un nombre de 1 à 100.',
        'error.insufficient_rights': '<tg-emoji emoji-id="5870704313440932932">🔓</tg-emoji> <b>Droits insuffisants.</b>',
        'error.unknown': '<tg-emoji emoji-id="5870657884844462243">🙅🏻\u200d♂️</tg-emoji> <b>Erreur inconnue</b>',
        'error': '<b>Erreur :</b> <code>{error}</code>',
        'done.muted.f': '<tg-emoji emoji-id="5870681133502435302">🔇</tg-emoji> <b>{user} a été rendu muet pour toujours</b>',
        'done.muted': '<tg-emoji emoji-id="5870681133502435302">🔇</tg-emoji> <b>{user} a été rendu muet pendant {timespan}</b>',
        'done.warned': '<tg-emoji emoji-id="5870931487146119264">⚠</tg-emoji> <b>{user} a reçu un avertissement</b>',
        'done.banned.f': '<tg-emoji emoji-id="5872988737826197458">⛔</tg-emoji> <b>{user} a été banni à jamais</b>',
        'done.banned': '<tg-emoji emoji-id="5872988737826197458">⛔</tg-emoji> <b>{user} a été banni pendant {timespan}</b>',
        'done.kicked': '<tg-emoji emoji-id="5870778972857438051">🍃</tg-emoji> <b>{user} a été expulsé</b>',
        'done.nomedia': '<tg-emoji emoji-id="5870782662234346251">🖼️</tg-emoji> <b>{user} ne pourra plus envoyer de médias pendant {timespan}</b>',
        'done.nomedia.f': '<tg-emoji emoji-id="5870782662234346251">🖼️</tg-emoji> <b>{user} ne pourra plus jamais envoyer de médias</b>',
        'done.allowmedia': '<tg-emoji emoji-id="5870782662234346251">🖼️</tg-emoji> <b>{user} peut à nouveau envoyer des médias</b>',
        'done.setrights.f': '<tg-emoji emoji-id="5870982283724328568">🔧</tg-emoji> <b>Les droits de <code>{user}</code> ont été définis sur {rights}</b>',
        'done.setrights': '<tg-emoji emoji-id="5870982283724328568">🔧</tg-emoji> <b>Les droits de <code>{user}</code> ont été définis sur {rights}</b> pendant {timespan}',
        'done.unmuted': '<tg-emoji emoji-id="5870693687691841267">🔊</tg-emoji> <b>{user} n\'est plus muet</b>',
        'done.unbanned': '<tg-emoji emoji-id="5870948572526022116">👋🏻</tg-emoji> <b>{user} a été débanni</b>',
        'done.unwarned.one': '<tg-emoji emoji-id="5870930636742595124">⚖️</tg-emoji> <b>Un avertissement a été retiré à {user}</b>',
        'done.unwarned.all': '<tg-emoji emoji-id="5870930636742595124">⚖️</tg-emoji> <b>Tous les avertissements de l\'utilisateur <code>{user}</code> ont été révoqués</b>',
        'done.da_kicked': '<tg-emoji emoji-id="5870778972857438051">🍃</tg-emoji> <b><code>{amount}</code> compte(s) supprimé(s) ont été expulsés</b>',
        'done.pin': '<tg-emoji emoji-id="5870930744116776638">📌</tg-emoji> <b>Épinglé</b>',
        'done.unpin': '<tg-emoji emoji-id="5870930744116776638">📌</tg-emoji> <b>Désépinglé</b>',
        'done.channel_ban.on': '<tg-emoji emoji-id="5870704313440932932">🔒</tg-emoji> <b>D\'accord, les utilisateurs ne pourront plus écrire au nom des canaux.</b>',
        'done.channel_ban.off': '<tg-emoji emoji-id="5870704313440932932">🔓</tg-emoji> <b>D\'accord, les utilisateurs peuvent à nouveau écrire au nom des canaux.</b>',
        'done.channel_ban.action': '<tg-emoji emoji-id="5872988737826197458">⛔</tg-emoji> <b>{user} a été banni pour toujours</b>\n<b>Raison :</b> écrivait au nom d\'un canal',
        'done.flushda': '<tg-emoji emoji-id="5870778972857438051">🍃</tg-emoji> <b>Suppression de <code>{amt}</code> comptes supprimés</b>',
        'done.glban.f': '<tg-emoji emoji-id="5870718740236079262">🌍</tg-emoji> <b>{user} est banni dans {count} chats pour toujours</b>',
        'done.glban': '<tg-emoji emoji-id="5870718740236079262">🌍</tg-emoji> <b>{user} est banni dans {count} chats pendant {timespan}</b>',
        'done.glunban': '<tg-emoji emoji-id="5870718740236079262">🌍</tg-emoji> <b>{user} est débanni dans {count} chats</b>',
        'done.leave': '<tg-emoji emoji-id="5870764288364252592">😶</tg-emoji> <b>Je pars.</b>',
        'done.leave.reason': '<tg-emoji emoji-id="5870764288364252592">😶</tg-emoji> <b>Je pars.</b>\n<b>Raison :</b> <i>{reason}</i>',
        'reason': '\n<b>Raison :</b> <i>{0}</i>',
        'chat_id': '<tg-emoji emoji-id="5870772616305839506">👥</tg-emoji> <b>ID du chat</b> : <code>{chat_id}</code>{additional}\n<tg-emoji emoji-id="5870994129244131212">👤</tg-emoji> <b>Votre ID</b> : <code>{my_id}</code>',
        'person_in_reply_id': '<tg-emoji emoji-id="5870772616305839506">🫂</tg-emoji> <b>ID de la personne répondue</b> : <code>{reply_id}</code>',
        'sys.DA': 'Compte supprimé',
        'sys.LANG': 'fr_FR',
        'sys.forever': 'pour toujours',
        'of_chat': 'groupe',
        'of_channel': 'Canal',
        'loading': '<tg-emoji emoji-id="5870813306826002498">🟡</tg-emoji> <b>Chargement des données ...</b>',
        'own_list': '<b>Mes possessions ({count}) :</b>\n\n{msg}',
        'no_ownerships': '<tg-emoji emoji-id="5870657884844462243">❌</tg-emoji> <b>Aucune possession.</b>',
        'not_a_chat': '<tg-emoji emoji-id="5870931487146119264">⚠️</tg-emoji> <b>Cela fonctionne uniquement dans les groupes !</b>',
        'admins_in_chat': '<tg-emoji emoji-id="5870684638195748414">👑</tg-emoji> <b>Admins dans <code>{title}</code> ({count}) :</b>\n\n',
        'admins_in_chat_caption': '<b>Admins dans "{}" :</b>',
        'too_many_admins': "Trop d'admins ici. Chargement de la liste dans un fichier...",
        'no_admins_in_chat': '<b>Aucun admin dans ce chat.</b>',
        'bots_in_chat': '<tg-emoji emoji-id="5870531058755178453">🤖</tg-emoji> <b>Bots dans <code>{title}</code> ({count}) :</b>\n\n',
        'bots_in_chat_caption': '<b>Bots dans <code>{}</code> :</b>',
        'too_many_bots': 'Trop de bots ici. Chargement de la liste dans un fichier...',
        'no_bots_in_chat': '<b>Aucun bot dans ce chat.</b>',
        'users_in_chat': '<tg-emoji emoji-id="5870994129244131212">👤</tg-emoji> <b>Utilisateurs dans <code>{title}</code> ({count}) :</b>\n\n',
        'users_in_chat_caption': '<b>Utilisateurs dans <code>{}</code> :</b>',
        'no_user_in_chat': '<b>Aucun utilisateur dans ce chat.</b>',
        'too_many_users': 'Trop de membres. La liste part en fichier…',
        'chat_muted': '<tg-emoji emoji-id="5870681133502435302">🔇</tg-emoji> <b>Le chat est maintenant silencieux pour les participants.</b>',
        'chat_unmuted': '<tg-emoji emoji-id="5870633910337015697">✅</tg-emoji> <b>Le chat est maintenant ouvert à tous les participants.</b>',
        'title_changed': '<b>Le titre de {type_of} a été changé de <code>{old_title}</code> à <code>{new_title}</code>.</b>',
        'user_invited': '<tg-emoji emoji-id="5870633910337015697">✅</tg-emoji> <b>L\'utilisateur <a href=\'tg://user?id={id}\'>{user}</a> est invité dans le chat.</b>',
        'creator': '<tg-emoji emoji-id="5870684638195748414">👑</tg-emoji> <b>Le créateur est <a href=\'tg://user?id={id}\'>{creator}</a>.</b>',
        'no_creator': '<tg-emoji emoji-id="5870657884844462243">❌</tg-emoji> <b>Aucun créateur trouvé.</b>',
        'channel_created': '<tg-emoji emoji-id="5870633910337015697">✅</tg-emoji> <b>Le canal <code>{title}</code> a été créé.\n</b><tg-emoji emoji-id="5870527201874546272">🔗</tg-emoji><b> Lien d\'invitation : {link}</b>',
        'group_created': '<tg-emoji emoji-id="5870633910337015697">✅</tg-emoji> <b>Le groupe <code>{title}</code> a été créé.\n</b><tg-emoji emoji-id="5870527201874546272">🔗</tg-emoji><b> Lien d\'invitation : {link}</b>',
        'temp_chat': '\n<tg-emoji emoji-id="5870875489362513438">🗑</tg-emoji> <b>Se supprime tout seul dans {timespan}.</b>',
        'type_group': 'Groupe',
        'type_channel': 'Canal',
        'type_unknown': 'Inconnu',
        'yes': '<tg-emoji emoji-id="5870633910337015697">✅</tg-emoji> Oui',
        'no': '<tg-emoji emoji-id="5870657884844462243">✖️</tg-emoji> Non',
        'all_approved': '<tg-emoji emoji-id="5870633910337015697">✅</tg-emoji> <b>Utilisateurs approuvés</b>',
        'all_dismissed': '<tg-emoji emoji-id="5870657884844462243">✖️</tg-emoji> <b>Demandes rejetées</b>',
        'log_text': '<tg-emoji emoji-id="5870994129244131212">👤</tg-emoji> <b>Utilisateur :</b> {user}\n<tg-emoji emoji-id="5870704313440932932">🔒</tg-emoji> <b>Admin :</b> {admin}\n<tg-emoji emoji-id="5872988737826197458">⛔️</tg-emoji> <b>Action :</b> {punishment}{reason}{time}{chat}',
        'log_chat': '\n<tg-emoji emoji-id="5872886929921413168">💬</tg-emoji> <b>Discussion :</b> {chat}',
        'log_reason': '\n<tg-emoji emoji-id="5870676941614354370">🖋</tg-emoji> <b>Raison :</b> {reason}',
        'log_time': '\n<tg-emoji emoji-id="5870729937215819584">⏰️</tg-emoji> <b>Durée :</b> {time}',
        'act.mute': 'Muet',
        'act.ban': 'Bannissement',
        'act.kick': 'Expulsion',
        'act.unmute': 'Son rétabli',
        'act.unban': 'Débanni',
        'act.warn': 'Avertissement',
        'act.nomedia': 'Médias restreints',
        'act.allowmedia': 'Médias autorisés',
        'act.rights': 'Droits modifiés',
        'flushda.loading': '<tg-emoji emoji-id="5870813306826002498">🟡</tg-emoji> <b>Suppression des comptes supprimés…</b>',
        'flushda.loading.chat': '<tg-emoji emoji-id="5870813306826002498">🟡</tg-emoji> <b>Suppression des comptes supprimés de ce chat…</b>',
        'flushda.loading.channels': '<tg-emoji emoji-id="5870813306826002498">🟡</tg-emoji> <b>Suppression des comptes supprimés des canaux…</b>',
        'monday': 'Lundi',
        'tuesday': 'Mardi',
        'wednesday': 'Mercredi',
        'thursday': 'Jeudi',
        'friday': 'Vendredi',
        'saturday': 'Samedi',
        'sunday': 'Dimanche',
        'cfg.gban_except': 'ID de chats ignorés par .gban et .ungban',
        'cfg.gban_pm_block': 'Bloquer en MP avec .gban, débloquer avec .ungban',
        'cfg.gban_pm_del_history': "Supprimer aussi l'historique du MP lors du blocage",
        'cfg.gban_pm_except': 'ID des utilisateurs jamais bloqués en MP',
        'cfg.global_logs': 'Journaliser les restrictions de tous les chats admin, pas seulement vos commandes',
        'gban.no_reason': 'Non précisée',
        'gban.args': '<tg-emoji emoji-id="5870994129244131212">👤</tg-emoji> <b>Indiquez un utilisateur.</b>\nRépondez, ou passez un nom ou un ID.',
        'gban.working': '<tg-emoji emoji-id="5870718740236079262">🌍</tg-emoji> <b>Bannissement de <a href="{url}">{name}</a> partout…</b>',
        'gban.unworking': '<tg-emoji emoji-id="5870718740236079262">🌍</tg-emoji> <b>Débannissement de <a href="{url}">{name}</a> partout…</b>',
        'gban.done': '<tg-emoji emoji-id="5872988737826197458">⛔</tg-emoji> <b><a href="{url}">{name}</a> est banni dans {count} chats</b>\n<b>Raison :</b> <i>{reason}</i>',
        'gban.undone': '<tg-emoji emoji-id="5870948572526022116">👋🏻</tg-emoji> <b><a href="{url}">{name}</a> est débanni dans {count} chats</b>',
        'gban.chats': '\n{chats}',
        'gban.pm_blocked': '\n<tg-emoji emoji-id="5872988737826197458">🚫</tg-emoji> <b>Bloqué en MP</b>',
        'gban.pm_unblocked': '\n<tg-emoji emoji-id="5870948572526022116">👋🏻</tg-emoji> <b>Débloqué en MP</b>',
        'gban.pm_failed': '\n<tg-emoji emoji-id="5870704313440932932">🔓</tg-emoji> <b>Blocage en MP impossible</b>',
        'gban.pm_cleared': ' · <b>Historique du MP supprimé</b>',
        'chatinfo': '<tg-emoji emoji-id="5870704313440932932">🔒</tg-emoji><b> Type: {type_of}\n</b><tg-emoji emoji-id="5870495350397079101">#️⃣</tg-emoji><b> ID du chat: </b><code>{id}</code><b>\n</b><tg-emoji emoji-id="5873225338984599714">🔥</tg-emoji><b> Titre: {title}\n\n</b><tg-emoji emoji-id="5870676941614354370">🖋</tg-emoji><b> Description: {about}\n\n</b><tg-emoji emoji-id="5870684638195748414">👑</tg-emoji><b> Admins: {admins_count}\n</b><tg-emoji emoji-id="5870633910337015697">✅</tg-emoji><b> En ligne: {online_count}\n</b><tg-emoji emoji-id="5870994129244131212">👤</tg-emoji><b> Membres: {participants_count}\n</b><tg-emoji emoji-id="5872988737826197458">🚫</tg-emoji><b> Exclus: {kicked_count}\n</b><tg-emoji emoji-id="5870892901159932239">🔀</tg-emoji><b> Demandes: {requests_pending}\n\n</b><tg-emoji emoji-id="5870729937215819584">🕐</tg-emoji><b> Mode lent: {slowmode_seconds}\n</b><tg-emoji emoji-id="5872980989705196227">📞</tg-emoji><b> Appel: {call}\n</b><tg-emoji emoji-id="5870875489362513438">🗑</tg-emoji><b> TTL: {ttl_period}\n</b><tg-emoji emoji-id="5870994129244131212">👤</tg-emoji><b> Demandes récentes: {recent_requesters}\n\n</b><tg-emoji emoji-id="5870772616305839506">👥</tg-emoji><b> Chat lié: {linked_chat_id}\n</b><tg-emoji emoji-id="5870704313440932932">🛡</tg-emoji><b> Antispam: {antispam}\n</b><tg-emoji emoji-id="5870542612217204751">👁</tg-emoji><b> Liste cachée: {participants_hidden}\n\n</b><tg-emoji emoji-id="5870527201874546272">🔗</tg-emoji><b> Lien: {link}</b>',
        'userinfo': '<blockquote><tg-emoji emoji-id="5870495350397079101">#️⃣</tg-emoji><b> ID: {user_id}\n</b><tg-emoji emoji-id="5873225338984599714">🔥</tg-emoji><b> Prénom: {first_name}\n</b><tg-emoji emoji-id="5873225338984599714">🔥</tg-emoji><b> Nom: {last_name}\n</b><tg-emoji emoji-id="5872980989705196227">📞</tg-emoji><b> Téléphone: {phone}\n</b><tg-emoji emoji-id="5870998024779468554">🐶</tg-emoji><b> Pseudos: {usernames}</b></blockquote><b>\n</b><blockquote><tg-emoji emoji-id="5870609858520158157">ℹ️</tg-emoji><b> À propos: {about}</b></blockquote><b>\n</b><blockquote><tg-emoji emoji-id="5870729937215819584">🕐</tg-emoji><b> Horaires: </b>{business_work_hours}\n<tg-emoji emoji-id="5870450871715761518">❤️</tg-emoji><b> Statut emoji: {emoji_status}</b></blockquote><b>\n</b><blockquote><tg-emoji emoji-id="5870693687691841267">🔉</tg-emoji><b> Canal: {personal_channel}\n</b><tg-emoji emoji-id="5870847962917113498">🎂</tg-emoji><b> Anniversaire: {birthday}\n</b><tg-emoji emoji-id="5870478797593120516">🎁</tg-emoji><b> Cadeaux: {stargifts_count}</b></blockquote><b>\n</b><blockquote><tg-emoji emoji-id="5870931487146119264">🚨</tg-emoji><b> Chats en commun: {common_chats_count}\n</b><tg-emoji emoji-id="5870772616305839506">👥</tg-emoji><b> Chats communs: {common_chats}</b></blockquote>',
        'promote.no_rights': '<tg-emoji emoji-id="5870704313440932932">🔓</tg-emoji> <b>Droits insuffisants pour modifier les admins.</b>',
        'promote.no_user': '<tg-emoji emoji-id="5870994129244131212">👤</tg-emoji> <b>Indiquez un utilisateur.</b>\nRépondez, ou passez un nom ou un ID.',
        'promote.demoted': '<tg-emoji emoji-id="5870948572526022116">👋🏻</tg-emoji> <b>{name}</b> [<code>{user_id}</code>] <b>n\'est plus admin.</b>',
        'promote.promoted_full': '<tg-emoji emoji-id="5870684638195748414">👑</tg-emoji> <b>{name}</b> [<code>{user_id}</code>] <b>est admin avec tous les droits.</b>\n<b>Rang :</b> {rank}',
        'promote.promoted': '<tg-emoji emoji-id="5870684638195748414">👑</tg-emoji> <b>{name}</b> [<code>{user_id}</code>] <b>est admin.</b>\n<b>Rang :</b> {rank}',
        'promote.choose': '<tg-emoji emoji-id="5870684638195748414">👑</tg-emoji> <b>Droits admin de {name}</b> [<code>{user_id}</code>]\n<b>Rang :</b> {rank}',
        'promote.confirm': 'Confirmer',
        'promote.default_rank': 'Admin',
        'promote.tag_group_only': '<tg-emoji emoji-id="5870931487146119264">⚠️</tg-emoji> <b>Les tags de membres n\'existent que dans les groupes.</b>',
        'promote.tag_usage': '<b>Usage :</b> <code>{prefix}settag @user tag</code> ou en réponse <code>{prefix}settag tag</code>. Sans tag ou <code>-</code> le retire.',
        'promote.tag_invalid': '<tg-emoji emoji-id="5870657884844462243">❌</tg-emoji> <b>Un tag fait 16 caractères au plus, sans emoji.</b>',
        'promote.tag_no_rights': '<tg-emoji emoji-id="5870704313440932932">🔓</tg-emoji> <b>Pour changer le tag d\'un autre, il faut le droit « Gérer les tags des membres ».</b>',
        'promote.tag_updated': '<tg-emoji emoji-id="5870676941614354370">🖋</tg-emoji> <b>Tag de {name} :</b> <code>{rank}</code>',
        'promote.tag_removed': '<tg-emoji emoji-id="5255831443816327915">🗑</tg-emoji> <b>Tag de {name} retiré.</b>',
        'promote.rpc_error': '<tg-emoji emoji-id="5870657884844462243">❌</tg-emoji> <b>Erreur Telegram :</b> <code>{error}</code>',
        'promote.right.change_info': '{emoji} Modifier les infos {where}',
        'promote.right.post_messages': '{emoji} Publier des messages',
        'promote.right.edit_messages': '{emoji} Modifier les posts',
        'promote.right.delete_messages': '{emoji} Supprimer des messages',
        'promote.right.ban_users': '{emoji} Restreindre des utilisateurs',
        'promote.right.invite_users': '{emoji} Inviter des utilisateurs',
        'promote.right.pin_messages': '{emoji} Épingler des messages',
        'promote.right.add_admins': '{emoji} Nommer des admins',
        'promote.right.anonymous': '{emoji} Anonyme',
        'promote.right.manage_call': '{emoji} Gérer les appels',
        'promote.right.manage_topics': '{emoji} Gérer les sujets',
        'promote.right.post_stories': '{emoji} Publier des stories',
        'promote.right.edit_stories': '{emoji} Modifier des stories',
        'promote.right.delete_stories': '{emoji} Supprimer des stories',
        'promote.right.manage_direct_messages': '{emoji} Gérer les messages privés',
        'promote.right.manage_ranks': '{emoji} Gérer les tags des membres',
        'promote.right.manage_linked_peers': '{emoji} Gérer les chats liés',
        'promote.right.manage_welcome_messages': '{emoji} Gérer les messages de bienvenue',
        'promote.right.other': '{emoji} Autres droits',
        'chat.not_channel': '<tg-emoji emoji-id="5870693687691841267">📣</tg-emoji> <b>Cela ne fonctionne que dans les supergroupes et les canaux.</b>',
        'chat.no_rights': '<tg-emoji emoji-id="5870704313440932932">🔓</tg-emoji> <b>Pas assez de droits pour modifier ce chat.</b>',
        'chat.usage.slow': '<b>Usage :</b> <code>{prefix}slow</code> off, ou <code>30</code>, <code>1m</code>, <code>5m</code>, <code>1h</code>.',
        'chat.usage.about': "<b>Usage :</b> <code>{prefix}setabout texte</code>. <code>-</code> l'efface.",
        'chat.usage.photo': '<b>Usage :</b> répondez à une photo avec <code>{prefix}setphoto</code>. <code>-</code> la retire.',
        'chat.usage.username': '<b>Usage :</b> <code>{prefix}setusername nom</code>. <code>-</code> le retire.',
        'chat.usage.link': '<b>Usage :</b> <code>{prefix}link</code>, <code>new</code>, <code>revoke</code> ou <code>titre</code>.',
        'chat.slow_off': '<tg-emoji emoji-id="5870729937215819584">🕐</tg-emoji> <b>Le mode lent est désactivé.</b>',
        'chat.slow_on': '<tg-emoji emoji-id="5870729937215819584">🕐</tg-emoji> <b>Mode lent :</b> <code>{seconds}</code> s',
        'chat.about_set': '<tg-emoji emoji-id="5870676941614354370">🖋</tg-emoji> <b>Description mise à jour.</b>',
        'chat.about_cleared': '<tg-emoji emoji-id="5255831443816327915">🗑</tg-emoji> <b>Description effacée.</b>',
        'chat.photo_set': '<tg-emoji emoji-id="5870782662234346251">🖼️</tg-emoji> <b>Photo du chat mise à jour.</b>',
        'chat.photo_cleared': '<tg-emoji emoji-id="5255831443816327915">🗑</tg-emoji> <b>Photo du chat retirée.</b>',
        'chat.username_set': '<tg-emoji emoji-id="5870527201874546272">🔗</tg-emoji> <b>Nom d\'utilisateur :</b> @{username}',
        'chat.username_cleared': '<tg-emoji emoji-id="5255831443816327915">🗑</tg-emoji> <b>Nom d\'utilisateur retiré.</b>',
        'chat.sign_on': '<tg-emoji emoji-id="5870676941614354370">🖋</tg-emoji> <b>Les signatures d\'auteur sont activées.</b>',
        'chat.sign_off': '<tg-emoji emoji-id="5870676941614354370">🖋</tg-emoji> <b>Les signatures d\'auteur sont désactivées.</b>',
        'chat.forum_on': '<tg-emoji emoji-id="5872886929921413168">💬</tg-emoji> <b>Les sujets sont activés.</b>',
        'chat.forum_off': '<tg-emoji emoji-id="5872886929921413168">💬</tg-emoji> <b>Les sujets sont désactivés.</b>',
        'chat.spam_on': '<tg-emoji emoji-id="5870704313440932932">🛡</tg-emoji> <b>L\'antispam agressif est activé.</b>',
        'chat.spam_off': '<tg-emoji emoji-id="5870704313440932932">🛡</tg-emoji> <b>L\'antispam agressif est désactivé.</b>',
        'chat.hidden_on': '<tg-emoji emoji-id="5870542612217204751">👁</tg-emoji> <b>La liste des membres est masquée.</b>',
        'chat.hidden_off': '<tg-emoji emoji-id="5870542612217204751">👁</tg-emoji> <b>La liste des membres est visible.</b>',
        'chat.history_on': '<tg-emoji emoji-id="5870729937215819584">🕐</tg-emoji> <b>Les nouveaux membres voient l\'historique.</b>',
        'chat.history_off': '<tg-emoji emoji-id="5870729937215819584">🕐</tg-emoji> <b>L\'historique est masqué aux nouveaux membres.</b>',
        'chat.join_on': '<tg-emoji emoji-id="5870892901159932239">🔀</tg-emoji> <b>Les demandes d\'adhésion sont activées.</b>',
        'chat.join_off': '<tg-emoji emoji-id="5870892901159932239">🔀</tg-emoji> <b>Les demandes d\'adhésion sont désactivées.</b>',
        'chat.link_none': '<tg-emoji emoji-id="5870527201874546272">🔗</tg-emoji> <b>Pas encore de lien d\'invitation.</b>',
        'chat.link': '<tg-emoji emoji-id="5870527201874546272">🔗</tg-emoji> <b>Invitation :</b> {link}',
        'chat.link_revoked': '<tg-emoji emoji-id="5255831443816327915">🗑</tg-emoji> <b>Invitation révoquée.</b>\n<tg-emoji emoji-id="5870527201874546272">🔗</tg-emoji> <b>Nouveau :</b> {link}',
        'chat.link_created': '<tg-emoji emoji-id="5870633910337015697">✅</tg-emoji> <b>Invitation créée.</b>\n<tg-emoji emoji-id="5870527201874546272">🔗</tg-emoji> {link}',
        'rights.header': '<tg-emoji emoji-id="5870684638195748414">👑</tg-emoji> <b>{name}</b> [<code>{user_id}</code>]\n<b>Rôle :</b> {role}\n<b>Rang :</b> {rank}',
        'rights.owner': 'Propriétaire',
        'rights.admin': 'Admin',
        'rights.member': 'Membre',
        'rights.none': '<tg-emoji emoji-id="5870657884844462243">✖️</tg-emoji> <b>{name}</b> [<code>{user_id}</code>] <b>n\'est pas admin.</b>',
        'rights.empty': '<i>Aucun droit.</i>',
    }

    strings_ja = {
        'name': 'Helm',
        'cfg.warnlimit': '制限までの警告回数',
        'cfg.ptime': '処罰の既定の期間',
        'cfg.wl_punishment': '警告上限に達したときの処罰',
        'cfg.wl_reason': '上限処罰の理由',
        'cfg.wl_timespan': '上限処罰の期間',
        'error.wrongchattype.pm': '<tg-emoji emoji-id="5870563425628721113">📧</tg-emoji> <b>このモジュールはPMでは使用できません。</b>\nグループチャット用です。',
        'error.wrongchattype.channel': '<tg-emoji emoji-id="5870693687691841267">📣</tg-emoji> <b>このモジュールはチャンネルでは使用できません。</b>\nグループチャット用です。',
        'error.no_args.user': '<tg-emoji emoji-id="5870994129244131212">👤</tg-emoji> <b>ユーザーを指定する必要があります。</b>\nユーザー名、ID、またはメッセージへの返信を使用してください。',
        'error.locate_user': '<tg-emoji emoji-id="5870974879200711167">🔎</tg-emoji> <b>ユーザーが見つかりませんでした。</b>\nユーザー名またはIDを再確認してください。',
        'error.can_not_restrict': '<tg-emoji emoji-id="5870704313440932932">🔓</tg-emoji> <b>ユーザーを制限できませんでした。</b>\n必要な権限がないか、権限のない管理者をBanしようとしています。',
        'error.reply_is_service': '<tg-emoji emoji-id="5870982283724328568">⚙️</tg-emoji> <b>サービスメッセージに返信してユーザーを制限することはできません。</b>\nユーザーのメッセージに返信してください。',
        'error.self': '<tg-emoji emoji-id="5872988737826197458">🔫</tg-emoji> <b>自分自身を制限することはできません。</b>\nそんなに自虐的にならないでください。',
        'error.warn_self': '<tg-emoji emoji-id="5870948572526022116">☝🏻</tg-emoji> <b>悪い子ですね。</b>\n遊んでいないでモデレーションをしてください。',
        'error.no_args.rights': '<tg-emoji emoji-id="5872996816659681395">❓</tg-emoji> <b>権限を指定する必要があります。</b>\n権限は数列です（例：すべての権限を設定するには`123456789ab`）。反転させるには先頭に`r`を付けます。',
        'error.no_user': '<tg-emoji emoji-id="5870994129244131212">👤</tg-emoji> <b>ユーザーを指定してください。</b>\n返信、ユーザー名、またはID。',
        'error.no_reply': '<tg-emoji emoji-id="5872886929921413168">💬</tg-emoji> <b>メッセージに返信してください。</b>',
        'error.invalid_args': '<tg-emoji emoji-id="5872996816659681395">❓</tg-emoji> <b>形式:</b> <code>g</code> か <code>c</code>、その後に名前。末尾の <code>30m</code>、<code>2h</code>、<code>1d</code> で後から削除。',
        'error.too_much': '<tg-emoji emoji-id="5870657884844462243">❌</tg-emoji> <b>不正な数です</b>\n1から100までの数を使用してください。',
        'error.insufficient_rights': '<tg-emoji emoji-id="5870704313440932932">🔓</tg-emoji> <b>権限が足りません。</b>',
        'error.unknown': '<tg-emoji emoji-id="5870657884844462243">🙅🏻\u200d♂️</tg-emoji> <b>不明なエラー</b>',
        'error': '<b>エラー:</b> <code>{error}</code>',
        'done.muted.f': '<tg-emoji emoji-id="5870681133502435302">🔇</tg-emoji> <b>{user} を永久にミュートしました</b>',
        'done.muted': '<tg-emoji emoji-id="5870681133502435302">🔇</tg-emoji> <b>{user} を {timespan} ミュートしました</b>',
        'done.warned': '<tg-emoji emoji-id="5870931487146119264">⚠</tg-emoji> <b>{user} に警告しました</b>',
        'done.banned.f': '<tg-emoji emoji-id="5872988737826197458">⛔</tg-emoji> <b>{user} を永久にBanしました</b>',
        'done.banned': '<tg-emoji emoji-id="5872988737826197458">⛔</tg-emoji> <b>{user} を {timespan} Banしました</b>',
        'done.kicked': '<tg-emoji emoji-id="5870778972857438051">🍃</tg-emoji> <b>{user} をキックしました</b>',
        'done.nomedia': '<tg-emoji emoji-id="5870782662234346251">🖼️</tg-emoji> <b>{user} は {timespan} メディアを送信できなくなりました</b>',
        'done.nomedia.f': '<tg-emoji emoji-id="5870782662234346251">🖼️</tg-emoji> <b>{user} はメディアを送信できなくなりました</b>',
        'done.allowmedia': '<tg-emoji emoji-id="5870782662234346251">🖼️</tg-emoji> <b>{user} は再びメディアを送信できます</b>',
        'done.setrights.f': '<tg-emoji emoji-id="5870982283724328568">🔧</tg-emoji> <b><code>{user}</code> の権限を {rights} に設定しました</b>',
        'done.setrights': '<tg-emoji emoji-id="5870982283724328568">🔧</tg-emoji> <b><code>{user}</code> の権限を {timespan} の間 {rights} に設定しました</b>',
        'done.unmuted': '<tg-emoji emoji-id="5870693687691841267">🔊</tg-emoji> <b>{user} のミュートを解除しました</b>',
        'done.unbanned': '<tg-emoji emoji-id="5870948572526022116">👋🏻</tg-emoji> <b>{user} のBanを解除しました</b>',
        'done.unwarned.one': '<tg-emoji emoji-id="5870930636742595124">⚖️</tg-emoji> <b>{user} の警告を1つ解除しました</b>',
        'done.unwarned.all': '<tg-emoji emoji-id="5870930636742595124">⚖️</tg-emoji> <b><code>{user}</code> のすべての警告を解除しました</b>',
        'done.da_kicked': '<tg-emoji emoji-id="5870778972857438051">🍃</tg-emoji> <b><code>{amount}</code> 件の削除済みアカウントがキックされました</b>',
        'done.pin': '<tg-emoji emoji-id="5870930744116776638">📌</tg-emoji> <b>ピン留めしました</b>',
        'done.unpin': '<tg-emoji emoji-id="5870930744116776638">📌</tg-emoji> <b>ピン留めを解除しました</b>',
        'done.channel_ban.on': '<tg-emoji emoji-id="5870704313440932932">🔒</tg-emoji> <b>ユーザーはチャンネル名義でメッセージを送信できなくなりました。</b>',
        'done.channel_ban.off': '<tg-emoji emoji-id="5870704313440932932">🔓</tg-emoji> <b>ユーザーは再びチャンネル名義でメッセージを送信できるようになりました。</b>',
        'done.channel_ban.action': '<tg-emoji emoji-id="5872988737826197458">⛔</tg-emoji> <b>{user} は永久にBanされました</b>\n<b>理由:</b> チャンネル名義での送信',
        'done.flushda': '<tg-emoji emoji-id="5870778972857438051">🍃</tg-emoji> <b><code>{amt}</code> 件の削除済みアカウントを削除しました</b>',
        'done.glban.f': '<tg-emoji emoji-id="5870718740236079262">🌍</tg-emoji> <b>{user} を {count} 件のチャットで永久にBanしました</b>',
        'done.glban': '<tg-emoji emoji-id="5870718740236079262">🌍</tg-emoji> <b>{user} を {count} 件のチャットで {timespan} Banしました</b>',
        'done.glunban': '<tg-emoji emoji-id="5870718740236079262">🌍</tg-emoji> <b>{user} を {count} 件のチャットで解除しました</b>',
        'done.leave': '<tg-emoji emoji-id="5870764288364252592">😶</tg-emoji> <b>退出します。</b>',
        'done.leave.reason': '<tg-emoji emoji-id="5870764288364252592">😶</tg-emoji> <b>退出します。</b>\n<b>理由:</b> <i>{reason}</i>',
        'reason': '\n<b>理由:</b> <i>{0}</i>',
        'chat_id': '<tg-emoji emoji-id="5870772616305839506">👥</tg-emoji> <b>チャットID</b>: <code>{chat_id}</code>{additional}\n<tg-emoji emoji-id="5870994129244131212">👤</tg-emoji> <b>あなたのID</b>: <code>{my_id}</code>',
        'person_in_reply_id': '<tg-emoji emoji-id="5870772616305839506">🫂</tg-emoji> <b>返信先のID</b>: <code>{reply_id}</code>',
        'sys.DA': '削除済みアカウント',
        'sys.LANG': 'en_US',
        'sys.forever': '永久',
        'of_chat': 'チャット',
        'of_channel': 'チャンネル',
        'loading': '<tg-emoji emoji-id="5870813306826002498">🟡</tg-emoji> <b>データを読み込んでいます...</b>',
        'own_list': '<b>私の所有リスト ({count}):</b>\n\n{msg}',
        'no_ownerships': '<tg-emoji emoji-id="5870657884844462243">❌</tg-emoji> <b>所有しているチャットはありません。</b>',
        'not_a_chat': '<tg-emoji emoji-id="5870931487146119264">⚠️</tg-emoji> <b>これはグループでのみ機能します！</b>',
        'admins_in_chat': '<tg-emoji emoji-id="5870684638195748414">👑</tg-emoji> <b><code>{title}</code> の管理者 ({count}):</b>\n\n',
        'admins_in_chat_caption': '<b>"{}" の管理者:</b>',
        'too_many_admins': '管理者が多すぎます。リストをファイルに保存しています...',
        'no_admins_in_chat': '<b>このチャットには管理者がいません。</b>',
        'bots_in_chat': '<tg-emoji emoji-id="5870531058755178453">🤖</tg-emoji> <b><code>{title}</code> のボット ({count}):</b>\n\n',
        'bots_in_chat_caption': '<b><code>{}</code> のボット:</b>',
        'too_many_bots': 'ボットが多すぎます。リストをファイルに保存しています...',
        'no_bots_in_chat': '<b>このチャットにはボットがいません。</b>',
        'users_in_chat': '<tg-emoji emoji-id="5870994129244131212">👤</tg-emoji> <b><code>{title}</code> のユーザー ({count}):</b>\n\n',
        'users_in_chat_caption': '<b><code>{}</code> のユーザー:</b>',
        'no_user_in_chat': '<b>このチャットにはユーザーがいません。</b>',
        'too_many_users': '参加者が多すぎます。リストをファイルで送ります…',
        'chat_muted': '<tg-emoji emoji-id="5870681133502435302">🔇</tg-emoji> <b>参加者のチャットがミュートされました。</b>',
        'chat_unmuted': '<tg-emoji emoji-id="5870633910337015697">✅</tg-emoji> <b>すべての参加者にチャットが開放されました。</b>',
        'title_changed': '<b>{type_of} のタイトルが <code>{old_title}</code> から <code>{new_title}</code> に変更されました。</b>',
        'user_invited': '<tg-emoji emoji-id="5870633910337015697">✅</tg-emoji> <b>ユーザー <a href=\'tg://user?id={id}\'>{user}</a> をチャットに招待しました。</b>',
        'creator': '<tg-emoji emoji-id="5870684638195748414">👑</tg-emoji> <b>作成者: <a href=\'tg://user?id={id}\'>{creator}</a>。</b>',
        'no_creator': '<tg-emoji emoji-id="5870657884844462243">❌</tg-emoji> <b>作成者が見つかりません。</b>',
        'channel_created': '<tg-emoji emoji-id="5870633910337015697">✅</tg-emoji> <b>チャンネル <code>{title}</code> が作成されました。\n</b><tg-emoji emoji-id="5870527201874546272">🔗</tg-emoji><b> 招待リンク: {link}</b>',
        'group_created': '<tg-emoji emoji-id="5870633910337015697">✅</tg-emoji> <b>グループ <code>{title}</code> が作成されました。\n</b><tg-emoji emoji-id="5870527201874546272">🔗</tg-emoji><b> 招待リンク: {link}</b>',
        'temp_chat': '\n<tg-emoji emoji-id="5870875489362513438">🗑</tg-emoji> <b>{timespan} 後に自動で削除されます。</b>',
        'type_group': 'グループ',
        'type_channel': 'チャンネル',
        'type_unknown': '不明',
        'yes': '<tg-emoji emoji-id="5870633910337015697">✅</tg-emoji> はい',
        'no': '<tg-emoji emoji-id="5870657884844462243">✖️</tg-emoji> いいえ',
        'all_approved': '<tg-emoji emoji-id="5870633910337015697">✅</tg-emoji> <b>承認されました</b>',
        'all_dismissed': '<tg-emoji emoji-id="5870657884844462243">✖️</tg-emoji> <b>リクエストが拒否されました</b>',
        'log_text': '<tg-emoji emoji-id="5870994129244131212">👤</tg-emoji> <b>ユーザー:</b> {user}\n<tg-emoji emoji-id="5870704313440932932">🔒</tg-emoji> <b>管理者:</b> {admin}\n<tg-emoji emoji-id="5872988737826197458">⛔️</tg-emoji> <b>処分:</b> {punishment}{reason}{time}{chat}',
        'log_chat': '\n<tg-emoji emoji-id="5872886929921413168">💬</tg-emoji> <b>チャット:</b> {chat}',
        'log_reason': '\n<tg-emoji emoji-id="5870676941614354370">🖋</tg-emoji> <b>理由:</b> {reason}',
        'log_time': '\n<tg-emoji emoji-id="5870729937215819584">⏰️</tg-emoji> <b>期間:</b> {time}',
        'act.mute': 'ミュート',
        'act.ban': 'Ban',
        'act.kick': 'キック',
        'act.unmute': 'ミュート解除',
        'act.unban': 'Ban解除',
        'act.warn': '警告',
        'act.nomedia': 'メディア制限',
        'act.allowmedia': 'メディア許可',
        'act.rights': '権限変更',
        'flushda.loading': '<tg-emoji emoji-id="5870813306826002498">🟡</tg-emoji> <b>削除済みアカウントを除いています…</b>',
        'flushda.loading.chat': '<tg-emoji emoji-id="5870813306826002498">🟡</tg-emoji> <b>このチャットから削除済みアカウントを除いています…</b>',
        'flushda.loading.channels': '<tg-emoji emoji-id="5870813306826002498">🟡</tg-emoji> <b>チャンネルから削除済みアカウントを除いています…</b>',
        'monday': '月曜日',
        'tuesday': '火曜日',
        'wednesday': '水曜日',
        'thursday': '木曜日',
        'friday': '金曜日',
        'saturday': '土曜日',
        'sunday': '日曜日',
        'cfg.gban_except': '.gban と .ungban の対象外にするチャットID',
        'cfg.gban_pm_block': '.gban でDMをブロックし、.ungban で解除する',
        'cfg.gban_pm_del_history': 'ブロック時にDMの履歴も削除する',
        'cfg.gban_pm_except': 'DMでブロックしないユーザーID',
        'cfg.global_logs': '自分のコマンドだけでなく、管理している全チャットの制限を記録する',
        'gban.no_reason': '未指定',
        'gban.args': '<tg-emoji emoji-id="5870994129244131212">👤</tg-emoji> <b>ユーザーを指定してください。</b>\n返信するか、ユーザー名かIDを渡してください。',
        'gban.working': '<tg-emoji emoji-id="5870718740236079262">🌍</tg-emoji> <b><a href="{url}">{name}</a> を全チャットでBanしています…</b>',
        'gban.unworking': '<tg-emoji emoji-id="5870718740236079262">🌍</tg-emoji> <b><a href="{url}">{name}</a> のBanを全チャットで解除しています…</b>',
        'gban.done': '<tg-emoji emoji-id="5872988737826197458">⛔</tg-emoji> <b><a href="{url}">{name}</a> を {count} 件のチャットでBanしました</b>\n<b>理由:</b> <i>{reason}</i>',
        'gban.undone': '<tg-emoji emoji-id="5870948572526022116">👋🏻</tg-emoji> <b><a href="{url}">{name}</a> を {count} 件のチャットで解除しました</b>',
        'gban.chats': '\n{chats}',
        'gban.pm_blocked': '\n<tg-emoji emoji-id="5872988737826197458">🚫</tg-emoji> <b>DMをブロックしました</b>',
        'gban.pm_unblocked': '\n<tg-emoji emoji-id="5870948572526022116">👋🏻</tg-emoji> <b>DMのブロックを解除しました</b>',
        'gban.pm_failed': '\n<tg-emoji emoji-id="5870704313440932932">🔓</tg-emoji> <b>DMをブロックできませんでした</b>',
        'gban.pm_cleared': ' · <b>DMの履歴を削除しました</b>',
        'chatinfo': '<tg-emoji emoji-id="5870704313440932932">🔒</tg-emoji><b> 種類: {type_of}\n</b><tg-emoji emoji-id="5870495350397079101">#️⃣</tg-emoji><b> チャットID: </b><code>{id}</code><b>\n</b><tg-emoji emoji-id="5873225338984599714">🔥</tg-emoji><b> 名前: {title}\n\n</b><tg-emoji emoji-id="5870676941614354370">🖋</tg-emoji><b> 説明: {about}\n\n</b><tg-emoji emoji-id="5870684638195748414">👑</tg-emoji><b> 管理者: {admins_count}\n</b><tg-emoji emoji-id="5870633910337015697">✅</tg-emoji><b> オンライン: {online_count}\n</b><tg-emoji emoji-id="5870994129244131212">👤</tg-emoji><b> 参加者: {participants_count}\n</b><tg-emoji emoji-id="5872988737826197458">🚫</tg-emoji><b> キック済み: {kicked_count}\n</b><tg-emoji emoji-id="5870892901159932239">🔀</tg-emoji><b> 参加申請: {requests_pending}\n\n</b><tg-emoji emoji-id="5870729937215819584">🕐</tg-emoji><b> 低速モード: {slowmode_seconds}\n</b><tg-emoji emoji-id="5872980989705196227">📞</tg-emoji><b> 通話: {call}\n</b><tg-emoji emoji-id="5870875489362513438">🗑</tg-emoji><b> TTL: {ttl_period}\n</b><tg-emoji emoji-id="5870994129244131212">👤</tg-emoji><b> 最近の申請者: {recent_requesters}\n\n</b><tg-emoji emoji-id="5870772616305839506">👥</tg-emoji><b> リンク先チャット: {linked_chat_id}\n</b><tg-emoji emoji-id="5870704313440932932">🛡</tg-emoji><b> 迷惑対策: {antispam}\n</b><tg-emoji emoji-id="5870542612217204751">👁</tg-emoji><b> 参加者非表示: {participants_hidden}\n\n</b><tg-emoji emoji-id="5870527201874546272">🔗</tg-emoji><b> リンク: {link}</b>',
        'userinfo': '<blockquote><tg-emoji emoji-id="5870495350397079101">#️⃣</tg-emoji><b> ID: {user_id}\n</b><tg-emoji emoji-id="5873225338984599714">🔥</tg-emoji><b> 名: {first_name}\n</b><tg-emoji emoji-id="5873225338984599714">🔥</tg-emoji><b> 姓: {last_name}\n</b><tg-emoji emoji-id="5872980989705196227">📞</tg-emoji><b> 電話: {phone}\n</b><tg-emoji emoji-id="5870998024779468554">🐶</tg-emoji><b> ユーザー名: {usernames}</b></blockquote><b>\n</b><blockquote><tg-emoji emoji-id="5870609858520158157">ℹ️</tg-emoji><b> 自己紹介: {about}</b></blockquote><b>\n</b><blockquote><tg-emoji emoji-id="5870729937215819584">🕐</tg-emoji><b> 営業時間: </b>{business_work_hours}\n<tg-emoji emoji-id="5870450871715761518">❤️</tg-emoji><b> 絵文字ステータス: {emoji_status}</b></blockquote><b>\n</b><blockquote><tg-emoji emoji-id="5870693687691841267">🔉</tg-emoji><b> チャンネル: {personal_channel}\n</b><tg-emoji emoji-id="5870847962917113498">🎂</tg-emoji><b> 誕生日: {birthday}\n</b><tg-emoji emoji-id="5870478797593120516">🎁</tg-emoji><b> ギフト: {stargifts_count}</b></blockquote><b>\n</b><blockquote><tg-emoji emoji-id="5870931487146119264">🚨</tg-emoji><b> 共通チャット数: {common_chats_count}\n</b><tg-emoji emoji-id="5870772616305839506">👥</tg-emoji><b> 共通チャット: {common_chats}</b></blockquote>',
        'promote.no_rights': '<tg-emoji emoji-id="5870704313440932932">🔓</tg-emoji> <b>管理者を変更する権限がありません。</b>',
        'promote.no_user': '<tg-emoji emoji-id="5870994129244131212">👤</tg-emoji> <b>ユーザーを指定してください。</b>\n返信するか、ユーザー名かIDを渡してください。',
        'promote.demoted': '<tg-emoji emoji-id="5870948572526022116">👋🏻</tg-emoji> <b>{name}</b> [<code>{user_id}</code>] <b>は管理者ではなくなりました。</b>',
        'promote.promoted_full': '<tg-emoji emoji-id="5870684638195748414">👑</tg-emoji> <b>{name}</b> [<code>{user_id}</code>] <b>を全権限の管理者にしました。</b>\n<b>肩書き:</b> {rank}',
        'promote.promoted': '<tg-emoji emoji-id="5870684638195748414">👑</tg-emoji> <b>{name}</b> [<code>{user_id}</code>] <b>を管理者にしました。</b>\n<b>肩書き:</b> {rank}',
        'promote.choose': '<tg-emoji emoji-id="5870684638195748414">👑</tg-emoji> <b>{name} の管理者権限</b> [<code>{user_id}</code>]\n<b>肩書き:</b> {rank}',
        'promote.confirm': '確認',
        'promote.default_rank': '管理者',
        'promote.tag_group_only': '<tg-emoji emoji-id="5870931487146119264">⚠️</tg-emoji> <b>メンバータグはグループでのみ使えます。</b>',
        'promote.tag_usage': '<b>使い方:</b> <code>{prefix}settag @user タグ</code>、または返信で <code>{prefix}settag タグ</code>。タグなし、または <code>-</code> で外します。',
        'promote.tag_invalid': '<tg-emoji emoji-id="5870657884844462243">❌</tg-emoji> <b>タグは16文字以内、絵文字なしです。</b>',
        'promote.tag_no_rights': '<tg-emoji emoji-id="5870704313440932932">🔓</tg-emoji> <b>他人のタグを変えるには「メンバータグの管理」が必要です。</b>',
        'promote.tag_updated': '<tg-emoji emoji-id="5870676941614354370">🖋</tg-emoji> <b>{name} のタグ:</b> <code>{rank}</code>',
        'promote.tag_removed': '<tg-emoji emoji-id="5255831443816327915">🗑</tg-emoji> <b>{name} のタグを外しました。</b>',
        'promote.rpc_error': '<tg-emoji emoji-id="5870657884844462243">❌</tg-emoji> <b>Telegramのエラー:</b> <code>{error}</code>',
        'promote.right.change_info': '{emoji} {where}の情報を変更',
        'promote.right.post_messages': '{emoji} メッセージを投稿',
        'promote.right.edit_messages': '{emoji} 投稿を編集',
        'promote.right.delete_messages': '{emoji} メッセージを削除',
        'promote.right.ban_users': '{emoji} ユーザーを制限',
        'promote.right.invite_users': '{emoji} ユーザーを招待',
        'promote.right.pin_messages': '{emoji} メッセージを固定',
        'promote.right.add_admins': '{emoji} 管理者を追加',
        'promote.right.anonymous': '{emoji} 匿名',
        'promote.right.manage_call': '{emoji} 通話を管理',
        'promote.right.manage_topics': '{emoji} トピックを管理',
        'promote.right.post_stories': '{emoji} ストーリーを投稿',
        'promote.right.edit_stories': '{emoji} ストーリーを編集',
        'promote.right.delete_stories': '{emoji} ストーリーを削除',
        'promote.right.manage_direct_messages': '{emoji} ダイレクトメッセージを管理',
        'promote.right.manage_ranks': '{emoji} メンバータグを管理',
        'promote.right.manage_linked_peers': '{emoji} リンク先チャットを管理',
        'promote.right.manage_welcome_messages': '{emoji} ウェルカムメッセージを管理',
        'promote.right.other': '{emoji} その他の権限',
        'chat.not_channel': '<tg-emoji emoji-id="5870693687691841267">📣</tg-emoji> <b>スーパーグループとチャンネルでのみ使えます。</b>',
        'chat.no_rights': '<tg-emoji emoji-id="5870704313440932932">🔓</tg-emoji> <b>このチャットを変更する権限がありません。</b>',
        'chat.usage.slow': '<b>使い方:</b> <code>{prefix}slow</code> off、または <code>30</code>、<code>1m</code>、<code>5m</code>、<code>1h</code>。',
        'chat.usage.about': '<b>使い方:</b> <code>{prefix}setabout テキスト</code>。<code>-</code> で消します。',
        'chat.usage.photo': '<b>使い方:</b> 写真に返信して <code>{prefix}setphoto</code>。<code>-</code> で外します。',
        'chat.usage.username': '<b>使い方:</b> <code>{prefix}setusername 名前</code>。<code>-</code> で外します。',
        'chat.usage.link': '<b>使い方:</b> <code>{prefix}link</code>、<code>new</code>、<code>revoke</code>、または <code>タイトル</code>。',
        'chat.slow_off': '<tg-emoji emoji-id="5870729937215819584">🕐</tg-emoji> <b>スローモードはオフです。</b>',
        'chat.slow_on': '<tg-emoji emoji-id="5870729937215819584">🕐</tg-emoji> <b>スローモード:</b> <code>{seconds}</code>秒',
        'chat.about_set': '<tg-emoji emoji-id="5870676941614354370">🖋</tg-emoji> <b>説明を更新しました。</b>',
        'chat.about_cleared': '<tg-emoji emoji-id="5255831443816327915">🗑</tg-emoji> <b>説明を消しました。</b>',
        'chat.photo_set': '<tg-emoji emoji-id="5870782662234346251">🖼️</tg-emoji> <b>チャット写真を更新しました。</b>',
        'chat.photo_cleared': '<tg-emoji emoji-id="5255831443816327915">🗑</tg-emoji> <b>チャット写真を外しました。</b>',
        'chat.username_set': '<tg-emoji emoji-id="5870527201874546272">🔗</tg-emoji> <b>ユーザー名:</b> @{username}',
        'chat.username_cleared': '<tg-emoji emoji-id="5255831443816327915">🗑</tg-emoji> <b>ユーザー名を外しました。</b>',
        'chat.sign_on': '<tg-emoji emoji-id="5870676941614354370">🖋</tg-emoji> <b>投稿者名の表示はオンです。</b>',
        'chat.sign_off': '<tg-emoji emoji-id="5870676941614354370">🖋</tg-emoji> <b>投稿者名の表示はオフです。</b>',
        'chat.forum_on': '<tg-emoji emoji-id="5872886929921413168">💬</tg-emoji> <b>トピックはオンです。</b>',
        'chat.forum_off': '<tg-emoji emoji-id="5872886929921413168">💬</tg-emoji> <b>トピックはオフです。</b>',
        'chat.spam_on': '<tg-emoji emoji-id="5870704313440932932">🛡</tg-emoji> <b>強力なスパム対策はオンです。</b>',
        'chat.spam_off': '<tg-emoji emoji-id="5870704313440932932">🛡</tg-emoji> <b>強力なスパム対策はオフです。</b>',
        'chat.hidden_on': '<tg-emoji emoji-id="5870542612217204751">👁</tg-emoji> <b>メンバー一覧は非表示です。</b>',
        'chat.hidden_off': '<tg-emoji emoji-id="5870542612217204751">👁</tg-emoji> <b>メンバー一覧は表示されます。</b>',
        'chat.history_on': '<tg-emoji emoji-id="5870729937215819584">🕐</tg-emoji> <b>新しいメンバーは履歴を見られます。</b>',
        'chat.history_off': '<tg-emoji emoji-id="5870729937215819584">🕐</tg-emoji> <b>新しいメンバーには履歴を隠します。</b>',
        'chat.join_on': '<tg-emoji emoji-id="5870892901159932239">🔀</tg-emoji> <b>参加申請はオンです。</b>',
        'chat.join_off': '<tg-emoji emoji-id="5870892901159932239">🔀</tg-emoji> <b>参加申請はオフです。</b>',
        'chat.link_none': '<tg-emoji emoji-id="5870527201874546272">🔗</tg-emoji> <b>招待リンクはまだありません。</b>',
        'chat.link': '<tg-emoji emoji-id="5870527201874546272">🔗</tg-emoji> <b>招待:</b> {link}',
        'chat.link_revoked': '<tg-emoji emoji-id="5255831443816327915">🗑</tg-emoji> <b>招待を取り消しました。</b>\n<tg-emoji emoji-id="5870527201874546272">🔗</tg-emoji> <b>新しいリンク:</b> {link}',
        'chat.link_created': '<tg-emoji emoji-id="5870633910337015697">✅</tg-emoji> <b>招待を作成しました。</b>\n<tg-emoji emoji-id="5870527201874546272">🔗</tg-emoji> {link}',
        'rights.header': '<tg-emoji emoji-id="5870684638195748414">👑</tg-emoji> <b>{name}</b> [<code>{user_id}</code>]\n<b>役割:</b> {role}\n<b>肩書:</b> {rank}',
        'rights.owner': 'オーナー',
        'rights.admin': '管理者',
        'rights.member': 'メンバー',
        'rights.none': '<tg-emoji emoji-id="5870657884844462243">✖️</tg-emoji> <b>{name}</b> [<code>{user_id}</code>] <b>は管理者ではありません。</b>',
        'rights.empty': '<i>権限なし。</i>',
    }

    strings_jp = strings_ja

    strings_uk = {
        'name': 'Helm',
        'cfg.warnlimit': 'Скільки попереджень до обмеження',
        'cfg.ptime': 'Термін покарання за замовчуванням',
        'cfg.wl_punishment': 'Що робити при досягненні ліміту попереджень',
        'cfg.wl_reason': 'Причина покарання за ліміт',
        'cfg.wl_timespan': 'На скільки карати за ліміт',
        'error.wrongchattype.pm': '<tg-emoji emoji-id="5870563425628721113">📧</tg-emoji> <b>Ви не можете використовувати цей модуль в ПП.</b>\nМодуль призначений для груп.',
        'error.wrongchattype.channel': '<tg-emoji emoji-id="5870693687691841267">📣</tg-emoji> <b>Ви не можете використовувати цей модуль в каналах.</b>\nМодуль призначений для груп.',
        'error.no_args.user': '<tg-emoji emoji-id="5870994129244131212">👤</tg-emoji> <b>Вам потрібно вказати користувача.</b>\nВи можете використовувати юзернейм, ID або відповісти на повідомлення.',
        'error.locate_user': '<tg-emoji emoji-id="5870974879200711167">🔎</tg-emoji> <b>Не вдалося знайти користувача.</b>\nПеревірте юзернейм або ID.',
        'error.can_not_restrict': '<tg-emoji emoji-id="5870704313440932932">🔓</tg-emoji> <b>Не вдалося обмежити користувача.</b>\nМожливо, у вас недостатньо прав або ви намагаєтесь забанити адміністратора, якого підвищили не ви.',
        'error.reply_is_service': '<tg-emoji emoji-id="5870982283724328568">⚙️</tg-emoji> <b>Ви не можете обмежити користувача, відповівши на службове повідомлення.</b>\nДайте відповідь на повідомлення користувача.',
        'error.self': '<tg-emoji emoji-id="5872988737826197458">🔫</tg-emoji> <b>Ви не можете обмежити себе.</b>\nНе будьте таким самокритичним.',
        'error.warn_self': '<tg-emoji emoji-id="5870948572526022116">☝🏻</tg-emoji> <b>Ата-та.</b>\nДосить гратися, займіться модерацією.',
        'error.no_args.rights': '<tg-emoji emoji-id="5872996816659681395">❓</tg-emoji> <b>Вам потрібно вказати права.</b>\nПрава — це послідовність (наприклад, `123456789ab` для встановлення всіх прав). Додайте `r` перед рядком, щоб інвертувати права.',
        'error.no_user': '<tg-emoji emoji-id="5870994129244131212">👤</tg-emoji> <b>Вкажи користувача.</b>\nВідповіддю, юзернеймом або ID.',
        'error.no_reply': '<tg-emoji emoji-id="5872886929921413168">💬</tg-emoji> <b>Відповідай на повідомлення.</b>',
        'error.invalid_args': '<tg-emoji emoji-id="5872996816659681395">❓</tg-emoji> <b>Формат:</b> <code>g</code> або <code>c</code>, потім назва. В кінці <code>30m</code>, <code>2h</code> або <code>1d</code> — чат видалиться сам.',
        'error.too_much': '<tg-emoji emoji-id="5870657884844462243">❌</tg-emoji> <b>Невірна кількість</b>\nВикористовуйте число від 1 до 100.',
        'error.insufficient_rights': '<tg-emoji emoji-id="5870704313440932932">🔓</tg-emoji> <b>Недостатньо прав.</b>',
        'error.unknown': '<tg-emoji emoji-id="5870657884844462243">🙅🏻\u200d♂️</tg-emoji> <b>Невідома помилка</b>',
        'error': '<b>Помилка:</b> <code>{error}</code>',
        'done.muted.f': '<tg-emoji emoji-id="5870681133502435302">🔇</tg-emoji> <b>{user} більше не зможе відправляти повідомлення</b>',
        'done.muted': '<tg-emoji emoji-id="5870681133502435302">🔇</tg-emoji> <b>{user} не зможе відправляти повідомлення {timespan}</b>',
        'done.warned': '<tg-emoji emoji-id="5870931487146119264">⚠</tg-emoji> <b>{user} отримав попередження</b>',
        'done.banned.f': '<tg-emoji emoji-id="5872988737826197458">⛔</tg-emoji> <b>{user} був забанений назавжди</b>',
        'done.banned': '<tg-emoji emoji-id="5872988737826197458">⛔</tg-emoji> <b>{user} був забанений на {timespan}</b>',
        'done.kicked': '<tg-emoji emoji-id="5870778972857438051">🍃</tg-emoji> <b>{user} був вилучений</b>',
        'done.nomedia': '<tg-emoji emoji-id="5870782662234346251">🖼️</tg-emoji> <b>{user} не зможе відправляти медіа {timespan}</b>',
        'done.nomedia.f': '<tg-emoji emoji-id="5870782662234346251">🖼️</tg-emoji> <b>{user} більше не зможе відправляти медіа</b>',
        'done.allowmedia': '<tg-emoji emoji-id="5870782662234346251">🖼️</tg-emoji> <b>{user} знову може відправляти медіа</b>',
        'done.setrights.f': '<tg-emoji emoji-id="5870982283724328568">🔧</tg-emoji> <b>Права для <code>{user}</code> назавжди встановлено на {rights}</b>',
        'done.setrights': '<tg-emoji emoji-id="5870982283724328568">🔧</tg-emoji> <b>Права для <code>{user}</code> встановлено на {rights}</b> на {timespan}',
        'done.unmuted': '<tg-emoji emoji-id="5870693687691841267">🔊</tg-emoji> <b>{user} знову може писати</b>',
        'done.unbanned': '<tg-emoji emoji-id="5870948572526022116">👋🏻</tg-emoji> <b>{user} знову може приєднатися</b>',
        'done.unwarned.one': '<tg-emoji emoji-id="5870930636742595124">⚖️</tg-emoji> <b>З користувача <code>{user}</code> було знято одне попередження</b>',
        'done.unwarned.all': '<tg-emoji emoji-id="5870930636742595124">⚖️</tg-emoji> <b>З користувача <code>{user}</code> були зняті всі попередження</b>',
        'done.da_kicked': '<tg-emoji emoji-id="5870778972857438051">🍃</tg-emoji> <b>Вилучено <code>{amount}</code> видалених акаунтів</b>',
        'done.pin': '<tg-emoji emoji-id="5870930744116776638">📌</tg-emoji> <b>Закріплено</b>',
        'done.unpin': '<tg-emoji emoji-id="5870930744116776638">📌</tg-emoji> <b>Відкріплено</b>',
        'done.channel_ban.on': '<tg-emoji emoji-id="5870704313440932932">🔒</tg-emoji> <b>Добре, користувачі більше не зможуть писати від імені каналів.</b>',
        'done.channel_ban.off': '<tg-emoji emoji-id="5870704313440932932">🔓</tg-emoji> <b>Добре, користувачі знову зможуть писати від імені каналів.</b>',
        'done.channel_ban.action': '<tg-emoji emoji-id="5872988737826197458">⛔</tg-emoji> <b>{user} забанений назавжди</b>\n<b>Причина:</b>: писав від імені каналу',
        'done.flushda': '<tg-emoji emoji-id="5870778972857438051">🍃</tg-emoji> <b>Вилучено <code>{amt}</code> видалених акаунтів</b>',
        'done.glban.f': '<tg-emoji emoji-id="5870718740236079262">🌍</tg-emoji> <b>{user} забанений у {count} чатах назавжди</b>',
        'done.glban': '<tg-emoji emoji-id="5870718740236079262">🌍</tg-emoji> <b>{user} забанений у {count} чатах на {timespan}</b>',
        'done.glunban': '<tg-emoji emoji-id="5870718740236079262">🌍</tg-emoji> <b>{user} розбанений у {count} чатах</b>',
        'done.leave': '<tg-emoji emoji-id="5870764288364252592">😶</tg-emoji> <b>Виходжу.</b>',
        'done.leave.reason': '<tg-emoji emoji-id="5870764288364252592">😶</tg-emoji> <b>Виходжу.</b>\n<b>Причина:</b> <i>{reason}</i>',
        'reason': '\n<b>Причина:</b> <i>{0}</i>',
        'chat_id': '<tg-emoji emoji-id="5870772616305839506">👥</tg-emoji> <b>ID чату</b>: <code>{chat_id}</code>{additional}\n<tg-emoji emoji-id="5870994129244131212">👤</tg-emoji> <b>Ваш ID</b>: <code>{my_id}</code>',
        'person_in_reply_id': '<tg-emoji emoji-id="5870772616305839506">🫂</tg-emoji> <b>ID людини у відповіді</b>: <code>{reply_id}</code>',
        'sys.DA': 'Видалений акаунт',
        'sys.LANG': 'en_US',
        'sys.forever': 'назавжди',
        'of_chat': 'Чат',
        'of_channel': 'Канал',
        'loading': '<tg-emoji emoji-id="5870813306826002498">🟡</tg-emoji> <b>Завантаження даних ...</b>',
        'own_list': '<b>Мої володіння ({count}):</b>\n\n{msg}',
        'no_ownerships': '<tg-emoji emoji-id="5870657884844462243">❌</tg-emoji> <b>Володінь не знайдено.</b>',
        'not_a_chat': '<tg-emoji emoji-id="5870931487146119264">⚠️</tg-emoji> <b>Працює тільки в групах!</b>',
        'admins_in_chat': '<tg-emoji emoji-id="5870684638195748414">👑</tg-emoji> <b>Адміни в <code>{title}</code> ({count}):</b>\n\n',
        'admins_in_chat_caption': '<b>Адміни в "{}":</b>',
        'too_many_admins': 'Занадто багато адмінів. Завантажую список у файл...',
        'no_admins_in_chat': '<b>У цьому чаті немає адмінів.</b>',
        'bots_in_chat': '<tg-emoji emoji-id="5870531058755178453">🤖</tg-emoji> <b>Боти в <code>{title}</code> ({count}):</b>\n\n',
        'bots_in_chat_caption': '<b>Боти в <code>{}</code>:</b>',
        'too_many_bots': 'Занадто багато ботів. Завантажую список у файл...',
        'no_bots_in_chat': '<b>У цьому чаті немає ботів.</b>',
        'users_in_chat': '<tg-emoji emoji-id="5870994129244131212">👤</tg-emoji> <b>Учасники в <code>{title}</code> ({count}):</b>\n\n',
        'users_in_chat_caption': '<b>Учасники в <code>{}</code>:</b>',
        'no_user_in_chat': '<b>У цьому чаті немає учасників.</b>',
        'too_many_users': 'Забагато учасників. Надсилаю список файлом…',
        'chat_muted': '<tg-emoji emoji-id="5870681133502435302">🔇</tg-emoji> <b>Чат тепер закритий для учасників.</b>',
        'chat_unmuted': '<tg-emoji emoji-id="5870633910337015697">✅</tg-emoji> <b>Чат тепер відкритий для всіх учасників.</b>',
        'title_changed': '<b>Назву {type_of} успішно змінено з <code>{old_title}</code> на <code>{new_title}</code>.</b>',
        'user_invited': '<tg-emoji emoji-id="5870633910337015697">✅</tg-emoji> <b>Користувача <a href=\'tg://user?id={id}\'>{user}</a> запрошено до чату.</b>',
        'creator': '<tg-emoji emoji-id="5870684638195748414">👑</tg-emoji> <b>Творець: <a href=\'tg://user?id={id}\'>{creator}</a>.</b>',
        'no_creator': '<tg-emoji emoji-id="5870657884844462243">❌</tg-emoji> <b>Творця не знайдено.</b>',
        'channel_created': '<tg-emoji emoji-id="5870633910337015697">✅</tg-emoji> <b>Канал <code>{title}</code> створено.\n</b><tg-emoji emoji-id="5870527201874546272">🔗</tg-emoji><b> Запрошувальне посилання: {link}</b>',
        'group_created': '<tg-emoji emoji-id="5870633910337015697">✅</tg-emoji> <b>Групу <code>{title}</code> створено.\n</b><tg-emoji emoji-id="5870527201874546272">🔗</tg-emoji><b> Запрошувальне посилання: {link}</b>',
        'temp_chat': '\n<tg-emoji emoji-id="5870875489362513438">🗑</tg-emoji> <b>Видалиться сам через {timespan}.</b>',
        'type_group': 'Група',
        'type_channel': 'Канал',
        'type_unknown': 'Невідомо',
        'yes': '<tg-emoji emoji-id="5870633910337015697">✅</tg-emoji> Так',
        'no': '<tg-emoji emoji-id="5870657884844462243">✖️</tg-emoji> Ні',
        'all_approved': '<tg-emoji emoji-id="5870633910337015697">✅</tg-emoji> <b>Користувачів схвалено</b>',
        'all_dismissed': '<tg-emoji emoji-id="5870657884844462243">✖️</tg-emoji> <b>Заявки відхилено</b>',
        'log_text': '<tg-emoji emoji-id="5870994129244131212">👤</tg-emoji> <b>Хто:</b> {user}\n<tg-emoji emoji-id="5870704313440932932">🔒</tg-emoji> <b>Хто покарав:</b> {admin}\n<tg-emoji emoji-id="5872988737826197458">⛔️</tg-emoji> <b>Що:</b> {punishment}{reason}{time}{chat}',
        'log_chat': '\n<tg-emoji emoji-id="5872886929921413168">💬</tg-emoji> <b>Чат:</b> {chat}',
        'log_reason': '\n<tg-emoji emoji-id="5870676941614354370">🖋</tg-emoji> <b>Причина:</b> {reason}',
        'log_time': '\n<tg-emoji emoji-id="5870729937215819584">⏰️</tg-emoji> <b>Термін:</b> {time}',
        'act.mute': 'Мут',
        'act.ban': 'Бан',
        'act.kick': 'Кік',
        'act.unmute': 'Розмут',
        'act.unban': 'Розбан',
        'act.warn': 'Попередження',
        'act.nomedia': 'Заборона медіа',
        'act.allowmedia': 'Медіа дозволено',
        'act.rights': 'Права змінено',
        'flushda.loading': '<tg-emoji emoji-id="5870813306826002498">🟡</tg-emoji> <b>Прибираю видалені акаунти…</b>',
        'flushda.loading.chat': '<tg-emoji emoji-id="5870813306826002498">🟡</tg-emoji> <b>Прибираю видалені акаунти з цього чату…</b>',
        'flushda.loading.channels': '<tg-emoji emoji-id="5870813306826002498">🟡</tg-emoji> <b>Прибираю видалені акаунти з каналів…</b>',
        'monday': 'Понеділок',
        'tuesday': 'Вівторок',
        'wednesday': 'Середа',
        'thursday': 'Четвер',
        'friday': "П'ятниця",
        'saturday': 'Субота',
        'sunday': 'Неділя',
        'cfg.gban_except': 'ID чатів, які .gban і .ungban не чіпають',
        'cfg.gban_pm_block': 'Блокувати в ЛС при .gban і розблоковувати при .ungban',
        'cfg.gban_pm_del_history': 'Разом із блокуванням видаляти переписку в ЛС',
        'cfg.gban_pm_except': 'ID користувачів, яких у ЛС не блокувати',
        'cfg.global_logs': 'Логувати обмеження з усіх чатів, де ви адмін, а не лише свої команди',
        'gban.no_reason': 'Не вказана',
        'gban.args': '<tg-emoji emoji-id="5870994129244131212">👤</tg-emoji> <b>Вкажи користувача.</b>\nВідповідай на повідомлення або передай юзернейм чи ID.',
        'gban.working': '<tg-emoji emoji-id="5870718740236079262">🌍</tg-emoji> <b>Баню <a href="{url}">{name}</a> скрізь…</b>',
        'gban.unworking': '<tg-emoji emoji-id="5870718740236079262">🌍</tg-emoji> <b>Розбанюю <a href="{url}">{name}</a> скрізь…</b>',
        'gban.done': '<tg-emoji emoji-id="5872988737826197458">⛔</tg-emoji> <b><a href="{url}">{name}</a> забанений у {count} чатах</b>\n<b>Причина:</b> <i>{reason}</i>',
        'gban.undone': '<tg-emoji emoji-id="5870948572526022116">👋🏻</tg-emoji> <b><a href="{url}">{name}</a> розбанений у {count} чатах</b>',
        'gban.chats': '\n{chats}',
        'gban.pm_blocked': '\n<tg-emoji emoji-id="5872988737826197458">🚫</tg-emoji> <b>Заблокований у ЛС</b>',
        'gban.pm_unblocked': '\n<tg-emoji emoji-id="5870948572526022116">👋🏻</tg-emoji> <b>Розблокований у ЛС</b>',
        'gban.pm_failed': '\n<tg-emoji emoji-id="5870704313440932932">🔓</tg-emoji> <b>Не вдалося заблокувати в ЛС</b>',
        'gban.pm_cleared': ' · <b>Переписку в ЛС видалено</b>',
        'chatinfo': '<tg-emoji emoji-id="5870704313440932932">🔒</tg-emoji><b> Тип: {type_of}\n</b><tg-emoji emoji-id="5870495350397079101">#️⃣</tg-emoji><b> ID чату: </b><code>{id}</code><b>\n</b><tg-emoji emoji-id="5873225338984599714">🔥</tg-emoji><b> Назва: {title}\n\n</b><tg-emoji emoji-id="5870676941614354370">🖋</tg-emoji><b> Опис: {about}\n\n</b><tg-emoji emoji-id="5870684638195748414">👑</tg-emoji><b> Адміни: {admins_count}\n</b><tg-emoji emoji-id="5870633910337015697">✅</tg-emoji><b> Онлайн: {online_count}\n</b><tg-emoji emoji-id="5870994129244131212">👤</tg-emoji><b> Учасники: {participants_count}\n</b><tg-emoji emoji-id="5872988737826197458">🚫</tg-emoji><b> Видалені: {kicked_count}\n</b><tg-emoji emoji-id="5870892901159932239">🔀</tg-emoji><b> Заявки: {requests_pending}\n\n</b><tg-emoji emoji-id="5870729937215819584">🕐</tg-emoji><b> Повільний режим: {slowmode_seconds}\n</b><tg-emoji emoji-id="5872980989705196227">📞</tg-emoji><b> Дзвінок: {call}\n</b><tg-emoji emoji-id="5870875489362513438">🗑</tg-emoji><b> TTL: {ttl_period}\n</b><tg-emoji emoji-id="5870994129244131212">👤</tg-emoji><b> Нещодавні заявки: {recent_requesters}\n\n</b><tg-emoji emoji-id="5870772616305839506">👥</tg-emoji><b> Пов\'язаний чат: {linked_chat_id}\n</b><tg-emoji emoji-id="5870704313440932932">🛡</tg-emoji><b> Антиспам: {antispam}\n</b><tg-emoji emoji-id="5870542612217204751">👁</tg-emoji><b> Список приховано: {participants_hidden}\n\n</b><tg-emoji emoji-id="5870527201874546272">🔗</tg-emoji><b> Посилання: {link}</b>',
        'userinfo': '<blockquote><tg-emoji emoji-id="5870495350397079101">#️⃣</tg-emoji><b> ID: {user_id}\n</b><tg-emoji emoji-id="5873225338984599714">🔥</tg-emoji><b> Ім\'я: {first_name}\n</b><tg-emoji emoji-id="5873225338984599714">🔥</tg-emoji><b> Прізвище: {last_name}\n</b><tg-emoji emoji-id="5872980989705196227">📞</tg-emoji><b> Телефон: {phone}\n</b><tg-emoji emoji-id="5870998024779468554">🐶</tg-emoji><b> Юзернейми: {usernames}</b></blockquote><b>\n</b><blockquote><tg-emoji emoji-id="5870609858520158157">ℹ️</tg-emoji><b> Про себе: {about}</b></blockquote><b>\n</b><blockquote><tg-emoji emoji-id="5870729937215819584">🕐</tg-emoji><b> Години: </b>{business_work_hours}\n<tg-emoji emoji-id="5870450871715761518">❤️</tg-emoji><b> Емодзі-статус: {emoji_status}</b></blockquote><b>\n</b><blockquote><tg-emoji emoji-id="5870693687691841267">🔉</tg-emoji><b> Канал: {personal_channel}\n</b><tg-emoji emoji-id="5870847962917113498">🎂</tg-emoji><b> День народження: {birthday}\n</b><tg-emoji emoji-id="5870478797593120516">🎁</tg-emoji><b> Подарунки: {stargifts_count}</b></blockquote><b>\n</b><blockquote><tg-emoji emoji-id="5870931487146119264">🚨</tg-emoji><b> Спільних чатів: {common_chats_count}\n</b><tg-emoji emoji-id="5870772616305839506">👥</tg-emoji><b> Спільні чати: {common_chats}</b></blockquote>',
        'promote.no_rights': '<tg-emoji emoji-id="5870704313440932932">🔓</tg-emoji> <b>Не вистачає прав, щоб змінювати адмінів.</b>',
        'promote.no_user': '<tg-emoji emoji-id="5870994129244131212">👤</tg-emoji> <b>Вкажи користувача.</b>\nВідповідай на повідомлення або передай юзернейм чи ID.',
        'promote.demoted': '<tg-emoji emoji-id="5870948572526022116">👋🏻</tg-emoji> <b>З {name}</b> [<code>{user_id}</code>] <b>знято права адміна.</b>',
        'promote.promoted_full': '<tg-emoji emoji-id="5870684638195748414">👑</tg-emoji> <b>{name}</b> [<code>{user_id}</code>] <b>підвищений з повними правами.</b>\n<b>Посада:</b> {rank}',
        'promote.promoted': '<tg-emoji emoji-id="5870684638195748414">👑</tg-emoji> <b>{name}</b> [<code>{user_id}</code>] <b>підвищений до адміна.</b>\n<b>Посада:</b> {rank}',
        'promote.choose': '<tg-emoji emoji-id="5870684638195748414">👑</tg-emoji> <b>Права для {name}</b> [<code>{user_id}</code>]\n<b>Посада:</b> {rank}',
        'promote.confirm': 'Підтвердити',
        'promote.default_rank': 'Адмін',
        'promote.tag_group_only': '<tg-emoji emoji-id="5870931487146119264">⚠️</tg-emoji> <b>Теги учасників є лише в групах.</b>',
        'promote.tag_usage': '<b>Використання:</b> <code>{prefix}settag @user тег</code> або відповіддю <code>{prefix}settag тег</code>. Без тега або <code>-</code> знімає його.',
        'promote.tag_invalid': '<tg-emoji emoji-id="5870657884844462243">❌</tg-emoji> <b>Тег — максимум 16 символів, без емодзі.</b>',
        'promote.tag_no_rights': '<tg-emoji emoji-id="5870704313440932932">🔓</tg-emoji> <b>Щоб змінювати чужий тег, потрібне право «Керування тегами учасників».</b>',
        'promote.tag_updated': '<tg-emoji emoji-id="5870676941614354370">🖋</tg-emoji> <b>Тег {name}:</b> <code>{rank}</code>',
        'promote.tag_removed': '<tg-emoji emoji-id="5255831443816327915">🗑</tg-emoji> <b>Тег {name} знято.</b>',
        'promote.rpc_error': '<tg-emoji emoji-id="5870657884844462243">❌</tg-emoji> <b>Помилка Telegram:</b> <code>{error}</code>',
        'promote.right.change_info': '{emoji} Зміна профілю {where}',
        'promote.right.post_messages': '{emoji} Публікувати пости',
        'promote.right.edit_messages': '{emoji} Змінювати пости',
        'promote.right.delete_messages': '{emoji} Видаляти повідомлення',
        'promote.right.ban_users': '{emoji} Обмежувати користувачів',
        'promote.right.invite_users': '{emoji} Додавати користувачів',
        'promote.right.pin_messages': '{emoji} Закріплювати повідомлення',
        'promote.right.add_admins': '{emoji} Призначати адмінів',
        'promote.right.anonymous': '{emoji} Анонімність',
        'promote.right.manage_call': '{emoji} Керування дзвінками',
        'promote.right.manage_topics': '{emoji} Керування темами',
        'promote.right.post_stories': '{emoji} Публікувати історії',
        'promote.right.edit_stories': '{emoji} Змінювати історії',
        'promote.right.delete_stories': '{emoji} Видаляти історії',
        'promote.right.manage_direct_messages': '{emoji} Керування ЛС каналу',
        'promote.right.manage_ranks': '{emoji} Керування тегами учасників',
        'promote.right.manage_linked_peers': '{emoji} Керування пов\'язаними чатами',
        'promote.right.manage_welcome_messages': '{emoji} Керування привітаннями',
        'promote.right.other': '{emoji} Інші права',
        'chat.not_channel': '<tg-emoji emoji-id="5870693687691841267">📣</tg-emoji> <b>Це лише для супергруп і каналів.</b>',
        'chat.no_rights': '<tg-emoji emoji-id="5870704313440932932">🔓</tg-emoji> <b>Не вистачає прав, щоб змінити цей чат.</b>',
        'chat.usage.slow': '<b>Використання:</b> <code>{prefix}slow</code> off, або <code>30</code>, <code>1m</code>, <code>5m</code>, <code>1h</code>.',
        'chat.usage.about': '<b>Використання:</b> <code>{prefix}setabout текст</code>. <code>-</code> очищає.',
        'chat.usage.photo': '<b>Використання:</b> відповіддю на фото <code>{prefix}setphoto</code>. <code>-</code> прибирає.',
        'chat.usage.username': "<b>Використання:</b> <code>{prefix}setusername ім'я</code>. <code>-</code> прибирає.",
        'chat.usage.link': '<b>Використання:</b> <code>{prefix}link</code>, <code>new</code>, <code>revoke</code> або <code>назва</code>.',
        'chat.slow_off': '<tg-emoji emoji-id="5870729937215819584">🕐</tg-emoji> <b>Повільний режим вимкнено.</b>',
        'chat.slow_on': '<tg-emoji emoji-id="5870729937215819584">🕐</tg-emoji> <b>Повільний режим:</b> <code>{seconds}</code> с',
        'chat.about_set': '<tg-emoji emoji-id="5870676941614354370">🖋</tg-emoji> <b>Опис оновлено.</b>',
        'chat.about_cleared': '<tg-emoji emoji-id="5255831443816327915">🗑</tg-emoji> <b>Опис очищено.</b>',
        'chat.photo_set': '<tg-emoji emoji-id="5870782662234346251">🖼️</tg-emoji> <b>Фото чату оновлено.</b>',
        'chat.photo_cleared': '<tg-emoji emoji-id="5255831443816327915">🗑</tg-emoji> <b>Фото чату прибрано.</b>',
        'chat.username_set': '<tg-emoji emoji-id="5870527201874546272">🔗</tg-emoji> <b>Ім\'я користувача:</b> @{username}',
        'chat.username_cleared': '<tg-emoji emoji-id="5255831443816327915">🗑</tg-emoji> <b>Ім\'я користувача прибрано.</b>',
        'chat.sign_on': '<tg-emoji emoji-id="5870676941614354370">🖋</tg-emoji> <b>Підписи авторів увімкнено.</b>',
        'chat.sign_off': '<tg-emoji emoji-id="5870676941614354370">🖋</tg-emoji> <b>Підписи авторів вимкнено.</b>',
        'chat.forum_on': '<tg-emoji emoji-id="5872886929921413168">💬</tg-emoji> <b>Теми увімкнено.</b>',
        'chat.forum_off': '<tg-emoji emoji-id="5872886929921413168">💬</tg-emoji> <b>Теми вимкнено.</b>',
        'chat.spam_on': '<tg-emoji emoji-id="5870704313440932932">🛡</tg-emoji> <b>Агресивний антиспам увімкнено.</b>',
        'chat.spam_off': '<tg-emoji emoji-id="5870704313440932932">🛡</tg-emoji> <b>Агресивний антиспам вимкнено.</b>',
        'chat.hidden_on': '<tg-emoji emoji-id="5870542612217204751">👁</tg-emoji> <b>Список учасників приховано.</b>',
        'chat.hidden_off': '<tg-emoji emoji-id="5870542612217204751">👁</tg-emoji> <b>Список учасників видно.</b>',
        'chat.history_on': '<tg-emoji emoji-id="5870729937215819584">🕐</tg-emoji> <b>Нові учасники бачать історію.</b>',
        'chat.history_off': '<tg-emoji emoji-id="5870729937215819584">🕐</tg-emoji> <b>Історію приховано від нових учасників.</b>',
        'chat.join_on': '<tg-emoji emoji-id="5870892901159932239">🔀</tg-emoji> <b>Заявки на вступ увімкнено.</b>',
        'chat.join_off': '<tg-emoji emoji-id="5870892901159932239">🔀</tg-emoji> <b>Заявки на вступ вимкнено.</b>',
        'chat.link_none': '<tg-emoji emoji-id="5870527201874546272">🔗</tg-emoji> <b>Інвайта ще немає.</b>',
        'chat.link': '<tg-emoji emoji-id="5870527201874546272">🔗</tg-emoji> <b>Інвайт:</b> {link}',
        'chat.link_revoked': '<tg-emoji emoji-id="5255831443816327915">🗑</tg-emoji> <b>Інвайт відкликано.</b>\n<tg-emoji emoji-id="5870527201874546272">🔗</tg-emoji> <b>Новий:</b> {link}',
        'chat.link_created': '<tg-emoji emoji-id="5870633910337015697">✅</tg-emoji> <b>Інвайт створено.</b>\n<tg-emoji emoji-id="5870527201874546272">🔗</tg-emoji> {link}',
        'rights.header': '<tg-emoji emoji-id="5870684638195748414">👑</tg-emoji> <b>{name}</b> [<code>{user_id}</code>]\n<b>Роль:</b> {role}\n<b>Посада:</b> {rank}',
        'rights.owner': 'Власник',
        'rights.admin': 'Адмін',
        'rights.member': 'Учасник',
        'rights.none': '<tg-emoji emoji-id="5870657884844462243">✖️</tg-emoji> <b>{name}</b> [<code>{user_id}</code>] <b>не адмін.</b>',
        'rights.empty': '<i>Прав немає.</i>',
    }

    strings_uz = {
        'name': 'Helm',
        'cfg.warnlimit': 'Cheklashdan oldingi ogohlantirishlar soni',
        'cfg.ptime': 'Jazo muddati, standart',
        'cfg.wl_punishment': "Ogohlantirish chegarasiga yetganda nima bo'ladi",
        'cfg.wl_reason': 'Chegara jazosining sababi',
        'cfg.wl_timespan': 'Chegara jazosi qancha davom etadi',
        'error.wrongchattype.pm': '<tg-emoji emoji-id="5870563425628721113">📧</tg-emoji> <b>Siz bu modulni shaxsiy xabarlarda ishlata olmaysiz.</b>\nBu modul guruhlar uchun mo\'ljallangan.',
        'error.wrongchattype.channel': '<tg-emoji emoji-id="5870693687691841267">📣</tg-emoji> <b>Siz bu modulni kanallarda ishlata olmaysiz.</b>\nBu modul guruhlar uchun mo\'ljallangan.',
        'error.no_args.user': '<tg-emoji emoji-id="5870994129244131212">👤</tg-emoji> <b>Foydalanuvchini ko\'rsatishingiz kerak.</b>\nFoydalanuvchi nomi, ID yoki xabarga javob orqali.',
        'error.locate_user': '<tg-emoji emoji-id="5870974879200711167">🔎</tg-emoji> <b>Foydalanuvchi topilmadi.</b>\nFoydalanuvchi nomi yoki ID ni qayta tekshiring.',
        'error.can_not_restrict': '<tg-emoji emoji-id="5870704313440932932">🔓</tg-emoji> <b>Foydalanuvchini cheklab bo\'lmadi.</b>\nSizda kerakli huquqlar yo\'q yoki o\'zingiz ko\'tarmagan adminni cheklamoqchisiz.',
        'error.reply_is_service': '<tg-emoji emoji-id="5870982283724328568">⚙️</tg-emoji> <b>Xizmat xabariga javob berib, foydalanuvchini cheklay olmaysiz.</b>\nFoydalanuvchi xabariga javob bering.',
        'error.self': '<tg-emoji emoji-id="5872988737826197458">🔫</tg-emoji> <b>O\'zingizni cheklay olmaysiz.</b>\nO\'zingizga nisbatan bunchalik qattiqqo\'l bo\'lmang.',
        'error.warn_self': '<tg-emoji emoji-id="5870948572526022116">☝🏻</tg-emoji> <b>Yomon bola.</b>\nO\'ynashni bas qiling, moderatsiya bilan shug\'ullaning.',
        'error.no_args.rights': '<tg-emoji emoji-id="5872996816659681395">❓</tg-emoji> <b>Huquqlarni ko\'rsatishingiz kerak.</b>\nHuquqlar ketma-ketlikdan iborat (masalan barcha huquqlar uchun `123456789ab`). Huquqlarni teskari qilish uchun oldiga `r` qo\'ying.',
        'error.no_user': '<tg-emoji emoji-id="5870994129244131212">👤</tg-emoji> <b>Foydalanuvchini ko\'rsating.</b>\nJavob, username yoki ID.',
        'error.no_reply': '<tg-emoji emoji-id="5872886929921413168">💬</tg-emoji> <b>Xabarga javob bering.</b>',
        'error.invalid_args': '<tg-emoji emoji-id="5872996816659681395">❓</tg-emoji> <b>Format:</b> <code>g</code> yoki <code>c</code>, keyin nom. Oxirida <code>30m</code>, <code>2h</code> yoki <code>1d</code> — chat o‘zi o‘chadi.',
        'error.too_much': '<tg-emoji emoji-id="5870657884844462243">❌</tg-emoji> <b>Noto\'g\'ri miqdor</b>\n1 dan 100 gacha son kiriting.',
        'error.insufficient_rights': '<tg-emoji emoji-id="5870704313440932932">🔓</tg-emoji> <b>Huquq yetarli emas.</b>',
        'error.unknown': '<tg-emoji emoji-id="5870657884844462243">🙅🏻\u200d♂️</tg-emoji> <b>Noma\'lum xato</b>',
        'error': '<b>Xato:</b> <code>{error}</code>',
        'done.muted.f': '<tg-emoji emoji-id="5870681133502435302">🔇</tg-emoji> <b>{user} abadiy ovozsiz qilindi</b>',
        'done.muted': '<tg-emoji emoji-id="5870681133502435302">🔇</tg-emoji> <b>{user} {timespan} ga ovozsiz qilindi</b>',
        'done.warned': '<tg-emoji emoji-id="5870931487146119264">⚠</tg-emoji> <b>{user} ogohlantirildi</b>',
        'done.banned.f': '<tg-emoji emoji-id="5872988737826197458">⛔</tg-emoji> <b>{user} abadiy bloklandi</b>',
        'done.banned': '<tg-emoji emoji-id="5872988737826197458">⛔</tg-emoji> <b>{user} {timespan} ga bloklandi</b>',
        'done.kicked': '<tg-emoji emoji-id="5870778972857438051">🍃</tg-emoji> <b>{user} guruhdan chiqarildi</b>',
        'done.nomedia': '<tg-emoji emoji-id="5870782662234346251">🖼️</tg-emoji> <b>{user} {timespan} davomida media yubora olmaydi</b>',
        'done.nomedia.f': '<tg-emoji emoji-id="5870782662234346251">🖼️</tg-emoji> <b>{user} ortiq media yubora olmaydi</b>',
        'done.allowmedia': '<tg-emoji emoji-id="5870782662234346251">🖼️</tg-emoji> <b>{user} yana media yubora oladi</b>',
        'done.setrights.f': '<tg-emoji emoji-id="5870982283724328568">🔧</tg-emoji> <b><code>{user}</code> huquqlari {rights} qilib belgilandi</b>',
        'done.setrights': '<tg-emoji emoji-id="5870982283724328568">🔧</tg-emoji> <b><code>{user}</code> huquqlari {timespan} ga {rights} qilib belgilandi</b>',
        'done.unmuted': '<tg-emoji emoji-id="5870693687691841267">🔊</tg-emoji> <b>{user} ovozi qayta tiklandi</b>',
        'done.unbanned': '<tg-emoji emoji-id="5870948572526022116">👋🏻</tg-emoji> <b>{user} blokdan chiqarildi</b>',
        'done.unwarned.one': '<tg-emoji emoji-id="5870930636742595124">⚖️</tg-emoji> <b>{user} dan bir ogohlantirish olib tashlandi</b>',
        'done.unwarned.all': '<tg-emoji emoji-id="5870930636742595124">⚖️</tg-emoji> <b><code>{user}</code> ning barcha ogohlantirishlari olib tashlandi</b>',
        'done.da_kicked': '<tg-emoji emoji-id="5870778972857438051">🍃</tg-emoji> <b><code>{amount}</code> ta o\'chirilgan akkaunt chiqarib yuborildi</b>',
        'done.pin': '<tg-emoji emoji-id="5870930744116776638">📌</tg-emoji> <b>Qadaldi</b>',
        'done.unpin': '<tg-emoji emoji-id="5870930744116776638">📌</tg-emoji> <b>Qadalgandan olib tashlandi</b>',
        'done.channel_ban.on': '<tg-emoji emoji-id="5870704313440932932">🔒</tg-emoji> <b>Yaxshi, foydalanuvchilar endi kanallar nomidan yoza olmaydilar.</b>',
        'done.channel_ban.off': '<tg-emoji emoji-id="5870704313440932932">🔓</tg-emoji> <b>Yaxshi, foydalanuvchilar yana kanallar nomidan yoza oladilar.</b>',
        'done.channel_ban.action': '<tg-emoji emoji-id="5872988737826197458">⛔</tg-emoji> <b>{user} abadiy bloklandi</b>\n<b>Sabab:</b> kanal nomidan yozgani uchun',
        'done.flushda': '<tg-emoji emoji-id="5870778972857438051">🍃</tg-emoji> <b><code>{amt}</code> ta o\'chirilgan hisob o\'chirib tashlandi</b>',
        'done.glban.f': '<tg-emoji emoji-id="5870718740236079262">🌍</tg-emoji> <b>{user} {count} ta chatda abadiy bloklandi</b>',
        'done.glban': '<tg-emoji emoji-id="5870718740236079262">🌍</tg-emoji> <b>{user} {count} ta chatda {timespan} ga bloklandi</b>',
        'done.glunban': '<tg-emoji emoji-id="5870718740236079262">🌍</tg-emoji> <b>{user} {count} ta chatda blokdan chiqarildi</b>',
        'done.leave': '<tg-emoji emoji-id="5870764288364252592">😶</tg-emoji> <b>Chiqyapman.</b>',
        'done.leave.reason': '<tg-emoji emoji-id="5870764288364252592">😶</tg-emoji> <b>Chiqyapman.</b>\n<b>Sabab:</b> <i>{reason}</i>',
        'reason': '\n<b>Sabab:</b> <i>{0}</i>',
        'chat_id': '<tg-emoji emoji-id="5870772616305839506">👥</tg-emoji> <b>Chat ID</b>: <code>{chat_id}</code>{additional}\n<tg-emoji emoji-id="5870994129244131212">👤</tg-emoji> <b>Sizning ID\'ingiz</b>: <code>{my_id}</code>',
        'person_in_reply_id': '<tg-emoji emoji-id="5870772616305839506">🫂</tg-emoji> <b>Javob berilgan shaxs ID\'si</b>: <code>{reply_id}</code>',
        'sys.DA': "O'chirilgan hisob",
        'sys.LANG': 'en_US',
        'sys.forever': 'abadiy',
        'of_chat': 'guruh',
        'of_channel': 'Kanal',
        'loading': '<tg-emoji emoji-id="5870813306826002498">🟡</tg-emoji> <b>Ma\'lumotlar yuklanmoqda ...</b>',
        'own_list': '<b>Mening mulklarim ({count}):</b>\n\n{msg}',
        'no_ownerships': '<tg-emoji emoji-id="5870657884844462243">❌</tg-emoji> <b>Mulklar yo\'q.</b>',
        'not_a_chat': '<tg-emoji emoji-id="5870931487146119264">⚠️</tg-emoji> <b>Bu faqat guruhlarda ishlaydi!</b>',
        'admins_in_chat': '<tg-emoji emoji-id="5870684638195748414">👑</tg-emoji> <b><code>{title}</code> da adminlar ({count}):</b>\n\n',
        'admins_in_chat_caption': '<b>"{}" da adminlar:</b>',
        'too_many_admins': "Adminlar juda ko'p. Ro'yxat faylga yuklanmoqda...",
        'no_admins_in_chat': "<b>Bu chatda adminlar yo'q.</b>",
        'bots_in_chat': '<tg-emoji emoji-id="5870531058755178453">🤖</tg-emoji> <b><code>{title}</code> dagi botlar ({count}):</b>\n\n',
        'bots_in_chat_caption': '<b><code>{}</code> dagi botlar:</b>',
        'too_many_bots': "Botlar juda ko'p. Ro'yxat faylga yuklanmoqda...",
        'no_bots_in_chat': "<b>Bu chatda botlar yo'q.</b>",
        'users_in_chat': '<tg-emoji emoji-id="5870994129244131212">👤</tg-emoji> <b><code>{title}</code> dagi foydalanuvchilar ({count}):</b>\n\n',
        'users_in_chat_caption': '<b><code>{}</code> dagi foydalanuvchilar:</b>',
        'no_user_in_chat': "<b>Bu chatda foydalanuvchilar yo'q.</b>",
        'too_many_users': "Ishtirokchilar juda ko'p. Ro'yxatni faylda yuboraman…",
        'chat_muted': '<tg-emoji emoji-id="5870681133502435302">🔇</tg-emoji> <b>Chat ishtirokchilar uchun ovozsiz qilindi.</b>',
        'chat_unmuted': '<tg-emoji emoji-id="5870633910337015697">✅</tg-emoji> <b>Chat barcha ishtirokchilar uchun ochildi.</b>',
        'title_changed': "<b>{type_of} nomi <code>{old_title}</code> dan <code>{new_title}</code> ga o'zgartirildi.</b>",
        'user_invited': '<tg-emoji emoji-id="5870633910337015697">✅</tg-emoji> <b>Foydalanuvchi <a href=\'tg://user?id={id}\'>{user}</a> chatga taklif qilindi.</b>',
        'creator': '<tg-emoji emoji-id="5870684638195748414">👑</tg-emoji> <b>Yaratuvchi: <a href=\'tg://user?id={id}\'>{creator}</a>.</b>',
        'no_creator': '<tg-emoji emoji-id="5870657884844462243">❌</tg-emoji> <b>Yaratuvchi topilmadi.</b>',
        'channel_created': '<tg-emoji emoji-id="5870633910337015697">✅</tg-emoji> <b><code>{title}</code> kanali yaratildi.\n</b><tg-emoji emoji-id="5870527201874546272">🔗</tg-emoji><b> Taklif havolasi: {link}</b>',
        'group_created': '<tg-emoji emoji-id="5870633910337015697">✅</tg-emoji> <b><code>{title}</code> guruhi yaratildi.\n</b><tg-emoji emoji-id="5870527201874546272">🔗</tg-emoji><b> Taklif havolasi: {link}</b>',
        'temp_chat': '\n<tg-emoji emoji-id="5870875489362513438">🗑</tg-emoji> <b>{timespan} dan keyin o‘zi o‘chadi.</b>',
        'type_group': 'Guruh',
        'type_channel': 'Kanal',
        'type_unknown': "Noma'lum",
        'yes': '<tg-emoji emoji-id="5870633910337015697">✅</tg-emoji> Ha',
        'no': '<tg-emoji emoji-id="5870657884844462243">✖️</tg-emoji> Yo\'q',
        'all_approved': '<tg-emoji emoji-id="5870633910337015697">✅</tg-emoji> <b>Foydalanuvchilar qabul qilindi</b>',
        'all_dismissed': '<tg-emoji emoji-id="5870657884844462243">✖️</tg-emoji> <b>So\'rovlar rad etildi</b>',
        'log_text': '<tg-emoji emoji-id="5870994129244131212">👤</tg-emoji> <b>Kim:</b> {user}\n<tg-emoji emoji-id="5870704313440932932">🔒</tg-emoji> <b>Kim jazoladi:</b> {admin}\n<tg-emoji emoji-id="5872988737826197458">⛔️</tg-emoji> <b>Nima:</b> {punishment}{reason}{time}{chat}',
        'log_chat': '\n<tg-emoji emoji-id="5872886929921413168">💬</tg-emoji> <b>Chat:</b> {chat}',
        'log_reason': '\n<tg-emoji emoji-id="5870676941614354370">🖋</tg-emoji> <b>Sabab:</b> {reason}',
        'log_time': '\n<tg-emoji emoji-id="5870729937215819584">⏰️</tg-emoji> <b>Muddat:</b> {time}',
        'act.mute': 'Ovozsiz',
        'act.ban': 'Blok',
        'act.kick': 'Chiqarish',
        'act.unmute': 'Ovoz berildi',
        'act.unban': 'Blokdan chiqarildi',
        'act.warn': 'Ogohlantirish',
        'act.nomedia': 'Media taqiqlandi',
        'act.allowmedia': 'Mediaga ruxsat',
        'act.rights': 'Huquqlar o‘zgardi',
        'flushda.loading': '<tg-emoji emoji-id="5870813306826002498">🟡</tg-emoji> <b>O\'chirilgan hisoblarni olib tashlayapman…</b>',
        'flushda.loading.chat': '<tg-emoji emoji-id="5870813306826002498">🟡</tg-emoji> <b>Bu chatdan o\'chirilgan hisoblarni olib tashlayapman…</b>',
        'flushda.loading.channels': '<tg-emoji emoji-id="5870813306826002498">🟡</tg-emoji> <b>Kanallardan o\'chirilgan hisoblarni olib tashlayapman…</b>',
        'monday': 'Dushanba',
        'tuesday': 'Seshanba',
        'wednesday': 'Chorshanba',
        'thursday': 'Payshanba',
        'friday': 'Juma',
        'saturday': 'Shanba',
        'sunday': 'Yakshanba',
        'cfg.gban_except': '.gban va .ungban tegmaydigan chat ID lari',
        'cfg.gban_pm_block': '.gban da shaxsiy chatni bloklash, .ungban da ochish',
        'cfg.gban_pm_del_history': 'Bloklash bilan birga shaxsiy yozishmani ham o‘chirish',
        'cfg.gban_pm_except': 'Shaxsiy chatda hech qachon bloklanmaydigan foydalanuvchi ID lari',
        'cfg.global_logs': 'Faqat o‘z buyruqlaringizni emas, admin bo‘lgan barcha chatlardagi cheklovlarni yozish',
        'gban.no_reason': 'Ko‘rsatilmagan',
        'gban.args': '<tg-emoji emoji-id="5870994129244131212">👤</tg-emoji> <b>Foydalanuvchini ko‘rsating.</b>\nXabarga javob bering yoki username yoki ID yuboring.',
        'gban.working': '<tg-emoji emoji-id="5870718740236079262">🌍</tg-emoji> <b><a href="{url}">{name}</a> hamma joyda bloklanmoqda…</b>',
        'gban.unworking': '<tg-emoji emoji-id="5870718740236079262">🌍</tg-emoji> <b><a href="{url}">{name}</a> hamma joyda blokdan chiqarilmoqda…</b>',
        'gban.done': '<tg-emoji emoji-id="5872988737826197458">⛔</tg-emoji> <b><a href="{url}">{name}</a> {count} ta chatda bloklandi</b>\n<b>Sabab:</b> <i>{reason}</i>',
        'gban.undone': '<tg-emoji emoji-id="5870948572526022116">👋🏻</tg-emoji> <b><a href="{url}">{name}</a> {count} ta chatda blokdan chiqarildi</b>',
        'gban.chats': '\n{chats}',
        'gban.pm_blocked': '\n<tg-emoji emoji-id="5872988737826197458">🚫</tg-emoji> <b>Shaxsiy chatda bloklandi</b>',
        'gban.pm_unblocked': '\n<tg-emoji emoji-id="5870948572526022116">👋🏻</tg-emoji> <b>Shaxsiy chatda blokdan chiqarildi</b>',
        'gban.pm_failed': '\n<tg-emoji emoji-id="5870704313440932932">🔓</tg-emoji> <b>Shaxsiy chatda bloklab bo‘lmadi</b>',
        'gban.pm_cleared': ' · <b>Shaxsiy yozishma o‘chirildi</b>',
        'chatinfo': '<tg-emoji emoji-id="5870704313440932932">🔒</tg-emoji><b> Turi: {type_of}\n</b><tg-emoji emoji-id="5870495350397079101">#️⃣</tg-emoji><b> Chat ID: </b><code>{id}</code><b>\n</b><tg-emoji emoji-id="5873225338984599714">🔥</tg-emoji><b> Nomi: {title}\n\n</b><tg-emoji emoji-id="5870676941614354370">🖋</tg-emoji><b> Tavsif: {about}\n\n</b><tg-emoji emoji-id="5870684638195748414">👑</tg-emoji><b> Adminlar: {admins_count}\n</b><tg-emoji emoji-id="5870633910337015697">✅</tg-emoji><b> Onlayn: {online_count}\n</b><tg-emoji emoji-id="5870994129244131212">👤</tg-emoji><b> Ishtirokchilar: {participants_count}\n</b><tg-emoji emoji-id="5872988737826197458">🚫</tg-emoji><b> Chiqarilganlar: {kicked_count}\n</b><tg-emoji emoji-id="5870892901159932239">🔀</tg-emoji><b> So\'rovlar: {requests_pending}\n\n</b><tg-emoji emoji-id="5870729937215819584">🕐</tg-emoji><b> Sekin rejim: {slowmode_seconds}\n</b><tg-emoji emoji-id="5872980989705196227">📞</tg-emoji><b> Qo\'ng\'iroq: {call}\n</b><tg-emoji emoji-id="5870875489362513438">🗑</tg-emoji><b> TTL: {ttl_period}\n</b><tg-emoji emoji-id="5870994129244131212">👤</tg-emoji><b> So\'nggi so\'rovlar: {recent_requesters}\n\n</b><tg-emoji emoji-id="5870772616305839506">👥</tg-emoji><b> Bog\'langan chat: {linked_chat_id}\n</b><tg-emoji emoji-id="5870704313440932932">🛡</tg-emoji><b> Antispam: {antispam}\n</b><tg-emoji emoji-id="5870542612217204751">👁</tg-emoji><b> Ro\'yxat yashirin: {participants_hidden}\n\n</b><tg-emoji emoji-id="5870527201874546272">🔗</tg-emoji><b> Havola: {link}</b>',
        'userinfo': '<blockquote><tg-emoji emoji-id="5870495350397079101">#️⃣</tg-emoji><b> ID: {user_id}\n</b><tg-emoji emoji-id="5873225338984599714">🔥</tg-emoji><b> Ism: {first_name}\n</b><tg-emoji emoji-id="5873225338984599714">🔥</tg-emoji><b> Familiya: {last_name}\n</b><tg-emoji emoji-id="5872980989705196227">📞</tg-emoji><b> Telefon: {phone}\n</b><tg-emoji emoji-id="5870998024779468554">🐶</tg-emoji><b> Username\'lar: {usernames}</b></blockquote><b>\n</b><blockquote><tg-emoji emoji-id="5870609858520158157">ℹ️</tg-emoji><b> Haqida: {about}</b></blockquote><b>\n</b><blockquote><tg-emoji emoji-id="5870729937215819584">🕐</tg-emoji><b> Soatlar: </b>{business_work_hours}\n<tg-emoji emoji-id="5870450871715761518">❤️</tg-emoji><b> Emoji status: {emoji_status}</b></blockquote><b>\n</b><blockquote><tg-emoji emoji-id="5870693687691841267">🔉</tg-emoji><b> Kanal: {personal_channel}\n</b><tg-emoji emoji-id="5870847962917113498">🎂</tg-emoji><b> Tug\'ilgan kun: {birthday}\n</b><tg-emoji emoji-id="5870478797593120516">🎁</tg-emoji><b> Sovg\'alar: {stargifts_count}</b></blockquote><b>\n</b><blockquote><tg-emoji emoji-id="5870931487146119264">🚨</tg-emoji><b> Umumiy chatlar soni: {common_chats_count}\n</b><tg-emoji emoji-id="5870772616305839506">👥</tg-emoji><b> Umumiy chatlar: {common_chats}</b></blockquote>',
        'promote.no_rights': '<tg-emoji emoji-id="5870704313440932932">🔓</tg-emoji> <b>Adminlarni o‘zgartirish uchun huquq yetarli emas.</b>',
        'promote.no_user': '<tg-emoji emoji-id="5870994129244131212">👤</tg-emoji> <b>Foydalanuvchini ko‘rsating.</b>\nXabarga javob bering yoki username yoki ID yuboring.',
        'promote.demoted': '<tg-emoji emoji-id="5870948572526022116">👋🏻</tg-emoji> <b>{name}</b> [<code>{user_id}</code>] <b>endi admin emas.</b>',
        'promote.promoted_full': '<tg-emoji emoji-id="5870684638195748414">👑</tg-emoji> <b>{name}</b> [<code>{user_id}</code>] <b>to‘liq huquqli admin qilindi.</b>\n<b>Lavozim:</b> {rank}',
        'promote.promoted': '<tg-emoji emoji-id="5870684638195748414">👑</tg-emoji> <b>{name}</b> [<code>{user_id}</code>] <b>admin qilindi.</b>\n<b>Lavozim:</b> {rank}',
        'promote.choose': '<tg-emoji emoji-id="5870684638195748414">👑</tg-emoji> <b>{name} uchun huquqlar</b> [<code>{user_id}</code>]\n<b>Lavozim:</b> {rank}',
        'promote.confirm': 'Tasdiqlash',
        'promote.default_rank': 'Admin',
        'promote.tag_group_only': '<tg-emoji emoji-id="5870931487146119264">⚠️</tg-emoji> <b>Ishtirokchi teglari faqat guruhlarda ishlaydi.</b>',
        'promote.tag_usage': '<b>Ishlatish:</b> <code>{prefix}settag @user teg</code> yoki javobda <code>{prefix}settag teg</code>. Tegsiz yoki <code>-</code> tegni olib tashlaydi.',
        'promote.tag_invalid': '<tg-emoji emoji-id="5870657884844462243">❌</tg-emoji> <b>Teg — ko‘pi bilan 16 belgi, emojisiz.</b>',
        'promote.tag_no_rights': '<tg-emoji emoji-id="5870704313440932932">🔓</tg-emoji> <b>Boshqaning tegini o‘zgartirish uchun «Ishtirokchi teglarini boshqarish» huquqi kerak.</b>',
        'promote.tag_updated': '<tg-emoji emoji-id="5870676941614354370">🖋</tg-emoji> <b>{name} tegi:</b> <code>{rank}</code>',
        'promote.tag_removed': '<tg-emoji emoji-id="5255831443816327915">🗑</tg-emoji> <b>{name} tegi olib tashlandi.</b>',
        'promote.rpc_error': '<tg-emoji emoji-id="5870657884844462243">❌</tg-emoji> <b>Telegram xatosi:</b> <code>{error}</code>',
        'promote.right.change_info': '{emoji} {where} ma’lumotini o‘zgartirish',
        'promote.right.post_messages': '{emoji} Post joylash',
        'promote.right.edit_messages': '{emoji} Postlarni tahrirlash',
        'promote.right.delete_messages': '{emoji} Xabarlarni o‘chirish',
        'promote.right.ban_users': '{emoji} Foydalanuvchilarni cheklash',
        'promote.right.invite_users': '{emoji} Foydalanuvchilarni qo‘shish',
        'promote.right.pin_messages': '{emoji} Xabarlarni qadash',
        'promote.right.add_admins': '{emoji} Admin tayinlash',
        'promote.right.anonymous': '{emoji} Anonimlik',
        'promote.right.manage_call': '{emoji} Qo‘ng‘iroqlarni boshqarish',
        'promote.right.manage_topics': '{emoji} Mavzularni boshqarish',
        'promote.right.post_stories': '{emoji} Hikoya joylash',
        'promote.right.edit_stories': '{emoji} Hikoyalarni tahrirlash',
        'promote.right.delete_stories': '{emoji} Hikoyalarni o‘chirish',
        'promote.right.manage_direct_messages': '{emoji} Kanal DM’larini boshqarish',
        'promote.right.manage_ranks': '{emoji} Ishtirokchi teglarini boshqarish',
        'promote.right.manage_linked_peers': '{emoji} Bog‘langan chatlarni boshqarish',
        'promote.right.manage_welcome_messages': '{emoji} Salomlashuvlarni boshqarish',
        'promote.right.other': '{emoji} Boshqa huquqlar',
        'chat.not_channel': '<tg-emoji emoji-id="5870693687691841267">📣</tg-emoji> <b>Bu faqat superguruh va kanallarda ishlaydi.</b>',
        'chat.no_rights': '<tg-emoji emoji-id="5870704313440932932">🔓</tg-emoji> <b>Bu chatni o\'zgartirish uchun huquq yetarli emas.</b>',
        'chat.usage.slow': '<b>Ishlatish:</b> <code>{prefix}slow</code> off, yoki <code>30</code>, <code>1m</code>, <code>5m</code>, <code>1h</code>.',
        'chat.usage.about': '<b>Ishlatish:</b> <code>{prefix}setabout matn</code>. <code>-</code> tozalaydi.',
        'chat.usage.photo': '<b>Ishlatish:</b> rasmga javoban <code>{prefix}setphoto</code>. <code>-</code> olib tashlaydi.',
        'chat.usage.username': '<b>Ishlatish:</b> <code>{prefix}setusername nom</code>. <code>-</code> olib tashlaydi.',
        'chat.usage.link': '<b>Ishlatish:</b> <code>{prefix}link</code>, <code>new</code>, <code>revoke</code> yoki <code>nom</code>.',
        'chat.slow_off': '<tg-emoji emoji-id="5870729937215819584">🕐</tg-emoji> <b>Sekin rejim o\'chiq.</b>',
        'chat.slow_on': '<tg-emoji emoji-id="5870729937215819584">🕐</tg-emoji> <b>Sekin rejim:</b> <code>{seconds}</code> s',
        'chat.about_set': '<tg-emoji emoji-id="5870676941614354370">🖋</tg-emoji> <b>Tavsif yangilandi.</b>',
        'chat.about_cleared': '<tg-emoji emoji-id="5255831443816327915">🗑</tg-emoji> <b>Tavsif tozalandi.</b>',
        'chat.photo_set': '<tg-emoji emoji-id="5870782662234346251">🖼️</tg-emoji> <b>Chat rasmi yangilandi.</b>',
        'chat.photo_cleared': '<tg-emoji emoji-id="5255831443816327915">🗑</tg-emoji> <b>Chat rasmi olib tashlandi.</b>',
        'chat.username_set': '<tg-emoji emoji-id="5870527201874546272">🔗</tg-emoji> <b>Username:</b> @{username}',
        'chat.username_cleared': '<tg-emoji emoji-id="5255831443816327915">🗑</tg-emoji> <b>Username olib tashlandi.</b>',
        'chat.sign_on': '<tg-emoji emoji-id="5870676941614354370">🖋</tg-emoji> <b>Muallif imzolari yoqildi.</b>',
        'chat.sign_off': '<tg-emoji emoji-id="5870676941614354370">🖋</tg-emoji> <b>Muallif imzolari o\'chirildi.</b>',
        'chat.forum_on': '<tg-emoji emoji-id="5872886929921413168">💬</tg-emoji> <b>Mavzular yoqildi.</b>',
        'chat.forum_off': '<tg-emoji emoji-id="5872886929921413168">💬</tg-emoji> <b>Mavzular o\'chirildi.</b>',
        'chat.spam_on': '<tg-emoji emoji-id="5870704313440932932">🛡</tg-emoji> <b>Kuchli antispam yoqildi.</b>',
        'chat.spam_off': '<tg-emoji emoji-id="5870704313440932932">🛡</tg-emoji> <b>Kuchli antispam o\'chirildi.</b>',
        'chat.hidden_on': '<tg-emoji emoji-id="5870542612217204751">👁</tg-emoji> <b>A\'zolar ro\'yxati yashirin.</b>',
        'chat.hidden_off': '<tg-emoji emoji-id="5870542612217204751">👁</tg-emoji> <b>A\'zolar ro\'yxati ochiq.</b>',
        'chat.history_on': '<tg-emoji emoji-id="5870729937215819584">🕐</tg-emoji> <b>Yangi a\'zolar tarixni ko\'radi.</b>',
        'chat.history_off': '<tg-emoji emoji-id="5870729937215819584">🕐</tg-emoji> <b>Tarix yangi a\'zolardan yashirin.</b>',
        'chat.join_on': '<tg-emoji emoji-id="5870892901159932239">🔀</tg-emoji> <b>Qo\'shilish so\'rovlari yoqildi.</b>',
        'chat.join_off': '<tg-emoji emoji-id="5870892901159932239">🔀</tg-emoji> <b>Qo\'shilish so\'rovlari o\'chirildi.</b>',
        'chat.link_none': '<tg-emoji emoji-id="5870527201874546272">🔗</tg-emoji> <b>Taklif havolasi hali yo\'q.</b>',
        'chat.link': '<tg-emoji emoji-id="5870527201874546272">🔗</tg-emoji> <b>Taklif:</b> {link}',
        'chat.link_revoked': '<tg-emoji emoji-id="5255831443816327915">🗑</tg-emoji> <b>Taklif bekor qilindi.</b>\n<tg-emoji emoji-id="5870527201874546272">🔗</tg-emoji> <b>Yangi:</b> {link}',
        'chat.link_created': '<tg-emoji emoji-id="5870633910337015697">✅</tg-emoji> <b>Taklif yaratildi.</b>\n<tg-emoji emoji-id="5870527201874546272">🔗</tg-emoji> {link}',
        'rights.header': '<tg-emoji emoji-id="5870684638195748414">👑</tg-emoji> <b>{name}</b> [<code>{user_id}</code>]\n<b>Rol:</b> {role}\n<b>Lavozim:</b> {rank}',
        'rights.owner': 'Egasi',
        'rights.admin': 'Admin',
        'rights.member': "A'zo",
        'rights.none': '<tg-emoji emoji-id="5870657884844462243">✖️</tg-emoji> <b>{name}</b> [<code>{user_id}</code>] <b>admin emas.</b>',
        'rights.empty': "<i>Huquq yo'q.</i>",
    }

    strings_kk = {
        'name': 'Helm',
        'cfg.warnlimit': 'Шектеуге дейінгі ескерту саны',
        'cfg.ptime': 'Жаза мерзімі, әдепкі',
        'cfg.wl_punishment': 'Ескерту шегіне жеткенде не болады',
        'cfg.wl_reason': 'Шек жазасының себебі',
        'cfg.wl_timespan': 'Шек жазасы қаншаға созылады',
        'error.wrongchattype.pm': '<tg-emoji emoji-id="5870563425628721113">📧</tg-emoji> <b>Бұл модульді жеке хабарламаларда пайдалана алмайсыз.</b>\nБұл модуль топтарға арналған.',
        'error.wrongchattype.channel': '<tg-emoji emoji-id="5870693687691841267">📣</tg-emoji> <b>Бұл модульді арналарда пайдалана алмайсыз.</b>\nБұл модуль топтарға арналған.',
        'error.no_args.user': '<tg-emoji emoji-id="5870994129244131212">👤</tg-emoji> <b>Пайдаланушыны көрсетуіңіз керек.</b>\nПайдаланушы атын, ID немесе хабарламаға жауап беруді пайдалана аласыз.',
        'error.locate_user': '<tg-emoji emoji-id="5870974879200711167">🔎</tg-emoji> <b>Пайдаланушы табылмады.</b>\nПайдаланушы атын немесе ID қайта тексеріңіз.',
        'error.can_not_restrict': '<tg-emoji emoji-id="5870704313440932932">🔓</tg-emoji> <b>Пайдаланушыны шектей алмадым.</b>\nСізде қажетті құқықтар жоқ немесе сіз көтермеген админді шектемексіз.',
        'error.reply_is_service': '<tg-emoji emoji-id="5870982283724328568">⚙️</tg-emoji> <b>Қызметтік хабарламаға жауап беру арқылы пайдаланушыны шектей алмайсыз.</b>\nПайдаланушының хабарламасына жауап беріңіз.',
        'error.self': '<tg-emoji emoji-id="5872988737826197458">🔫</tg-emoji> <b>Өзіңізді шектей алмайсыз.</b>\nӨзіңізге сонша қатал болмаңыз.',
        'error.warn_self': '<tg-emoji emoji-id="5870948572526022116">☝🏻</tg-emoji> <b>Жаман бала.</b>\nОйнауды доғарып, модерациямен айналысыңыз.',
        'error.no_args.rights': '<tg-emoji emoji-id="5872996816659681395">❓</tg-emoji> <b>Құқықтарды көрсетуіңіз керек.</b>\nҚұқықтар тізбек болып табылады (мысалы, барлық құқықтар үшін `123456789ab`). Инверсиялау үшін алдына `r` қойыңыз.',
        'error.no_user': '<tg-emoji emoji-id="5870994129244131212">👤</tg-emoji> <b>Пайдаланушыны көрсетіңіз.</b>\nЖауап, username немесе ID.',
        'error.no_reply': '<tg-emoji emoji-id="5872886929921413168">💬</tg-emoji> <b>Хабарға жауап беріңіз.</b>',
        'error.invalid_args': '<tg-emoji emoji-id="5872996816659681395">❓</tg-emoji> <b>Формат:</b> <code>g</code> немесе <code>c</code>, содан кейін атау. Соңында <code>30m</code>, <code>2h</code> немесе <code>1d</code> — чат өзі жойылады.',
        'error.too_much': '<tg-emoji emoji-id="5870657884844462243">❌</tg-emoji> <b>Қате мөлшер</b>\n1 мен 100 аралығындағы санды енгізіңіз.',
        'error.insufficient_rights': '<tg-emoji emoji-id="5870704313440932932">🔓</tg-emoji> <b>Құқық жеткіліксіз.</b>',
        'error.unknown': '<tg-emoji emoji-id="5870657884844462243">🙅🏻\u200d♂️</tg-emoji> <b>Белгісіз қате</b>',
        'error': '<b>Қате:</b> <code>{error}</code>',
        'done.muted.f': '<tg-emoji emoji-id="5870681133502435302">🔇</tg-emoji> <b>{user} мәңгілікке дыбыссыз етілді</b>',
        'done.muted': '<tg-emoji emoji-id="5870681133502435302">🔇</tg-emoji> <b>{user} {timespan} уақытқа дыбыссыз етілді</b>',
        'done.warned': '<tg-emoji emoji-id="5870931487146119264">⚠</tg-emoji> <b>{user} ескерту алды</b>',
        'done.banned.f': '<tg-emoji emoji-id="5872988737826197458">⛔</tg-emoji> <b>{user} мәңгілікке бұғатталды</b>',
        'done.banned': '<tg-emoji emoji-id="5872988737826197458">⛔</tg-emoji> <b>{user} {timespan} уақытқа бұғатталды</b>',
        'done.kicked': '<tg-emoji emoji-id="5870778972857438051">🍃</tg-emoji> <b>{user} топтан шығарылды</b>',
        'done.nomedia': '<tg-emoji emoji-id="5870782662234346251">🖼️</tg-emoji> <b>{user} {timespan} бойы медиа жібере алмайды</b>',
        'done.nomedia.f': '<tg-emoji emoji-id="5870782662234346251">🖼️</tg-emoji> <b>{user} бұдан былай медиа жібере алмайды</b>',
        'done.allowmedia': '<tg-emoji emoji-id="5870782662234346251">🖼️</tg-emoji> <b>{user} қайтадан медиа жібере алады</b>',
        'done.setrights.f': '<tg-emoji emoji-id="5870982283724328568">🔧</tg-emoji> <b><code>{user}</code> үшін құқықтар {rights} етіп орнатылды</b>',
        'done.setrights': '<tg-emoji emoji-id="5870982283724328568">🔧</tg-emoji> <b><code>{user}</code> үшін құқықтар {timespan} уақытқа {rights} етіп орнатылды</b>',
        'done.unmuted': '<tg-emoji emoji-id="5870693687691841267">🔊</tg-emoji> <b>{user} қайтадан жаза алады</b>',
        'done.unbanned': '<tg-emoji emoji-id="5870948572526022116">👋🏻</tg-emoji> <b>{user} бұғаттан шығарылды</b>',
        'done.unwarned.one': '<tg-emoji emoji-id="5870930636742595124">⚖️</tg-emoji> <b>{user} бір ескертуден босатылды</b>',
        'done.unwarned.all': '<tg-emoji emoji-id="5870930636742595124">⚖️</tg-emoji> <b><code>{user}</code> барлық ескертулері жойылды</b>',
        'done.da_kicked': '<tg-emoji emoji-id="5870778972857438051">🍃</tg-emoji> <b><code>{amount}</code> жойылған аккаунт шығарылды</b>',
        'done.pin': '<tg-emoji emoji-id="5870930744116776638">📌</tg-emoji> <b>Бекітілді</b>',
        'done.unpin': '<tg-emoji emoji-id="5870930744116776638">📌</tg-emoji> <b>Бекіту алынды</b>',
        'done.channel_ban.on': '<tg-emoji emoji-id="5870704313440932932">🔒</tg-emoji> <b>Жақсы, енді пайдаланушылар арналар атынан жаза алмайды.</b>',
        'done.channel_ban.off': '<tg-emoji emoji-id="5870704313440932932">🔓</tg-emoji> <b>Жақсы, пайдаланушылар қайтадан арналар атынан жаза алады.</b>',
        'done.channel_ban.action': '<tg-emoji emoji-id="5872988737826197458">⛔</tg-emoji> <b>{user} мәңгілікке бұғатталды</b>\n<b>Себебі:</b> арна атынан жазғаны үшін',
        'done.flushda': '<tg-emoji emoji-id="5870778972857438051">🍃</tg-emoji> <b><code>{amt}</code> жойылған аккаунт өшірілді</b>',
        'done.glban.f': '<tg-emoji emoji-id="5870718740236079262">🌍</tg-emoji> <b>{user} {count} чатта мәңгілікке бұғатталды</b>',
        'done.glban': '<tg-emoji emoji-id="5870718740236079262">🌍</tg-emoji> <b>{user} {count} чатта {timespan} уақытқа бұғатталды</b>',
        'done.glunban': '<tg-emoji emoji-id="5870718740236079262">🌍</tg-emoji> <b>{user} {count} чатта бұғаттан шығарылды</b>',
        'done.leave': '<tg-emoji emoji-id="5870764288364252592">😶</tg-emoji> <b>Шығып жатырмын.</b>',
        'done.leave.reason': '<tg-emoji emoji-id="5870764288364252592">😶</tg-emoji> <b>Шығып жатырмын.</b>\n<b>Себебі:</b> <i>{reason}</i>',
        'reason': '\n<b>Себебі:</b> <i>{0}</i>',
        'chat_id': '<tg-emoji emoji-id="5870772616305839506">👥</tg-emoji> <b>Чат ID</b>: <code>{chat_id}</code>{additional}\n<tg-emoji emoji-id="5870994129244131212">👤</tg-emoji> <b>Сіздің ID</b>: <code>{my_id}</code>',
        'person_in_reply_id': '<tg-emoji emoji-id="5870772616305839506">🫂</tg-emoji> <b>Жауап берілген адам ID</b>: <code>{reply_id}</code>',
        'sys.DA': 'Жойылған аккаунт',
        'sys.LANG': 'en_US',
        'sys.forever': 'мәңгілікке',
        'of_chat': 'Чат',
        'of_channel': 'Арна',
        'loading': '<tg-emoji emoji-id="5870813306826002498">🟡</tg-emoji> <b>Деректер жүктелуде ...</b>',
        'own_list': '<b>Менің иеліктерім ({count}):</b>\n\n{msg}',
        'no_ownerships': '<tg-emoji emoji-id="5870657884844462243">❌</tg-emoji> <b>Иеліктер жоқ.</b>',
        'not_a_chat': '<tg-emoji emoji-id="5870931487146119264">⚠️</tg-emoji> <b>Бұл тек топтарда жұмыс істейді!</b>',
        'admins_in_chat': '<tg-emoji emoji-id="5870684638195748414">👑</tg-emoji> <b><code>{title}</code> админдері ({count}):</b>\n\n',
        'admins_in_chat_caption': '<b>"{}" админдері:</b>',
        'too_many_admins': 'Админдер өте көп. Тізім файлға жүктелуде...',
        'no_admins_in_chat': '<b>Бұл чатта админдер жоқ.</b>',
        'bots_in_chat': '<tg-emoji emoji-id="5870531058755178453">🤖</tg-emoji> <b><code>{title}</code> боттары ({count}):</b>\n\n',
        'bots_in_chat_caption': '<b><code>{}</code> боттары:</b>',
        'too_many_bots': 'Боттар өте көп. Тізім файлға жүктелуде...',
        'no_bots_in_chat': '<b>Бұл чатта боттар жоқ.</b>',
        'users_in_chat': '<tg-emoji emoji-id="5870994129244131212">👤</tg-emoji> <b><code>{title}</code> қатысушылары ({count}):</b>\n\n',
        'users_in_chat_caption': '<b><code>{}</code> қатысушылары:</b>',
        'no_user_in_chat': '<b>Бұл чатта қатысушылар жоқ.</b>',
        'too_many_users': 'Қатысушылар тым көп. Тізімді файлмен жіберемін…',
        'chat_muted': '<tg-emoji emoji-id="5870681133502435302">🔇</tg-emoji> <b>Чат қатысушылар үшін жабылды.</b>',
        'chat_unmuted': '<tg-emoji emoji-id="5870633910337015697">✅</tg-emoji> <b>Чат барлық қатысушылар үшін ашылды.</b>',
        'title_changed': '<b>{type_of} атауы <code>{old_title}</code> орнына <code>{new_title}</code> болып өзгертілді.</b>',
        'user_invited': '<tg-emoji emoji-id="5870633910337015697">✅</tg-emoji> <b><a href=\'tg://user?id={id}\'>{user}</a> чатқа шақырылды.</b>',
        'creator': '<tg-emoji emoji-id="5870684638195748414">👑</tg-emoji> <b>Құрушы: <a href=\'tg://user?id={id}\'>{creator}</a>.</b>',
        'no_creator': '<tg-emoji emoji-id="5870657884844462243">❌</tg-emoji> <b>Құрушы табылмады.</b>',
        'channel_created': '<tg-emoji emoji-id="5870633910337015697">✅</tg-emoji> <b><code>{title}</code> арнасы құрылды.\n</b><tg-emoji emoji-id="5870527201874546272">🔗</tg-emoji><b> Шақыру сілтемесі: {link}</b>',
        'group_created': '<tg-emoji emoji-id="5870633910337015697">✅</tg-emoji> <b><code>{title}</code> тобы құрылды.\n</b><tg-emoji emoji-id="5870527201874546272">🔗</tg-emoji><b> Шақыру сілтемесі: {link}</b>',
        'temp_chat': '\n<tg-emoji emoji-id="5870875489362513438">🗑</tg-emoji> <b>{timespan} кейін өзі жойылады.</b>',
        'type_group': 'Топ',
        'type_channel': 'Арна',
        'type_unknown': 'Белгісіз',
        'yes': '<tg-emoji emoji-id="5870633910337015697">✅</tg-emoji> Иә',
        'no': '<tg-emoji emoji-id="5870657884844462243">✖️</tg-emoji> Жоқ',
        'all_approved': '<tg-emoji emoji-id="5870633910337015697">✅</tg-emoji> <b>Пайдаланушылар мақұлданды</b>',
        'all_dismissed': '<tg-emoji emoji-id="5870657884844462243">✖️</tg-emoji> <b>Сұраулар қабылданбады</b>',
        'log_text': '<tg-emoji emoji-id="5870994129244131212">👤</tg-emoji> <b>Кім:</b> {user}\n<tg-emoji emoji-id="5870704313440932932">🔒</tg-emoji> <b>Кім жазалады:</b> {admin}\n<tg-emoji emoji-id="5872988737826197458">⛔️</tg-emoji> <b>Не:</b> {punishment}{reason}{time}{chat}',
        'log_chat': '\n<tg-emoji emoji-id="5872886929921413168">💬</tg-emoji> <b>Чат:</b> {chat}',
        'log_reason': '\n<tg-emoji emoji-id="5870676941614354370">🖋</tg-emoji> <b>Себебі:</b> {reason}',
        'log_time': '\n<tg-emoji emoji-id="5870729937215819584">⏰️</tg-emoji> <b>Мерзім:</b> {time}',
        'act.mute': 'Дыбыссыз',
        'act.ban': 'Бұғат',
        'act.kick': 'Шығару',
        'act.unmute': 'Дыбысы қосылды',
        'act.unban': 'Бұғаттан шығарылды',
        'act.warn': 'Ескерту',
        'act.nomedia': 'Медиаға тыйым',
        'act.allowmedia': 'Медиаға рұқсат',
        'act.rights': 'Құқықтар өзгерді',
        'flushda.loading': '<tg-emoji emoji-id="5870813306826002498">🟡</tg-emoji> <b>Жойылған аккаунттарды алып жатырмын…</b>',
        'flushda.loading.chat': '<tg-emoji emoji-id="5870813306826002498">🟡</tg-emoji> <b>Осы чаттан жойылған аккаунттарды алып жатырмын…</b>',
        'flushda.loading.channels': '<tg-emoji emoji-id="5870813306826002498">🟡</tg-emoji> <b>Арналардан жойылған аккаунттарды алып жатырмын…</b>',
        'monday': 'Дүйсенбі',
        'tuesday': 'Сейсенбі',
        'wednesday': 'Сәрсенбі',
        'thursday': 'Бейсенбі',
        'friday': 'Жұма',
        'saturday': 'Сенбі',
        'sunday': 'Жексенбі',
        'cfg.gban_except': '.gban мен .ungban тиіспейтін чат ID-лері',
        'cfg.gban_pm_block': '.gban кезінде жеке чатты бұғаттау, .ungban кезінде ашу',
        'cfg.gban_pm_del_history': 'Бұғаттаумен бірге жеке хат алмасуды да жою',
        'cfg.gban_pm_except': 'Жеке чатта ешқашан бұғатталмайтын пайдаланушы ID-лері',
        'cfg.global_logs': 'Тек өз командаларыңызды емес, админ болған барлық чаттардағы шектеулерді жазу',
        'gban.no_reason': 'Көрсетілмеген',
        'gban.args': '<tg-emoji emoji-id="5870994129244131212">👤</tg-emoji> <b>Пайдаланушыны көрсетіңіз.</b>\nХабарға жауап беріңіз немесе username не ID жіберіңіз.',
        'gban.working': '<tg-emoji emoji-id="5870718740236079262">🌍</tg-emoji> <b><a href="{url}">{name}</a> барлық жерде бұғатталуда…</b>',
        'gban.unworking': '<tg-emoji emoji-id="5870718740236079262">🌍</tg-emoji> <b><a href="{url}">{name}</a> барлық жерде бұғаттан шығарылуда…</b>',
        'gban.done': '<tg-emoji emoji-id="5872988737826197458">⛔</tg-emoji> <b><a href="{url}">{name}</a> {count} чатта бұғатталды</b>\n<b>Себебі:</b> <i>{reason}</i>',
        'gban.undone': '<tg-emoji emoji-id="5870948572526022116">👋🏻</tg-emoji> <b><a href="{url}">{name}</a> {count} чатта бұғаттан шығарылды</b>',
        'gban.chats': '\n{chats}',
        'gban.pm_blocked': '\n<tg-emoji emoji-id="5872988737826197458">🚫</tg-emoji> <b>Жеке чатта бұғатталды</b>',
        'gban.pm_unblocked': '\n<tg-emoji emoji-id="5870948572526022116">👋🏻</tg-emoji> <b>Жеке чатта бұғаттан шығарылды</b>',
        'gban.pm_failed': '\n<tg-emoji emoji-id="5870704313440932932">🔓</tg-emoji> <b>Жеке чатта бұғаттау сәтсіз аяқталды</b>',
        'gban.pm_cleared': ' · <b>Жеке хат алмасу жойылды</b>',
        'chatinfo': '<tg-emoji emoji-id="5870704313440932932">🔒</tg-emoji><b> Түрі: {type_of}\n</b><tg-emoji emoji-id="5870495350397079101">#️⃣</tg-emoji><b> Чат ID: </b><code>{id}</code><b>\n</b><tg-emoji emoji-id="5873225338984599714">🔥</tg-emoji><b> Атауы: {title}\n\n</b><tg-emoji emoji-id="5870676941614354370">🖋</tg-emoji><b> Сипаттама: {about}\n\n</b><tg-emoji emoji-id="5870684638195748414">👑</tg-emoji><b> Әкімшілер: {admins_count}\n</b><tg-emoji emoji-id="5870633910337015697">✅</tg-emoji><b> Онлайн: {online_count}\n</b><tg-emoji emoji-id="5870994129244131212">👤</tg-emoji><b> Қатысушылар: {participants_count}\n</b><tg-emoji emoji-id="5872988737826197458">🚫</tg-emoji><b> Шығарылғандар: {kicked_count}\n</b><tg-emoji emoji-id="5870892901159932239">🔀</tg-emoji><b> Өтінімдер: {requests_pending}\n\n</b><tg-emoji emoji-id="5870729937215819584">🕐</tg-emoji><b> Баяу режим: {slowmode_seconds}\n</b><tg-emoji emoji-id="5872980989705196227">📞</tg-emoji><b> Қоңырау: {call}\n</b><tg-emoji emoji-id="5870875489362513438">🗑</tg-emoji><b> TTL: {ttl_period}\n</b><tg-emoji emoji-id="5870994129244131212">👤</tg-emoji><b> Соңғы өтінімдер: {recent_requesters}\n\n</b><tg-emoji emoji-id="5870772616305839506">👥</tg-emoji><b> Байланысқан чат: {linked_chat_id}\n</b><tg-emoji emoji-id="5870704313440932932">🛡</tg-emoji><b> Антиспам: {antispam}\n</b><tg-emoji emoji-id="5870542612217204751">👁</tg-emoji><b> Тізім жасырын: {participants_hidden}\n\n</b><tg-emoji emoji-id="5870527201874546272">🔗</tg-emoji><b> Сілтеме: {link}</b>',
        'userinfo': '<blockquote><tg-emoji emoji-id="5870495350397079101">#️⃣</tg-emoji><b> ID: {user_id}\n</b><tg-emoji emoji-id="5873225338984599714">🔥</tg-emoji><b> Аты: {first_name}\n</b><tg-emoji emoji-id="5873225338984599714">🔥</tg-emoji><b> Тегі: {last_name}\n</b><tg-emoji emoji-id="5872980989705196227">📞</tg-emoji><b> Телефон: {phone}\n</b><tg-emoji emoji-id="5870998024779468554">🐶</tg-emoji><b> Username-дер: {usernames}</b></blockquote><b>\n</b><blockquote><tg-emoji emoji-id="5870609858520158157">ℹ️</tg-emoji><b> Өзі туралы: {about}</b></blockquote><b>\n</b><blockquote><tg-emoji emoji-id="5870729937215819584">🕐</tg-emoji><b> Сағаттар: </b>{business_work_hours}\n<tg-emoji emoji-id="5870450871715761518">❤️</tg-emoji><b> Эмодзи-мәртебе: {emoji_status}</b></blockquote><b>\n</b><blockquote><tg-emoji emoji-id="5870693687691841267">🔉</tg-emoji><b> Арна: {personal_channel}\n</b><tg-emoji emoji-id="5870847962917113498">🎂</tg-emoji><b> Туған күн: {birthday}\n</b><tg-emoji emoji-id="5870478797593120516">🎁</tg-emoji><b> Сыйлықтар: {stargifts_count}</b></blockquote><b>\n</b><blockquote><tg-emoji emoji-id="5870931487146119264">🚨</tg-emoji><b> Ортақ чаттар саны: {common_chats_count}\n</b><tg-emoji emoji-id="5870772616305839506">👥</tg-emoji><b> Ортақ чаттар: {common_chats}</b></blockquote>',
        'promote.no_rights': '<tg-emoji emoji-id="5870704313440932932">🔓</tg-emoji> <b>Әкімшілерді өзгертуге құқық жетпейді.</b>',
        'promote.no_user': '<tg-emoji emoji-id="5870994129244131212">👤</tg-emoji> <b>Пайдаланушыны көрсетіңіз.</b>\nХабарға жауап беріңіз немесе username не ID жіберіңіз.',
        'promote.demoted': '<tg-emoji emoji-id="5870948572526022116">👋🏻</tg-emoji> <b>{name}</b> [<code>{user_id}</code>] <b>енді әкімші емес.</b>',
        'promote.promoted_full': '<tg-emoji emoji-id="5870684638195748414">👑</tg-emoji> <b>{name}</b> [<code>{user_id}</code>] <b>толық құқықпен әкімші болды.</b>\n<b>Лауазымы:</b> {rank}',
        'promote.promoted': '<tg-emoji emoji-id="5870684638195748414">👑</tg-emoji> <b>{name}</b> [<code>{user_id}</code>] <b>әкімші болды.</b>\n<b>Лауазымы:</b> {rank}',
        'promote.choose': '<tg-emoji emoji-id="5870684638195748414">👑</tg-emoji> <b>{name} құқықтары</b> [<code>{user_id}</code>]\n<b>Лауазымы:</b> {rank}',
        'promote.confirm': 'Растау',
        'promote.default_rank': 'Әкімші',
        'promote.tag_group_only': '<tg-emoji emoji-id="5870931487146119264">⚠️</tg-emoji> <b>Қатысушы тегтері тек топтарда жұмыс істейді.</b>',
        'promote.tag_usage': '<b>Қолдану:</b> <code>{prefix}settag @user тег</code> немесе жауаппен <code>{prefix}settag тег</code>. Тегсіз немесе <code>-</code> тегті алып тастайды.',
        'promote.tag_invalid': '<tg-emoji emoji-id="5870657884844462243">❌</tg-emoji> <b>Тег — ең көбі 16 таңба, эмодзисіз.</b>',
        'promote.tag_no_rights': '<tg-emoji emoji-id="5870704313440932932">🔓</tg-emoji> <b>Бөтен тегті өзгерту үшін «Қатысушы тегтерін басқару» құқығы керек.</b>',
        'promote.tag_updated': '<tg-emoji emoji-id="5870676941614354370">🖋</tg-emoji> <b>{name} тегі:</b> <code>{rank}</code>',
        'promote.tag_removed': '<tg-emoji emoji-id="5255831443816327915">🗑</tg-emoji> <b>{name} тегі алынды.</b>',
        'promote.rpc_error': '<tg-emoji emoji-id="5870657884844462243">❌</tg-emoji> <b>Telegram қатесі:</b> <code>{error}</code>',
        'promote.right.change_info': '{emoji} {where} ақпаратын өзгерту',
        'promote.right.post_messages': '{emoji} Пост жариялау',
        'promote.right.edit_messages': '{emoji} Посттарды өзгерту',
        'promote.right.delete_messages': '{emoji} Хабарларды жою',
        'promote.right.ban_users': '{emoji} Пайдаланушыларды шектеу',
        'promote.right.invite_users': '{emoji} Пайдаланушыларды қосу',
        'promote.right.pin_messages': '{emoji} Хабарларды бекіту',
        'promote.right.add_admins': '{emoji} Әкімші тағайындау',
        'promote.right.anonymous': '{emoji} Анонимділік',
        'promote.right.manage_call': '{emoji} Қоңырауларды басқару',
        'promote.right.manage_topics': '{emoji} Тақырыптарды басқару',
        'promote.right.post_stories': '{emoji} Сторис жариялау',
        'promote.right.edit_stories': '{emoji} Стористі өзгерту',
        'promote.right.delete_stories': '{emoji} Стористі жою',
        'promote.right.manage_direct_messages': '{emoji} Арна ЖХ басқару',
        'promote.right.manage_ranks': '{emoji} Қатысушы тегтерін басқару',
        'promote.right.manage_linked_peers': '{emoji} Байланысқан чаттарды басқару',
        'promote.right.manage_welcome_messages': '{emoji} Сәлемдесулерді басқару',
        'promote.right.other': '{emoji} Басқа құқықтар',
        'chat.not_channel': '<tg-emoji emoji-id="5870693687691841267">📣</tg-emoji> <b>Бұл тек супертоп пен арналарда жұмыс істейді.</b>',
        'chat.no_rights': '<tg-emoji emoji-id="5870704313440932932">🔓</tg-emoji> <b>Бұл чатты өзгертуге құқық жеткіліксіз.</b>',
        'chat.usage.slow': '<b>Қолдану:</b> <code>{prefix}slow</code> off, не <code>30</code>, <code>1m</code>, <code>5m</code>, <code>1h</code>.',
        'chat.usage.about': '<b>Қолдану:</b> <code>{prefix}setabout мәтін</code>. <code>-</code> тазартады.',
        'chat.usage.photo': '<b>Қолдану:</b> фотоға жауаппен <code>{prefix}setphoto</code>. <code>-</code> алып тастайды.',
        'chat.usage.username': '<b>Қолдану:</b> <code>{prefix}setusername атау</code>. <code>-</code> алып тастайды.',
        'chat.usage.link': '<b>Қолдану:</b> <code>{prefix}link</code>, <code>new</code>, <code>revoke</code> не <code>атау</code>.',
        'chat.slow_off': '<tg-emoji emoji-id="5870729937215819584">🕐</tg-emoji> <b>Баяу режим өшірулі.</b>',
        'chat.slow_on': '<tg-emoji emoji-id="5870729937215819584">🕐</tg-emoji> <b>Баяу режим:</b> <code>{seconds}</code> с',
        'chat.about_set': '<tg-emoji emoji-id="5870676941614354370">🖋</tg-emoji> <b>Сипаттама жаңартылды.</b>',
        'chat.about_cleared': '<tg-emoji emoji-id="5255831443816327915">🗑</tg-emoji> <b>Сипаттама тазартылды.</b>',
        'chat.photo_set': '<tg-emoji emoji-id="5870782662234346251">🖼️</tg-emoji> <b>Чат фотосы жаңартылды.</b>',
        'chat.photo_cleared': '<tg-emoji emoji-id="5255831443816327915">🗑</tg-emoji> <b>Чат фотосы алынды.</b>',
        'chat.username_set': '<tg-emoji emoji-id="5870527201874546272">🔗</tg-emoji> <b>Пайдаланушы аты:</b> @{username}',
        'chat.username_cleared': '<tg-emoji emoji-id="5255831443816327915">🗑</tg-emoji> <b>Пайдаланушы аты алынды.</b>',
        'chat.sign_on': '<tg-emoji emoji-id="5870676941614354370">🖋</tg-emoji> <b>Автор қолтаңбасы қосулы.</b>',
        'chat.sign_off': '<tg-emoji emoji-id="5870676941614354370">🖋</tg-emoji> <b>Автор қолтаңбасы өшірулі.</b>',
        'chat.forum_on': '<tg-emoji emoji-id="5872886929921413168">💬</tg-emoji> <b>Тақырыптар қосулы.</b>',
        'chat.forum_off': '<tg-emoji emoji-id="5872886929921413168">💬</tg-emoji> <b>Тақырыптар өшірулі.</b>',
        'chat.spam_on': '<tg-emoji emoji-id="5870704313440932932">🛡</tg-emoji> <b>Күшті антиспам қосулы.</b>',
        'chat.spam_off': '<tg-emoji emoji-id="5870704313440932932">🛡</tg-emoji> <b>Күшті антиспам өшірулі.</b>',
        'chat.hidden_on': '<tg-emoji emoji-id="5870542612217204751">👁</tg-emoji> <b>Мүшелер тізімі жасырын.</b>',
        'chat.hidden_off': '<tg-emoji emoji-id="5870542612217204751">👁</tg-emoji> <b>Мүшелер тізімі көрінеді.</b>',
        'chat.history_on': '<tg-emoji emoji-id="5870729937215819584">🕐</tg-emoji> <b>Жаңа мүшелер тарихты көреді.</b>',
        'chat.history_off': '<tg-emoji emoji-id="5870729937215819584">🕐</tg-emoji> <b>Тарих жаңа мүшелерден жасырын.</b>',
        'chat.join_on': '<tg-emoji emoji-id="5870892901159932239">🔀</tg-emoji> <b>Қосылу өтінімдері қосулы.</b>',
        'chat.join_off': '<tg-emoji emoji-id="5870892901159932239">🔀</tg-emoji> <b>Қосылу өтінімдері өшірулі.</b>',
        'chat.link_none': '<tg-emoji emoji-id="5870527201874546272">🔗</tg-emoji> <b>Шақыру сілтемесі әлі жоқ.</b>',
        'chat.link': '<tg-emoji emoji-id="5870527201874546272">🔗</tg-emoji> <b>Шақыру:</b> {link}',
        'chat.link_revoked': '<tg-emoji emoji-id="5255831443816327915">🗑</tg-emoji> <b>Шақыру қайтарылды.</b>\n<tg-emoji emoji-id="5870527201874546272">🔗</tg-emoji> <b>Жаңа:</b> {link}',
        'chat.link_created': '<tg-emoji emoji-id="5870633910337015697">✅</tg-emoji> <b>Шақыру жасалды.</b>\n<tg-emoji emoji-id="5870527201874546272">🔗</tg-emoji> {link}',
        'rights.header': '<tg-emoji emoji-id="5870684638195748414">👑</tg-emoji> <b>{name}</b> [<code>{user_id}</code>]\n<b>Рөл:</b> {role}\n<b>Лауазым:</b> {rank}',
        'rights.owner': 'Иесі',
        'rights.admin': 'Админ',
        'rights.member': 'Мүше',
        'rights.none': '<tg-emoji emoji-id="5870657884844462243">✖️</tg-emoji> <b>{name}</b> [<code>{user_id}</code>] <b>админ емес.</b>',
        'rights.empty': '<i>Құқық жоқ.</i>',
    }


    strings_leet = {
        'name': 'H3lm',
        'cfg.warnlimit': 'W4rn5 b3f0r3 4 u53r 15 r357r1c73d',
        'cfg.ptime': 'D3f4ul7 pun15hm3n7 l3ng7h',
        'cfg.wl_punishment': 'Wh47 h4pp3n5 wh3n 7h3 w4rn l1m17 15 h17',
        'cfg.wl_reason': 'R3450n u53d f0r 7h3 w4rn-l1m17 pun15hm3n7',
        'cfg.wl_timespan': 'H0w l0ng 7h3 w4rn-l1m17 pun15hm3n7 l4575',
        'error.wrongchattype.pm': '<tg-emoji emoji-id="5870563425628721113">📧</tg-emoji> <b>7h15 0nly w0rk5 1n gr0up5.</b>',
        'error.wrongchattype.channel': '<tg-emoji emoji-id="5870693687691841267">📣</tg-emoji> <b>7h15 0nly w0rk5 1n gr0up5, n07 ch4nn3l5.</b>',
        'error.no_args.user': '<tg-emoji emoji-id="5870994129244131212">👤</tg-emoji> <b>5p3c1fy 4 u53r.</b>\nR3ply, 0r p455 4 u53rn4m3 0r 1D.',
        'error.locate_user': '<tg-emoji emoji-id="5870974879200711167">🔎</tg-emoji> <b>U53r n07 f0und.</b>\nCh3ck 7h3 u53rn4m3 0r 1D.',
        'error.can_not_restrict': '<tg-emoji emoji-id="5870704313440932932">🔓</tg-emoji> <b>C0uldn\'7 r357r1c7 7h3m.</b>\nY0u m4y l4ck 7h3 r1gh75, 0r 7h3y w3r3 pr0m073d by 50m30n3 3l53.',
        'error.reply_is_service': '<tg-emoji emoji-id="5870982283724328568">⚙️</tg-emoji> <b>7h47\'5 4 53rv1c3 m3554g3.</b>\nR3ply 70 4 n0rm4l m3554g3.',
        'error.self': '<tg-emoji emoji-id="5872988737826197458">🔫</tg-emoji> <b>Y0u c4n\'7 r357r1c7 y0ur53lf.</b>',
        'error.warn_self': '<tg-emoji emoji-id="5870948572526022116">☝🏻</tg-emoji> <b>Y0u c4n\'7 w4rn y0ur53lf.</b>',
        'error.no_args.rights': '<tg-emoji emoji-id="5872996816659681395">❓</tg-emoji> <b>5p3c1fy 7h3 r1gh75.</b>\n4 53qu3nc3 l1k3 <code>123456789ab</code>. Pu7 <code>r</code> 1n fr0n7 70 74k3 7h053 r1gh75 4w4y.',
        'error.no_user': '<tg-emoji emoji-id="5870994129244131212">👤</tg-emoji> <b>5p3c1fy 4 u53r.</b>\nR3ply, 0r p455 4 u53rn4m3 0r 1D.',
        'error.no_reply': '<tg-emoji emoji-id="5872886929921413168">💬</tg-emoji> <b>R3ply 70 4 m3554g3.</b>',
        'error.invalid_args': '<tg-emoji emoji-id="5872996816659681395">❓</tg-emoji> <b>U54g3:</b> <code>g</code> 0r <code>c</code>, 7h3n 4 717l3. 4 7r41l1ng <code>30m</code>, <code>2h</code> 0r <code>1d</code> d3l3735 17 l473r.',
        'error.too_much': '<tg-emoji emoji-id="5870657884844462243">❌</tg-emoji> <b>B4d c0un7.</b>\nU53 4 numb3r fr0m 1 70 100.',
        'error.insufficient_rights': '<tg-emoji emoji-id="5870704313440932932">🔓</tg-emoji> <b>N07 3n0ugh r1gh75.</b>',
        'error.unknown': '<tg-emoji emoji-id="5870657884844462243">🙅🏻‍♂️</tg-emoji> <b>Unkn0wn 3rr0r.</b>',
        'error': '<b>3rr0r:</b> <code>{error}</code>',
        'done.muted.f': '<tg-emoji emoji-id="5870681133502435302">🔇</tg-emoji> <b>{user} 15 mu73d f0r3v3r</b>',
        'done.muted': '<tg-emoji emoji-id="5870681133502435302">🔇</tg-emoji> <b>{user} 15 mu73d f0r {timespan}</b>',
        'done.warned': '<tg-emoji emoji-id="5870931487146119264">⚠️</tg-emoji> <b>{user} h45 b33n w4rn3d</b>',
        'done.banned.f': '<tg-emoji emoji-id="5872988737826197458">⛔</tg-emoji> <b>{user} 15 b4nn3d f0r3v3r</b>',
        'done.banned': '<tg-emoji emoji-id="5872988737826197458">⛔</tg-emoji> <b>{user} 15 b4nn3d f0r {timespan}</b>',
        'done.kicked': '<tg-emoji emoji-id="5870778972857438051">🍃</tg-emoji> <b>{user} h45 b33n k1ck3d</b>',
        'done.nomedia': '<tg-emoji emoji-id="5870782662234346251">🖼️</tg-emoji> <b>{user} c4n\'7 53nd m3d14 f0r {timespan}</b>',
        'done.nomedia.f': '<tg-emoji emoji-id="5870782662234346251">🖼️</tg-emoji> <b>{user} c4n\'7 53nd m3d14 4nym0r3</b>',
        'done.allowmedia': '<tg-emoji emoji-id="5870782662234346251">🖼️</tg-emoji> <b>{user} c4n 53nd m3d14 4g41n</b>',
        'done.setrights.f': '<tg-emoji emoji-id="5870982283724328568">🔧</tg-emoji> <b>R1gh75 f0r <code>{user}</code> 537 70 {rights}</b>',
        'done.setrights': '<tg-emoji emoji-id="5870982283724328568">🔧</tg-emoji> <b>R1gh75 f0r <code>{user}</code> 537 70 {rights}</b> f0r {timespan}',
        'done.unmuted': '<tg-emoji emoji-id="5870693687691841267">🔊</tg-emoji> <b>{user} c4n wr173 4g41n</b>',
        'done.unbanned': '<tg-emoji emoji-id="5870948572526022116">👋🏻</tg-emoji> <b>{user} 15 unb4nn3d</b>',
        'done.unwarned.one': '<tg-emoji emoji-id="5870930636742595124">⚖️</tg-emoji> <b>0n3 w4rn 74k3n 0ff {user}</b>',
        'done.unwarned.all': '<tg-emoji emoji-id="5870930636742595124">⚖️</tg-emoji> <b>4ll w4rn5 74k3n 0ff <code>{user}</code></b>',
        'done.da_kicked': '<tg-emoji emoji-id="5870778972857438051">🍃</tg-emoji> <b>K1ck3d <code>{amount}</code> d3l373d 4cc0un75</b>',
        'done.pin': '<tg-emoji emoji-id="5870930744116776638">📌</tg-emoji> <b>P1nn3d.</b>',
        'done.unpin': '<tg-emoji emoji-id="5870930744116776638">📌</tg-emoji> <b>Unp1nn3d.</b>',
        'done.channel_ban.on': '<tg-emoji emoji-id="5870704313440932932">🔒</tg-emoji> <b>M3554g35 53n7 45 4 ch4nn3l w1ll b3 b4nn3d.</b>',
        'done.channel_ban.off': '<tg-emoji emoji-id="5870704313440932932">🔓</tg-emoji> <b>M3554g35 53n7 45 4 ch4nn3l 4r3 4ll0w3d 4g41n.</b>',
        'done.channel_ban.action': '<tg-emoji emoji-id="5872988737826197458">⛔</tg-emoji> <b>{user} 15 b4nn3d f0r3v3r</b>\n<b>R3450n:</b> p0571ng 45 4 ch4nn3l',
        'done.flushda': '<tg-emoji emoji-id="5870778972857438051">🍃</tg-emoji> <b>R3m0v3d <code>{amt}</code> d3l373d 4cc0un75</b>',
        'done.glban.f': '<tg-emoji emoji-id="5870718740236079262">🌍</tg-emoji> <b>{user} 15 b4nn3d 1n {count} ch475 f0r3v3r</b>',
        'done.glban': '<tg-emoji emoji-id="5870718740236079262">🌍</tg-emoji> <b>{user} 15 b4nn3d 1n {count} ch475 f0r {timespan}</b>',
        'done.glunban': '<tg-emoji emoji-id="5870718740236079262">🌍</tg-emoji> <b>{user} 15 unb4nn3d 1n {count} ch475</b>',
        'done.leave': '<tg-emoji emoji-id="5870764288364252592">😶</tg-emoji> <b>L34v1ng.</b>',
        'done.leave.reason': '<tg-emoji emoji-id="5870764288364252592">😶</tg-emoji> <b>L34v1ng.</b>\n<b>R3450n:</b> <i>{reason}</i>',
        'reason': '\n<b>R3450n:</b> <i>{0}</i>',
        'chat_id': '<tg-emoji emoji-id="5870772616305839506">👥</tg-emoji> <b>Ch47 1D:</b> <code>{chat_id}</code>{additional}\n<tg-emoji emoji-id="5870994129244131212">👤</tg-emoji> <b>Y0ur 1D:</b> <code>{my_id}</code>',
        'person_in_reply_id': '<tg-emoji emoji-id="5870772616305839506">🫂</tg-emoji> <b>R3ply 1D:</b> <code>{reply_id}</code>',
        'sys.DA': 'D3l373d 4cc0un7',
        'sys.LANG': 'en_US',
        'sys.forever': '4 3v3r',
        'of_chat': 'gr0up',
        'of_channel': 'ch4nn3l',
        'loading': '<tg-emoji emoji-id="5870813306826002498">🟡</tg-emoji> <b>L04d1ng…</b>',
        'own_list': '<b>Ch475 y0u run ({count}):</b>\n\n{msg}',
        'no_ownerships': '<tg-emoji emoji-id="5870657884844462243">❌</tg-emoji> <b>Y0u d0n\'7 run 4ny ch475.</b>',
        'not_a_chat': '<tg-emoji emoji-id="5870931487146119264">⚠️</tg-emoji> <b>Gr0up5 0nly.</b>',
        'admins_in_chat': '<tg-emoji emoji-id="5870684638195748414">👑</tg-emoji> <b>4dm1n5 1n <code>{title}</code> ({count}):</b>\n\n',
        'admins_in_chat_caption': '<b>4dm1n5 1n {}:</b>',
        'too_many_admins': '700 m4ny 4dm1n5. 53nd1ng 7h3 l157 45 4 f1l3…',
        'no_admins_in_chat': '<b>N0 4dm1n5 h3r3.</b>',
        'bots_in_chat': '<tg-emoji emoji-id="5870531058755178453">🤖</tg-emoji> <b>B075 1n <code>{title}</code> ({count}):</b>\n\n',
        'bots_in_chat_caption': '<b>B075 1n <code>{}</code>:</b>',
        'too_many_bots': '700 m4ny b075. 53nd1ng 7h3 l157 45 4 f1l3…',
        'no_bots_in_chat': '<b>N0 b075 h3r3.</b>',
        'users_in_chat': '<tg-emoji emoji-id="5870994129244131212">👤</tg-emoji> <b>M3mb3r5 1n <code>{title}</code> ({count}):</b>\n\n',
        'users_in_chat_caption': '<b>M3mb3r5 1n <code>{}</code>:</b>',
        'no_user_in_chat': '<b>N0 m3mb3r5 h3r3.</b>',
        'too_many_users': '700 m4ny m3mb3r5. 53nd1ng 7h3 l157 45 4 f1l3…',
        'chat_muted': '<tg-emoji emoji-id="5870681133502435302">🔇</tg-emoji> <b>M3mb3r5 c4n n0 l0ng3r wr173.</b>',
        'chat_unmuted': '<tg-emoji emoji-id="5870633910337015697">✅</tg-emoji> <b>M3mb3r5 c4n wr173 4g41n.</b>',
        'title_changed': '<b>{type_of} r3n4m3d fr0m <code>{old_title}</code> 70 <code>{new_title}</code>.</b>',
        'user_invited': '<tg-emoji emoji-id="5870633910337015697">✅</tg-emoji> <b><a href=\'tg://user?id={id}\'>{user}</a> 1nv173d.</b>',
        'creator': '<tg-emoji emoji-id="5870684638195748414">👑</tg-emoji> <b>0wn3r: <a href=\'tg://user?id={id}\'>{creator}</a>.</b>',
        'no_creator': '<tg-emoji emoji-id="5870657884844462243">❌</tg-emoji> <b>N0 0wn3r f0und.</b>',
        'channel_created': '<tg-emoji emoji-id="5870633910337015697">✅</tg-emoji> <b>Ch4nn3l <code>{title}</code> cr3473d.</b>\n<tg-emoji emoji-id="5870527201874546272">🔗</tg-emoji> <b>1nv173: {link}</b>',
        'group_created': '<tg-emoji emoji-id="5870633910337015697">✅</tg-emoji> <b>Gr0up <code>{title}</code> cr3473d.</b>\n<tg-emoji emoji-id="5870527201874546272">🔗</tg-emoji> <b>1nv173: {link}</b>',
        'temp_chat': '\n<tg-emoji emoji-id="5870875489362513438">🗑</tg-emoji> <b>D3l3735 1753lf 1n {timespan}.</b>',
        'type_group': 'Gr0up',
        'type_channel': 'Ch4nn3l',
        'type_unknown': 'Unkn0wn',
        'yes': '<tg-emoji emoji-id="5870633910337015697">✅</tg-emoji> Y35',
        'no': '<tg-emoji emoji-id="5870657884844462243">✖️</tg-emoji> N0',
        'all_approved': '<tg-emoji emoji-id="5870633910337015697">✅</tg-emoji> <b>R3qu3575 4ppr0v3d</b>',
        'all_dismissed': '<tg-emoji emoji-id="5870657884844462243">✖️</tg-emoji> <b>R3qu3575 d3cl1n3d</b>',
        'log_text': '<tg-emoji emoji-id="5870994129244131212">👤</tg-emoji> <b>U53r:</b> {user}\n<tg-emoji emoji-id="5870704313440932932">🔒</tg-emoji> <b>4dm1n:</b> {admin}\n<tg-emoji emoji-id="5872988737826197458">⛔️</tg-emoji> <b>4c710n:</b> {punishment}{reason}{time}{chat}',
        'log_chat': '\n<tg-emoji emoji-id="5872886929921413168">💬</tg-emoji> <b>Ch47:</b> {chat}',
        'log_reason': '\n<tg-emoji emoji-id="5870676941614354370">🖋</tg-emoji> <b>R3450n:</b> {reason}',
        'log_time': '\n<tg-emoji emoji-id="5870729937215819584">⏰️</tg-emoji> <b>71m3:</b> {time}',
        'act.mute': 'Mu73',
        'act.ban': 'B4n',
        'act.kick': 'K1ck',
        'act.unmute': 'Unmu73',
        'act.unban': 'Unb4n',
        'act.warn': 'W4rn',
        'act.nomedia': 'M3d14 r357r1c73d',
        'act.allowmedia': 'M3d14 4ll0w3d',
        'act.rights': 'R1gh75 ch4ng3d',
        'flushda.loading': '<tg-emoji emoji-id="5870813306826002498">🟡</tg-emoji> <b>R3m0v1ng d3l373d 4cc0un75…</b>',
        'flushda.loading.chat': '<tg-emoji emoji-id="5870813306826002498">🟡</tg-emoji> <b>R3m0v1ng d3l373d 4cc0un75 fr0m 7h15 ch47…</b>',
        'flushda.loading.channels': '<tg-emoji emoji-id="5870813306826002498">🟡</tg-emoji> <b>R3m0v1ng d3l373d 4cc0un75 fr0m ch4nn3l5…</b>',
        'monday': 'M0nd4y',
        'tuesday': '7u35d4y',
        'wednesday': 'W3dn35d4y',
        'thursday': '7hur5d4y',
        'friday': 'Fr1d4y',
        'saturday': '547urd4y',
        'sunday': '5und4y',
        'cfg.gban_except': 'Ch47 1D5 l3f7 0u7 0f .gb4n 4nd .ungb4n',
        'cfg.gban_pm_block': 'Bl0ck 7h3 u53r 1n PM 0n .gb4n, 4nd unbl0ck 0n .ungb4n',
        'cfg.gban_pm_del_history': '4l50 d3l373 7h3 PM h1570ry wh3n bl0ck1ng',
        'cfg.gban_pm_except': 'U53r 1D5 7h47 4r3 n3v3r bl0ck3d 1n PM',
        'cfg.global_logs': 'L0g r357r1c710n5 fr0m 3v3ry 4dm1n ch47, n07 0nly y0ur 0wn c0mm4nd5',
        'gban.no_reason': 'N07 5p3c1f13d',
        'gban.args': '<tg-emoji emoji-id="5870994129244131212">👤</tg-emoji> <b>5p3c1fy 4 u53r.</b>\nR3ply, 0r p455 4 u53rn4m3 0r 1D.',
        'gban.working': '<tg-emoji emoji-id="5870718740236079262">🌍</tg-emoji> <b>B4nn1ng <a href="{url}">{name}</a> 3v3rywh3r3…</b>',
        'gban.unworking': '<tg-emoji emoji-id="5870718740236079262">🌍</tg-emoji> <b>Unb4nn1ng <a href="{url}">{name}</a> 3v3rywh3r3…</b>',
        'gban.done': '<tg-emoji emoji-id="5872988737826197458">⛔</tg-emoji> <b><a href="{url}">{name}</a> 15 b4nn3d 1n {count} ch475</b>\n<b>R3450n:</b> <i>{reason}</i>',
        'gban.undone': '<tg-emoji emoji-id="5870948572526022116">👋🏻</tg-emoji> <b><a href="{url}">{name}</a> 15 unb4nn3d 1n {count} ch475</b>',
        'gban.chats': '\n{chats}',
        'gban.pm_blocked': '\n<tg-emoji emoji-id="5872988737826197458">🚫</tg-emoji> <b>Bl0ck3d 1n PM</b>',
        'gban.pm_unblocked': '\n<tg-emoji emoji-id="5870948572526022116">👋🏻</tg-emoji> <b>Unbl0ck3d 1n PM</b>',
        'gban.pm_failed': '\n<tg-emoji emoji-id="5870704313440932932">🔓</tg-emoji> <b>C0uldn\'7 bl0ck 1n PM</b>',
        'gban.pm_cleared': ' · <b>PM h1570ry d3l373d</b>',
        'chatinfo': '<tg-emoji emoji-id="5870704313440932932">🔒</tg-emoji><b> 7yp3: {type_of}\n</b><tg-emoji emoji-id="5870495350397079101">#️⃣</tg-emoji><b> Ch47 1D: </b><code>{id}</code><b>\n</b><tg-emoji emoji-id="5873225338984599714">🔥</tg-emoji><b> 717l3: {title}\n\n</b><tg-emoji emoji-id="5870676941614354370">🖋</tg-emoji><b> 4b0u7: {about}\n\n</b><tg-emoji emoji-id="5870684638195748414">👑</tg-emoji><b> 4dm1n5: {admins_count}\n</b><tg-emoji emoji-id="5870633910337015697">✅</tg-emoji><b> 0nl1n3: {online_count}\n</b><tg-emoji emoji-id="5870994129244131212">👤</tg-emoji><b> M3mb3r5: {participants_count}\n</b><tg-emoji emoji-id="5872988737826197458">🚫</tg-emoji><b> K1ck3d: {kicked_count}\n</b><tg-emoji emoji-id="5870892901159932239">🔀</tg-emoji><b> P3nd1ng r3qu3575: {requests_pending}\n\n</b><tg-emoji emoji-id="5870729937215819584">🕐</tg-emoji><b> 5l0w m0d3: {slowmode_seconds}\n</b><tg-emoji emoji-id="5872980989705196227">📞</tg-emoji><b> C4ll: {call}\n</b><tg-emoji emoji-id="5870875489362513438">🗑</tg-emoji><b> 77L: {ttl_period}\n</b><tg-emoji emoji-id="5870994129244131212">👤</tg-emoji><b> R3c3n7 r3qu3573r5: {recent_requesters}\n\n</b><tg-emoji emoji-id="5870772616305839506">👥</tg-emoji><b> L1nk3d ch47: {linked_chat_id}\n</b><tg-emoji emoji-id="5870704313440932932">🛡</tg-emoji><b> 4n715p4m: {antispam}\n</b><tg-emoji emoji-id="5870542612217204751">👁</tg-emoji><b> M3mb3r5 h1dd3n: {participants_hidden}\n\n</b><tg-emoji emoji-id="5870527201874546272">🔗</tg-emoji><b> L1nk: {link}</b>',
        'userinfo': '<blockquote><tg-emoji emoji-id="5870495350397079101">#️⃣</tg-emoji><b> 1D: {user_id}\n</b><tg-emoji emoji-id="5873225338984599714">🔥</tg-emoji><b> F1r57 n4m3: {first_name}\n</b><tg-emoji emoji-id="5873225338984599714">🔥</tg-emoji><b> L457 n4m3: {last_name}\n</b><tg-emoji emoji-id="5872980989705196227">📞</tg-emoji><b> Ph0n3: {phone}\n</b><tg-emoji emoji-id="5870998024779468554">🐶</tg-emoji><b> U53rn4m35: {usernames}</b></blockquote><b>\n</b><blockquote><tg-emoji emoji-id="5870609858520158157">ℹ️</tg-emoji><b> 4b0u7: {about}</b></blockquote><b>\n</b><blockquote><tg-emoji emoji-id="5870729937215819584">🕐</tg-emoji><b> H0ur5: </b>{business_work_hours}\n<tg-emoji emoji-id="5870450871715761518">❤️</tg-emoji><b> 3m0j1 5747u5: {emoji_status}</b></blockquote><b>\n</b><blockquote><tg-emoji emoji-id="5870693687691841267">🔉</tg-emoji><b> Ch4nn3l: {personal_channel}\n</b><tg-emoji emoji-id="5870847962917113498">🎂</tg-emoji><b> B1r7hd4y: {birthday}\n</b><tg-emoji emoji-id="5870478797593120516">🎁</tg-emoji><b> G1f75: {stargifts_count}</b></blockquote><b>\n</b><blockquote><tg-emoji emoji-id="5870931487146119264">🚨</tg-emoji><b> Ch475 1n c0mm0n: {common_chats_count}\n</b><tg-emoji emoji-id="5870772616305839506">👥</tg-emoji><b> C0mm0n ch475: {common_chats}</b></blockquote>',
        'promote.no_rights': '<tg-emoji emoji-id="5870704313440932932">🔓</tg-emoji> <b>N07 3n0ugh r1gh75 70 ch4ng3 4dm1n5.</b>',
        'promote.no_user': '<tg-emoji emoji-id="5870994129244131212">👤</tg-emoji> <b>5p3c1fy 4 u53r.</b>\nR3ply, 0r p455 4 u53rn4m3 0r 1D.',
        'promote.demoted': '<tg-emoji emoji-id="5870948572526022116">👋🏻</tg-emoji> <b>{name}</b> [<code>{user_id}</code>] <b>15 n0 l0ng3r 4n 4dm1n.</b>',
        'promote.promoted_full': '<tg-emoji emoji-id="5870684638195748414">👑</tg-emoji> <b>{name}</b> [<code>{user_id}</code>] <b>15 4n 4dm1n w17h fu11 r1gh75.</b>\n<b>R4nk:</b> {rank}',
        'promote.promoted': '<tg-emoji emoji-id="5870684638195748414">👑</tg-emoji> <b>{name}</b> [<code>{user_id}</code>] <b>15 4n 4dm1n.</b>\n<b>R4nk:</b> {rank}',
        'promote.choose': '<tg-emoji emoji-id="5870684638195748414">👑</tg-emoji> <b>4dm1n r1gh75 f0r {name}</b> [<code>{user_id}</code>]\n<b>R4nk:</b> {rank}',
        'promote.confirm': 'C0nf1rm',
        'promote.default_rank': '4dm1n',
        'promote.tag_group_only': '<tg-emoji emoji-id="5870931487146119264">⚠️</tg-emoji> <b>M3mb3r 74g5 0nly w0rk 1n gr0up5.</b>',
        'promote.tag_usage': '<b>U54g3:</b> <code>{prefix}settag @user tag</code> 0r r3ply w17h <code>{prefix}settag tag</code>. N0 74g 0r <code>-</code> r3m0v35 17.',
        'promote.tag_invalid': '<tg-emoji emoji-id="5870657884844462243">❌</tg-emoji> <b>4 m3mb3r 74g 15 47 m057 16 ch4r4c73r5, w17h n0 3m0j1.</b>',
        'promote.tag_no_rights': '<tg-emoji emoji-id="5870704313440932932">🔓</tg-emoji> <b>Y0u n33d M4n4g3 m3mb3r 74g5 70 ch4ng3 50m30n3 3l53\'5 74g.</b>',
        'promote.tag_updated': '<tg-emoji emoji-id="5870676941614354370">🖋</tg-emoji> <b>M3mb3r 74g f0r {name}:</b> <code>{rank}</code>',
        'promote.tag_removed': '<tg-emoji emoji-id="5255831443816327915">🗑</tg-emoji> <b>M3mb3r 74g r3m0v3d f0r {name}.</b>',
        'promote.rpc_error': '<tg-emoji emoji-id="5870657884844462243">❌</tg-emoji> <b>73l3gr4m 3rr0r:</b> <code>{error}</code>',
        'promote.right.change_info': '{emoji} Ch4ng3 {where} 1nf0',
        'promote.right.post_messages': '{emoji} P057 m3554g35',
        'promote.right.edit_messages': '{emoji} 3d17 p0575',
        'promote.right.delete_messages': '{emoji} D3l373 m3554g35',
        'promote.right.ban_users': '{emoji} R357r1c7 u53r5',
        'promote.right.invite_users': '{emoji} 1nv173 u53r5',
        'promote.right.pin_messages': '{emoji} P1n m3554g35',
        'promote.right.add_admins': '{emoji} 4dd 4dm1n5',
        'promote.right.anonymous': '{emoji} 4n0nym0u5',
        'promote.right.manage_call': '{emoji} M4n4g3 c4ll5',
        'promote.right.manage_topics': '{emoji} M4n4g3 70p1c5',
        'promote.right.post_stories': '{emoji} P057 570r135',
        'promote.right.edit_stories': '{emoji} 3d17 570r135',
        'promote.right.delete_stories': '{emoji} D3l373 570r135',
        'promote.right.manage_direct_messages': '{emoji} M4n4g3 d1r3c7 m3554g35',
        'promote.right.manage_ranks': '{emoji} M4n4g3 m3mb3r 74g5',
        'promote.right.manage_linked_peers': '{emoji} M4n4g3 l1nk3d ch475',
        'promote.right.manage_welcome_messages': '{emoji} M4n4g3 w3lc0m3 m3554g35',
        'promote.right.other': '{emoji} 07h3r r1gh75',
        'chat.not_channel': '<tg-emoji emoji-id="5870693687691841267">📣</tg-emoji> <b>7h15 0nly w0rk5 1n 5up3rgr0up5 4nd ch4nn3l5.</b>',
        'chat.no_rights': '<tg-emoji emoji-id="5870704313440932932">🔓</tg-emoji> <b>N07 3n0ugh r1gh75 70 ch4ng3 7h15 ch47.</b>',
        'chat.usage.slow': '<b>U54g3:</b> <code>{prefix}5l0w</code> 0ff, 0r <code>30</code>, <code>1m</code>, <code>5m</code>, <code>1h</code>.',
        'chat.usage.about': '<b>U54g3:</b> <code>{prefix}5374b0u7 73x7</code>. <code>-</code> cl34r5 17.',
        'chat.usage.photo': '<b>U54g3:</b> r3ply 70 4 ph070 w17h <code>{prefix}537ph070</code>. <code>-</code> r3m0v35 17.',
        'chat.usage.username': '<b>U54g3:</b> <code>{prefix}537u53rn4m3 n4m3</code>. <code>-</code> r3m0v35 17.',
        'chat.usage.link': '<b>U54g3:</b> <code>{prefix}l1nk</code>, <code>n3w</code>, <code>r3v0k3</code>, 0r <code>717l3</code>.',
        'chat.slow_off': '<tg-emoji emoji-id="5870729937215819584">🕐</tg-emoji> <b>5l0w m0d3 15 0ff.</b>',
        'chat.slow_on': '<tg-emoji emoji-id="5870729937215819584">🕐</tg-emoji> <b>5l0w m0d3:</b> <code>{seconds}</code>5',
        'chat.about_set': '<tg-emoji emoji-id="5870676941614354370">🖋</tg-emoji> <b>D35cr1p710n upd473d.</b>',
        'chat.about_cleared': '<tg-emoji emoji-id="5255831443816327915">🗑</tg-emoji> <b>D35cr1p710n cl34r3d.</b>',
        'chat.photo_set': '<tg-emoji emoji-id="5870782662234346251">🖼️</tg-emoji> <b>Ch47 ph070 upd473d.</b>',
        'chat.photo_cleared': '<tg-emoji emoji-id="5255831443816327915">🗑</tg-emoji> <b>Ch47 ph070 r3m0v3d.</b>',
        'chat.username_set': '<tg-emoji emoji-id="5870527201874546272">🔗</tg-emoji> <b>U53rn4m3:</b> @{username}',
        'chat.username_cleared': '<tg-emoji emoji-id="5255831443816327915">🗑</tg-emoji> <b>U53rn4m3 r3m0v3d.</b>',
        'chat.sign_on': '<tg-emoji emoji-id="5870676941614354370">🖋</tg-emoji> <b>4u7h0r 51gn47ur35 4r3 0n.</b>',
        'chat.sign_off': '<tg-emoji emoji-id="5870676941614354370">🖋</tg-emoji> <b>4u7h0r 51gn47ur35 4r3 0ff.</b>',
        'chat.forum_on': '<tg-emoji emoji-id="5872886929921413168">💬</tg-emoji> <b>70p1c5 4r3 0n.</b>',
        'chat.forum_off': '<tg-emoji emoji-id="5872886929921413168">💬</tg-emoji> <b>70p1c5 4r3 0ff.</b>',
        'chat.spam_on': '<tg-emoji emoji-id="5870704313440932932">🛡</tg-emoji> <b>4ggr3551v3 4n715p4m 15 0n.</b>',
        'chat.spam_off': '<tg-emoji emoji-id="5870704313440932932">🛡</tg-emoji> <b>4ggr3551v3 4n715p4m 15 0ff.</b>',
        'chat.hidden_on': '<tg-emoji emoji-id="5870542612217204751">👁</tg-emoji> <b>7h3 m3mb3r l157 15 h1dd3n.</b>',
        'chat.hidden_off': '<tg-emoji emoji-id="5870542612217204751">👁</tg-emoji> <b>7h3 m3mb3r l157 15 v151bl3.</b>',
        'chat.history_on': '<tg-emoji emoji-id="5870729937215819584">🕐</tg-emoji> <b>N3w m3mb3r5 c4n 533 7h3 h1570ry.</b>',
        'chat.history_off': '<tg-emoji emoji-id="5870729937215819584">🕐</tg-emoji> <b>H1570ry 15 h1dd3n fr0m n3w m3mb3r5.</b>',
        'chat.join_on': '<tg-emoji emoji-id="5870892901159932239">🔀</tg-emoji> <b>J01n r3qu3575 4r3 0n.</b>',
        'chat.join_off': '<tg-emoji emoji-id="5870892901159932239">🔀</tg-emoji> <b>J01n r3qu3575 4r3 0ff.</b>',
        'chat.link_none': '<tg-emoji emoji-id="5870527201874546272">🔗</tg-emoji> <b>N0 1nv173 l1nk y37.</b>',
        'chat.link': '<tg-emoji emoji-id="5870527201874546272">🔗</tg-emoji> <b>1nv173:</b> {link}',
        'chat.link_revoked': '<tg-emoji emoji-id="5255831443816327915">🗑</tg-emoji> <b>1nv173 r3v0k3d.</b>\n<tg-emoji emoji-id="5870527201874546272">🔗</tg-emoji> <b>N3w:</b> {link}',
        'chat.link_created': '<tg-emoji emoji-id="5870633910337015697">✅</tg-emoji> <b>1nv173 cr3473d.</b>\n<tg-emoji emoji-id="5870527201874546272">🔗</tg-emoji> {link}',
        'rights.header': '<tg-emoji emoji-id="5870684638195748414">👑</tg-emoji> <b>{name}</b> [<code>{user_id}</code>]\n<b>R0l3:</b> {role}\n<b>R4nk:</b> {rank}',
        'rights.owner': '0wn3r',
        'rights.admin': '4dm1n',
        'rights.member': 'M3mb3r',
        'rights.none': '<tg-emoji emoji-id="5870657884844462243">✖️</tg-emoji> <b>{name}</b> [<code>{user_id}</code>] <b>15 n07 4n 4dm1n.</b>',
        'rights.empty': '<i>N0 r1gh75.</i>',
    }

    strings_uwu = {
        'name': 'Hewm',
        'cfg.warnlimit': 'Wawns befowe a usew is westwicted',
        'cfg.ptime': 'Defauwt punishment wength',
        'cfg.wl_punishment': 'What happens when da wawn wimit is hit',
        'cfg.wl_reason': 'Weason used fow da wawn-wimit punishment',
        'cfg.wl_timespan': 'How wong da wawn-wimit punishment wasts',
        'error.wrongchattype.pm': '<tg-emoji emoji-id="5870563425628721113">📧</tg-emoji> <b>Dis onwy wowks in gwoups.</b>',
        'error.wrongchattype.channel': '<tg-emoji emoji-id="5870693687691841267">📣</tg-emoji> <b>Dis onwy wowks in gwoups, nyot channyews.</b>',
        'error.no_args.user': '<tg-emoji emoji-id="5870994129244131212">👤</tg-emoji> <b>Specify a usew.</b>\nWepwy, ow pass a usewname ow ID! UwU',
        'error.locate_user': '<tg-emoji emoji-id="5870974879200711167">🔎</tg-emoji> <b>Usew nyot found.</b>\nCheck da usewname ow ID! UwU',
        'error.can_not_restrict': '<tg-emoji emoji-id="5870704313440932932">🔓</tg-emoji> <b>Cannyot\'t westwict them.</b>\nYou may wack da wights, ow they wewe pwomoted by someone ewse.',
        'error.reply_is_service': '<tg-emoji emoji-id="5870982283724328568">⚙️</tg-emoji> <b>Dat\'s a sewvice message.</b>\nWepwy to a nowmaw message! UwU',
        'error.self': '<tg-emoji emoji-id="5872988737826197458">🔫</tg-emoji> <b>You can\'t westwict youwsewf.</b>',
        'error.warn_self': '<tg-emoji emoji-id="5870948572526022116">☝🏻</tg-emoji> <b>You can\'t wawn youwsewf.</b>',
        'error.no_args.rights': '<tg-emoji emoji-id="5872996816659681395">❓</tg-emoji> <b>Specify da wights.</b>\nA sequence wike <code>123456789ab</code>. Put <code>r</code> in fwont to take those wights away.',
        'error.no_user': '<tg-emoji emoji-id="5870994129244131212">👤</tg-emoji> <b>Specify a usew.</b>\nWepwy, ow pass a usewname ow ID! UwU',
        'error.no_reply': '<tg-emoji emoji-id="5872886929921413168">💬</tg-emoji> <b>Wepwy to a message.</b>',
        'error.invalid_args': '<tg-emoji emoji-id="5872996816659681395">❓</tg-emoji> <b>Usage:</b> <code>g</code> ow <code>c</code>, then a titwe. A twaiwing <code>30m</code>, <code>2h</code> ow <code>1d</code> dewetes it watew.',
        'error.too_much': '<tg-emoji emoji-id="5870657884844462243">❌</tg-emoji> <b>Bad count.</b>\nUse a numbew fwom 1 to 100! UwU',
        'error.insufficient_rights': '<tg-emoji emoji-id="5870704313440932932">🔓</tg-emoji> <b>Nyot enough wights.</b>',
        'error.unknown': '<tg-emoji emoji-id="5870657884844462243">🙅🏻‍♂️</tg-emoji> <b>Unknown ewwow.</b>',
        'error': '<b>Ewwow:</b> <code>{error}</code>',
        'done.muted.f': '<tg-emoji emoji-id="5870681133502435302">🔇</tg-emoji> <b>{user} is muted fowevew</b>',
        'done.muted': '<tg-emoji emoji-id="5870681133502435302">🔇</tg-emoji> <b>{user} is muted fow {timespan}</b>',
        'done.warned': '<tg-emoji emoji-id="5870931487146119264">⚠️</tg-emoji> <b>{user} has been wawned</b>',
        'done.banned.f': '<tg-emoji emoji-id="5872988737826197458">⛔</tg-emoji> <b>{user} is banned fowevew</b>',
        'done.banned': '<tg-emoji emoji-id="5872988737826197458">⛔</tg-emoji> <b>{user} is banned fow {timespan}</b>',
        'done.kicked': '<tg-emoji emoji-id="5870778972857438051">🍃</tg-emoji> <b>{user} has been kicked</b>',
        'done.nomedia': '<tg-emoji emoji-id="5870782662234346251">🖼️</tg-emoji> <b>{user} can\'t send media fow {timespan}</b>',
        'done.nomedia.f': '<tg-emoji emoji-id="5870782662234346251">🖼️</tg-emoji> <b>{user} can\'t send media anymowe</b>',
        'done.allowmedia': '<tg-emoji emoji-id="5870782662234346251">🖼️</tg-emoji> <b>{user} can send media again</b>',
        'done.setrights.f': '<tg-emoji emoji-id="5870982283724328568">🔧</tg-emoji> <b>Wights fow <code>{user}</code> set to {rights}</b>',
        'done.setrights': '<tg-emoji emoji-id="5870982283724328568">🔧</tg-emoji> <b>Wights fow <code>{user}</code> set to {rights}</b> fow {timespan}',
        'done.unmuted': '<tg-emoji emoji-id="5870693687691841267">🔊</tg-emoji> <b>{user} can wwite again</b>',
        'done.unbanned': '<tg-emoji emoji-id="5870948572526022116">👋🏻</tg-emoji> <b>{user} is unbanned</b>',
        'done.unwarned.one': '<tg-emoji emoji-id="5870930636742595124">⚖️</tg-emoji> <b>One wawn taken off {user}</b>',
        'done.unwarned.all': '<tg-emoji emoji-id="5870930636742595124">⚖️</tg-emoji> <b>Aww wawns taken off <code>{user}</code></b>',
        'done.da_kicked': '<tg-emoji emoji-id="5870778972857438051">🍃</tg-emoji> <b>Kicked <code>{amount}</code> deweted accounts</b>',
        'done.pin': '<tg-emoji emoji-id="5870930744116776638">📌</tg-emoji> <b>Pinned.</b>',
        'done.unpin': '<tg-emoji emoji-id="5870930744116776638">📌</tg-emoji> <b>Unpinned.</b>',
        'done.channel_ban.on': '<tg-emoji emoji-id="5870704313440932932">🔒</tg-emoji> <b>Messages sent as a channyew wiww be banned.</b>',
        'done.channel_ban.off': '<tg-emoji emoji-id="5870704313440932932">🔓</tg-emoji> <b>Messages sent as a channyew awe awwowed again.</b>',
        'done.channel_ban.action': '<tg-emoji emoji-id="5872988737826197458">⛔</tg-emoji> <b>{user} is banned fowevew</b>\n<b>Weason:</b> posting as a channyew',
        'done.flushda': '<tg-emoji emoji-id="5870778972857438051">🍃</tg-emoji> <b>Wemoved <code>{amt}</code> deweted accounts</b>',
        'done.glban.f': '<tg-emoji emoji-id="5870718740236079262">🌍</tg-emoji> <b>{user} is banned in {count} chats fowevew</b>',
        'done.glban': '<tg-emoji emoji-id="5870718740236079262">🌍</tg-emoji> <b>{user} is banned in {count} chats fow {timespan}</b>',
        'done.glunban': '<tg-emoji emoji-id="5870718740236079262">🌍</tg-emoji> <b>{user} is unbanned in {count} chats</b>',
        'done.leave': '<tg-emoji emoji-id="5870764288364252592">😶</tg-emoji> <b>Weaving.</b>',
        'done.leave.reason': '<tg-emoji emoji-id="5870764288364252592">😶</tg-emoji> <b>Weaving.</b>\n<b>Weason:</b> <i>{reason}</i>',
        'reason': '\n<b>Weason:</b> <i>{0}</i>',
        'chat_id': '<tg-emoji emoji-id="5870772616305839506">👥</tg-emoji> <b>Chat ID:</b> <code>{chat_id}</code>{additional}\n<tg-emoji emoji-id="5870994129244131212">👤</tg-emoji> <b>Youw ID:</b> <code>{my_id}</code>',
        'person_in_reply_id': '<tg-emoji emoji-id="5870772616305839506">🫂</tg-emoji> <b>Wepwy ID:</b> <code>{reply_id}</code>',
        'sys.DA': 'Deweted account',
        'sys.LANG': 'en_US',
        'sys.forever': 'fowevew',
        'of_chat': 'gwoup',
        'of_channel': 'channyew',
        'loading': '<tg-emoji emoji-id="5870813306826002498">🟡</tg-emoji> <b>Woading…</b>',
        'own_list': '<b>Chats you wun ({count}):</b>\n\n{msg}',
        'no_ownerships': '<tg-emoji emoji-id="5870657884844462243">❌</tg-emoji> <b>You don\'t wun any chats.</b>',
        'not_a_chat': '<tg-emoji emoji-id="5870931487146119264">⚠️</tg-emoji> <b>Gwoups onwy.</b>',
        'admins_in_chat': '<tg-emoji emoji-id="5870684638195748414">👑</tg-emoji> <b>Admins in <code>{title}</code> ({count}):</b>\n\n',
        'admins_in_chat_caption': '<b>Admins in {}:</b>',
        'too_many_admins': 'Too many admins. Sending da wist as a fiwe… OwO',
        'no_admins_in_chat': '<b>Nyo admins hewe.</b>',
        'bots_in_chat': '<tg-emoji emoji-id="5870531058755178453">🤖</tg-emoji> <b>Bots in <code>{title}</code> ({count}):</b>\n\n',
        'bots_in_chat_caption': '<b>Bots in <code>{}</code>:</b>',
        'too_many_bots': 'Too many bots. Sending da wist as a fiwe… OwO',
        'no_bots_in_chat': '<b>Nyo bots hewe.</b>',
        'users_in_chat': '<tg-emoji emoji-id="5870994129244131212">👤</tg-emoji> <b>Membews in <code>{title}</code> ({count}):</b>\n\n',
        'users_in_chat_caption': '<b>Membews in <code>{}</code>:</b>',
        'no_user_in_chat': '<b>Nyo membews hewe.</b>',
        'too_many_users': 'Too many membews. Sending da wist as a fiwe… OwO',
        'chat_muted': '<tg-emoji emoji-id="5870681133502435302">🔇</tg-emoji> <b>Membews can nyo wongew wwite.</b>',
        'chat_unmuted': '<tg-emoji emoji-id="5870633910337015697">✅</tg-emoji> <b>Membews can wwite again.</b>',
        'title_changed': '<b>{type_of} wenamed fwom <code>{old_title}</code> to <code>{new_title}</code>.</b>',
        'user_invited': '<tg-emoji emoji-id="5870633910337015697">✅</tg-emoji> <b><a href=\'tg://user?id={id}\'>{user}</a> invited.</b>',
        'creator': '<tg-emoji emoji-id="5870684638195748414">👑</tg-emoji> <b>Ownew: <a href=\'tg://user?id={id}\'>{creator}</a>.</b>',
        'no_creator': '<tg-emoji emoji-id="5870657884844462243">❌</tg-emoji> <b>Nyo ownew found.</b>',
        'channel_created': '<tg-emoji emoji-id="5870633910337015697">✅</tg-emoji> <b>Channyew <code>{title}</code> cweated.</b>\n<tg-emoji emoji-id="5870527201874546272">🔗</tg-emoji> <b>Invite: {link}</b>',
        'group_created': '<tg-emoji emoji-id="5870633910337015697">✅</tg-emoji> <b>Gwoup <code>{title}</code> cweated.</b>\n<tg-emoji emoji-id="5870527201874546272">🔗</tg-emoji> <b>Invite: {link}</b>',
        'temp_chat': '\n<tg-emoji emoji-id="5870875489362513438">🗑</tg-emoji> <b>Dewetes itsewf in {timespan}.</b>',
        'type_group': 'Gwoup',
        'type_channel': 'Channyew',
        'type_unknown': 'Unknown',
        'yes': '<tg-emoji emoji-id="5870633910337015697">✅</tg-emoji> Yes',
        'no': '<tg-emoji emoji-id="5870657884844462243">✖️</tg-emoji> Nyo',
        'all_approved': '<tg-emoji emoji-id="5870633910337015697">✅</tg-emoji> <b>Wequests appwoved</b>',
        'all_dismissed': '<tg-emoji emoji-id="5870657884844462243">✖️</tg-emoji> <b>Wequests decwined</b>',
        'log_text': '<tg-emoji emoji-id="5870994129244131212">👤</tg-emoji> <b>Usew:</b> {user}\n<tg-emoji emoji-id="5870704313440932932">🔒</tg-emoji> <b>Admin:</b> {admin}\n<tg-emoji emoji-id="5872988737826197458">⛔️</tg-emoji> <b>Action:</b> {punishment}{reason}{time}{chat}',
        'log_chat': '\n<tg-emoji emoji-id="5872886929921413168">💬</tg-emoji> <b>Chat:</b> {chat}',
        'log_reason': '\n<tg-emoji emoji-id="5870676941614354370">🖋</tg-emoji> <b>Weason:</b> {reason}',
        'log_time': '\n<tg-emoji emoji-id="5870729937215819584">⏰️</tg-emoji> <b>Time:</b> {time}',
        'act.mute': 'Mute',
        'act.ban': 'Ban',
        'act.kick': 'Kick',
        'act.unmute': 'Unmute',
        'act.unban': 'Unban',
        'act.warn': 'Wawn',
        'act.nomedia': 'Media westwicted',
        'act.allowmedia': 'Media awwowed',
        'act.rights': 'Wights changed',
        'flushda.loading': '<tg-emoji emoji-id="5870813306826002498">🟡</tg-emoji> <b>Wemoving deweted accounts…</b>',
        'flushda.loading.chat': '<tg-emoji emoji-id="5870813306826002498">🟡</tg-emoji> <b>Wemoving deweted accounts fwom dis chat…</b>',
        'flushda.loading.channels': '<tg-emoji emoji-id="5870813306826002498">🟡</tg-emoji> <b>Wemoving deweted accounts fwom channyews…</b>',
        'monday': 'Monday',
        'tuesday': 'Tuesday',
        'wednesday': 'Wednesday',
        'thursday': 'Thuwsday',
        'friday': 'Fwiday',
        'saturday': 'Satuwday',
        'sunday': 'Sunday',
        'cfg.gban_except': 'Chat IDs weft out of .gban and .ungban',
        'cfg.gban_pm_block': 'Bwock da usew in PM on .gban, and unbwock on .ungban',
        'cfg.gban_pm_del_history': 'Awso dewete da PM histowy when bwocking',
        'cfg.gban_pm_except': 'Usew IDs dat awe nevew bwocked in PM',
        'cfg.global_logs': 'Wog westwictions fwom evewy admin chat, nyot onwy youw own commands',
        'gban.no_reason': 'Nyot specified',
        'gban.args': '<tg-emoji emoji-id="5870994129244131212">👤</tg-emoji> <b>Specify a usew.</b>\nWepwy, ow pass a usewname ow ID! UwU',
        'gban.working': '<tg-emoji emoji-id="5870718740236079262">🌍</tg-emoji> <b>Banning <a href="{url}">{name}</a> evewywhewe…</b>',
        'gban.unworking': '<tg-emoji emoji-id="5870718740236079262">🌍</tg-emoji> <b>Unbanning <a href="{url}">{name}</a> evewywhewe…</b>',
        'gban.done': '<tg-emoji emoji-id="5872988737826197458">⛔</tg-emoji> <b><a href="{url}">{name}</a> is banned in {count} chats</b>\n<b>Weason:</b> <i>{reason}</i>',
        'gban.undone': '<tg-emoji emoji-id="5870948572526022116">👋🏻</tg-emoji> <b><a href="{url}">{name}</a> is unbanned in {count} chats</b>',
        'gban.chats': '\n{chats}',
        'gban.pm_blocked': '\n<tg-emoji emoji-id="5872988737826197458">🚫</tg-emoji> <b>Bwocked in PM</b>',
        'gban.pm_unblocked': '\n<tg-emoji emoji-id="5870948572526022116">👋🏻</tg-emoji> <b>Unbwocked in PM</b>',
        'gban.pm_failed': '\n<tg-emoji emoji-id="5870704313440932932">🔓</tg-emoji> <b>Cannyot\'t bwock in PM</b>',
        'gban.pm_cleared': ' · <b>PM histowy deweted</b>',
        'chatinfo': '<tg-emoji emoji-id="5870704313440932932">🔒</tg-emoji><b> Type: {type_of}\n</b><tg-emoji emoji-id="5870495350397079101">#️⃣</tg-emoji><b> Chat ID: </b><code>{id}</code><b>\n</b><tg-emoji emoji-id="5873225338984599714">🔥</tg-emoji><b> Titwe: {title}\n\n</b><tg-emoji emoji-id="5870676941614354370">🖋</tg-emoji><b> About: {about}\n\n</b><tg-emoji emoji-id="5870684638195748414">👑</tg-emoji><b> Admins: {admins_count}\n</b><tg-emoji emoji-id="5870633910337015697">✅</tg-emoji><b> Onwine: {online_count}\n</b><tg-emoji emoji-id="5870994129244131212">👤</tg-emoji><b> Membews: {participants_count}\n</b><tg-emoji emoji-id="5872988737826197458">🚫</tg-emoji><b> Kicked: {kicked_count}\n</b><tg-emoji emoji-id="5870892901159932239">🔀</tg-emoji><b> Pending wequests: {requests_pending}\n\n</b><tg-emoji emoji-id="5870729937215819584">🕐</tg-emoji><b> Swow mode: {slowmode_seconds}\n</b><tg-emoji emoji-id="5872980989705196227">📞</tg-emoji><b> Caww: {call}\n</b><tg-emoji emoji-id="5870875489362513438">🗑</tg-emoji><b> TTW: {ttl_period}\n</b><tg-emoji emoji-id="5870994129244131212">👤</tg-emoji><b> Wecent wequestews: {recent_requesters}\n\n</b><tg-emoji emoji-id="5870772616305839506">👥</tg-emoji><b> Winked chat: {linked_chat_id}\n</b><tg-emoji emoji-id="5870704313440932932">🛡</tg-emoji><b> Antispam: {antispam}\n</b><tg-emoji emoji-id="5870542612217204751">👁</tg-emoji><b> Membews hidden: {participants_hidden}\n\n</b><tg-emoji emoji-id="5870527201874546272">🔗</tg-emoji><b> Wink: {link}</b>',
        'userinfo': '<blockquote><tg-emoji emoji-id="5870495350397079101">#️⃣</tg-emoji><b> ID: {user_id}\n</b><tg-emoji emoji-id="5873225338984599714">🔥</tg-emoji><b> Fiwst name: {first_name}\n</b><tg-emoji emoji-id="5873225338984599714">🔥</tg-emoji><b> Wast name: {last_name}\n</b><tg-emoji emoji-id="5872980989705196227">📞</tg-emoji><b> Phone: {phone}\n</b><tg-emoji emoji-id="5870998024779468554">🐶</tg-emoji><b> Usewnames: {usernames}</b></blockquote><b>\n</b><blockquote><tg-emoji emoji-id="5870609858520158157">ℹ️</tg-emoji><b> About: {about}</b></blockquote><b>\n</b><blockquote><tg-emoji emoji-id="5870729937215819584">🕐</tg-emoji><b> Houws: </b>{business_work_hours}\n<tg-emoji emoji-id="5870450871715761518">❤️</tg-emoji><b> Emoji status: {emoji_status}</b></blockquote><b>\n</b><blockquote><tg-emoji emoji-id="5870693687691841267">🔉</tg-emoji><b> Channyew: {personal_channel}\n</b><tg-emoji emoji-id="5870847962917113498">🎂</tg-emoji><b> Biwthday: {birthday}\n</b><tg-emoji emoji-id="5870478797593120516">🎁</tg-emoji><b> Gifts: {stargifts_count}</b></blockquote><b>\n</b><blockquote><tg-emoji emoji-id="5870931487146119264">🚨</tg-emoji><b> Chats in common: {common_chats_count}\n</b><tg-emoji emoji-id="5870772616305839506">👥</tg-emoji><b> Common chats: {common_chats}</b></blockquote>',
        'promote.no_rights': '<tg-emoji emoji-id="5870704313440932932">🔓</tg-emoji> <b>Nyot enough wights to change admins.</b>',
        'promote.no_user': '<tg-emoji emoji-id="5870994129244131212">👤</tg-emoji> <b>Specify a usew.</b>\nWepwy, ow pass a usewname ow ID! UwU',
        'promote.demoted': '<tg-emoji emoji-id="5870948572526022116">👋🏻</tg-emoji> <b>{name}</b> [<code>{user_id}</code>] <b>is nyo wongew an admin.</b>',
        'promote.promoted_full': '<tg-emoji emoji-id="5870684638195748414">👑</tg-emoji> <b>{name}</b> [<code>{user_id}</code>] <b>is an admin with fuww wights.</b>\n<b>Wank:</b> {rank}',
        'promote.promoted': '<tg-emoji emoji-id="5870684638195748414">👑</tg-emoji> <b>{name}</b> [<code>{user_id}</code>] <b>is an admin.</b>\n<b>Wank:</b> {rank}',
        'promote.choose': '<tg-emoji emoji-id="5870684638195748414">👑</tg-emoji> <b>Admin wights fow {name}</b> [<code>{user_id}</code>]\n<b>Wank:</b> {rank}',
        'promote.confirm': 'Confiwm',
        'promote.default_rank': 'Admin',
        'promote.tag_group_only': '<tg-emoji emoji-id="5870931487146119264">⚠️</tg-emoji> <b>Membew tags onwy wowk in gwoups.</b>',
        'promote.tag_usage': '<b>Usage:</b> <code>{prefix}settag @user tag</code> ow wepwy with <code>{prefix}settag tag</code>. No tag ow <code>-</code> wemoves it.',
        'promote.tag_invalid': '<tg-emoji emoji-id="5870657884844462243">❌</tg-emoji> <b>A membew tag is at most 16 chawactews, with nyo emoji.</b>',
        'promote.tag_no_rights': '<tg-emoji emoji-id="5870704313440932932">🔓</tg-emoji> <b>You need Manage membew tags to change someone ewse\'s tag.</b>',
        'promote.tag_updated': '<tg-emoji emoji-id="5870676941614354370">🖋</tg-emoji> <b>Membew tag fow {name}:</b> <code>{rank}</code>',
        'promote.tag_removed': '<tg-emoji emoji-id="5255831443816327915">🗑</tg-emoji> <b>Membew tag wemoved fow {name}.</b>',
        'promote.rpc_error': '<tg-emoji emoji-id="5870657884844462243">❌</tg-emoji> <b>Tewegwam ewwow:</b> <code>{error}</code>',
        'promote.right.change_info': '{emoji} Change {where} infow',
        'promote.right.post_messages': '{emoji} Post messages',
        'promote.right.edit_messages': '{emoji} Edit posts',
        'promote.right.delete_messages': '{emoji} Dewete messages',
        'promote.right.ban_users': '{emoji} Westwict usews',
        'promote.right.invite_users': '{emoji} Invite usews',
        'promote.right.pin_messages': '{emoji} Pin messages',
        'promote.right.add_admins': '{emoji} Add admins',
        'promote.right.anonymous': '{emoji} Anonywmous',
        'promote.right.manage_call': '{emoji} Manage cawws',
        'promote.right.manage_topics': '{emoji} Manage topics',
        'promote.right.post_stories': '{emoji} Post stowies',
        'promote.right.edit_stories': '{emoji} Edit stowies',
        'promote.right.delete_stories': '{emoji} Dewete stowies',
        'promote.right.manage_direct_messages': '{emoji} Manage diwect messages',
        'promote.right.manage_ranks': '{emoji} Manage membew tags',
        'promote.right.manage_linked_peers': '{emoji} Manage winked chats',
        'promote.right.manage_welcome_messages': '{emoji} Manage wewcome messages',
        'promote.right.other': '{emoji} Othew wights',
        'chat.not_channel': '<tg-emoji emoji-id="5870693687691841267">📣</tg-emoji> <b>This onwy wowks in supewgwoups and channews.</b>',
        'chat.no_rights': '<tg-emoji emoji-id="5870704313440932932">🔓</tg-emoji> <b>Nyot enyough wights to change this chat.</b>',
        'chat.usage.slow': '<b>Usage:</b> <code>{prefix}swow</code> off, ow <code>30</code>, <code>1m</code>, <code>5m</code>, <code>1h</code>.',
        'chat.usage.about': '<b>Usage:</b> <code>{prefix}setabout text</code>. <code>-</code> cweaws it.',
        'chat.usage.photo': '<b>Usage:</b> wepwy to a photo with <code>{prefix}setphoto</code>. <code>-</code> wemuvs it.',
        'chat.usage.username': '<b>Usage:</b> <code>{prefix}setusewnyame nyame</code>. <code>-</code> wemuvs it.',
        'chat.usage.link': '<b>Usage:</b> <code>{prefix}wink</code>, <code>new</code>, <code>wevoke</code>, ow <code>titwe</code>.',
        'chat.slow_off': '<tg-emoji emoji-id="5870729937215819584">🕐</tg-emoji> <b>Swow mode is off.</b>',
        'chat.slow_on': '<tg-emoji emoji-id="5870729937215819584">🕐</tg-emoji> <b>Swow mode:</b> <code>{seconds}</code>s',
        'chat.about_set': '<tg-emoji emoji-id="5870676941614354370">🖋</tg-emoji> <b>Descwiption updated.</b>',
        'chat.about_cleared': '<tg-emoji emoji-id="5255831443816327915">🗑</tg-emoji> <b>Descwiption cweawed.</b>',
        'chat.photo_set': '<tg-emoji emoji-id="5870782662234346251">🖼️</tg-emoji> <b>Chat photo updated.</b>',
        'chat.photo_cleared': '<tg-emoji emoji-id="5255831443816327915">🗑</tg-emoji> <b>Chat photo wemuvd.</b>',
        'chat.username_set': '<tg-emoji emoji-id="5870527201874546272">🔗</tg-emoji> <b>Usewnyame:</b> @{username}',
        'chat.username_cleared': '<tg-emoji emoji-id="5255831443816327915">🗑</tg-emoji> <b>Usewnyame wemuvd.</b>',
        'chat.sign_on': '<tg-emoji emoji-id="5870676941614354370">🖋</tg-emoji> <b>Authow signyatuwes awe on.</b>',
        'chat.sign_off': '<tg-emoji emoji-id="5870676941614354370">🖋</tg-emoji> <b>Authow signyatuwes awe off.</b>',
        'chat.forum_on': '<tg-emoji emoji-id="5872886929921413168">💬</tg-emoji> <b>Topics awe on.</b>',
        'chat.forum_off': '<tg-emoji emoji-id="5872886929921413168">💬</tg-emoji> <b>Topics awe off.</b>',
        'chat.spam_on': '<tg-emoji emoji-id="5870704313440932932">🛡</tg-emoji> <b>Aggwessive antispam is on.</b>',
        'chat.spam_off': '<tg-emoji emoji-id="5870704313440932932">🛡</tg-emoji> <b>Aggwessive antispam is off.</b>',
        'chat.hidden_on': '<tg-emoji emoji-id="5870542612217204751">👁</tg-emoji> <b>The membew wist is hidden.</b>',
        'chat.hidden_off': '<tg-emoji emoji-id="5870542612217204751">👁</tg-emoji> <b>The membew wist is visibwe.</b>',
        'chat.history_on': '<tg-emoji emoji-id="5870729937215819584">🕐</tg-emoji> <b>New membews can see the histowy.</b>',
        'chat.history_off': '<tg-emoji emoji-id="5870729937215819584">🕐</tg-emoji> <b>Histowy is hidden fwom new membews.</b>',
        'chat.join_on': '<tg-emoji emoji-id="5870892901159932239">🔀</tg-emoji> <b>Join wequests awe on.</b>',
        'chat.join_off': '<tg-emoji emoji-id="5870892901159932239">🔀</tg-emoji> <b>Join wequests awe off.</b>',
        'chat.link_none': '<tg-emoji emoji-id="5870527201874546272">🔗</tg-emoji> <b>Nyo invite wink yet.</b>',
        'chat.link': '<tg-emoji emoji-id="5870527201874546272">🔗</tg-emoji> <b>Invite:</b> {link}',
        'chat.link_revoked': '<tg-emoji emoji-id="5255831443816327915">🗑</tg-emoji> <b>Invite wevoked.</b>\n<tg-emoji emoji-id="5870527201874546272">🔗</tg-emoji> <b>New:</b> {link}',
        'chat.link_created': '<tg-emoji emoji-id="5870633910337015697">✅</tg-emoji> <b>Invite cweated.</b>\n<tg-emoji emoji-id="5870527201874546272">🔗</tg-emoji> {link}',
        'rights.header': '<tg-emoji emoji-id="5870684638195748414">👑</tg-emoji> <b>{name}</b> [<code>{user_id}</code>]\n<b>Wowe:</b> {role}\n<b>Wank:</b> {rank}',
        'rights.owner': 'Ownew',
        'rights.admin': 'Admin',
        'rights.member': 'Membew',
        'rights.none': '<tg-emoji emoji-id="5870657884844462243">✖️</tg-emoji> <b>{name}</b> [<code>{user_id}</code>] <b>is nyot an admin.</b>',
        'rights.empty': '<i>Nyo wights.</i>',
    }

    strings_tiktok = {
        'name': 'Helm',
        'cfg.warnlimit': 'Сколько варнов, пока юзера не снесут',
        'cfg.ptime': 'На сколько обычно наказывать',
        'cfg.wl_punishment': 'Что будет, когда варны кончатся',
        'cfg.wl_reason': 'Причина, когда лимит варнов',
        'cfg.wl_timespan': 'На сколько кидать за лимит варнов',
        'error.wrongchattype.pm': '<tg-emoji emoji-id="5870563425628721113">📧</tg-emoji> <b>Это только в группах, бро.</b>',
        'error.wrongchattype.channel': '<tg-emoji emoji-id="5870693687691841267">📣</tg-emoji> <b>Группы, не каналы. Не тупи.</b>',
        'error.no_args.user': '<tg-emoji emoji-id="5870994129244131212">👤</tg-emoji> <b>Юзера укажи.</b>\nОтветом, юзом или айди.',
        'error.locate_user': '<tg-emoji emoji-id="5870974879200711167">🔎</tg-emoji> <b>Юзера нет, кринж.</b>\nЧекни юз или айди.',
        'error.can_not_restrict': '<tg-emoji emoji-id="5870704313440932932">🔓</tg-emoji> <b>Не снёс, гг.</b>\nПрав нет, или его поднял не ты.',
        'error.reply_is_service': '<tg-emoji emoji-id="5870982283724328568">⚙️</tg-emoji> <b>Это служебка, не то.</b>\nОтветь на норм сообщение.',
        'error.self': '<tg-emoji emoji-id="5872988737826197458">🔫</tg-emoji> <b>Себя сносить? Ты в муте?</b>',
        'error.warn_self': '<tg-emoji emoji-id="5870948572526022116">☝🏻</tg-emoji> <b>Себя варнить нельзя, лол.</b>',
        'error.no_args.rights': '<tg-emoji emoji-id="5872996816659681395">❓</tg-emoji> <b>Права укажи.</b>\nТипа строка <code>123456789ab</code>. Кинь <code>r</code> в начало, чтоб забрать права.',
        'error.no_user': '<tg-emoji emoji-id="5870994129244131212">👤</tg-emoji> <b>Юзера укажи.</b>\nОтветом, юзом или айди.',
        'error.no_reply': '<tg-emoji emoji-id="5872886929921413168">💬</tg-emoji> <b>Ответь на сообщение, ну.</b>',
        'error.invalid_args': '<tg-emoji emoji-id="5872996816659681395">❓</tg-emoji> <b>Юзай так:</b> <code>g</code> или <code>c</code>, потом название. В конце <code>30m</code>, <code>2h</code> или <code>1d</code> и чат сам снесётся.',
        'error.too_much': '<tg-emoji emoji-id="5870657884844462243">❌</tg-emoji> <b>Число кривое.</b>\nОт 1 до 100, не больше.',
        'error.insufficient_rights': '<tg-emoji emoji-id="5870704313440932932">🔓</tg-emoji> <b>Прав мало, гг.</b>',
        'error.unknown': '<tg-emoji emoji-id="5870657884844462243">🙅🏻‍♂️</tg-emoji> <b>Ошибка какая-то, хз.</b>',
        'error': '<b>Ошибка:</b> <code>{error}</code>',
        'done.muted.f': '<tg-emoji emoji-id="5870681133502435302">🔇</tg-emoji> <b>{user} в муте навсегда, пожизненно</b>',
        'done.muted': '<tg-emoji emoji-id="5870681133502435302">🔇</tg-emoji> <b>{user} в муте на {timespan}</b>',
        'done.warned': '<tg-emoji emoji-id="5870931487146119264">⚠️</tg-emoji> <b>{user} словлил варн</b>',
        'done.banned.f': '<tg-emoji emoji-id="5872988737826197458">⛔</tg-emoji> <b>{user} в бане навсегда, пожизненно</b>',
        'done.banned': '<tg-emoji emoji-id="5872988737826197458">⛔</tg-emoji> <b>{user} в бане на {timespan}</b>',
        'done.kicked': '<tg-emoji emoji-id="5870778972857438051">🍃</tg-emoji> <b>{user} кикнут, пока</b>',
        'done.nomedia': '<tg-emoji emoji-id="5870782662234346251">🖼️</tg-emoji> <b>{user} не может кидать медиа {timespan}</b>',
        'done.nomedia.f': '<tg-emoji emoji-id="5870782662234346251">🖼️</tg-emoji> <b>{user} больше не кидает медиа, гг</b>',
        'done.allowmedia': '<tg-emoji emoji-id="5870782662234346251">🖼️</tg-emoji> <b>{user} снова может кидать медиа</b>',
        'done.setrights.f': '<tg-emoji emoji-id="5870982283724328568">🔧</tg-emoji> <b>Права <code>{user}</code> теперь {rights}</b>',
        'done.setrights': '<tg-emoji emoji-id="5870982283724328568">🔧</tg-emoji> <b>Права <code>{user}</code> теперь {rights}</b> fили {timespan}',
        'done.unmuted': '<tg-emoji emoji-id="5870693687691841267">🔊</tg-emoji> <b>{user} снова может писать</b>',
        'done.unbanned': '<tg-emoji emoji-id="5870948572526022116">👋🏻</tg-emoji> <b>{user} разбанен</b>',
        'done.unwarned.one': '<tg-emoji emoji-id="5870930636742595124">⚖️</tg-emoji> <b>Один варн сняли с {user}</b>',
        'done.unwarned.all': '<tg-emoji emoji-id="5870930636742595124">⚖️</tg-emoji> <b>Все варны сняли с <code>{user}</code></b>',
        'done.da_kicked': '<tg-emoji emoji-id="5870778972857438051">🍃</tg-emoji> <b>Кикнул <code>{amount}</code> удалёнки</b>',
        'done.pin': '<tg-emoji emoji-id="5870930744116776638">📌</tg-emoji> <b>Закреп, огонь.</b>',
        'done.unpin': '<tg-emoji emoji-id="5870930744116776638">📌</tg-emoji> <b>Откреп.</b>',
        'done.channel_ban.on': '<tg-emoji emoji-id="5870704313440932932">🔒</tg-emoji> <b>Кто пишет от канала — в бан.</b>',
        'done.channel_ban.off': '<tg-emoji emoji-id="5870704313440932932">🔓</tg-emoji> <b>От канала снова можно.</b>',
        'done.channel_ban.action': '<tg-emoji emoji-id="5872988737826197458">⛔</tg-emoji> <b>{user} в бане навсегда, пожизненно</b>\n<b>Причина:</b> писал от канала',
        'done.flushda': '<tg-emoji emoji-id="5870778972857438051">🍃</tg-emoji> <b>Снёс <code>{amt}</code> удалёнки</b>',
        'done.glban.f': '<tg-emoji emoji-id="5870718740236079262">🌍</tg-emoji> <b>{user} в бане в {count} чатах навсегда</b>',
        'done.glban': '<tg-emoji emoji-id="5870718740236079262">🌍</tg-emoji> <b>{user} в бане в {count} чатах на {timespan}</b>',
        'done.glunban': '<tg-emoji emoji-id="5870718740236079262">🌍</tg-emoji> <b>{user} разбанен в {count} chats</b>',
        'done.leave': '<tg-emoji emoji-id="5870764288364252592">😶</tg-emoji> <b>Ливаю.</b>',
        'done.leave.reason': '<tg-emoji emoji-id="5870764288364252592">😶</tg-emoji> <b>Ливаю.</b>\n<b>Причина:</b> <i>{reason}</i>',
        'reason': '\n<b>Причина:</b> <i>{0}</i>',
        'chat_id': '<tg-emoji emoji-id="5870772616305839506">👥</tg-emoji> <b>Айди чата:</b> <code>{chat_id}</code>{additional}\n<tg-emoji emoji-id="5870994129244131212">👤</tg-emoji> <b>Твой айди:</b> <code>{my_id}</code>',
        'person_in_reply_id': '<tg-emoji emoji-id="5870772616305839506">🫂</tg-emoji> <b>Айди в ответе:</b> <code>{reply_id}</code>',
        'sys.DA': 'Удалёнка',
        'sys.LANG': 'ru_RU',
        'sys.forever': 'навсегда (пожизненно)',
        'of_chat': 'группа',
        'of_channel': 'канал',
        'loading': '<tg-emoji emoji-id="5870813306826002498">🟡</tg-emoji> <b>Гружу…</b>',
        'own_list': '<b>Чаты, где ты сигма ({count}):</b>\n\n{msg}',
        'no_ownerships': '<tg-emoji emoji-id="5870657884844462243">❌</tg-emoji> <b>Таких чатов ноль, лол.</b>',
        'not_a_chat': '<tg-emoji emoji-id="5870931487146119264">⚠️</tg-emoji> <b>Только группы.</b>',
        'admins_in_chat': '<tg-emoji emoji-id="5870684638195748414">👑</tg-emoji> <b>Админы в <code>{title}</code> ({count}):</b>\n\n',
        'admins_in_chat_caption': '<b>Админы в {}:</b>',
        'too_many_admins': 'Админов дофига. Кидаю файлом…',
        'no_admins_in_chat': '<b>Админов нет.</b>',
        'bots_in_chat': '<tg-emoji emoji-id="5870531058755178453">🤖</tg-emoji> <b>Боты в <code>{title}</code> ({count}):</b>\n\n',
        'bots_in_chat_caption': '<b>Боты в <code>{}</code>:</b>',
        'too_many_bots': 'Ботов дофига. Кидаю файлом…',
        'no_bots_in_chat': '<b>Ботов нет.</b>',
        'users_in_chat': '<tg-emoji emoji-id="5870994129244131212">👤</tg-emoji> <b>Участники в <code>{title}</code> ({count}):</b>\n\n',
        'users_in_chat_caption': '<b>Участники в <code>{}</code>:</b>',
        'no_user_in_chat': '<b>Тут пусто.</b>',
        'too_many_users': 'Народа дофига. Кидаю файлом…',
        'chat_muted': '<tg-emoji emoji-id="5870681133502435302">🔇</tg-emoji> <b>Писать больше нельзя, мут на чат.</b>',
        'chat_unmuted': '<tg-emoji emoji-id="5870633910337015697">✅</tg-emoji> <b>Снова можно писать.</b>',
        'title_changed': '<b>{type_of} переименован с <code>{old_title}</code> на <code>{new_title}</code>.</b>',
        'user_invited': '<tg-emoji emoji-id="5870633910337015697">✅</tg-emoji> <b><a href=\'tg://user?id={id}\'>{user}</a> заинвайчен.</b>',
        'creator': '<tg-emoji emoji-id="5870684638195748414">👑</tg-emoji> <b>Овнер: <a href=\'tg://user?id={id}\'>{creator}</a>.</b>',
        'no_creator': '<tg-emoji emoji-id="5870657884844462243">❌</tg-emoji> <b>Овнера нет, кринж.</b>',
        'channel_created': '<tg-emoji emoji-id="5870633910337015697">✅</tg-emoji> <b>Канал <code>{title}</code> создан.</b>\n<tg-emoji emoji-id="5870527201874546272">🔗</tg-emoji> <b>Инвайт: {link}</b>',
        'group_created': '<tg-emoji emoji-id="5870633910337015697">✅</tg-emoji> <b>Группа <code>{title}</code> создан.</b>\n<tg-emoji emoji-id="5870527201874546272">🔗</tg-emoji> <b>Инвайт: {link}</b>',
        'temp_chat': '\n<tg-emoji emoji-id="5870875489362513438">🗑</tg-emoji> <b>Сам снесётся через {timespan}.</b>',
        'type_group': 'Группа',
        'type_channel': 'Канал',
        'type_unknown': 'Хз',
        'yes': '<tg-emoji emoji-id="5870633910337015697">✅</tg-emoji> Ага',
        'no': '<tg-emoji emoji-id="5870657884844462243">✖️</tg-emoji> Неа',
        'all_approved': '<tg-emoji emoji-id="5870633910337015697">✅</tg-emoji> <b>Заявки приняты</b>',
        'all_dismissed': '<tg-emoji emoji-id="5870657884844462243">✖️</tg-emoji> <b>Заявки в отказ</b>',
        'log_text': '<tg-emoji emoji-id="5870994129244131212">👤</tg-emoji> <b>Юзер:</b> {user}\n<tg-emoji emoji-id="5870704313440932932">🔒</tg-emoji> <b>Админ:</b> {admin}\n<tg-emoji emoji-id="5872988737826197458">⛔️</tg-emoji> <b>Чё сделали:</b> {punishment}{reason}{time}{chat}',
        'log_chat': '\n<tg-emoji emoji-id="5872886929921413168">💬</tg-emoji> <b>Чат:</b> {chat}',
        'log_reason': '\n<tg-emoji emoji-id="5870676941614354370">🖋</tg-emoji> <b>Причина:</b> {reason}',
        'log_time': '\n<tg-emoji emoji-id="5870729937215819584">⏰️</tg-emoji> <b>Срок:</b> {time}',
        'act.mute': 'Мут',
        'act.ban': 'Бан',
        'act.kick': 'Кик',
        'act.unmute': 'Анмут',
        'act.unban': 'Анбан',
        'act.warn': 'Варн',
        'act.nomedia': 'Медиа в бане',
        'act.allowmedia': 'Медиа вернули',
        'act.rights': 'Права крутанули',
        'flushda.loading': '<tg-emoji emoji-id="5870813306826002498">🟡</tg-emoji> <b>Чищу удалёнки…</b>',
        'flushda.loading.chat': '<tg-emoji emoji-id="5870813306826002498">🟡</tg-emoji> <b>Чищу удалёнки в этом чате…</b>',
        'flushda.loading.channels': '<tg-emoji emoji-id="5870813306826002498">🟡</tg-emoji> <b>Чищу удалёнки в каналах…</b>',
        'monday': 'Пн',
        'tuesday': 'Вт',
        'wednesday': 'Ср',
        'thursday': 'Чт',
        'friday': 'Пт',
        'saturday': 'Сб',
        'sunday': 'Вс',
        'cfg.gban_except': 'Айди чатов, которые .gban не трогает',
        'cfg.gban_pm_block': 'В лс тоже банить на .gban и отпускать на .ungban',
        'cfg.gban_pm_del_history': 'И переписку в лс сносить',
        'cfg.gban_pm_except': 'Кого в лс никогда не банить',
        'cfg.global_logs': 'Логи не только своих команд, а из всех чатов где ты админ',
        'gban.no_reason': 'Без причины, лол',
        'gban.args': '<tg-emoji emoji-id="5870994129244131212">👤</tg-emoji> <b>Юзера укажи.</b>\nОтветом, юзом или айди.',
        'gban.working': '<tg-emoji emoji-id="5870718740236079262">🌍</tg-emoji> <b>Баню <a href="{url}">{name}</a> везде…</b>',
        'gban.unworking': '<tg-emoji emoji-id="5870718740236079262">🌍</tg-emoji> <b>Разбаню <a href="{url}">{name}</a> везде…</b>',
        'gban.done': '<tg-emoji emoji-id="5872988737826197458">⛔</tg-emoji> <b><a href="{url}">{name}</a> в бане в {count} chats</b>\n<b>Причина:</b> <i>{reason}</i>',
        'gban.undone': '<tg-emoji emoji-id="5870948572526022116">👋🏻</tg-emoji> <b><a href="{url}">{name}</a> разбанен в {count} chats</b>',
        'gban.chats': '\n{chats}',
        'gban.pm_blocked': '\n<tg-emoji emoji-id="5872988737826197458">🚫</tg-emoji> <b>В лс тоже бан</b>',
        'gban.pm_unblocked': '\n<tg-emoji emoji-id="5870948572526022116">👋🏻</tg-emoji> <b>В лс разбан</b>',
        'gban.pm_failed': '\n<tg-emoji emoji-id="5870704313440932932">🔓</tg-emoji> <b>В лс не забанил, гг</b>',
        'gban.pm_cleared': ' · <b>переписку снёс</b>',
        'chatinfo': '<tg-emoji emoji-id="5870704313440932932">🔒</tg-emoji><b> Тип: {type_of}\n</b><tg-emoji emoji-id="5870495350397079101">#️⃣</tg-emoji><b> Айди чата: </b><code>{id}</code><b>\n</b><tg-emoji emoji-id="5873225338984599714">🔥</tg-emoji><b> Название: {title}\n\n</b><tg-emoji emoji-id="5870676941614354370">🖋</tg-emoji><b> Описание: {about}\n\n</b><tg-emoji emoji-id="5870684638195748414">👑</tg-emoji><b> Админы: {admins_count}\n</b><tg-emoji emoji-id="5870633910337015697">✅</tg-emoji><b> Онлайн: {online_count}\n</b><tg-emoji emoji-id="5870994129244131212">👤</tg-emoji><b> Участники: {participants_count}\n</b><tg-emoji emoji-id="5872988737826197458">🚫</tg-emoji><b> Кикнутые: {kicked_count}\n</b><tg-emoji emoji-id="5870892901159932239">🔀</tg-emoji><b> Заявки: {requests_pending}\n\n</b><tg-emoji emoji-id="5870729937215819584">🕐</tg-emoji><b> Слоумод: {slowmode_seconds}\n</b><tg-emoji emoji-id="5872980989705196227">📞</tg-emoji><b> Звонок: {call}\n</b><tg-emoji emoji-id="5870875489362513438">🗑</tg-emoji><b> TTL: {ttl_period}\n</b><tg-emoji emoji-id="5870994129244131212">👤</tg-emoji><b> Кто просился: {recent_requesters}\n\n</b><tg-emoji emoji-id="5870772616305839506">👥</tg-emoji><b> Связанный чат: {linked_chat_id}\n</b><tg-emoji emoji-id="5870704313440932932">🛡</tg-emoji><b> Антиспам: {antispam}\n</b><tg-emoji emoji-id="5870542612217204751">👁</tg-emoji><b> Список скрыт: {participants_hidden}\n\n</b><tg-emoji emoji-id="5870527201874546272">🔗</tg-emoji><b> Ссылка: {link}</b>',
        'userinfo': '<blockquote><tg-emoji emoji-id="5870495350397079101">#️⃣</tg-emoji><b> ID: {user_id}\n</b><tg-emoji emoji-id="5873225338984599714">🔥</tg-emoji><b> Имя: {first_name}\n</b><tg-emoji emoji-id="5873225338984599714">🔥</tg-emoji><b> Фамилия: {last_name}\n</b><tg-emoji emoji-id="5872980989705196227">📞</tg-emoji><b> Телефон: {phone}\n</b><tg-emoji emoji-id="5870998024779468554">🐶</tg-emoji><b> Usernames: {usernames}</b></blockquote><b>\n</b><blockquote><tg-emoji emoji-id="5870609858520158157">ℹ️</tg-emoji><b> Описание: {about}</b></blockquote><b>\n</b><blockquote><tg-emoji emoji-id="5870729937215819584">🕐</tg-emoji><b> Часы: </b>{business_work_hours}\n<tg-emoji emoji-id="5870450871715761518">❤️</tg-emoji><b> Эмодзи-статус: {emoji_status}</b></blockquote><b>\n</b><blockquote><tg-emoji emoji-id="5870693687691841267">🔉</tg-emoji><b> Канал: {personal_channel}\n</b><tg-emoji emoji-id="5870847962917113498">🎂</tg-emoji><b> День рождения: {birthday}\n</b><tg-emoji emoji-id="5870478797593120516">🎁</tg-emoji><b> Гифты: {stargifts_count}</b></blockquote><b>\n</b><blockquote><tg-emoji emoji-id="5870931487146119264">🚨</tg-emoji><b> Общие чаты: {common_chats_count}\n</b><tg-emoji emoji-id="5870772616305839506">👥</tg-emoji><b> Common chats: {common_chats}</b></blockquote>',
        'promote.no_rights': '<tg-emoji emoji-id="5870704313440932932">🔓</tg-emoji> <b>Прав нет, админов не тронешь. гг.</b>',
        'promote.no_user': '<tg-emoji emoji-id="5870994129244131212">👤</tg-emoji> <b>Юзера укажи.</b>\nОтветом, юзом или айди.',
        'promote.demoted': '<tg-emoji emoji-id="5870948572526022116">👋🏻</tg-emoji> <b>{name}</b> [<code>{user_id}</code>] <b>больше не админ, лол.</b>',
        'promote.promoted_full': '<tg-emoji emoji-id="5870684638195748414">👑</tg-emoji> <b>{name}</b> [<code>{user_id}</code>] <b>админ на фулл, сигма.</b>\n<b>Должность:</b> {rank}',
        'promote.promoted': '<tg-emoji emoji-id="5870684638195748414">👑</tg-emoji> <b>{name}</b> [<code>{user_id}</code>] <b>теперь админ.</b>\n<b>Должность:</b> {rank}',
        'promote.choose': '<tg-emoji emoji-id="5870684638195748414">👑</tg-emoji> <b>Права для {name}</b> [<code>{user_id}</code>]\n<b>Должность:</b> {rank}',
        'promote.confirm': 'Ок',
        'promote.default_rank': 'Админ',
        'promote.tag_group_only': '<tg-emoji emoji-id="5870931487146119264">⚠️</tg-emoji> <b>Теги только в группах, не тупи.</b>',
        'promote.tag_usage': '<b>Юзай:</b> <code>{prefix}settag @user тег</code> или ответом <code>{prefix}settag тег</code>. Без тега или <code>-</code> снимает его.',
        'promote.tag_invalid': '<tg-emoji emoji-id="5870657884844462243">❌</tg-emoji> <b>Тег максимум 16 символов, без эмодзи. кринж.</b>',
        'promote.tag_no_rights': '<tg-emoji emoji-id="5870704313440932932">🔓</tg-emoji> <b>Чужой тег без права «Управление тегами» не поменять. гг.</b>',
        'promote.tag_updated': '<tg-emoji emoji-id="5870676941614354370">🖋</tg-emoji> <b>Тег {name}:</b> <code>{rank}</code>',
        'promote.tag_removed': '<tg-emoji emoji-id="5255831443816327915">🗑</tg-emoji> <b>Тег {name} снёс.</b>',
        'promote.rpc_error': '<tg-emoji emoji-id="5870657884844462243">❌</tg-emoji> <b>Телега орёт:</b> <code>{error}</code>',
        'promote.right.change_info': '{emoji} Менять инфу {where}',
        'promote.right.post_messages': '{emoji} Постить',
        'promote.right.edit_messages': '{emoji} Редактить посты',
        'promote.right.delete_messages': '{emoji} Сносить сообщения',
        'promote.right.ban_users': '{emoji} Ограничивать юзеров',
        'promote.right.invite_users': '{emoji} Добавлять юзеров',
        'promote.right.pin_messages': '{emoji} Закреплять',
        'promote.right.add_admins': '{emoji} Назначать админов',
        'promote.right.anonymous': '{emoji} Аноним',
        'promote.right.manage_call': '{emoji} Звонки',
        'promote.right.manage_topics': '{emoji} Темы',
        'promote.right.post_stories': '{emoji} Постить сторис',
        'promote.right.edit_stories': '{emoji} Редактить сторис',
        'promote.right.delete_stories': '{emoji} Сносить сторис',
        'promote.right.manage_direct_messages': '{emoji} ЛС канала',
        'promote.right.manage_ranks': '{emoji} Теги участников',
        'promote.right.manage_linked_peers': '{emoji} Связанные чаты',
        'promote.right.manage_welcome_messages': '{emoji} Приветки',
        'promote.right.other': '{emoji} Прочие права',
        'chat.not_channel': '<tg-emoji emoji-id="5870693687691841267">📣</tg-emoji> <b>Это только супергруппы и каналы, не тупи.</b>',
        'chat.no_rights': '<tg-emoji emoji-id="5870704313440932932">🔓</tg-emoji> <b>Прав нет, чат не тронешь. гг.</b>',
        'chat.usage.slow': '<b>Юзай:</b> <code>{prefix}slow</code> off, либо <code>30</code>, <code>1m</code>, <code>5m</code>, <code>1h</code>.',
        'chat.usage.about': '<b>Юзай:</b> <code>{prefix}setabout текст</code>. <code>-</code> сносит.',
        'chat.usage.photo': '<b>Юзай:</b> ответом на фото <code>{prefix}setphoto</code>. <code>-</code> сносит.',
        'chat.usage.username': '<b>Юзай:</b> <code>{prefix}setusername имя</code>. <code>-</code> сносит.',
        'chat.usage.link': '<b>Юзай:</b> <code>{prefix}link</code>, <code>new</code>, <code>revoke</code> или <code>название</code>.',
        'chat.slow_off': '<tg-emoji emoji-id="5870729937215819584">🕐</tg-emoji> <b>Слоумод вырубил.</b>',
        'chat.slow_on': '<tg-emoji emoji-id="5870729937215819584">🕐</tg-emoji> <b>Слоумод:</b> <code>{seconds}</code> сек',
        'chat.about_set': '<tg-emoji emoji-id="5870676941614354370">🖋</tg-emoji> <b>Описание обновил.</b>',
        'chat.about_cleared': '<tg-emoji emoji-id="5255831443816327915">🗑</tg-emoji> <b>Описание снёс.</b>',
        'chat.photo_set': '<tg-emoji emoji-id="5870782662234346251">🖼️</tg-emoji> <b>Фото чата обновил.</b>',
        'chat.photo_cleared': '<tg-emoji emoji-id="5255831443816327915">🗑</tg-emoji> <b>Фото чата снёс.</b>',
        'chat.username_set': '<tg-emoji emoji-id="5870527201874546272">🔗</tg-emoji> <b>Юз:</b> @{username}',
        'chat.username_cleared': '<tg-emoji emoji-id="5255831443816327915">🗑</tg-emoji> <b>Юз снёс.</b>',
        'chat.sign_on': '<tg-emoji emoji-id="5870676941614354370">🖋</tg-emoji> <b>Подписи авторов вкл, сигма.</b>',
        'chat.sign_off': '<tg-emoji emoji-id="5870676941614354370">🖋</tg-emoji> <b>Подписи авторов выкл.</b>',
        'chat.forum_on': '<tg-emoji emoji-id="5872886929921413168">💬</tg-emoji> <b>Темы вкл.</b>',
        'chat.forum_off': '<tg-emoji emoji-id="5872886929921413168">💬</tg-emoji> <b>Темы выкл.</b>',
        'chat.spam_on': '<tg-emoji emoji-id="5870704313440932932">🛡</tg-emoji> <b>Жёсткий антиспам вкл.</b>',
        'chat.spam_off': '<tg-emoji emoji-id="5870704313440932932">🛡</tg-emoji> <b>Жёсткий антиспам выкл.</b>',
        'chat.hidden_on': '<tg-emoji emoji-id="5870542612217204751">👁</tg-emoji> <b>Список участников скрыл.</b>',
        'chat.hidden_off': '<tg-emoji emoji-id="5870542612217204751">👁</tg-emoji> <b>Список участников открыл.</b>',
        'chat.history_on': '<tg-emoji emoji-id="5870729937215819584">🕐</tg-emoji> <b>Новые видят историю.</b>',
        'chat.history_off': '<tg-emoji emoji-id="5870729937215819584">🕐</tg-emoji> <b>Историю от новых скрыл.</b>',
        'chat.join_on': '<tg-emoji emoji-id="5870892901159932239">🔀</tg-emoji> <b>Заявки вкл.</b>',
        'chat.join_off': '<tg-emoji emoji-id="5870892901159932239">🔀</tg-emoji> <b>Заявки выкл.</b>',
        'chat.link_none': '<tg-emoji emoji-id="5870527201874546272">🔗</tg-emoji> <b>Инвайта нет, лол.</b>',
        'chat.link': '<tg-emoji emoji-id="5870527201874546272">🔗</tg-emoji> <b>Инвайт:</b> {link}',
        'chat.link_revoked': '<tg-emoji emoji-id="5255831443816327915">🗑</tg-emoji> <b>Инвайт отозвал.</b>\n<tg-emoji emoji-id="5870527201874546272">🔗</tg-emoji> <b>Новый:</b> {link}',
        'chat.link_created': '<tg-emoji emoji-id="5870633910337015697">✅</tg-emoji> <b>Инвайт создал.</b>\n<tg-emoji emoji-id="5870527201874546272">🔗</tg-emoji> {link}',
        'rights.header': '<tg-emoji emoji-id="5870684638195748414">👑</tg-emoji> <b>{name}</b> [<code>{user_id}</code>]\n<b>Роль:</b> {role}\n<b>Должность:</b> {rank}',
        'rights.owner': 'Владелец',
        'rights.admin': 'Админ',
        'rights.member': 'Участник',
        'rights.none': '<tg-emoji emoji-id="5870657884844462243">✖️</tg-emoji> <b>{name}</b> [<code>{user_id}</code>] <b>не админ, кринж.</b>',
        'rights.empty': '<i>Прав ноль.</i>',
    }

    strings_neofit = {
        'name': 'Helm',
        'cfg.warnlimit': 'warns bef|e restrict()',
        'cfg.ptime': 'default ttl',
        'cfg.wl_punishment': 'action when warn_limit is reached',
        'cfg.wl_reason': 'reason string f| warn_limit action',
        'cfg.wl_timespan': 'ttl of the warn_limit action',
        'error.wrongchattype.pm': '<tg-emoji emoji-id="5870563425628721113">📧</tg-emoji> <b>OSstderr: expected a group, got a private fd</b>',
        'error.wrongchattype.channel': '<tg-emoji emoji-id="5870693687691841267">📣</tg-emoji> <b>OSstderr: channels are not groups</b>',
        'error.no_args.user': '<tg-emoji emoji-id="5870994129244131212">👤</tg-emoji> <b>Typestderr: user argument required</b>\npass a reply, username | uid',
        'error.locate_user': '<tg-emoji emoji-id="5870974879200711167">🔎</tg-emoji> <b>Lookupstderr: user not in passwd</b>\ncheck username | uid',
        'error.can_not_restrict': '<tg-emoji emoji-id="5870704313440932932">🔓</tg-emoji> <b>EPERM: restrict() failed</b>\nmissing cap_admin, | promoted by another uid',
        'error.reply_is_service': '<tg-emoji emoji-id="5870982283724328568">⚙️</tg-emoji> <b>EINVAL: service message, not a user payload</b>\nreply to a non-service message',
        'error.self': '<tg-emoji emoji-id="5872988737826197458">🔫</tg-emoji> <b>PermissionError: chmod on self denied</b>',
        'error.warn_self': '<tg-emoji emoji-id="5870948572526022116">☝🏻</tg-emoji> <b>Permissionstderr: warn(self) denied</b>',
        'error.no_args.rights': '<tg-emoji emoji-id="5872996816659681395">❓</tg-emoji> <b>usage: rights bitmask required</b>\nbitstring like <code>123456789ab</code>. prefix <code>r</code> to clear those bits.',
        'error.no_user': '<tg-emoji emoji-id="5870994129244131212">👤</tg-emoji> <b>Typestderr: user argument required</b>\npass a reply, username | uid',
        'error.no_reply': '<tg-emoji emoji-id="5872886929921413168">💬</tg-emoji> <b>ESRCH: no reply message</b>',
        'error.invalid_args': '<tg-emoji emoji-id="5872996816659681395">❓</tg-emoji> <b>usage:</b> <code>g</code> | <code>c</code>, TITLE. optional <code>30m</code>, <code>2h</code> | <code>1d</code> schedules unlink.',
        'error.too_much': '<tg-emoji emoji-id="5870657884844462243">❌</tg-emoji> <b>ERANGE: count out of range</b>\nexpected 1..100',
        'error.insufficient_rights': '<tg-emoji emoji-id="5870704313440932932">🔓</tg-emoji> <b>EACCES: insufficient permissions</b>',
        'error.unknown': '<tg-emoji emoji-id="5870657884844462243">🙅🏻‍♂️</tg-emoji> <b>EUNKNOWN</b>',
        'error': '<b>stderr:</b> <code>{error}</code>',
        'done.muted.f': '<tg-emoji emoji-id="5870681133502435302">🔇</tg-emoji> <b>{user} muted until while(true)</b>',
        'done.muted': '<tg-emoji emoji-id="5870681133502435302">🔇</tg-emoji> <b>{user} muted f| {timespan}</b>',
        'done.warned': '<tg-emoji emoji-id="5870931487146119264">⚠️</tg-emoji> <b>{user} warn++</b>',
        'done.banned.f': '<tg-emoji emoji-id="5872988737826197458">⛔</tg-emoji> <b>{user} banned until while(true)</b>',
        'done.banned': '<tg-emoji emoji-id="5872988737826197458">⛔</tg-emoji> <b>{user} banned f| {timespan}</b>',
        'done.kicked': '<tg-emoji emoji-id="5870778972857438051">🍃</tg-emoji> <b>{user} killed (SIGKILL)</b>',
        'done.nomedia': '<tg-emoji emoji-id="5870782662234346251">🖼️</tg-emoji> <b>{user} send_media=0 f| {timespan}</b>',
        'done.nomedia.f': '<tg-emoji emoji-id="5870782662234346251">🖼️</tg-emoji> <b>{user} send_media=0 permanently</b>',
        'done.allowmedia': '<tg-emoji emoji-id="5870782662234346251">🖼️</tg-emoji> <b>{user} send_media=1</b>',
        'done.setrights.f': '<tg-emoji emoji-id="5870982283724328568">🔧</tg-emoji> <b>chmod <code>{user}</code> = {rights}</b>',
        'done.setrights': '<tg-emoji emoji-id="5870982283724328568">🔧</tg-emoji> <b>chmod <code>{user}</code> = {rights}</b> f| {timespan}',
        'done.unmuted': '<tg-emoji emoji-id="5870693687691841267">🔊</tg-emoji> <b>{user} write(2) rest|ed</b>',
        'done.unbanned': '<tg-emoji emoji-id="5870948572526022116">👋🏻</tg-emoji> <b>{user} unbanned (exit 0)</b>',
        'done.unwarned.one': '<tg-emoji emoji-id="5870930636742595124">⚖️</tg-emoji> <b>warn-- f| {user}</b>',
        'done.unwarned.all': '<tg-emoji emoji-id="5870930636742595124">⚖️</tg-emoji> <b>warns=0 f| <code>{user}</code></b>',
        'done.da_kicked': '<tg-emoji emoji-id="5870778972857438051">🍃</tg-emoji> <b>killed <code>{amount}</code> uid=0 ghost accounts</b>',
        'done.pin': '<tg-emoji emoji-id="5870930744116776638">📌</tg-emoji> <b>pinned (ln -s)</b>',
        'done.unpin': '<tg-emoji emoji-id="5870930744116776638">📌</tg-emoji> <b>unpinned (unlink)</b>',
        'done.channel_ban.on': '<tg-emoji emoji-id="5870704313440932932">🔒</tg-emoji> <b>channel-auth|ed writes will get EPERM</b>',
        'done.channel_ban.off': '<tg-emoji emoji-id="5870704313440932932">🔓</tg-emoji> <b>channel-auth|ed writes allowed again</b>',
        'done.channel_ban.action': '<tg-emoji emoji-id="5872988737826197458">⛔</tg-emoji> <b>{user} banned until while(true)</b>\n<b>errno:</b> write() as channel',
        'done.flushda': '<tg-emoji emoji-id="5870778972857438051">🍃</tg-emoji> <b>rm <code>{amt}</code> uid=0 ghost accounts</b>',
        'done.glban.f': '<tg-emoji emoji-id="5870718740236079262">🌍</tg-emoji> <b>{user} banned in {count} chats until while(true)</b>',
        'done.glban': '<tg-emoji emoji-id="5870718740236079262">🌍</tg-emoji> <b>{user} banned in {count} chats f| {timespan}</b>',
        'done.glunban': '<tg-emoji emoji-id="5870718740236079262">🌍</tg-emoji> <b>{user} unbanned in {count} chats</b>',
        'done.leave': '<tg-emoji emoji-id="5870764288364252592">😶</tg-emoji> <b>exit(0)</b>',
        'done.leave.reason': '<tg-emoji emoji-id="5870764288364252592">😶</tg-emoji> <b>exit(0)</b>\n<b>errno:</b> <i>{reason}</i>',
        'reason': '\n<b>errno:</b> <i>{0}</i>',
        'chat_id': '<tg-emoji emoji-id="5870772616305839506">👥</tg-emoji> <b>chat.fd:</b> <code>{chat_id}</code>{additional}\n<tg-emoji emoji-id="5870994129244131212">👤</tg-emoji> <b>uid:</b> <code>{my_id}</code>',
        'person_in_reply_id': '<tg-emoji emoji-id="5870772616305839506">🫂</tg-emoji> <b>reply.fd:</b> <code>{reply_id}</code>',
        'sys.DA': 'deleted uid',
        'sys.LANG': 'en_US',
        'sys.forever': 'while(true)',
        'of_chat': 'group',
        'of_channel': 'channel',
        'loading': '<tg-emoji emoji-id="5870813306826002498">🟡</tg-emoji> <b>loading…</b>',
        'own_list': '<b>chats where uid==0 ({count}):</b>\n\n{msg}',
        'no_ownerships': '<tg-emoji emoji-id="5870657884844462243">❌</tg-emoji> <b>Indexstderr: no owned chats</b>',
        'not_a_chat': '<tg-emoji emoji-id="5870931487146119264">⚠️</tg-emoji> <b>Typestderr: expected Chat, not Channel</b>',
        'admins_in_chat': '<tg-emoji emoji-id="5870684638195748414">👑</tg-emoji> <b>admins[] in <code>{title}</code> ({count}):</b>\n\n',
        'admins_in_chat_caption': '<b>admins[] in {}:</b>',
        'too_many_admins': 'EMSGSIZE: admin list dumped to file',
        'no_admins_in_chat': '<b>admins[] is empty</b>',
        'bots_in_chat': '<tg-emoji emoji-id="5870531058755178453">🤖</tg-emoji> <b>bots[] in <code>{title}</code> ({count}):</b>\n\n',
        'bots_in_chat_caption': '<b>bots[] in <code>{}</code>:</b>',
        'too_many_bots': 'EMSGSIZE: bot list dumped to file',
        'no_bots_in_chat': '<b>bots[] is empty</b>',
        'users_in_chat': '<tg-emoji emoji-id="5870994129244131212">👤</tg-emoji> <b>members[] in <code>{title}</code> ({count}):</b>\n\n',
        'users_in_chat_caption': '<b>members[] in <code>{}</code>:</b>',
        'no_user_in_chat': '<b>members[] is empty</b>',
        'too_many_users': 'EMSGSIZE: member list dumped to file',
        'chat_muted': '<tg-emoji emoji-id="5870681133502435302">🔇</tg-emoji> <b>chat.default_send=0</b>',
        'chat_unmuted': '<tg-emoji emoji-id="5870633910337015697">✅</tg-emoji> <b>chat.default_send=1</b>',
        'title_changed': '<b>{type_of} rename() <code>{old_title}</code> to <code>{new_title}</code>.</b>',
        'user_invited': '<tg-emoji emoji-id="5870633910337015697">✅</tg-emoji> <b><a href=\'tg://user?id={id}\'>{user}</a> useradd ok.</b>',
        'creator': '<tg-emoji emoji-id="5870684638195748414">👑</tg-emoji> <b>root: <a href=\'tg://user?id={id}\'>{creator}</a>.</b>',
        'no_creator': '<tg-emoji emoji-id="5870657884844462243">❌</tg-emoji> <b>ENOENT: no owner</b>',
        'channel_created': '<tg-emoji emoji-id="5870633910337015697">✅</tg-emoji> <b>Channel <code>{title}</code> created (exit 0).</b>\n<tg-emoji emoji-id="5870527201874546272">🔗</tg-emoji> <b>invite: {link}</b>',
        'group_created': '<tg-emoji emoji-id="5870633910337015697">✅</tg-emoji> <b>Group <code>{title}</code> created (exit 0).</b>\n<tg-emoji emoji-id="5870527201874546272">🔗</tg-emoji> <b>invite: {link}</b>',
        'temp_chat': '\n<tg-emoji emoji-id="5870875489362513438">🗑</tg-emoji> <b>unlink scheduled in {timespan}.</b>',
        'type_group': 'Group',
        'type_channel': 'Channel',
        'type_unknown': 'unknown',
        'yes': '<tg-emoji emoji-id="5870633910337015697">✅</tg-emoji> true',
        'no': '<tg-emoji emoji-id="5870657884844462243">✖️</tg-emoji> false',
        'all_approved': '<tg-emoji emoji-id="5870633910337015697">✅</tg-emoji> <b>requests: accept(*)</b>',
        'all_dismissed': '<tg-emoji emoji-id="5870657884844462243">✖️</tg-emoji> <b>requests: reject(*)</b>',
        'log_text': '<tg-emoji emoji-id="5870994129244131212">👤</tg-emoji> <b>uid:</b> {user}\n<tg-emoji emoji-id="5870704313440932932">🔒</tg-emoji> <b>act|:</b> {admin}\n<tg-emoji emoji-id="5872988737826197458">⛔️</tg-emoji> <b>syscall:</b> {punishment}{reason}{time}{chat}',
        'log_chat': '\n<tg-emoji emoji-id="5872886929921413168">💬</tg-emoji> <b>chat:</b> {chat}',
        'log_reason': '\n<tg-emoji emoji-id="5870676941614354370">🖋</tg-emoji> <b>errno:</b> {reason}',
        'log_time': '\n<tg-emoji emoji-id="5870729937215819584">⏰️</tg-emoji> <b>ttl:</b> {time}',
        'act.mute': 'mute',
        'act.ban': 'ban',
        'act.kick': 'kill',
        'act.unmute': 'unmute',
        'act.unban': 'unban',
        'act.warn': 'warn',
        'act.nomedia': 'send_media=0',
        'act.allowmedia': 'send_media=1',
        'act.rights': 'chmod',
        'flushda.loading': '<tg-emoji emoji-id="5870813306826002498">🟡</tg-emoji> <b>rm -rf deleted uids…</b>',
        'flushda.loading.chat': '<tg-emoji emoji-id="5870813306826002498">🟡</tg-emoji> <b>rm deleted uids from this chat…</b>',
        'flushda.loading.channels': '<tg-emoji emoji-id="5870813306826002498">🟡</tg-emoji> <b>rm deleted uids from channels…</b>',
        'monday': 'Monday',
        'tuesday': 'Tuesday',
        'wednesday': 'Wednesday',
        'thursday': 'Thursday',
        'friday': 'Friday',
        'saturday': 'Saturday',
        'sunday': 'Sunday',
        'cfg.gban_except': 'chat ids excluded from .gban/.ungban',
        'cfg.gban_pm_block': 'block PM on .gban, unblock on .ungban',
        'cfg.gban_pm_del_history': 'also DeleteHist|y on PM block',
        'cfg.gban_pm_except': 'uids exempt from PM block',
        'cfg.global_logs': 'log bans from every admin chat, not only local syscalls',
        'gban.no_reason': 'NULL',
        'gban.args': '<tg-emoji emoji-id="5870994129244131212">👤</tg-emoji> <b>Typestderr: user argument required</b>\npass a reply, username | uid',
        'gban.working': '<tg-emoji emoji-id="5870718740236079262">🌍</tg-emoji> <b>banning <a href="{url}">{name}</a> in all chats…</b>',
        'gban.unworking': '<tg-emoji emoji-id="5870718740236079262">🌍</tg-emoji> <b>unbanning <a href="{url}">{name}</a> in all chats…</b>',
        'gban.done': '<tg-emoji emoji-id="5872988737826197458">⛔</tg-emoji> <b><a href="{url}">{name}</a> banned in {count} chats</b>\n<b>errno:</b> <i>{reason}</i>',
        'gban.undone': '<tg-emoji emoji-id="5870948572526022116">👋🏻</tg-emoji> <b><a href="{url}">{name}</a> unbanned in {count} chats</b>',
        'gban.chats': '\n{chats}',
        'gban.pm_blocked': '\n<tg-emoji emoji-id="5872988737826197458">🚫</tg-emoji> <b>PM blocked</b>',
        'gban.pm_unblocked': '\n<tg-emoji emoji-id="5870948572526022116">👋🏻</tg-emoji> <b>PM unblocked</b>',
        'gban.pm_failed': '\n<tg-emoji emoji-id="5870704313440932932">🔓</tg-emoji> <b>PM block failed</b>',
        'gban.pm_cleared': ' · <b>PM hist|y unlinked</b>',
        'chatinfo': '<tg-emoji emoji-id="5870704313440932932">🔒</tg-emoji><b> type: {type_of}\n</b><tg-emoji emoji-id="5870495350397079101">#️⃣</tg-emoji><b> chat.fd: </b><code>{id}</code><b>\n</b><tg-emoji emoji-id="5873225338984599714">🔥</tg-emoji><b> title: {title}\n\n</b><tg-emoji emoji-id="5870676941614354370">🖋</tg-emoji><b> about: {about}\n\n</b><tg-emoji emoji-id="5870684638195748414">👑</tg-emoji><b> admins: {admins_count}\n</b><tg-emoji emoji-id="5870633910337015697">✅</tg-emoji><b> online: {online_count}\n</b><tg-emoji emoji-id="5870994129244131212">👤</tg-emoji><b> members: {participants_count}\n</b><tg-emoji emoji-id="5872988737826197458">🚫</tg-emoji><b> kicked: {kicked_count}\n</b><tg-emoji emoji-id="5870892901159932239">🔀</tg-emoji><b> pending: {requests_pending}\n\n</b><tg-emoji emoji-id="5870729937215819584">🕐</tg-emoji><b> slowmode: {slowmode_seconds}\n</b><tg-emoji emoji-id="5872980989705196227">📞</tg-emoji><b> call: {call}\n</b><tg-emoji emoji-id="5870875489362513438">🗑</tg-emoji><b> TTL: {ttl_period}\n</b><tg-emoji emoji-id="5870994129244131212">👤</tg-emoji><b> recent: {recent_requesters}\n\n</b><tg-emoji emoji-id="5870772616305839506">👥</tg-emoji><b> linked: {linked_chat_id}\n</b><tg-emoji emoji-id="5870704313440932932">🛡</tg-emoji><b> antispam: {antispam}\n</b><tg-emoji emoji-id="5870542612217204751">👁</tg-emoji><b> hidden: {participants_hidden}\n\n</b><tg-emoji emoji-id="5870527201874546272">🔗</tg-emoji><b> link: {link}</b>',
        'userinfo': '<blockquote><tg-emoji emoji-id="5870495350397079101">#️⃣</tg-emoji><b> ID: {user_id}\n</b><tg-emoji emoji-id="5873225338984599714">🔥</tg-emoji><b> first_name: {first_name}\n</b><tg-emoji emoji-id="5873225338984599714">🔥</tg-emoji><b> last_name: {last_name}\n</b><tg-emoji emoji-id="5872980989705196227">📞</tg-emoji><b> phone: {phone}\n</b><tg-emoji emoji-id="5870998024779468554">🐶</tg-emoji><b> Usernames: {usernames}</b></blockquote><b>\n</b><blockquote><tg-emoji emoji-id="5870609858520158157">ℹ️</tg-emoji><b> about: {about}</b></blockquote><b>\n</b><blockquote><tg-emoji emoji-id="5870729937215819584">🕐</tg-emoji><b> hours: </b>{business_work_hours}\n<tg-emoji emoji-id="5870450871715761518">❤️</tg-emoji><b> emoji_status: {emoji_status}</b></blockquote><b>\n</b><blockquote><tg-emoji emoji-id="5870693687691841267">🔉</tg-emoji><b> channel: {personal_channel}\n</b><tg-emoji emoji-id="5870847962917113498">🎂</tg-emoji><b> birthday: {birthday}\n</b><tg-emoji emoji-id="5870478797593120516">🎁</tg-emoji><b> gifts: {stargifts_count}</b></blockquote><b>\n</b><blockquote><tg-emoji emoji-id="5870931487146119264">🚨</tg-emoji><b> common_chats: {common_chats_count}\n</b><tg-emoji emoji-id="5870772616305839506">👥</tg-emoji><b> Common chats: {common_chats}</b></blockquote>',
        'promote.no_rights': '<tg-emoji emoji-id="5870704313440932932">🔓</tg-emoji> <b>EPERM: edit_admin() denied</b>',
        'promote.no_user': '<tg-emoji emoji-id="5870994129244131212">👤</tg-emoji> <b>Typestderr: user argument required</b>\npass a reply, username | uid',
        'promote.demoted': '<tg-emoji emoji-id="5870948572526022116">👋🏻</tg-emoji> <b>{name}</b> [<code>{user_id}</code>] <b>admin bit cleared.</b>',
        'promote.promoted_full': '<tg-emoji emoji-id="5870684638195748414">👑</tg-emoji> <b>{name}</b> [<code>{user_id}</code>] <b>promoted, caps=ALL.</b>\n<b>rank:</b> {rank}',
        'promote.promoted': '<tg-emoji emoji-id="5870684638195748414">👑</tg-emoji> <b>{name}</b> [<code>{user_id}</code>] <b>promoted.</b>\n<b>rank:</b> {rank}',
        'promote.choose': '<tg-emoji emoji-id="5870684638195748414">👑</tg-emoji> <b>admin caps f| {name}</b> [<code>{user_id}</code>]\n<b>rank:</b> {rank}',
        'promote.confirm': 'commit',
        'promote.default_rank': 'admin',
        'promote.tag_group_only': '<tg-emoji emoji-id="5870931487146119264">⚠️</tg-emoji> <b>ENOTSUP: member tags exist only on group fds</b>',
        'promote.tag_usage': '<b>usage:</b> <code>{prefix}settag @user tag</code> | reply <code>{prefix}settag tag</code>. no tag or <code>-</code> unlinks it.',
        'promote.tag_invalid': '<tg-emoji emoji-id="5870657884844462243">❌</tg-emoji> <b>EINVAL: tag max 16 bytes, emoji rejected</b>',
        'promote.tag_no_rights': '<tg-emoji emoji-id="5870704313440932932">🔓</tg-emoji> <b>EPERM: cap_manage_ranks required to write another uid\'s tag</b>',
        'promote.tag_updated': '<tg-emoji emoji-id="5870676941614354370">🖋</tg-emoji> <b>tag({name}):</b> <code>{rank}</code>',
        'promote.tag_removed': '<tg-emoji emoji-id="5255831443816327915">🗑</tg-emoji> <b>tag({name}) unlinked.</b>',
        'promote.rpc_error': '<tg-emoji emoji-id="5870657884844462243">❌</tg-emoji> <b>RPC errno:</b> <code>{error}</code>',
        'promote.right.change_info': '{emoji} change {where} info',
        'promote.right.post_messages': '{emoji} post messages',
        'promote.right.edit_messages': '{emoji} edit posts',
        'promote.right.delete_messages': '{emoji} unlink messages',
        'promote.right.ban_users': '{emoji} restrict uids',
        'promote.right.invite_users': '{emoji} invite uids',
        'promote.right.pin_messages': '{emoji} pin messages',
        'promote.right.add_admins': '{emoji} add admins',
        'promote.right.anonymous': '{emoji} anonymous',
        'promote.right.manage_call': '{emoji} manage calls',
        'promote.right.manage_topics': '{emoji} manage topics',
        'promote.right.post_stories': '{emoji} post stories',
        'promote.right.edit_stories': '{emoji} edit stories',
        'promote.right.delete_stories': '{emoji} unlink stories',
        'promote.right.manage_direct_messages': '{emoji} manage direct messages',
        'promote.right.manage_ranks': '{emoji} manage member tags',
        'promote.right.manage_linked_peers': '{emoji} manage linked chats',
        'promote.right.manage_welcome_messages': '{emoji} manage welcome messages',
        'promote.right.other': '{emoji} other caps',
        'chat.not_channel': '<tg-emoji emoji-id="5870693687691841267">📣</tg-emoji> <b>ENOTSUP: supergroup|channel only.</b>',
        'chat.no_rights': '<tg-emoji emoji-id="5870704313440932932">🔓</tg-emoji> <b>EPERM: chat mutation denied.</b>',
        'chat.usage.slow': '<b>usage:</b> <code>{prefix}slow</code> off | <code>30</code> | <code>1m</code> | <code>5m</code> | <code>1h</code>.',
        'chat.usage.about': '<b>usage:</b> <code>{prefix}setabout text</code>. <code>-</code> truncates.',
        'chat.usage.photo': '<b>usage:</b> reply photo <code>{prefix}setphoto</code>. <code>-</code> unlinks.',
        'chat.usage.username': '<b>usage:</b> <code>{prefix}setusername name</code>. <code>-</code> unlinks.',
        'chat.usage.link': '<b>usage:</b> <code>{prefix}link</code> | <code>new</code> | <code>revoke</code> | <code>title</code>.',
        'chat.slow_off': '<tg-emoji emoji-id="5870729937215819584">🕐</tg-emoji> <b>slowmode = 0.</b>',
        'chat.slow_on': '<tg-emoji emoji-id="5870729937215819584">🕐</tg-emoji> <b>slowmode =</b> <code>{seconds}</code>',
        'chat.about_set': '<tg-emoji emoji-id="5870676941614354370">🖋</tg-emoji> <b>about committed.</b>',
        'chat.about_cleared': '<tg-emoji emoji-id="5255831443816327915">🗑</tg-emoji> <b>about truncated.</b>',
        'chat.photo_set': '<tg-emoji emoji-id="5870782662234346251">🖼️</tg-emoji> <b>photo committed.</b>',
        'chat.photo_cleared': '<tg-emoji emoji-id="5255831443816327915">🗑</tg-emoji> <b>photo unlinked.</b>',
        'chat.username_set': '<tg-emoji emoji-id="5870527201874546272">🔗</tg-emoji> <b>username =</b> @{username}',
        'chat.username_cleared': '<tg-emoji emoji-id="5255831443816327915">🗑</tg-emoji> <b>username unlinked.</b>',
        'chat.sign_on': '<tg-emoji emoji-id="5870676941614354370">🖋</tg-emoji> <b>signatures = 1.</b>',
        'chat.sign_off': '<tg-emoji emoji-id="5870676941614354370">🖋</tg-emoji> <b>signatures = 0.</b>',
        'chat.forum_on': '<tg-emoji emoji-id="5872886929921413168">💬</tg-emoji> <b>topics = 1.</b>',
        'chat.forum_off': '<tg-emoji emoji-id="5872886929921413168">💬</tg-emoji> <b>topics = 0.</b>',
        'chat.spam_on': '<tg-emoji emoji-id="5870704313440932932">🛡</tg-emoji> <b>antispam = aggressive.</b>',
        'chat.spam_off': '<tg-emoji emoji-id="5870704313440932932">🛡</tg-emoji> <b>antispam = 0.</b>',
        'chat.hidden_on': '<tg-emoji emoji-id="5870542612217204751">👁</tg-emoji> <b>members hidden = 1.</b>',
        'chat.hidden_off': '<tg-emoji emoji-id="5870542612217204751">👁</tg-emoji> <b>members hidden = 0.</b>',
        'chat.history_on': '<tg-emoji emoji-id="5870729937215819584">🕐</tg-emoji> <b>prehistory visible = 1.</b>',
        'chat.history_off': '<tg-emoji emoji-id="5870729937215819584">🕐</tg-emoji> <b>prehistory visible = 0.</b>',
        'chat.join_on': '<tg-emoji emoji-id="5870892901159932239">🔀</tg-emoji> <b>join requests = 1.</b>',
        'chat.join_off': '<tg-emoji emoji-id="5870892901159932239">🔀</tg-emoji> <b>join requests = 0.</b>',
        'chat.link_none': '<tg-emoji emoji-id="5870527201874546272">🔗</tg-emoji> <b>invite = NULL.</b>',
        'chat.link': '<tg-emoji emoji-id="5870527201874546272">🔗</tg-emoji> <b>invite:</b> {link}',
        'chat.link_revoked': '<tg-emoji emoji-id="5255831443816327915">🗑</tg-emoji> <b>invite revoked.</b>\n<tg-emoji emoji-id="5870527201874546272">🔗</tg-emoji> <b>new:</b> {link}',
        'chat.link_created': '<tg-emoji emoji-id="5870633910337015697">✅</tg-emoji> <b>invite committed.</b>\n<tg-emoji emoji-id="5870527201874546272">🔗</tg-emoji> {link}',
        'rights.header': '<tg-emoji emoji-id="5870684638195748414">👑</tg-emoji> <b>{name}</b> [<code>{user_id}</code>]\n<b>role:</b> {role}\n<b>rank:</b> {rank}',
        'rights.owner': 'owner',
        'rights.admin': 'admin',
        'rights.member': 'member',
        'rights.none': '<tg-emoji emoji-id="5870657884844462243">✖️</tg-emoji> <b>{name}</b> [<code>{user_id}</code>] <b>caps = 0.</b>',
        'rights.empty': '<i>caps empty.</i>',
    }

    strings_pirate = {
        'name': 'Helm',
        'cfg.warnlimit': 'Warns before a hand is clapped in irons',
        'cfg.ptime': 'Usual length of the sentence',
        'cfg.wl_punishment': 'What befalls when the warn tally is full',
        'cfg.wl_reason': 'Cause spoken for the warn-tally sentence',
        'cfg.wl_timespan': 'How long the warn-tally sentence holds',
        'error.wrongchattype.pm': '<tg-emoji emoji-id="5870563425628721113">📧</tg-emoji> <b>This only works aboard a crew.</b>',
        'error.wrongchattype.channel': '<tg-emoji emoji-id="5870693687691841267">📣</tg-emoji> <b>This be fer crews, not signal flags.</b>',
        'error.no_args.user': '<tg-emoji emoji-id="5870994129244131212">👤</tg-emoji> <b>Name a hand.</b>\nAnswer a dispatch, or give a name or number.',
        'error.locate_user': '<tg-emoji emoji-id="5870974879200711167">🔎</tg-emoji> <b>Nay such hand on these seas.</b>\nCheck the name or the number.',
        'error.can_not_restrict': '<tg-emoji emoji-id="5870704313440932932">🔓</tg-emoji> <b>Couldn\'t clap them in irons.</b>\nYe may lack the leave, or another mate raised them.',
        'error.reply_is_service': '<tg-emoji emoji-id="5870982283724328568">⚙️</tg-emoji> <b>That be a ship\'s bell, not a dispatch.</b>\nAnswer a proper dispatch.',
        'error.self': '<tg-emoji emoji-id="5872988737826197458">🔫</tg-emoji> <b>Ye can\'t maroon yer own self.</b>',
        'error.warn_self': '<tg-emoji emoji-id="5870948572526022116">☝🏻</tg-emoji> <b>Ye can\'t warn yer own self.</b>',
        'error.no_args.rights': '<tg-emoji emoji-id="5872996816659681395">❓</tg-emoji> <b>Name the leaves.</b>\nA string like <code>123456789ab</code>. Set <code>r</code> afore it to strike those leaves.',
        'error.no_user': '<tg-emoji emoji-id="5870994129244131212">👤</tg-emoji> <b>Name a hand.</b>\nAnswer a dispatch, or give a name or number.',
        'error.no_reply': '<tg-emoji emoji-id="5872886929921413168">💬</tg-emoji> <b>Answer a dispatch.</b>',
        'error.invalid_args': '<tg-emoji emoji-id="5872996816659681395">❓</tg-emoji> <b>How to hail:</b> <code>g</code> or <code>c</code>, then a name. A trailing <code>30m</code>, <code>2h</code> or <code>1d</code> scuttles it later.',
        'error.too_much': '<tg-emoji emoji-id="5870657884844462243">❌</tg-emoji> <b>Foul tally.</b>\nGive a number from 1 to 100.',
        'error.insufficient_rights': '<tg-emoji emoji-id="5870704313440932932">🔓</tg-emoji> <b>Nayt enough leave.</b>',
        'error.unknown': '<tg-emoji emoji-id="5870657884844462243">🙅🏻‍♂️</tg-emoji> <b>Uncharted mishap.</b>',
        'error': '<b>Mishap:</b> <code>{error}</code>',
        'done.muted.f': '<tg-emoji emoji-id="5870681133502435302">🔇</tg-emoji> <b>{user} is gagged till the seas run dry</b>',
        'done.muted': '<tg-emoji emoji-id="5870681133502435302">🔇</tg-emoji> <b>{user} is gagged fer {timespan}</b>',
        'done.warned': '<tg-emoji emoji-id="5870931487146119264">⚠️</tg-emoji> <b>{user} has been warned</b>',
        'done.banned.f': '<tg-emoji emoji-id="5872988737826197458">⛔</tg-emoji> <b>{user} is marooned till the seas run dry</b>',
        'done.banned': '<tg-emoji emoji-id="5872988737826197458">⛔</tg-emoji> <b>{user} is marooned fer {timespan}</b>',
        'done.kicked': '<tg-emoji emoji-id="5870778972857438051">🍃</tg-emoji> <b>{user} has been cast overboard</b>',
        'done.nomedia': '<tg-emoji emoji-id="5870782662234346251">🖼️</tg-emoji> <b>{user} can\'t send pictures fer {timespan}</b>',
        'done.nomedia.f': '<tg-emoji emoji-id="5870782662234346251">🖼️</tg-emoji> <b>{user} can\'t send pictures anymore</b>',
        'done.allowmedia': '<tg-emoji emoji-id="5870782662234346251">🖼️</tg-emoji> <b>{user} may send pictures again</b>',
        'done.setrights.f': '<tg-emoji emoji-id="5870982283724328568">🔧</tg-emoji> <b>Leaves fer <code>{user}</code> set to {rights}</b>',
        'done.setrights': '<tg-emoji emoji-id="5870982283724328568">🔧</tg-emoji> <b>Leaves fer <code>{user}</code> set to {rights}</b> for {timespan}',
        'done.unmuted': '<tg-emoji emoji-id="5870693687691841267">🔊</tg-emoji> <b>{user} may write again</b>',
        'done.unbanned': '<tg-emoji emoji-id="5870948572526022116">👋🏻</tg-emoji> <b>{user} is welcomed back</b>',
        'done.unwarned.one': '<tg-emoji emoji-id="5870930636742595124">⚖️</tg-emoji> <b>One warn struck from {user}</b>',
        'done.unwarned.all': '<tg-emoji emoji-id="5870930636742595124">⚖️</tg-emoji> <b>All warns struck from <code>{user}</code></b>',
        'done.da_kicked': '<tg-emoji emoji-id="5870778972857438051">🍃</tg-emoji> <b>Cast overboard <code>{amount}</code> dead accounts</b>',
        'done.pin': '<tg-emoji emoji-id="5870930744116776638">📌</tg-emoji> <b>Nailed up.</b>',
        'done.unpin': '<tg-emoji emoji-id="5870930744116776638">📌</tg-emoji> <b>Torn down.</b>',
        'done.channel_ban.on': '<tg-emoji emoji-id="5870704313440932932">🔒</tg-emoji> <b>Dispatches sent as a signal flag will be marooned.</b>',
        'done.channel_ban.off': '<tg-emoji emoji-id="5870704313440932932">🔓</tg-emoji> <b>Dispatches sent as a signal flag are allowed again.</b>',
        'done.channel_ban.action': '<tg-emoji emoji-id="5872988737826197458">⛔</tg-emoji> <b>{user} is marooned till the seas run dry</b>\n<b>Cause:</b> writing under a signal flag',
        'done.flushda': '<tg-emoji emoji-id="5870778972857438051">🍃</tg-emoji> <b>Swept away <code>{amt}</code> dead accounts</b>',
        'done.glban.f': '<tg-emoji emoji-id="5870718740236079262">🌍</tg-emoji> <b>{user} is marooned in {count} taverns till the seas run dry</b>',
        'done.glban': '<tg-emoji emoji-id="5870718740236079262">🌍</tg-emoji> <b>{user} is marooned in {count} taverns fer {timespan}</b>',
        'done.glunban': '<tg-emoji emoji-id="5870718740236079262">🌍</tg-emoji> <b>{user} is welcomed back in {count} taverns</b>',
        'done.leave': '<tg-emoji emoji-id="5870764288364252592">😶</tg-emoji> <b>Abandoning ship.</b>',
        'done.leave.reason': '<tg-emoji emoji-id="5870764288364252592">😶</tg-emoji> <b>Abandoning ship.</b>\n<b>Cause:</b> <i>{reason}</i>',
        'reason': '\n<b>Cause:</b> <i>{0}</i>',
        'chat_id': '<tg-emoji emoji-id="5870772616305839506">👥</tg-emoji> <b>Tavern number:</b> <code>{chat_id}</code>{additional}\n<tg-emoji emoji-id="5870994129244131212">👤</tg-emoji> <b>Yer number:</b> <code>{my_id}</code>',
        'person_in_reply_id': '<tg-emoji emoji-id="5870772616305839506">🫂</tg-emoji> <b>Answer number:</b> <code>{reply_id}</code>',
        'sys.DA': 'Dead account',
        'sys.LANG': 'en_US',
        'sys.forever': 'till the seas run dry',
        'of_chat': 'crew',
        'of_channel': 'signal flag',
        'loading': '<tg-emoji emoji-id="5870813306826002498">🟡</tg-emoji> <b>Hauling…</b>',
        'own_list': '<b>Taverns ye run ({count}):</b>\n\n{msg}',
        'no_ownerships': '<tg-emoji emoji-id="5870657884844462243">❌</tg-emoji> <b>Ye run nary a tavern.</b>',
        'not_a_chat': '<tg-emoji emoji-id="5870931487146119264">⚠️</tg-emoji> <b>Crews only.</b>',
        'admins_in_chat': '<tg-emoji emoji-id="5870684638195748414">👑</tg-emoji> <b>Quartermasters in <code>{title}</code> ({count}):</b>\n\n',
        'admins_in_chat_caption': '<b>Quartermasters in {}:</b>',
        'too_many_admins': 'Too many quartermasters. Sending the roll as a scroll…',
        'no_admins_in_chat': '<b>Nary a quartermaster here.</b>',
        'bots_in_chat': '<tg-emoji emoji-id="5870531058755178453">🤖</tg-emoji> <b>Clockwork mates in <code>{title}</code> ({count}):</b>\n\n',
        'bots_in_chat_caption': '<b>Clockwork mates in <code>{}</code>:</b>',
        'too_many_bots': 'Too many clockwork mates. Sending the roll as a scroll…',
        'no_bots_in_chat': '<b>Nary a clockwork mate here.</b>',
        'users_in_chat': '<tg-emoji emoji-id="5870994129244131212">👤</tg-emoji> <b>Hands in <code>{title}</code> ({count}):</b>\n\n',
        'users_in_chat_caption': '<b>Hands in <code>{}</code>:</b>',
        'no_user_in_chat': '<b>Nary a hand here.</b>',
        'too_many_users': 'Too many hands. Sending the roll as a scroll…',
        'chat_muted': '<tg-emoji emoji-id="5870681133502435302">🔇</tg-emoji> <b>Hands can write no more.</b>',
        'chat_unmuted': '<tg-emoji emoji-id="5870633910337015697">✅</tg-emoji> <b>Hands may write again.</b>',
        'title_changed': '<b>{type_of} renamed from <code>{old_title}</code> to <code>{new_title}</code>.</b>',
        'user_invited': '<tg-emoji emoji-id="5870633910337015697">✅</tg-emoji> <b><a href=\'tg://user?id={id}\'>{user}</a> brought aboard.</b>',
        'creator': '<tg-emoji emoji-id="5870684638195748414">👑</tg-emoji> <b>Cap\'n: <a href=\'tg://user?id={id}\'>{creator}</a>.</b>',
        'no_creator': '<tg-emoji emoji-id="5870657884844462243">❌</tg-emoji> <b>Nay cap\'n found.</b>',
        'channel_created': '<tg-emoji emoji-id="5870633910337015697">✅</tg-emoji> <b>Signal flag <code>{title}</code> raised.</b>\n<tg-emoji emoji-id="5870527201874546272">🔗</tg-emoji> <b>Boarding line: {link}</b>',
        'group_created': '<tg-emoji emoji-id="5870633910337015697">✅</tg-emoji> <b>Crew <code>{title}</code> raised.</b>\n<tg-emoji emoji-id="5870527201874546272">🔗</tg-emoji> <b>Boarding line: {link}</b>',
        'temp_chat': '\n<tg-emoji emoji-id="5870875489362513438">🗑</tg-emoji> <b>Scuttles itself in {timespan}.</b>',
        'type_group': 'Crew',
        'type_channel': 'Signal flag',
        'type_unknown': 'Uncharted',
        'yes': '<tg-emoji emoji-id="5870633910337015697">✅</tg-emoji> Aye',
        'no': '<tg-emoji emoji-id="5870657884844462243">✖️</tg-emoji> Nay',
        'all_approved': '<tg-emoji emoji-id="5870633910337015697">✅</tg-emoji> <b>Pleas granted</b>',
        'all_dismissed': '<tg-emoji emoji-id="5870657884844462243">✖️</tg-emoji> <b>Pleas refused</b>',
        'log_text': '<tg-emoji emoji-id="5870994129244131212">👤</tg-emoji> <b>Hand:</b> {user}\n<tg-emoji emoji-id="5870704313440932932">🔒</tg-emoji> <b>Quartermaster:</b> {admin}\n<tg-emoji emoji-id="5872988737826197458">⛔️</tg-emoji> <b>Deed:</b> {punishment}{reason}{time}{chat}',
        'log_chat': '\n<tg-emoji emoji-id="5872886929921413168">💬</tg-emoji> <b>Tavern:</b> {chat}',
        'log_reason': '\n<tg-emoji emoji-id="5870676941614354370">🖋</tg-emoji> <b>Cause:</b> {reason}',
        'log_time': '\n<tg-emoji emoji-id="5870729937215819584">⏰️</tg-emoji> <b>Watch:</b> {time}',
        'act.mute': 'Gag',
        'act.ban': 'Maroon',
        'act.kick': 'Overboard',
        'act.unmute': 'Ungag',
        'act.unban': 'Welcome back',
        'act.warn': 'Warn',
        'act.nomedia': 'Pictures forbidden',
        'act.allowmedia': 'Pictures allowed',
        'act.rights': 'Leaves changed',
        'flushda.loading': '<tg-emoji emoji-id="5870813306826002498">🟡</tg-emoji> <b>Sweeping dead accounts…</b>',
        'flushda.loading.chat': '<tg-emoji emoji-id="5870813306826002498">🟡</tg-emoji> <b>Sweeping dead accounts from this tavern…</b>',
        'flushda.loading.channels': '<tg-emoji emoji-id="5870813306826002498">🟡</tg-emoji> <b>Sweeping dead accounts from signal flags…</b>',
        'monday': 'Moonday',
        'tuesday': 'Twosday',
        'wednesday': 'Windsday',
        'thursday': 'Thorsday',
        'friday': 'Freeday',
        'saturday': 'Satursday',
        'sunday': 'Sunsday',
        'cfg.gban_except': 'Tavern numbers spared from .gban and .ungban',
        'cfg.gban_pm_block': 'Bar the hand in private on .gban, and lift it on .ungban',
        'cfg.gban_pm_del_history': 'Also burn the private log when barring',
        'cfg.gban_pm_except': 'Hands never barred in private',
        'cfg.global_logs': 'Log irons from every tavern ye run, not only yer own orders',
        'gban.no_reason': 'Nayt spoken',
        'gban.args': '<tg-emoji emoji-id="5870994129244131212">👤</tg-emoji> <b>Name a hand.</b>\nAnswer a dispatch, or give a name or number.',
        'gban.working': '<tg-emoji emoji-id="5870718740236079262">🌍</tg-emoji> <b>Marooning <a href="{url}">{name}</a> on every sea…</b>',
        'gban.unworking': '<tg-emoji emoji-id="5870718740236079262">🌍</tg-emoji> <b>Welcoming back <a href="{url}">{name}</a> on every sea…</b>',
        'gban.done': '<tg-emoji emoji-id="5872988737826197458">⛔</tg-emoji> <b><a href="{url}">{name}</a> is marooned in {count} taverns</b>\n<b>Cause:</b> <i>{reason}</i>',
        'gban.undone': '<tg-emoji emoji-id="5870948572526022116">👋🏻</tg-emoji> <b><a href="{url}">{name}</a> is welcomed back in {count} taverns</b>',
        'gban.chats': '\n{chats}',
        'gban.pm_blocked': '\n<tg-emoji emoji-id="5872988737826197458">🚫</tg-emoji> <b>Barred in private</b>',
        'gban.pm_unblocked': '\n<tg-emoji emoji-id="5870948572526022116">👋🏻</tg-emoji> <b>Welcomed in private</b>',
        'gban.pm_failed': '\n<tg-emoji emoji-id="5870704313440932932">🔓</tg-emoji> <b>Couldn\'t bar them in private</b>',
        'gban.pm_cleared': ' · <b>private log burned</b>',
        'chatinfo': '<tg-emoji emoji-id="5870704313440932932">🔒</tg-emoji><b> Kind: {type_of}\n</b><tg-emoji emoji-id="5870495350397079101">#️⃣</tg-emoji><b> Tavern number: </b><code>{id}</code><b>\n</b><tg-emoji emoji-id="5873225338984599714">🔥</tg-emoji><b> Name: {title}\n\n</b><tg-emoji emoji-id="5870676941614354370">🖋</tg-emoji><b> Word: {about}\n\n</b><tg-emoji emoji-id="5870684638195748414">👑</tg-emoji><b> Quartermasters: {admins_count}\n</b><tg-emoji emoji-id="5870633910337015697">✅</tg-emoji><b> On deck: {online_count}\n</b><tg-emoji emoji-id="5870994129244131212">👤</tg-emoji><b> Hands: {participants_count}\n</b><tg-emoji emoji-id="5872988737826197458">🚫</tg-emoji><b> Cast off: {kicked_count}\n</b><tg-emoji emoji-id="5870892901159932239">🔀</tg-emoji><b> Waiting pleas: {requests_pending}\n\n</b><tg-emoji emoji-id="5870729937215819584">🕐</tg-emoji><b> Slow bell: {slowmode_seconds}\n</b><tg-emoji emoji-id="5872980989705196227">📞</tg-emoji><b> Hail: {call}\n</b><tg-emoji emoji-id="5870875489362513438">🗑</tg-emoji><b> TTL: {ttl_period}\n</b><tg-emoji emoji-id="5870994129244131212">👤</tg-emoji><b> Late pleaders: {recent_requesters}\n\n</b><tg-emoji emoji-id="5870772616305839506">👥</tg-emoji><b> Sister tavern: {linked_chat_id}\n</b><tg-emoji emoji-id="5870704313440932932">🛡</tg-emoji><b> Rat-watch: {antispam}\n</b><tg-emoji emoji-id="5870542612217204751">👁</tg-emoji><b> Hands hidden: {participants_hidden}\n\n</b><tg-emoji emoji-id="5870527201874546272">🔗</tg-emoji><b> Line: {link}</b>',
        'userinfo': '<blockquote><tg-emoji emoji-id="5870495350397079101">#️⃣</tg-emoji><b> ID: {user_id}\n</b><tg-emoji emoji-id="5873225338984599714">🔥</tg-emoji><b> Given name: {first_name}\n</b><tg-emoji emoji-id="5873225338984599714">🔥</tg-emoji><b> Family name: {last_name}\n</b><tg-emoji emoji-id="5872980989705196227">📞</tg-emoji><b> Speaking tube: {phone}\n</b><tg-emoji emoji-id="5870998024779468554">🐶</tg-emoji><b> Usernames: {usernames}</b></blockquote><b>\n</b><blockquote><tg-emoji emoji-id="5870609858520158157">ℹ️</tg-emoji><b> Word: {about}</b></blockquote><b>\n</b><blockquote><tg-emoji emoji-id="5870729937215819584">🕐</tg-emoji><b> Watches: </b>{business_work_hours}\n<tg-emoji emoji-id="5870450871715761518">❤️</tg-emoji><b> Mark: {emoji_status}</b></blockquote><b>\n</b><blockquote><tg-emoji emoji-id="5870693687691841267">🔉</tg-emoji><b> Signal flag: {personal_channel}\n</b><tg-emoji emoji-id="5870847962917113498">🎂</tg-emoji><b> Birth watch: {birthday}\n</b><tg-emoji emoji-id="5870478797593120516">🎁</tg-emoji><b> Treasures: {stargifts_count}</b></blockquote><b>\n</b><blockquote><tg-emoji emoji-id="5870931487146119264">🚨</tg-emoji><b> Shared taverns: {common_chats_count}\n</b><tg-emoji emoji-id="5870772616305839506">👥</tg-emoji><b> Common taverns: {common_chats}</b></blockquote>',
        'promote.no_rights': '<tg-emoji emoji-id="5870704313440932932">🔓</tg-emoji> <b>Ye lack the leave to raise or strike an officer.</b>',
        'promote.no_user': '<tg-emoji emoji-id="5870994129244131212">👤</tg-emoji> <b>Name a hand.</b>\nAnswer a dispatch, or give a name or number.',
        'promote.demoted': '<tg-emoji emoji-id="5870948572526022116">👋🏻</tg-emoji> <b>{name}</b> [<code>{user_id}</code>] <b>is an officer no more.</b>',
        'promote.promoted_full': '<tg-emoji emoji-id="5870684638195748414">👑</tg-emoji> <b>{name}</b> [<code>{user_id}</code>] <b>is raised with every right of the ship.</b>\n<b>Rank:</b> {rank}',
        'promote.promoted': '<tg-emoji emoji-id="5870684638195748414">👑</tg-emoji> <b>{name}</b> [<code>{user_id}</code>] <b>is raised to officer.</b>\n<b>Rank:</b> {rank}',
        'promote.choose': '<tg-emoji emoji-id="5870684638195748414">👑</tg-emoji> <b>Officer rights for {name}</b> [<code>{user_id}</code>]\n<b>Rank:</b> {rank}',
        'promote.confirm': 'Aye',
        'promote.default_rank': 'Mate',
        'promote.tag_group_only': '<tg-emoji emoji-id="5870931487146119264">⚠️</tg-emoji> <b>Crew marks only hold aboard a crew, not a signal flag.</b>',
        'promote.tag_usage': '<b>How:</b> <code>{prefix}settag @user mark</code> or answer with <code>{prefix}settag mark</code>. No mark or <code>-</code> strikes it.',
        'promote.tag_invalid': '<tg-emoji emoji-id="5870657884844462243">❌</tg-emoji> <b>A crew mark is 16 letters at most, and no fancy marks.</b>',
        'promote.tag_no_rights': '<tg-emoji emoji-id="5870704313440932932">🔓</tg-emoji> <b>To mark another hand, ye need leave to manage crew marks.</b>',
        'promote.tag_updated': '<tg-emoji emoji-id="5870676941614354370">🖋</tg-emoji> <b>Crew mark of {name}:</b> <code>{rank}</code>',
        'promote.tag_removed': '<tg-emoji emoji-id="5255831443816327915">🗑</tg-emoji> <b>Crew mark of {name} struck.</b>',
        'promote.rpc_error': '<tg-emoji emoji-id="5870657884844462243">❌</tg-emoji> <b>The sea spat back:</b> <code>{error}</code>',
        'promote.right.change_info': '{emoji} Change {where} word',
        'promote.right.post_messages': '{emoji} Post dispatches',
        'promote.right.edit_messages': '{emoji} Amend posts',
        'promote.right.delete_messages': '{emoji} Burn messages',
        'promote.right.ban_users': '{emoji} Clap hands in irons',
        'promote.right.invite_users': '{emoji} Invite hands',
        'promote.right.pin_messages': '{emoji} Nail messages',
        'promote.right.add_admins': '{emoji} Raise officers',
        'promote.right.anonymous': '{emoji} Nameless',
        'promote.right.manage_call': '{emoji} Manage hails',
        'promote.right.manage_topics': '{emoji} Manage topics',
        'promote.right.post_stories': '{emoji} Post tales',
        'promote.right.edit_stories': '{emoji} Amend tales',
        'promote.right.delete_stories': '{emoji} Burn tales',
        'promote.right.manage_direct_messages': '{emoji} Manage private hails',
        'promote.right.manage_ranks': '{emoji} Manage crew marks',
        'promote.right.manage_linked_peers': '{emoji} Manage sister taverns',
        'promote.right.manage_welcome_messages': '{emoji} Manage welcomes',
        'promote.right.other': '{emoji} Other rights',
        'chat.not_channel': '<tg-emoji emoji-id="5870693687691841267">📣</tg-emoji> <b>That be for supergroups and channels only, mate.</b>',
        'chat.no_rights': '<tg-emoji emoji-id="5870704313440932932">🔓</tg-emoji> <b>Ye lack the rights to change this tavern.</b>',
        'chat.usage.slow': '<b>How:</b> <code>{prefix}slow</code> off, or <code>30</code>, <code>1m</code>, <code>5m</code>, <code>1h</code>.',
        'chat.usage.about': '<b>How:</b> <code>{prefix}setabout text</code>. <code>-</code> strikes it.',
        'chat.usage.photo': '<b>How:</b> answer a portrait with <code>{prefix}setphoto</code>. <code>-</code> strikes it.',
        'chat.usage.username': '<b>How:</b> <code>{prefix}setusername name</code>. <code>-</code> strikes it.',
        'chat.usage.link': '<b>How:</b> <code>{prefix}link</code>, <code>new</code>, <code>revoke</code>, or a <code>title</code>.',
        'chat.slow_off': '<tg-emoji emoji-id="5870729937215819584">🕐</tg-emoji> <b>Slow tide be off.</b>',
        'chat.slow_on': '<tg-emoji emoji-id="5870729937215819584">🕐</tg-emoji> <b>Slow tide:</b> <code>{seconds}</code>s',
        'chat.about_set': '<tg-emoji emoji-id="5870676941614354370">🖋</tg-emoji> <b>The tale be updated.</b>',
        'chat.about_cleared': '<tg-emoji emoji-id="5255831443816327915">🗑</tg-emoji> <b>The tale be struck.</b>',
        'chat.photo_set': '<tg-emoji emoji-id="5870782662234346251">🖼️</tg-emoji> <b>The tavern portrait be updated.</b>',
        'chat.photo_cleared': '<tg-emoji emoji-id="5255831443816327915">🗑</tg-emoji> <b>The tavern portrait be struck.</b>',
        'chat.username_set': '<tg-emoji emoji-id="5870527201874546272">🔗</tg-emoji> <b>Name:</b> @{username}',
        'chat.username_cleared': '<tg-emoji emoji-id="5255831443816327915">🗑</tg-emoji> <b>The name be struck.</b>',
        'chat.sign_on': '<tg-emoji emoji-id="5870676941614354370">🖋</tg-emoji> <b>Crew signatures be on.</b>',
        'chat.sign_off': '<tg-emoji emoji-id="5870676941614354370">🖋</tg-emoji> <b>Crew signatures be off.</b>',
        'chat.forum_on': '<tg-emoji emoji-id="5872886929921413168">💬</tg-emoji> <b>Topics be on.</b>',
        'chat.forum_off': '<tg-emoji emoji-id="5872886929921413168">💬</tg-emoji> <b>Topics be off.</b>',
        'chat.spam_on': '<tg-emoji emoji-id="5870704313440932932">🛡</tg-emoji> <b>The hard antispam be on.</b>',
        'chat.spam_off': '<tg-emoji emoji-id="5870704313440932932">🛡</tg-emoji> <b>The hard antispam be off.</b>',
        'chat.hidden_on': '<tg-emoji emoji-id="5870542612217204751">👁</tg-emoji> <b>The crew list be hidden.</b>',
        'chat.hidden_off': '<tg-emoji emoji-id="5870542612217204751">👁</tg-emoji> <b>The crew list be visible.</b>',
        'chat.history_on': '<tg-emoji emoji-id="5870729937215819584">🕐</tg-emoji> <b>New hands can see the log.</b>',
        'chat.history_off': '<tg-emoji emoji-id="5870729937215819584">🕐</tg-emoji> <b>The log be hidden from new hands.</b>',
        'chat.join_on': '<tg-emoji emoji-id="5870892901159932239">🔀</tg-emoji> <b>Join requests be on.</b>',
        'chat.join_off': '<tg-emoji emoji-id="5870892901159932239">🔀</tg-emoji> <b>Join requests be off.</b>',
        'chat.link_none': '<tg-emoji emoji-id="5870527201874546272">🔗</tg-emoji> <b>No invite yet, mate.</b>',
        'chat.link': '<tg-emoji emoji-id="5870527201874546272">🔗</tg-emoji> <b>Invite:</b> {link}',
        'chat.link_revoked': '<tg-emoji emoji-id="5255831443816327915">🗑</tg-emoji> <b>Invite struck.</b>\n<tg-emoji emoji-id="5870527201874546272">🔗</tg-emoji> <b>New:</b> {link}',
        'chat.link_created': '<tg-emoji emoji-id="5870633910337015697">✅</tg-emoji> <b>Invite forged.</b>\n<tg-emoji emoji-id="5870527201874546272">🔗</tg-emoji> {link}',
        'rights.header': '<tg-emoji emoji-id="5870684638195748414">👑</tg-emoji> <b>{name}</b> [<code>{user_id}</code>]\n<b>Role:</b> {role}\n<b>Rank:</b> {rank}',
        'rights.owner': 'Captain',
        'rights.admin': 'Officer',
        'rights.member': 'Hand',
        'rights.none': '<tg-emoji emoji-id="5870657884844462243">✖️</tg-emoji> <b>{name}</b> [<code>{user_id}</code>] <b>be no officer.</b>',
        'rights.empty': '<i>No rights aboard.</i>',
    }

    async def __get_raw_data(self, m: Message) -> typing.Union[tuple, None, Message]:
        """
        Get the target, timespan and reason from the message.
        :param m: The message object.
        :return: The chat and user objects.
        """
        prefix = rf"{self.get_prefix()}"

        if prefix in QUANTIFIERS:
            prefix = rf"\{prefix}"

        data = sub(rf"{prefix}[a-z]+", "", m.raw_text, 1)
        data = data.split("\n", maxsplit=1)
        punishment = data[0].strip()
        reason = data[1].strip() if len(data) > 1 else ""

        args = punishment.split()
        reply = await m.get_reply_message()

        match (bool(args), bool(m.is_reply)):
            case (True, _):
                if findall(r"@([0-9]{5,12})|([a-zA-Z][a-zA-Z0-9_]{4,31})", args[0]):
                    value = args[0]

                    if value[1:].isnumeric():
                        value = int(value[1:])

                    try:
                        user = await self.client.get_entity(value)
                    except ValueError:
                        return await utils.answer(m, self.strings["error.locate_user"])
                    args = args[1:]

                elif findall(r"@([0-9]{5,12})|([a-zA-Z][a-zA-Z0-9_]{4,31})", args[-1]):
                    value = args[-1]

                    if value[1:].isnumeric():
                        value = int(value[1:])

                    try:
                        user = await self.client.get_entity(value)
                    except ValueError:
                        return await utils.answer(m, self.strings["error.locate_user"])
                    args = args[:-1]

                elif m.is_reply:
                    if isinstance((await m.get_reply_message()), MessageService):
                        return await utils.answer(m, self.strings["error.reply_is_service"])
                    user = await (await m.get_reply_message()).get_sender()

                else:
                    return await utils.answer(m, self.strings["error.no_args.user"])

            case (False, True):
                if isinstance((await m.get_reply_message()), MessageService):
                    return await utils.answer(m, self.strings["error.reply_is_service"])
                user = await (await m.get_reply_message()).get_sender()

                return (
                    user,
                    convert_timespan(self.config["default_ptime"]),
                    reason,
                    [],
                    reply,
                )

            case _:
                return await utils.answer(m, self.strings["error.no_args.user"])

        if user.id == self.tg_id:
            return await utils.answer(m, self.strings["error.self"])

        args_filtered = []
        leftovers = []

        for arg in args:
            if fullmatch(r"[0-9]*[c-z]", arg):
                args_filtered.append(arg)
            else:
                leftovers.append(arg)

        args = " ".join(args_filtered)
        leftovers = " ".join(leftovers)
        timespan = (
            convert_timespan(args)
            if args_filtered
            else convert_timespan(self.config["default_ptime"])
        )
        return user, timespan, reason, leftovers, reply

    def identify(
        self,
        source: typing.Union[Message, User, Channel],
        markup: bool = True,
        return_id: bool = True,
    ) -> str:
        """
        Return sender's full name/channel name/standard value for deleted account
        :param m: The message object.
        :param markup: Whether to return the name with markup.
        :param return_id: Whether to return the ID.
        :return: The name.
        """
        result = ""

        if isinstance(source, Message):
            source = source.sender

        match source:
            case Channel():
                if markup:
                    result += f"<code>{es(source.title)}</code>"
                else:
                    result += source.title

            case _ if source.deleted:
                if markup:
                    result += f'<b>{self.strings["sys.DA"]}</b>'
                else:
                    result += self.strings["sys.DA"]

            case _:
                if markup:
                    result += f'<code>{es(source.first_name)}{(" " + es(source.last_name)) if source.last_name else ""}</code>'
                else:
                    result += f'{source.first_name}{(" " + source.last_name) if source.last_name else ""}'

        if return_id:
            if markup:
                result += f" [<code>{source.id}</code>]"
            else:
                result += f" [{source.id}]"

        return result

    async def invite_user(self, message, chat, user):
        try:
            await self._client(
                channels.InviteToChannelRequest(channel=chat, users=[user])
            )
        except Exception as e:
            return await utils.answer(
                message,
                self.strings["error"].format(error=str(e)),
            )
        await utils.answer(
            message,
            self.strings["user_invited"].format(user=user.first_name, id=user.id),
        )
        await asyncio.sleep(3)
        return None

    def _chat_label(self, chat) -> str:
        if chat is None:
            return ""
        if isinstance(chat, str):
            return chat
        title = getattr(chat, "title", None) or getattr(chat, "username", None)
        chat_id = getattr(chat, "id", None)
        if not title:
            title = str(chat_id) if chat_id else "?"
        link = utils.get_entity_url(chat)
        if not link and chat_id:
            link = f"https://t.me/c/{chat_id}"
        title = es(str(title))
        return f'<a href="{link}">{title}</a>' if link else f"<b>{title}</b>"

    def _restriction_span(self, rights) -> str:
        until = getattr(rights, "until_date", None)
        if not until:
            return self.strings["sys.forever"]
        if until.tzinfo is None:
            until = until.replace(tzinfo=timezone.utc)
        left = until - datetime.now(timezone.utc)
        if left >= timedelta(days=365) or left.total_seconds() <= 0:
            return self.strings["sys.forever"]
        return self._span(left)

    @staticmethod
    def _until_stamp(rights) -> int:
        until = getattr(rights, "until_date", None)
        if not until:
            return 0
        if until.tzinfo is None:
            until = until.replace(tzinfo=timezone.utc)
        return int(until.timestamp())

    @staticmethod
    def _rights_signature(rights) -> tuple:
        if rights is None:
            return ()
        return tuple(
            sorted(
                (name, bool(getattr(rights, name, False)))
                for name in _CHAT_BANNED_RIGHT_FIELDS
                if name != "until_date"
            )
        )

    def _classify_restriction(self, prev, new):
        if not isinstance(new, ChannelParticipantBanned):
            if isinstance(prev, ChannelParticipantBanned):
                rights = prev.banned_rights
                if getattr(rights, "view_messages", None):
                    return "act.unban", ""
                if getattr(rights, "send_messages", None):
                    return "act.unmute", ""
                return "act.allowmedia", ""
            return None

        rights = new.banned_rights
        prev_rights = (
            prev.banned_rights if isinstance(prev, ChannelParticipantBanned) else None
        )
        match (
            bool(getattr(rights, "view_messages", None)),
            bool(getattr(rights, "send_messages", None)),
            bool(getattr(new, "left", None)),
        ):
            case (True, _, True):
                return "act.kick", ""
            case (True, _, _):
                kind, span = "act.ban", self._restriction_span(rights)
            case (False, True, _):
                kind, span = "act.mute", self._restriction_span(rights)
            case _:
                kind, span = "act.nomedia", self._restriction_span(rights)

        # Same restriction kind is still an edit when the term or rights change.
        if prev_rights is not None and (
            self._until_stamp(prev_rights) != self._until_stamp(rights)
            or self._rights_signature(prev_rights) != self._rights_signature(rights)
        ):
            return "act.rights", span
        return kind, span

    async def _log_entity(self, entities: dict, peer_id: int):
        entity = entities.get(peer_id)
        if entity is None:
            try:
                entity = await self.client.get_entity(peer_id)
            except Exception:
                return None
        return entity

    async def log_action(
        self, admin, user, punishment, reason="", time="", chat=None
    ):
        if not getattr(self, "asset_channel", None) or not getattr(
            self, "_log_topic", None
        ):
            return

        try:
            if isinstance(admin, str):
                admin_str = admin
            else:
                admin_str = self.identify(admin)
            user_str = user if isinstance(user, str) else self.identify(user)
            reason_str = (
                self.strings["log_reason"].format(reason=es(reason)) if reason else ""
            )
            time_str = self.strings["log_time"].format(time=time) if time else ""
            chat_str = (
                self.strings["log_chat"].format(chat=self._chat_label(chat))
                if chat
                else ""
            )

            text = self.strings["log_text"].format(
                user=user_str,
                admin=admin_str,
                punishment=punishment,
                reason=reason_str,
                time=time_str,
                chat=chat_str,
            )
            peer = int(f"-100{self.asset_channel}")
            try:
                await self.inline.bot.send_message(
                    peer,
                    text,
                    disable_web_page_preview=True,
                    message_thread_id=self._log_topic.id,
                )
            except errors.DocumentInvalidError:
                # Bot without a Fragment username can't attach custom emoji.
                await self.client.send_message(
                    peer,
                    text,
                    parse_mode="HTML",
                    link_preview=False,
                    reply_to=self._log_topic.id,
                )
        except Exception as e:
            log.error(f"Helm log failed: {e}")

    async def _refresh_admin_chats(self):
        chats = []
        async for dialog in self.client.iter_dialogs():
            entity = dialog.entity
            if not isinstance(entity, Channel) or not entity.megagroup:
                continue
            rights = entity.admin_rights
            if entity.creator or (rights and rights.ban_users):
                chats.append(entity.id)
        self._admin_chats = chats

    @loader.loop(interval=45, autostart=False)
    async def modlog(self):
        if not self.config["global_logs"]:
            return
        if not self._admin_chats or not getattr(self, "_log_cursors", None):
            await self._refresh_admin_chats()
            self._log_cursors = True

        cursors = self.get("log_cursors", {})
        seen = self.get("log_seen", [])

        for chat_id in list(self._admin_chats):
            try:
                await self._scan_chat_log(chat_id, cursors, seen)
            except Exception as e:
                log.error(f"Helm admin log failed in {chat_id}: {e}")

        if cursors != self.get("log_cursors", {}) or seen != self.get("log_seen", []):
            self.set("log_cursors", cursors)
            self.set("log_seen", seen[-400:])

    async def _scan_chat_log(self, chat_id, cursors, seen):
        key = str(chat_id)
        max_id = int(cursors.get(key, 0))
        result = await self.client(
            channels.GetAdminLogRequest(
                channel=chat_id,
                q="",
                max_id=0,
                min_id=max_id,
                limit=50,
                events_filter=ChannelAdminLogEventsFilter(
                    ban=True, unban=True, kick=True
                ),
            )
        )

        entities = {item.id: item for item in (*result.users, *result.chats)}
        chat = await self._log_entity(entities, chat_id)
        fresh = []
        for event in result.events:
            if event.id > max_id:
                max_id = event.id
            if f"{chat_id}:{event.id}" in seen:
                continue
            action = event.action
            if not isinstance(action, ChannelAdminLogEventActionParticipantToggleBan):
                continue
            target_id = action_user_id(action.new_participant) or action_user_id(
                action.prev_participant
            )
            if not target_id:
                continue
            classified = self._classify_restriction(
                action.prev_participant, action.new_participant
            )
            if not classified:
                continue
            fresh.append((event, classified, target_id))

        cursors[key] = max_id
        for event, (act_key, span), target_id in reversed(fresh):
            mark = f"{chat_id}:{event.id}"
            if mark in seen or event.user_id == self._me_id:
                seen.append(mark)
                continue
            admin = await self._log_entity(entities, event.user_id)
            user = await self._log_entity(entities, target_id)
            await self.log_action(
                admin or f"<code>{event.user_id}</code>",
                user or f"<code>{target_id}</code>",
                self.strings[act_key],
                time=span,
                chat=chat,
            )
            seen.append(mark)

    async def mutecmd(self, m: Message):
        """
        /mute [username | ID | reply] [time]
        [reason]
        Mute a user for a specified time (sr Abbr:. `r1`). Add `del`, `delete` after time to delete the message.
        """
        if not isinstance(m.input_chat, (InputPeerChannel, InputPeerChat)):
            return await utils.answer(m, self.strings["error.wrongchattype.pm"])

        if m.chat.default_banned_rights is None:
            return await utils.answer(m, self.strings["error.wrongchattype.channel"])

        try:
            user, timespan, reason, ifdel, r = await self.__get_raw_data(m)
        except ValueError:
            return
        except TypeError:
            return

        if ifdel in ["del", "delete"] and r:
            if not isinstance(r, MessageService):
                await r.delete()

        try:
            await edit_permissions(
                self.client,
                m.chat.id,
                user.id,
                timespan,
                **seq_rights("1", inv=True),
            )
        except ChatAdminRequiredError:
            return await utils.answer(m, self.strings["error.can_not_restrict"])
        except UserAdminInvalidError:
            return await utils.answer(m, self.strings["error.can_not_restrict"])

        userstring = self.identify(user)

        time_str = self._span(timespan)
        await self.log_action(
            m.sender, user, self.strings["act.mute"], reason, time_str, m.chat
        )

        if timespan >= timedelta(days=365):
            return await utils.answer(
                m,
                self.strings["done.muted.f"].format(user=userstring)
                + (self.strings["reason"].format(reason) if reason else ""),
            )

        await utils.answer(
            m,
            self.strings["done.muted"].format(
                user=userstring,
                timespan=self._span(timespan),
            )
            + (self.strings["reason"].format(reason) if reason else ""),
        )

    @loader.command
    async def owner(self, message):
        """Shows the list of chats, channels and groups where you are an admin/owner"""
        count = 0
        msg = ""
        await utils.answer(message, self.strings["loading"])
        async for dialog in self._client.iter_dialogs():
            if dialog.is_channel or dialog.is_group:
                chat = await self._client.get_entity(dialog.id)
                if chat.admin_rights or chat.creator:
                    count += 1
                    chat_type = (
                        self.strings["of_chat"]
                        if dialog.is_group
                        else self.strings["of_channel"]
                    )
                    msg += f"• {chat.title} <b>({chat_type})</b> | <code>{chat.id}</code>\n"

        if msg:
            await utils.answer(
                message,
                f"<blockquote expandable><b>{self.strings['own_list'].format(count=count, msg=msg)}</b></blockquote>",
                parse_mode="html",
            )
        else:
            await utils.answer(message, self.strings["no_ownerships", message])

    @loader.command()
    async def admins(self, message):
        """Shows the admins in the chat/channel"""
        if message.is_private:
            return await utils.answer(message, self.strings["not_a_chat"])
        chat = await message.get_chat()
        title = chat.title
        admins = await self._client.get_participants(
            message.chat_id, filter=types.ChannelParticipantsAdmins()
        )
        real_members = [
            member for member in admins if not member.bot and not member.deleted
        ]
        admins_header = self.strings["admins_in_chat"].format(
            title=title, count=len(real_members)
        )
        if len(real_members) == 0:
            return await utils.answer(message, self.strings["no_admins_in_chat"])
        for user in real_members:
            if not user.deleted:
                admins_header += f'<tg-emoji emoji-id="5870657884844462243">❌</tg-emoji> <a href="tg://user?id={user.id}">{user.first_name}</a> | <code>{user.id}</code>\n'
        try:
            await utils.answer(
                message,
                f"<blockquote expandable><b>{admins_header}</b></blockquote>",
            )
        except errors.MessageTooLongError:
            await utils.answer(message, self.strings["too_many_admins"])
            file = io.BytesIO(admins_header.encode())
            file.name = "admins.md"
            await message.client.send_file(
                message.chat_id,
                file,
                caption=self.strings["admins_in_chat_caption"].format(title),
                reply_to=message.id,
            )
            await message.delete()
        except Exception as e:
            return await utils.answer(message, self.strings["error"].format(error=str(e)))

    @loader.command(
        ru_doc="Показывает ботов в группе/канале",
        jp_doc="グループ・チャンネルのボットを表示する",
    )
    async def bots(self, message):
        """Shows the bots in the chat/channel"""
        if message.is_private:
            return await utils.answer(message, self.strings["not_a_chat"])
        chat = await message.get_chat()
        title = chat.title
        bots = await self._client.get_participants(
            message.chat_id, filter=types.ChannelParticipantsBots()
        )
        bots_header = self.strings["bots_in_chat"].format(title=title, count=len(bots))
        if len(bots) == 0:
            return await utils.answer(message, self.strings["no_bots_in_chat"])
        for user in bots:
            if not user.deleted:
                bots_header += f'<tg-emoji emoji-id="5870657884844462243">❌</tg-emoji> <a href="tg://user?id={user.id}">{user.first_name}</a> | <code>{user.id}</code>\n'
        try:
            await utils.answer(
                message, f"<blockquote expandable><b>{bots_header}</b></blockquote>"
            )
        except errors.MessageTooLongError:
            await utils.answer(message, self.strings["too_many_bots"])
            file = io.BytesIO(bots_header.encode())
            file.name = "bots.md"
            await message.client.send_file(
                message.chat_id,
                file,
                caption=self.strings["bots_in_chat_caption"].format(title),
                reply_to=message.id,
            )
            await message.delete()
        except Exception as e:
            return await utils.answer(
                message, self.strings["error"].format(error=str(e))
            )

    @loader.command(
        ru_doc="Показывает простых участников чата/канала",
        jp_doc="グループ・チャンネルのユーザーを表示する",
    )
    async def users(self, message):
        """Shows the users in the chat/channel"""
        if message.is_private:
            return await utils.answer(message, self.strings["not_a_chat"])
        chat = await message.get_chat()
        title = chat.title
        users = await self._client.get_participants(message.chat_id)
        real_users = [
            member for member in users if not member.bot and not member.deleted
        ]
        users_header = self.strings["users_in_chat"].format(
            title=title, count=len(real_users)
        )
        if len(real_users) == 0:
            return await utils.answer(message, self.strings["no_user_in_chat"])
        for user in users:
            if not user.bot and not user.deleted:
                users_header += f'<tg-emoji emoji-id="5870994129244131212">👤</tg-emoji> <a href ="tg://user?id={user.id}">{user.first_name}</a> | <code>{user.id}</code>\n'
        try:
            await utils.answer(
                message, f"<blockquote expandable><b>{users_header}</b></blockquote>"
            )
            return
        except errors.MessageTooLongError:
            await utils.answer(message, self.strings["too_many_users"])
            file = io.BytesIO(users_header.encode())
            file.name = "users.md"
            await message.client.send_file(
                message.chat_id,
                file,
                caption=self.strings["users_in_chat_caption"].format(title),
                reply_to=message.id,
            )
            await message.delete()
            return
        except Exception as e:
            return await utils.answer(
                message, self.strings["error"].format(error=str(e))
            )

    @loader.command(
        ru_doc="Закрыть чат для всех кроме админов",
        jp_doc="チャットを管理者以外のユーザーに限定して閉じる",
    )
    async def mc(self, message):
        """Mute the chat for everyone except admins"""
        if message.is_private:
            return await utils.answer(message, self.strings["not_a_chat"])
        chat = await message.get_chat()
        current = chat.default_banned_rights
        is_muted = current.send_messages is True
        try:
            await self._client(
                messages.EditChatDefaultBannedRightsRequest(
                    chat,
                    _make_chat_banned_rights(
                        until_date=0,
                        send_messages=not is_muted,
                        send_plain=not is_muted,
                    ),
                )
            )
        except Exception as e:
            return await utils.answer(
                message, self.strings["error"].format(error=str(e))
            )
        if is_muted:
            return await utils.answer(message, self.strings["chat_unmuted"])
        else:
            return await utils.answer(message, self.strings["chat_muted"])

    @loader.command(
        ru_doc="Переименовать группу/канал",
        jp_doc="グループ・チャンネルの名前を変更する",
    )
    async def rename(self, message):
        """Rename the chat/channel"""
        if message.is_private:
            return await utils.answer(message, self.strings["not_a_chat"])
        chat = await message.get_chat()
        old_title = chat.title
        new_title = utils.get_args_raw(message)
        if message.is_channel:
            if message.is_group:
                type_of = self.strings["of_chat"]
            else:
                type_of = self.strings["of_channel"]
            try:
                await self._client(
                    channels.EditTitleRequest(channel=chat, title=new_title)
                )
            except Exception as e:
                return await utils.answer(
                    message, self.strings["error"].format(error=str(e))
                )
        else:
            type_of = self.strings["of_chat"]
            try:
                await self._client(
                    messages.EditChatTitleRequest(chat_id=chat.id, title=new_title)
                )
            except Exception as e:
                return await utils.answer(
                    message, self.strings["error"].format(error=str(e))
                )
        return await utils.answer(
            message,
            self.strings["title_changed"].format(
                old_title=old_title, new_title=new_title, type_of=type_of
            ),
        )

    @staticmethod
    def _split_ttl(parts: list) -> tuple:
        if len(parts) >= 2 and fullmatch(r"\d+[ywdhms]", parts[-1].lower()):
            return parts[:-1], parts[-1].lower()
        return parts, ""

    def _schedule_temp_chat(self, chat_id: int, delete_at: float):
        old = self._temp_tasks.pop(chat_id, None)
        if old and not old.done():
            old.cancel()
        self._temp_tasks[chat_id] = asyncio.get_running_loop().create_task(
            self._expire_temp_chat(chat_id, delete_at)
        )

    async def _resume_temp_chats(self):
        for chat_id, delete_at in list(self.get("temp_chats", {}).items()):
            try:
                self._schedule_temp_chat(int(chat_id), float(delete_at))
            except (TypeError, ValueError):
                continue

    async def _expire_temp_chat(self, chat_id: int, delete_at: float):
        try:
            delay = delete_at - time.time()
            if delay > 0:
                await asyncio.sleep(delay)
            try:
                await self.client(channels.DeleteChannelRequest(chat_id))
            except Exception as e:
                log.error(f"Helm temp chat delete failed: {e}")
            pending = self.get("temp_chats", {})
            pending.pop(str(chat_id), None)
            self.set("temp_chats", pending)
        except asyncio.CancelledError:
            return
        finally:
            current = self._temp_tasks.get(chat_id)
            if current is asyncio.current_task():
                self._temp_tasks.pop(chat_id, None)

    @loader.command(
        ru_doc="[g/c] [название] [срок] — создать группу/канал. Срок в конце: 30m, 2h, 1d",
        jp_doc="[g/c] [名前] [期限] — グループ・チャンネルを作成。末尾に 30m、2h、1d",
    )
    async def create(self, message):
        """[g/c] [title] [time] - Create a group or channel. A trailing span like 30m, 2h or 1d deletes it later."""
        args = utils.get_args(message)
        if len(args) < 2 or args[0] not in ("g", "c"):
            return await utils.answer(message, self.strings["error.invalid_args"])

        title_parts, ttl = self._split_ttl(args[1:])
        title = " ".join(title_parts).strip()
        if not title:
            return await utils.answer(message, self.strings["error.invalid_args"])

        timespan = None
        if ttl:
            try:
                timespan = convert_timespan(ttl)
            except ValueError:
                return await utils.answer(message, self.strings["error.invalid_args"])
            if timespan < timedelta(minutes=1):
                return await utils.answer(message, self.strings["error.invalid_args"])

        try:
            result = await self._client(
                channels.CreateChannelRequest(
                    title=title,
                    megagroup=args[0] == "g",
                    broadcast=args[0] == "c",
                    about="",
                )
            )
            chat = result.chats[0]
            invite_link = await self._client(
                messages.ExportChatInviteRequest(peer=chat.id, title="Invite link")
            )
        except Exception as e:
            return await utils.answer(
                message, self.strings["error"].format(error=str(e))
            )

        key = "group_created" if args[0] == "g" else "channel_created"
        text = self.strings[key].format(link=invite_link.link, title=es(title))
        if timespan:
            delete_at = time.time() + timespan.total_seconds()
            pending = self.get("temp_chats", {})
            pending[str(chat.id)] = delete_at
            self.set("temp_chats", pending)
            self._schedule_temp_chat(chat.id, delete_at)
            text += self.strings["temp_chat"].format(timespan=self._span(timespan))
        return await utils.answer(message, text)

    @loader.command(
        ru_doc="Пригласить пользователя в чат", jp_doc="ユーザーをチャットに招待する"
    )
    async def invite(self, message):
        """Invite a user to the chat"""
        chat = await message.get_chat()
        reply = await message.get_reply_message()
        args = utils.get_args(message)
        match (bool(reply), bool(args)):
            case (True, _):
                user = await self._client.get_entity(reply.sender_id)
                result = await self.invite_user(message, chat, user)
                if result:
                    return result
            case (False, True):
                for user in args:
                    entity = await self._client.get_entity(
                        int(user) if user.isdigit() else user
                    )
                    result = await self.invite_user(message, chat, entity)
                    if result:
                        return result
            case _:
                return await utils.answer(message, self.strings["error.no_user"])

    async def kickcmd(self, m: Message):
        """
        /kick [username | ID | reply]
        [reason]
        Kick a user from the chat so he can return later.  Add `del`, `delete` after command to delete the
        message.
        """
        if not isinstance(m.input_chat, (InputPeerChannel, InputPeerChat)):
            return await utils.answer(m, self.strings["error.wrongchattype.pm"])

        if m.chat.default_banned_rights is None:
            return await utils.answer(m, self.strings["error.wrongchattype.channel"])

        try:
            user, _, reason, ifdel, r = await self.__get_raw_data(m)
        except ValueError:
            return
        except TypeError:
            return

        if ifdel in ["del", "delete"] and r:
            if not isinstance(r, MessageService):
                await r.delete()

        try:
            await self.client.kick_participant(m.chat.id, user.id)
        except ChatAdminRequiredError:
            return await utils.answer(m, self.strings["error.can_not_restrict"])
        except UserAdminInvalidError:
            return await utils.answer(m, self.strings["error.can_not_restrict"])

        userstring = self.identify(user)

        await self.log_action(
            m.sender, user, self.strings["act.kick"], reason, chat=m.chat
        )

        await utils.answer(
            m,
            self.strings["done.kicked"].format(user=userstring)
            + (self.strings["reason"].format(reason) if reason else ""),
        )

    async def bancmd(self, m: Message):
        """
        /ban [username | ID | reply] [time]
        [reason]
        Ban a user from the chat (sr Abbr.: `r0`. The user won't be able to return until you unban him.  Add `del`,
        `delete` after time to delete the message.
        """
        if not isinstance(m.input_chat, (InputPeerChannel, InputPeerChat)):
            return await utils.answer(m, self.strings["error.wrongchattype.pm"])

        if m.chat.default_banned_rights is None:
            return await utils.answer(m, self.strings["error.wrongchattype.channel"])

        try:
            user, timespan, reason, ifdel, r = await self.__get_raw_data(m)
        except ValueError:
            return
        except TypeError:
            return

        if ifdel in ["del", "delete"] and r:
            if not isinstance(r, MessageService):
                await r.delete()

        try:
            await edit_permissions(
                self.client,
                m.chat.id,
                user.id,
                timespan,
                **seq_rights("0", inv=True),
            )
        except ChatAdminRequiredError:
            return await utils.answer(m, self.strings["error.can_not_restrict"])
        except UserAdminInvalidError:
            return await utils.answer(m, self.strings["error.can_not_restrict"])

        userstring = self.identify(user)

        time_str = (
            self._span(timespan)
        )
        await self.log_action(
            m.sender, user, self.strings["act.ban"], reason, time_str, m.chat
        )

        if timespan >= timedelta(days=365):
            return await utils.answer(
                m,
                self.strings["done.banned.f"].format(user=userstring)
                + (self.strings["reason"].format(reason) if reason else ""),
            )

        await utils.answer(
            m,
            self.strings["done.banned"].format(
                user=userstring,
                timespan=self._span(timespan),
            )
            + (self.strings["reason"].format(reason) if reason else ""),
        )

    async def warncmd(self, m: Message):
        """
        /warn [username | ID | reply]
        [reason]
        Warn a user. If the user has too many warns, he will be restricted (you can set settings in config). Add `del`,
        `delete` after time to delete the message.
        """
        if not isinstance(m.input_chat, (InputPeerChannel, InputPeerChat)):
            return await utils.answer(m, self.strings["error.wrongchattype.pm"])

        if m.chat.default_banned_rights is None:
            return await utils.answer(m, self.strings["error.wrongchattype.channel"])

        try:
            user, _, reason, ifdel, r = await self.__get_raw_data(m)
        except ValueError:
            return
        except TypeError:
            return

        if ifdel in ["del", "delete"] and r:
            if not isinstance(r, MessageService):
                await r.delete()

        warndict = self.get("warns", {})
        warns_chat = warndict.get(m.chat.id, {})

        if warns_chat == {}:
            warndict[m.chat.id] = warns_chat

        warns = warns_chat.get(user.id, 0)
        warns += 1

        warns_chat[user.id] = warns
        warndict[m.chat.id] = warns_chat

        userstring = self.identify(user)

        if warns >= self.config["warnlimit"]:
            warns_chat[user.id] = 0
            warndict[m.chat.id] = warns_chat
            self.set("warns", warndict)

            timespan = convert_timespan(self.config["wl_timespan"])
            time_str = self._span(timespan)
            act = (
                "act.mute"
                if self.config["wl_punishment"] == "mute"
                else "act.ban"
            )
            await self.log_action(
                m.sender,
                user,
                self.strings[act],
                reason or self.config["wl_reason"],
                time_str,
                m.chat,
            )

            if self.config["wl_punishment"] == "mute":
                await edit_permissions(
                    self.client,
                    m.chat.id,
                    user.id,
                    timespan,
                    **seq_rights("1", inv=True),
                )

                if timespan >= timedelta(days=365):
                    return await utils.answer(
                        m,
                        self.strings["done.muted.f"].format(user=userstring)
                        + (self.strings["reason"].format(reason) if reason else ""),
                    )

                return await utils.answer(
                    m,
                    self.strings["done.muted"].format(
                        user=userstring,
                        timespan=self._span(timespan),
                    )
                    + (self.strings["reason"].format(reason) if reason else ""),
                )

            await edit_permissions(
                self.client,
                m.chat.id,
                user.id,
                timespan,
                **seq_rights("0", inv=True),
            )

            if timespan >= timedelta(days=365):
                return await utils.answer(
                    m,
                    self.strings["done.banned.f"].format(user=userstring)
                    + (self.strings["reason"].format(reason) if reason else ""),
                )

            return await utils.answer(
                m,
                self.strings["done.banned"].format(
                    user=userstring,
                    timespan=self._span(timespan),
                )
                + (self.strings["reason"].format(reason) if reason else ""),
            )

        self.set("warns", warndict)

        await self.log_action(
            m.sender, user, self.strings["act.warn"], reason, chat=m.chat
        )

        await utils.answer(
            m,
            self.strings["done.warned"].format(user=userstring)
            + (self.strings["reason"].format(reason) if reason else ""),
        )

    async def srcmd(self, m: Message):
        """
        /sr [username | ID | reply] [rights] [time]
        [reason]
        Set rights for a user for a specified time.
        Rights are a sequence of numbers from 0 to b:
        0 - view_messages; 1 - send_messages; 2 - send_media; 3 - send_stickers; 4 - send_gifs; 5 - send_games;
        6 - send_inline; 7 - embed_link_previews; 8 - send_polls; 9 - change_info; a - invite_users; b - pin_messages.
        Prepend rights with `r` to restrict user from using such media. Add `del`, `delete` after time to
        delete the message.
        """
        if not isinstance(m.input_chat, (InputPeerChannel, InputPeerChat)):
            return await utils.answer(m, self.strings["error.wrongchattype.pm"])

        if m.chat.default_banned_rights is None:
            return await utils.answer(m, self.strings["error.wrongchattype.channel"])

        try:
            user, timespan, reason, rightsstring, r = await self.__get_raw_data(m)
        except TypeError:
            return
        except ValueError:
            return

        if " " in rightsstring and [
            x for x in rightsstring if x in ["d", "del", "delete"]
        ]:
            rightsseq = rightsstring.split(" ", 1)

            match (
                rightsseq[0] in ["d", "del", "delete"],
                rightsseq[1] in ["d", "del", "delete"],
            ):
                case (True, _):
                    ifdel = rightsseq[0]
                    rightsstring = rightsseq[1]
                case (False, True):
                    ifdel = rightsseq[1]
                    rightsstring = rightsseq[0]
                case _:
                    ifdel = ""
        else:
            ifdel = ""

        if ifdel in ["del", "delete"] and r:
            if not isinstance(r, MessageService):
                await r.delete()

        inverse = rightsstring.startswith("r")

        rights = seq_rights(rightsstring[1:] if inverse else rightsstring, inverse)

        if not rights:
            return await utils.answer(m, self.strings["error.no_args.rights"])

        match rightsstring:
            case "0":
                string = "unbanned"
            case "1":
                string = "unmuted"
            case "234567":
                string = "allowmedia"
            case "r0":
                string = "banned"
            case "r1":
                string = "muted"
            case "r234567":
                string = "nomedia"
            case _:
                string = "setrights"

        try:
            await edit_permissions(
                self.client,
                m.chat.id,
                user.id,
                timespan,
                **rights,
            )
        except ChatAdminRequiredError:
            return await utils.answer(m, self.strings["error.can_not_restrict"])
        except UserAdminInvalidError:
            return await utils.answer(m, self.strings["error.can_not_restrict"])

        userstring = self.identify(user)
        act = {
            "unbanned": "act.unban",
            "unmuted": "act.unmute",
            "allowmedia": "act.allowmedia",
            "banned": "act.ban",
            "muted": "act.mute",
            "nomedia": "act.nomedia",
        }.get(string, "act.rights")
        await self.log_action(
            m.sender,
            user,
            self.strings[act],
            reason,
            "" if timespan >= timedelta(days=365) else self._span(timespan),
            m.chat,
        )

        if timespan >= timedelta(days=365):
            return await utils.answer(
                m,
                self.strings[f"done.{string}.f"].format(
                    user=userstring, rights=rightsstring
                )
                + (self.strings["reason"].format(reason) if reason else ""),
            )

        await utils.answer(
            m,
            self.strings[f"done.{string}"].format(
                user=userstring,
                rights=rightsstring,
                timespan=self._span(timespan),
            )
            + (self.strings["reason"].format(reason) if reason else ""),
        )

    async def unmutecmd(self, m: Message):
        """
        /unmute [username | ID | reply]
        Unmute a user, so he'll be able to send messages again.
        """
        if not isinstance(m.input_chat, (InputPeerChannel, InputPeerChat)):
            return await utils.answer(m, self.strings["error.wrongchattype.pm"])

        if m.chat.default_banned_rights is None:
            return await utils.answer(m, self.strings["error.wrongchattype.channel"])

        try:
            user, _, reason, _, _ = await self.__get_raw_data(m)
        except ValueError:
            return
        except TypeError:
            return

        try:
            await edit_permissions(
                self.client,
                m.chat.id,
                user.id,
                None,
                **seq_rights("1"),
            )
        except ChatAdminRequiredError:
            return await utils.answer(m, self.strings["error.can_not_restrict"])
        except UserAdminInvalidError:
            return await utils.answer(m, self.strings["error.can_not_restrict"])

        userstring = self.identify(user)

        await self.log_action(
            m.sender, user, self.strings["act.unmute"], reason, chat=m.chat
        )

        await utils.answer(
            m,
            self.strings["done.unmuted"].format(user=userstring)
            + (self.strings["reason"].format(reason) if reason else ""),
        )

    async def unbancmd(self, m: Message):
        """
        /unban [username | ID | reply]
        Unban a user, so he'll be able to return to the chat.
        """
        if not isinstance(m.input_chat, (InputPeerChannel, InputPeerChat)):
            return await utils.answer(m, self.strings["error.wrongchattype.pm"])

        if m.chat.default_banned_rights is None:
            return await utils.answer(m, self.strings["error.wrongchattype.channel"])

        try:
            user, _, reason, _, _ = await self.__get_raw_data(m)
        except ValueError:
            return
        except TypeError:
            return

        try:
            await edit_permissions(
                self.client,
                m.chat.id,
                user.id,
                None,
                **seq_rights("0"),
            )
        except ChatAdminRequiredError:
            return await utils.answer(m, self.strings["error.can_not_restrict"])
        except UserAdminInvalidError:
            return await utils.answer(m, self.strings["error.can_not_restrict"])

        userstring = self.identify(user)

        await self.log_action(
            m.sender, user, self.strings["act.unban"], reason, chat=m.chat
        )

        await utils.answer(
            m,
            self.strings["done.unbanned"].format(user=userstring)
            + (self.strings["reason"].format(reason) if reason else ""),
        )

    async def unwarncmd(self, m: Message):
        """
        /unwarn [username | ID | reply] ['all']
        Remove a warn from a user. If 'all' is specified, all warns will be removed.
        """
        if not isinstance(m.input_chat, (InputPeerChannel, InputPeerChat)):
            return await utils.answer(m, self.strings["error.wrongchattype.pm"])

        if m.chat.default_banned_rights is None:
            return await utils.answer(m, self.strings["error.wrongchattype.channel"])

        try:
            user, _, _, if_all, _ = await self.__get_raw_data(m)
        except ValueError:
            return
        except TypeError:
            return

        warndict = self.get("warns", {})
        warns_chat = warndict.get(m.chat.id, {})

        if warns_chat == {}:
            warndict[m.chat.id] = warns_chat

        warns = warns_chat.get(user.id, 0)
        warns -= 1

        if warns < 0:
            warns = 0

        warns_chat[user.id] = warns
        warndict[m.chat.id] = warns_chat

        userstring = self.identify(user)

        if if_all in ["all", "все", "всё", "alle"]:
            warns_chat[user.id] = 0
            warndict[m.chat.id] = warns_chat
            self.set("warns", warndict)

            return await utils.answer(
                m, self.strings["done.unwarned.all"].format(user=userstring)
            )

        self.set("warns", warndict)

        if warns == 0:
            return await utils.answer(
                m, self.strings["done.unwarned.all"].format(user=userstring)
            )

        await utils.answer(m, self.strings["done.unwarned.one"].format(user=userstring))

    async def nomediacmd(self, m: Message):
        """
        /nomedia [username | ID | reply] [time]
        [reason]
        Restrict a user from sending all media types (sr Abbr.: `r234567`) for a specified time. Add `del`, `delete` or
        `d` after time to delete the message.
        """
        if not isinstance(m.input_chat, (InputPeerChannel, InputPeerChat)):
            return await utils.answer(m, self.strings["error.wrongchattype.pm"])

        if m.chat.default_banned_rights is None:
            return await utils.answer(m, self.strings["error.wrongchattype.channel"])

        try:
            user, timespan, reason, ifdel, r = await self.__get_raw_data(m)
        except ValueError:
            return
        except TypeError:
            return

        if ifdel in ["del", "delete"] and r:
            if not isinstance(r, MessageService):
                await r.delete()

        try:
            await edit_permissions(
                self.client,
                m.chat.id,
                user.id,
                timespan,
                **seq_rights("234567", inv=True),
            )
        except ChatAdminRequiredError:
            return await utils.answer(m, self.strings["error.can_not_restrict"])
        except UserAdminInvalidError:
            return await utils.answer(m, self.strings["error.can_not_restrict"])

        userstring = self.identify(user)

        await self.log_action(
            m.sender,
            user,
            self.strings["act.nomedia"],
            reason,
            self._span(timespan),
            m.chat,
        )

        if timespan >= timedelta(days=365):
            return await utils.answer(
                m,
                self.strings["done.nomedia.f"].format(user=userstring)
                + (self.strings["reason"].format(reason) if reason else ""),
            )

        await utils.answer(
            m,
            self.strings["done.nomedia"].format(
                user=userstring,
                timespan=self._span(timespan),
            )
            + (self.strings["reason"].format(reason) if reason else ""),
        )

    async def allowmediacmd(self, m: Message):
        """
        /allowmedia [username | ID | reply]
        Allow a user to send media again.
        """
        if not isinstance(m.input_chat, (InputPeerChannel, InputPeerChat)):
            return await utils.answer(m, self.strings["error.wrongchattype.pm"])

        if m.chat.default_banned_rights is None:
            return await utils.answer(m, self.strings["error.wrongchattype.channel"])

        try:
            user, _, reason, _, _ = await self.__get_raw_data(m)
        except ValueError:
            return
        except TypeError:
            return

        try:
            await edit_permissions(
                self.client,
                m.chat.id,
                user.id,
                None,
                **seq_rights("234567"),
            )
        except ChatAdminRequiredError:
            return await utils.answer(m, self.strings["error.can_not_restrict"])
        except UserAdminInvalidError:
            return await utils.answer(m, self.strings["error.can_not_restrict"])

        userstring = self.identify(user)

        await self.log_action(
            m.sender, user, self.strings["act.allowmedia"], reason, chat=m.chat
        )

        await utils.answer(
            m,
            self.strings["done.allowmedia"].format(user=userstring)
            + (self.strings["reason"].format(reason) if reason else ""),
        )

    async def _purge_ids(self, peer, ids):
        for start in range(0, len(ids), 100):
            chunk = ids[start : start + 100]
            while True:
                try:
                    await self.client.delete_messages(peer, chunk)
                    break
                except (errors.FloodWaitError, errors.FloodPremiumWaitError) as error:
                    await asyncio.sleep(error.seconds + 1)

    async def _purge_stream(self, peer, messages):
        batch = []
        async for message in messages:
            batch.append(message.id)
            if len(batch) >= 100:
                await self._purge_ids(peer, batch)
                batch.clear()
        if batch:
            await self._purge_ids(peer, batch)

    @loader.command()
    async def dcmd(self, m: Message):
        """
        .d [a[N]] [b[N]] | [reply]
        Delete messages around a target. Bare a/b means the whole history
        after/before it. aN and bN take any count, with no cap.
        """
        args = utils.get_args_raw(m).split()
        after = before = None
        all_after = all_before = False

        for arg in args:
            if arg.startswith("a"):
                if not arg[1:]:
                    all_after = True
                    after = None
                else:
                    try:
                        after = int(arg[1:])
                        all_after = False
                    except ValueError:
                        pass
            elif arg.startswith("b"):
                if not arg[1:]:
                    all_before = True
                    before = None
                else:
                    try:
                        before = int(arg[1:])
                        all_before = False
                    except ValueError:
                        pass

        if (after is not None and after < 0) or (before is not None and before < 0):
            return await utils.answer(m, self.strings["error.too_much"])

        if m.is_reply:
            target_id = (await m.get_reply_message()).id
            ids = [target_id, m.id]
        else:
            target_id = m.id
            ids = [m.id]

        if after is not None:
            ids.extend(target_id + 1 + i for i in range(after))
        if before is not None:
            ids.extend(target_id - (i + 1) for i in range(before))

        try:
            await self._purge_ids(m.peer_id, list(dict.fromkeys(ids)))
            if all_after:
                await self._purge_stream(
                    m.peer_id,
                    self.client.iter_messages(m.peer_id, min_id=target_id, reverse=True),
                )
            if all_before:
                await self._purge_stream(
                    m.peer_id,
                    self.client.iter_messages(m.peer_id, max_id=target_id),
                )
        except Exception:
            pass

    @loader.command()
    async def gfl(self, m: Message):
        """Global Kick deleted accounts"""

        await utils.answer(
            m,
            self.strings["flushda.loading"],
        )

        chats = [
            chat.entity.id
            async for chat in self._client.iter_dialogs()
            if (
                (
                    isinstance(chat.entity, Chat)
                    or (
                        isinstance(chat.entity, Channel)
                        and getattr(chat.entity, "megagroup", False)
                        or getattr(chat.entity, "broadcast", False)
                    )
                )
                and not isinstance(chat.entity, ChannelForbidden)
                and not isinstance(chat.entity, ChatForbidden)
                and chat.entity.admin_rights
                and chat.entity.participants_count > 7
                and chat.entity.admin_rights.ban_users
            )
        ]

        amt = 0

        for chat in chats:
            async for user in self.client.iter_participants(chat):
                if user.deleted:
                    try:
                        await self.client.kick_participant(chat, user.id)
                        amt += 1
                    except Exception:
                        pass

        await utils.answer(m, self.strings["done.flushda"].format(amt=amt))

    @loader.command()
    async def cfl(self, m: Message):
        """Kick deleted accounts in channels"""

        await utils.answer(
            m,
            self.strings["flushda.loading.channels"],
        )

        chats = [
            chat.entity.id
            async for chat in self._client.iter_dialogs()
            if (
                (
                    isinstance(chat.entity, Chat)
                    or (
                        isinstance(chat.entity, Channel)
                        and getattr(chat.entity, "broadcast", False)
                    )
                )
                and not isinstance(chat.entity, ChannelForbidden)
                and not isinstance(chat.entity, ChatForbidden)
                and chat.entity.admin_rights
                and chat.entity.participants_count > 7
                and chat.entity.admin_rights.ban_users
            )
        ]

        amt = 0

        for chat in chats:
            async for user in self.client.iter_participants(chat):
                if user.deleted:
                    try:
                        await self.client.kick_participant(chat, user.id)
                        amt += 1
                    except Exception:
                        pass

        await utils.answer(m, self.strings["done.flushda"].format(amt=amt))

    async def pincmd(self, m: Message):
        """
        /pin [reply]
        Pin a message in a chat.
        """
        if not isinstance(m.input_chat, (InputPeerChannel, InputPeerChat)):
            return await utils.answer(m, self.strings["error.wrongchattype.pm"])

        if m.chat.default_banned_rights is None:
            return await utils.answer(m, self.strings["error.wrongchattype.channel"])

        if not m.is_reply:
            return await utils.answer(m, self.strings["error.no_reply"])

        target = await m.get_reply_message()

        try:
            await self.client.pin_message(m.chat.id, target.id, notify=False)
        except Exception:
            return await utils.answer(m, self.strings["error.insufficient_rights"])

        await utils.answer(m, self.strings["done.pin"])

    async def leavecmd(self, message):
        """Leave this chat. A reason after the command is shown before you go."""
        args = utils.get_args_raw(message)
        if message.is_private:
            return await utils.answer(message, self.strings["not_a_chat"])
        if args:
            await utils.answer(
                message,
                self.strings["done.leave.reason"].format(reason=es(args)),
            )
        else:
            await utils.answer(message, self.strings["done.leave"])
        await message.client(LeaveChannelRequest(message.peer_id))

    async def unpincmd(self, m: Message):
        """
        /unpin
        Unpin a message in a chat.
        """
        if not isinstance(m.input_chat, (InputPeerChannel, InputPeerChat)):
            return await utils.answer(m, self.strings["error.wrongchattype.pm"])

        if m.chat.default_banned_rights is None:
            return await utils.answer(m, self.strings["error.wrongchattype.channel"])

        try:
            await self.client.pin_message(m.chat.id, 0, notify=False)
        except Exception:
            return await utils.answer(m, self.strings["error.insufficient_rights"])

        await utils.answer(m, self.strings["done.unpin"])

    async def nochannelcmd(self, m: Message):
        """
        /nochannel
        Switch module to ban or not all channels from this chat when they appear.
        """
        if not isinstance(m.input_chat, (InputPeerChannel, InputPeerChat)):
            return await utils.answer(m, self.strings["error.wrongchattype.pm"])

        if m.chat.default_banned_rights is None:
            return await utils.answer(m, self.strings["error.wrongchattype.channel"])

        properties = self.get("chat_properties", {})
        chat_id = str(m.chat.id)

        if not properties.get(chat_id):
            properties[chat_id] = []

        if "nochannel" in properties[chat_id]:
            properties[chat_id].remove("nochannel")
            self.set("chat_properties", properties)
            return await utils.answer(m, self.strings["done.channel_ban.off"])
        else:
            properties[chat_id].append("nochannel")
            self.set("chat_properties", properties)
            return await utils.answer(m, self.strings["done.channel_ban.on"])

    async def cidcmd(self, m: Message):
        """
        /cid
        Get the chat ID. If a reply is specified, gets the id of person who sent the message.
        """
        chat_id = m.chat.id
        my_id = m.sender.id
        rs_id = None

        if r := await m.get_reply_message():
            rs_id = r.sender.id

        additional = ""

        if not isinstance(m.input_chat, InputPeerUser):
            additional = f" (<code>-100{chat_id}</code>)"

        if m.chat.default_banned_rights is None:
            rs_id = None

        await utils.answer(
            m,
            (
                self.strings["chat_id"].format(
                    chat_id=chat_id,
                    my_id=my_id,
                    additional=additional,
                )
                + (
                    "\n" + self.strings["person_in_reply_id"].format(reply_id=rs_id)
                    if rs_id
                    else ""
                )
            ),
        )

    async def watcher(self, m: Message):
        if not isinstance(m.input_chat, (InputPeerChannel, InputPeerChat)):
            return

        if not hasattr(m, "chat"):
            return

        if not hasattr(m.chat, "default_banned_rights"):
            return

        if m.chat.default_banned_rights is None:
            return

        properties = self.get("chat_properties", {})
        chat_id = str(m.chat.id)

        if chat_id not in properties:
            properties[chat_id] = []

        if "nochannel" in properties[chat_id] and isinstance(m.sender, Channel):
            try:
                await edit_permissions(
                    self.client,
                    m.chat.id,
                    m.sender_id,
                    None,
                    **seq_rights("0", inv=True),
                )
            except Exception:
                pass

    @loader.command(ru_doc="[-i] Получить информацию о сущности")
    async def inspect(self, message):
        """[-i] Get the info about the entity"""
        opts = self.xdlib.parse.opts(utils.get_args(message))
        reply = await message.get_reply_message()
        target = (
            opts.get("i")
            or (reply.sender if reply else await message.get_chat())
            or None
        )
        if not target:
            return await utils.answer(message, self.strings["error.no_user"])
        ent = await self._client.get_entity(target)
        if isinstance(ent, types.Channel):
            try:
                chatinfo = await self.xdlib.chat.get_info(ent)
                photo = chatinfo.get("chat_photo")
                photo = photo if not isinstance(photo, types.PhotoEmpty) else None
                return await utils.answer(
                    message,
                    self.strings["chatinfo"].format(
                        id=chatinfo.get("id"),
                        title=chatinfo.get("title"),
                        about=chatinfo.get("about") or self.strings["no"],
                        admins_count=chatinfo.get("admins_count"),
                        online_count=chatinfo.get("online_count"),
                        participants_count=chatinfo.get("participants_count"),
                        kicked_count=chatinfo.get("kicked_count"),
                        slowmode_seconds=(
                            self.xdlib.format.time(chatinfo.get("slowmode_seconds"))
                            if chatinfo.get("slowmode_seconds")
                            else self.strings["no"]
                        ),
                        call=(
                            self.strings["yes"]
                            if chatinfo.get("call")
                            else self.strings["no"]
                        ),
                        ttl_period=(
                            self.xdlib.format.time(chatinfo.get("ttl_period"))
                            if chatinfo.get("ttl_period")
                            else self.strings["no"]
                        ),
                        requests_pending=chatinfo.get("requests_pending"),
                        recent_requesters=", ".join(
                            [
                                f"<code>{user}</code>"
                                for user in chatinfo.get("recent_requesters")
                            ]
                        )
                        or self.strings["no"],
                        linked_chat_id=chatinfo.get("linked_chat_id")
                        or self.strings["no"],
                        antispam=(
                            self.strings["yes"]
                            if chatinfo.get("antispam")
                            else self.strings["no"]
                        ),
                        participants_hidden=(
                            self.strings["yes"]
                            if chatinfo.get("participants_hidden")
                            else self.strings["no"]
                        ),
                        link=chatinfo.get("link") or self.strings["no"],
                        is_forum=(
                            self.strings["yes"]
                            if chatinfo.get("is_forum")
                            else self.strings["no"]
                        ),
                        type_of=(
                            self.strings["type_group"]
                            if chatinfo.get("is_group")
                            else (
                                self.strings["type_channel"]
                                if chatinfo.get("is_channel")
                                else self.strings["type_unknown"]
                            )
                        ),
                    ),
                    file=(
                        types.InputMediaPhoto(
                            types.InputPhoto(
                                photo.id, photo.access_hash, photo.file_reference
                            )
                        )
                        if photo
                        else None
                    ),
                )
            except Exception as e:
                log.error(str(e))
                return await utils.answer(
                    message, self.strings["error"].format(error=str(e))
                )
        if isinstance(ent, types.User):
            try:
                userinfo = await self.xdlib.user.get_info(ent)
                photo = userinfo.get("profile_photo")
                working_hours = (
                    userinfo.get("business_work_hours").weekly_open
                    if userinfo.get("business_work_hours")
                    else 0
                )
                weekdays = [
                    self.strings["monday"],
                    self.strings["tuesday"],
                    self.strings["wednesday"],
                    self.strings["thursday"],
                    self.strings["friday"],
                    self.strings["saturday"],
                    self.strings["sunday"],
                ]
                personal_channel = userinfo.get("personal_channel")
                working_hours_output = []
                if working_hours:
                    for item in working_hours:
                        day_index = item.start_minute // (24 * 60)
                        day = weekdays[day_index]

                        start = self.xdlib.parse.minutes_to_hhmm(item.start_minute)
                        end = self.xdlib.parse.minutes_to_hhmm(item.end_minute)
                        working_hours_output.append(f"<b>{day}: {start} - {end}</b>")
                return await utils.answer(
                    message,
                    self.strings["userinfo"].format(
                        common_chats_count=userinfo.get("common_chats_count") or 0,
                        phone=userinfo.get("phone") or self.strings["no"],
                        common_chats=(
                            ", ".join(
                                [
                                    f"<a href='{(await self.xdlib.chat.get_info(channel)).get('link')}'>{channel.title}</a>"
                                    for channel in userinfo.get("common_chats")
                                ]
                            )
                            if userinfo.get("common_chats")
                            else self.strings["no"]
                        ),
                        user_id=userinfo.get("id", 0),
                        first_name=userinfo.get("first_name") or self.strings["no"],
                        last_name=userinfo.get("last_name") or self.strings["no"],
                        about=userinfo.get("about") or self.strings["no"],
                        emoji_status=(
                            f"<tg-emoji emoji-id=\"{userinfo.get('emoji_status')}\">🌙</tg-emoji>"
                            if userinfo.get("emoji_status")
                            else self.strings["no"]
                        ),
                        business_work_hours=", ".join(working_hours_output)
                        or self.strings["no"],
                        birthday=(
                            f"{userinfo.get('birthday').day or ''}."
                            f"{userinfo.get('birthday').month or ''}."
                            f"{userinfo.get('birthday').year or ''}"
                            if userinfo.get("birthday")
                            else self.strings["no"]
                        ),
                        stargifts_count=userinfo.get("stargifts_count")
                        or self.strings["no"],
                        usernames=(
                            ", ".join(
                                [
                                    f"@{username}"
                                    for username in userinfo.get("usernames")
                                ]
                            )
                            if userinfo.get("usernames")
                            else self.strings["no"]
                        ),
                        personal_channel=(
                            f"<a href='{(await self.xdlib.chat.get_info(personal_channel)).get('link')}'>"
                            f"{personal_channel.title}</a>"
                            if personal_channel
                            else self.strings["no"]
                        ),
                    ),
                    file=(
                        types.InputMediaPhoto(
                            types.InputPhoto(
                                photo.id, photo.access_hash, photo.file_reference
                            )
                        )
                        if photo
                        else None
                    ),
                )
            except Exception as e:
                log.error(e)
                return await utils.answer(
                    message, self.strings["error"].format(error=str(e))
                )

    @loader.command(ru_doc="[-a] - Принять заявки на вступление")
    async def approve(self, message):
        """[-a] - Accept join requests"""
        opts = self.xdlib.parse.opts(utils.get_args(message))
        if opts.get("a"):
            await self.xdlib.chat.join_requests(message.chat, True)
            return await utils.answer(message, self.strings["all_approved"])
        args = utils.get_args(message)
        for arg in args:
            if arg.isdigit():
                await self.xdlib.chat.join_request(message.chat, int(arg), True)
            else:
                await self.xdlib.chat.join_request(message.chat, arg, True)
        return await utils.answer(message, self.strings["all_approved"])

    @loader.command(ru_doc="[-a] - Отклонить заявки на вступление")
    async def dismiss(self, message):
        """[-a] - Decline join requests"""
        opts = self.xdlib.parse.opts(utils.get_args(message))
        if opts.get("a"):
            await self.xdlib.chat.join_requests(message.chat, False)
            return await utils.answer(message, self.strings["all_dismissed"])
        args = utils.get_args(message)
        for arg in args:
            if arg.isdigit():
                await self.xdlib.chat.join_request(message.chat, int(arg), False)
            else:
                await self.xdlib.chat.join_request(message.chat, arg, False)
        return await utils.answer(message, self.strings["all_dismissed"])

    def _gban_name(self, user) -> str:
        if isinstance(user, Channel):
            return es(user.title or "")
        return es(
            f"{user.first_name or ''} {user.last_name or ''}".strip()
            or self.strings["sys.DA"]
        )

    async def _gban_target(self, message: Message):
        raw = (utils.get_args_raw(message) or "").strip()
        silent = False
        if " -s" in f" {raw}":
            silent = True
            raw = raw.replace(" -s", "").replace("-s ", "").replace("-s", "").strip()

        reply = await message.get_reply_message()
        if not raw:
            if not reply or isinstance(reply, MessageService):
                return None
            try:
                user = await self.client.get_entity(reply.sender_id)
            except Exception:
                return None
            return user, self.strings["gban.no_reason"], silent

        parts = raw.split()
        token = parts[0]
        try:
            user = await self.client.get_entity(int(token) if token.lstrip("-").isdigit() else token)
            reason = " ".join(parts[1:]).strip()
        except Exception:
            if not reply or isinstance(reply, MessageService):
                return None
            try:
                user = await self.client.get_entity(reply.sender_id)
            except Exception:
                return None
            reason = raw
        if getattr(user, "id", None) == self.tg_id:
            await utils.answer(message, self.strings["error.self"])
            return False
        return user, es(reason) if reason else self.strings["gban.no_reason"], silent

    async def _gban_chats(self) -> list:
        cached = self._gban_cache
        if cached and cached.get("exp", 0) > time.time():
            return cached["chats"]

        skipped = set(self.config["gban_except"] or [])
        chats = []
        async for dialog in self.client.iter_dialogs():
            entity = dialog.entity
            if isinstance(entity, (ChannelForbidden, ChatForbidden)):
                continue
            if not isinstance(entity, (Chat, Channel)):
                continue
            if isinstance(entity, Channel) and entity.id in skipped:
                continue
            rights = getattr(entity, "admin_rights", None)
            if not rights or not rights.ban_users:
                continue
            if (getattr(entity, "participants_count", 0) or 0) < 2:
                continue
            chats.append(entity.id)

        self._gban_cache = {"exp": time.time() + 10 * 60, "chats": chats}
        return chats

    async def _gban_block_pm(self, user, clear: bool) -> bool:
        uid = int(getattr(user, "id", user))
        if uid in (self.config["gban_pm_except"] or []):
            return False
        try:
            await self.client(BlockRequest(id=uid))
        except Exception:
            return False
        if clear:
            try:
                await self.client(
                    DeleteHistoryRequest(peer=uid, max_id=0, just_clear=False, revoke=True)
                )
            except Exception:
                pass
        return True

    async def gbancmd(self, message: Message):
        """
        .gban [username | ID | reply] [reason] [-s]
        Ban a user in every chat where you can ban. -s hides the chat list.
        """
        parsed = await self._gban_target(message)
        if parsed is False:
            return
        if not parsed:
            return await utils.answer(message, self.strings["gban.args"])

        user, reason, silent = parsed
        url = utils.get_entity_url(user)
        name = self._gban_name(user)
        message = await utils.answer(
            message, self.strings["gban.working"].format(url=url, name=name)
        )

        count = 0
        lines = []
        for chat_id in await self._gban_chats():
            try:
                await edit_permissions(
                    self.client,
                    chat_id,
                    user,
                    timedelta(days=365),
                    **seq_rights("0", inv=True),
                )
            except errors.FloodWaitError as e:
                await asyncio.sleep(int(getattr(e, "seconds", 1)) + 1)
                try:
                    await edit_permissions(
                        self.client,
                        chat_id,
                        user,
                        timedelta(days=365),
                        **seq_rights("0", inv=True),
                    )
                except Exception:
                    continue
            except Exception:
                continue
            count += 1
            if silent or len(lines) >= 30:
                continue
            try:
                chat = await self.client.get_entity(chat_id)
                title = es(getattr(chat, "title", None) or str(chat_id))
                link = utils.get_entity_url(chat)
                lines.append(
                    f'▫️ <b><a href="{link}">{title}</a></b>' if link else f"▫️ <b>{title}</b>"
                )
            except Exception:
                lines.append(f"▫️ <code>{chat_id}</code>")

        note = ""
        excluded = int(user.id) in (self.config["gban_pm_except"] or [])
        if self.config["gban_pm_block"] and not excluded:
            if await self._gban_block_pm(user, self.config["gban_pm_del_history"]):
                note = self.strings["gban.pm_blocked"]
                if self.config["gban_pm_del_history"]:
                    note += self.strings["gban.pm_cleared"]
            else:
                note = self.strings["gban.pm_failed"]

        text = self.strings["gban.done"].format(
            url=url, name=name, count=count, reason=reason
        )
        if not silent and lines:
            text += self.strings["gban.chats"].format(chats="\n".join(lines))
        await self.log_action(
            message.sender,
            user,
            self.strings["act.ban"],
            reason,
            self.strings["sys.forever"],
        )
        await utils.answer(message, text + note)

    async def ungbancmd(self, message: Message):
        """
        .ungban [username | ID | reply] [-s]
        Unban a user in every chat where you can ban. -s hides the chat list.
        """
        parsed = await self._gban_target(message)
        if parsed is False:
            return
        if not parsed:
            return await utils.answer(message, self.strings["gban.args"])

        user, _, silent = parsed
        url = utils.get_entity_url(user)
        name = self._gban_name(user)
        message = await utils.answer(
            message, self.strings["gban.unworking"].format(url=url, name=name)
        )

        count = 0
        lines = []
        for chat_id in await self._gban_chats():
            try:
                await edit_permissions(
                    self.client,
                    chat_id,
                    user,
                    None,
                    **seq_rights("0"),
                )
            except errors.FloodWaitError as e:
                await asyncio.sleep(int(getattr(e, "seconds", 1)) + 1)
                try:
                    await edit_permissions(
                        self.client,
                        chat_id,
                        user,
                        None,
                        **seq_rights("0"),
                    )
                except Exception:
                    continue
            except Exception:
                continue
            count += 1
            if silent or len(lines) >= 30:
                continue
            try:
                chat = await self.client.get_entity(chat_id)
                title = es(getattr(chat, "title", None) or str(chat_id))
                link = utils.get_entity_url(chat)
                lines.append(
                    f'▫️ <b><a href="{link}">{title}</a></b>' if link else f"▫️ <b>{title}</b>"
                )
            except Exception:
                lines.append(f"▫️ <code>{chat_id}</code>")

        note = ""
        if self.config["gban_pm_block"]:
            try:
                await self.client(UnblockRequest(id=int(user.id)))
                note = self.strings["gban.pm_unblocked"]
            except Exception:
                note = ""

        text = self.strings["gban.undone"].format(url=url, name=name, count=count)
        if not silent and lines:
            text += self.strings["gban.chats"].format(chats="\n".join(lines))
        await utils.answer(message, text + note)


    def _slow_seconds(self, raw):
        raw = (raw or "").strip().lower()
        if raw in ("", "0", "off", "disable", "-", "no"):
            return 0
        if raw.isdigit():
            return int(raw)
        unit = raw[-1]
        value = raw[:-1]
        if not value.isdigit() or unit not in "smh":
            return None
        seconds = int(value) * {"s": 1, "m": 60, "h": 3600}[unit]
        return seconds

    async def _chat_mutation(self, message):
        if message.is_private:
            await utils.answer(message, self.strings["not_a_chat"])
            return None
        chat = await message.get_chat()
        if not isinstance(chat, Channel):
            await utils.answer(message, self.strings["chat.not_channel"])
            return None
        rights = getattr(chat, "admin_rights", None)
        if not getattr(chat, "creator", False) and not (rights and rights.change_info):
            await utils.answer(message, self.strings["chat.no_rights"])
            return None
        return chat

    async def _chat_rpc(self, message, request, done):
        try:
            await message.client(request)
        except errors.ChatAdminRequiredError:
            return await utils.answer(message, self.strings["chat.no_rights"])
        except errors.RPCError as error:
            return await utils.answer(message, self.strings["promote.rpc_error"].format(error=es(str(error))))
        return await utils.answer(message, done)

    @loader.command(ru_doc="[секунды|off] — медленный режим. 30, 1m, 5m, 1h или off")
    async def slowcmd(self, message: Message):
        """[seconds|off] — slow mode. 30, 1m, 5m, 1h, or off"""
        chat = await self._chat_mutation(message)
        if not chat:
            return
        seconds = self._slow_seconds(utils.get_args_raw(message))
        allowed = {0, 10, 30, 60, 300, 900, 3600}
        if seconds not in allowed:
            return await utils.answer(
                message, self.strings["chat.usage.slow"].format(prefix=es(self.get_prefix()))
            )
        text = self.strings["chat.slow_off"] if not seconds else self.strings["chat.slow_on"].format(seconds=seconds)
        await self._chat_rpc(message, channels.ToggleSlowModeRequest(chat.id, seconds), text)

    @loader.command(ru_doc="<текст> — описание чата. - очищает")
    async def setaboutcmd(self, message: Message):
        """<text> — chat description. - clears it"""
        chat = await self._chat_mutation(message)
        if not chat:
            return
        about = utils.get_args_raw(message).strip()
        if not about:
            return await utils.answer(
                message, self.strings["chat.usage.about"].format(prefix=es(self.get_prefix()))
            )
        about = "" if about == "-" else about
        if len(about) > 255:
            about = about[:255]
        key = "chat.about_cleared" if not about else "chat.about_set"
        await self._chat_rpc(message, messages.EditChatAboutRequest(chat.id, about), self.strings[key])

    @loader.command(ru_doc="ответом на фото — аватар чата. - убирает")
    async def setphotocmd(self, message: Message):
        """reply to a photo — chat photo. - removes it"""
        chat = await self._chat_mutation(message)
        if not chat:
            return
        arg = utils.get_args_raw(message).strip()
        reply = await message.get_reply_message()
        if arg == "-":
            photo = types.InputChatPhotoEmpty()
            key = "chat.photo_cleared"
        elif reply and reply.photo:
            uploaded = await message.client.upload_file(await reply.download_media(bytes))
            photo = types.InputChatUploadedPhoto(uploaded)
            key = "chat.photo_set"
        else:
            return await utils.answer(
                message, self.strings["chat.usage.photo"].format(prefix=es(self.get_prefix()))
            )
        await self._chat_rpc(message, channels.EditPhotoRequest(chat.id, photo), self.strings[key])

    @loader.command(ru_doc="<юзернейм> — публичная ссылка. - убирает")
    async def setusernamecmd(self, message: Message):
        """<username> — public link. - removes it"""
        chat = await self._chat_mutation(message)
        if not chat:
            return
        raw = utils.get_args_raw(message).strip().lstrip("@")
        if not raw:
            return await utils.answer(
                message, self.strings["chat.usage.username"].format(prefix=es(self.get_prefix()))
            )
        username = "" if raw == "-" else raw
        if username and not fullmatch(r"[a-zA-Z][a-zA-Z0-9_]{3,30}[a-zA-Z0-9]", username):
            return await utils.answer(
                message, self.strings["chat.usage.username"].format(prefix=es(self.get_prefix()))
            )
        text = (
            self.strings["chat.username_cleared"]
            if not username
            else self.strings["chat.username_set"].format(username=es(username))
        )
        await self._chat_rpc(message, channels.UpdateUsernameRequest(chat.id, username), text)

    async def _toggle_chat(self, message, attr, request, on_key, off_key):
        chat = await self._chat_mutation(message)
        if not chat:
            return
        enabled = not bool(getattr(chat, attr, False))
        text = self.strings[on_key if enabled else off_key]
        await self._chat_rpc(message, request(chat.id, enabled), text)

    @loader.command(ru_doc="переключить подпись автора")
    async def signcmd(self, message: Message):
        """Toggle author signatures"""
        chat = await self._chat_mutation(message)
        if not chat:
            return
        enabled = not bool(getattr(chat, "signatures", False))
        await self._chat_rpc(
            message,
            channels.ToggleSignaturesRequest(chat.id, enabled, None),
            self.strings["chat.sign_on" if enabled else "chat.sign_off"],
        )

    @loader.command(ru_doc="переключить темы. Только группа, от 200 участников, не для всех чатов")
    async def forumcmd(self, message: Message):
        """Toggle topics. Groups of 200+ members; not available in every chat"""
        chat = await self._chat_mutation(message)
        if not chat:
            return
        if getattr(chat, "broadcast", False):
            return await utils.answer(message, self.strings["promote.tag_group_only"])
        enabled = not bool(getattr(chat, "forum", False))
        await self._chat_rpc(
            message,
            channels.ToggleForumRequest(chat.id, enabled, None),
            self.strings["chat.forum_on" if enabled else "chat.forum_off"],
        )

    @loader.command(ru_doc="переключить агрессивный антиспам")
    async def antispamcmd(self, message: Message):
        """Toggle aggressive antispam"""
        await self._toggle_chat(
            message, "antispam", channels.ToggleAntiSpamRequest, "chat.spam_on", "chat.spam_off"
        )

    @loader.command(ru_doc="скрыть или показать список участников")
    async def hidememberscmd(self, message: Message):
        """Hide or show the member list"""
        await self._toggle_chat(
            message,
            "participants_hidden",
            channels.ToggleParticipantsHiddenRequest,
            "chat.hidden_on",
            "chat.hidden_off",
        )

    @loader.command(ru_doc="скрыть или показать историю новым участникам")
    async def historycmd(self, message: Message):
        """Hide or show history for new members"""
        chat = await self._chat_mutation(message)
        if not chat:
            return
        try:
            full = await message.client(channels.GetFullChannelRequest(chat.id))
        except errors.RPCError as error:
            return await utils.answer(message, self.strings["promote.rpc_error"].format(error=es(str(error))))
        currently_hidden = bool(getattr(full.full_chat, "hidden_prehistory", False))
        enabled_visible = currently_hidden
        await self._chat_rpc(
            message,
            channels.TogglePreHistoryHiddenRequest(chat.id, not enabled_visible),
            self.strings["chat.history_on" if enabled_visible else "chat.history_off"],
        )

    @loader.command(ru_doc="переключить заявки на вступление")
    async def joinreqcmd(self, message: Message):
        """Toggle join requests"""
        chat = await self._chat_mutation(message)
        if not chat:
            return
        enabled = not bool(getattr(chat, "join_request", False))
        await self._chat_rpc(
            message,
            channels.ToggleJoinRequestRequest(chat.id, enabled),
            self.strings["chat.join_on" if enabled else "chat.join_off"],
        )

    async def _primary_invite(self, message, chat):
        me = await message.client.get_input_entity(self._me_id)
        result = await message.client(messages.GetExportedChatInvitesRequest(
            peer=chat.id, admin_id=me, limit=20, revoked=False,
        ))
        invites = [item for item in result.invites if getattr(item, "link", None) and not getattr(item, "revoked", False)]
        permanent = [item for item in invites if not getattr(item, "expire_date", None) and not getattr(item, "usage_limit", None) and not getattr(item, "request_needed", False)]
        return (permanent or invites or [None])[0]

    @loader.command(ru_doc="[new|revoke|название] — инвайт. Без аргументов показывает основной")
    async def linkcmd(self, message: Message):
        """[new|revoke|title] — invite link. No args shows the primary one"""
        chat = await self._chat_mutation(message)
        if not chat:
            return
        arg = utils.get_args_raw(message).strip()
        try:
            if not arg:
                invite = await self._primary_invite(message, chat)
                if not invite:
                    return await utils.answer(message, self.strings["chat.link_none"])
                return await utils.answer(message, self.strings["chat.link"].format(link=es(invite.link)))
            if arg.lower() == "revoke":
                invite = await self._primary_invite(message, chat)
                if invite:
                    await message.client(messages.DeleteExportedChatInviteRequest(chat.id, invite.link))
                exported = await message.client(messages.ExportChatInviteRequest(peer=chat.id))
                return await utils.answer(message, self.strings["chat.link_revoked"].format(link=es(exported.link)))
            title = None if arg.lower() == "new" else arg[:32]
            exported = await message.client(messages.ExportChatInviteRequest(peer=chat.id, title=title))
            return await utils.answer(message, self.strings["chat.link_created"].format(link=es(exported.link)))
        except errors.ChatAdminRequiredError:
            return await utils.answer(message, self.strings["chat.no_rights"])
        except errors.RPCError as error:
            return await utils.answer(message, self.strings["promote.rpc_error"].format(error=es(str(error))))

    def _rights_lines(self, chat, admin_rights):
        lines = []
        for name in self._admin_right_names(chat):
            if not getattr(admin_rights, name, False):
                continue
            key = f"promote.right.{name}"
            label = self.strings[key] if key in self.strings else name
            lines.append(label.format(
                emoji="✅",
                where=self.strings["of_channel"] if getattr(chat, "broadcast", False) else self.strings["of_chat"],
            ))
        return lines

    @loader.command(ru_doc="[пользователь] — текущие права админа. Без аргументов — свои")
    async def rightscmd(self, message: Message):
        """[user] — current admin rights. No args shows yours"""
        if message.is_private:
            return await utils.answer(message, self.strings["not_a_chat"])
        chat = await message.get_chat()
        if not isinstance(chat, Channel):
            return await utils.answer(message, self.strings["chat.not_channel"])
        args = utils.get_args_raw(message).strip()
        reply = await message.get_reply_message()
        try:
            if reply and reply.sender_id:
                user = await message.client.get_entity(reply.sender_id)
            elif args:
                target = int(args) if args.lstrip("-").isdigit() else args
                user = await message.client.get_entity(target)
            else:
                user = await message.client.get_entity(self._me_id)
        except (ValueError, TypeError):
            return await utils.answer(message, self.strings["promote.no_user"])
        if not isinstance(user, User):
            return await utils.answer(message, self.strings["promote.no_user"])
        try:
            result = await message.client(channels.GetParticipantRequest(chat.id, user.id))
        except errors.RPCError as error:
            return await utils.answer(message, self.strings["promote.rpc_error"].format(error=es(str(error))))
        participant = result.participant
        if isinstance(participant, types.ChannelParticipantCreator):
            role, rank, admin_rights = self.strings["rights.owner"], participant.rank or "—", participant.admin_rights
        elif isinstance(participant, types.ChannelParticipantAdmin):
            role, rank, admin_rights = self.strings["rights.admin"], participant.rank or "—", participant.admin_rights
        else:
            return await utils.answer(
                message,
                self.strings["rights.none"].format(name=self._promote_name(user), user_id=user.id),
            )
        lines = self._rights_lines(chat, admin_rights) if admin_rights else []
        text = self.strings["rights.header"].format(
            name=self._promote_name(user),
            user_id=user.id,
            role=role,
            rank=es(rank or "—"),
        )
        text += "\n" + ("\n".join(lines) if lines else self.strings["rights.empty"])
        await utils.answer(message, text)

    @staticmethod
    def _admin_right_fields():
        return [
            name
            for name in types.ChatAdminRights.__init__.__annotations__
            if name != "other"
        ]

    def _admin_right_names(self, chat):
        broadcast = bool(getattr(chat, "broadcast", False))
        names = []
        for name in self._admin_right_fields():
            if broadcast and name in ("pin_messages", "manage_call", "manage_topics", "manage_ranks", "manage_linked_peers", "manage_welcome_messages"):
                continue
            if not broadcast and name in ("post_messages", "edit_messages", "manage_direct_messages"):
                continue
            names.append(name)
        return names

    def _promote_button(self, name, rights, chat, rank, user):
        key = f"promote.right.{name}"
        label = self.strings[key] if key in self.strings else name
        return {
            "text": label.format(
                emoji="✅" if rights.get(name) else "✖️",
                where=self.strings["of_channel"] if getattr(chat, "broadcast", False) else self.strings["of_chat"],
            ),
            "callback": self._ch_admin_rights,
            "args": [name, rights, chat.id, rank, user.id],
        }

    def _promote_markup(self, rights, chat, rank, user):
        buttons = [
            self._promote_button(name, rights, chat, rank, user)
            for name in self._admin_right_names(chat)
        ]
        rows = [buttons[i:i + 2] for i in range(0, len(buttons), 2)]
        rows.append([{
            "text": self.strings["promote.confirm"],
            "callback": self._inline_promote,
            "args": [rights, chat.id, rank, user.id],
        }])
        return rows

    async def _promote_target(self, message):
        if message.is_private:
            await utils.answer(message, self.strings["error.wrongchattype.pm"])
            return None
        chat = await message.get_chat()
        if (not getattr(chat, "admin_rights", None) or not chat.admin_rights.add_admins) and not getattr(chat, "creator", False):
            await utils.answer(message, self.strings["promote.no_rights"])
            return None
        args = utils.get_args_raw(message).strip()
        reply = await message.get_reply_message()
        rank = self.strings["promote.default_rank"]
        if reply and reply.sender_id and reply.sender_id != self.tg_id:
            user_id = reply.sender_id
            if args:
                rank = args
        else:
            user_id = await utils.get_target(message)
            parts = args.split(maxsplit=1)
            if len(parts) > 1:
                rank = parts[1]
        if not user_id:
            await utils.answer(message, self.strings["promote.no_user"])
            return None
        try:
            user = await message.client.get_entity(user_id)
        except (ValueError, TypeError):
            await utils.answer(message, self.strings["promote.no_user"])
            return None
        if not isinstance(user, User):
            await utils.answer(message, self.strings["promote.no_user"])
            return None
        return chat, user, rank

    def _promote_name(self, user):
        return es(getattr(user, "first_name", None) or str(user.id))

    async def _edit_admin(self, chat, user, rights, rank):
        await self.client(EditAdminRequest(chat.id, user.id, rights, rank))

    @loader.command(ru_doc="<пользователь> — снять права админа")
    async def demotecmd(self, message: Message):
        """<user> — demote an admin"""
        parsed = await self._promote_target(message)
        if not parsed:
            return
        chat, user, _rank = parsed
        try:
            await self._edit_admin(chat, user, types.ChatAdminRights(), "")
        except errors.ChatAdminRequiredError:
            return await utils.answer(message, self.strings["promote.no_rights"])
        except errors.RPCError as error:
            return await utils.answer(message, self.strings["promote.rpc_error"].format(error=es(str(error))))
        await utils.answer(
            message,
            self.strings["promote.demoted"].format(name=self._promote_name(user), user_id=user.id),
        )

    @loader.command(ru_doc="<пользователь> [должность] — админ со всеми правами")
    async def fullrightscmd(self, message: Message):
        """<user> [rank] — promote with every admin right"""
        parsed = await self._promote_target(message)
        if not parsed:
            return
        chat, user, rank = parsed
        try:
            await self._edit_admin(
                chat,
                user,
                types.ChatAdminRights(**{
                    name: True
                    for name in self._admin_right_names(chat)
                    if name != "anonymous"
                }),
                rank,
            )
        except errors.ChatAdminRequiredError:
            return await utils.answer(message, self.strings["promote.no_rights"])
        except errors.RPCError as error:
            return await utils.answer(message, self.strings["promote.rpc_error"].format(error=es(str(error))))
        await utils.answer(
            message,
            self.strings["promote.promoted_full"].format(
                name=self._promote_name(user), user_id=user.id, rank=es(rank)
            ),
        )

    @loader.command(ru_doc="<пользователь> [должность] — выбрать права админа")
    async def promotecmd(self, message: Message):
        """<user> [rank] — pick admin rights and promote"""
        parsed = await self._promote_target(message)
        if not parsed:
            return
        chat, user, rank = parsed
        rights = {name: False for name in self._admin_right_names(chat)}
        await self.inline.form(
            message=message,
            text=self.strings["promote.choose"].format(
                name=self._promote_name(user), user_id=user.id, rank=es(rank)
            ),
            silent=True,
            reply_markup=self._promote_markup(rights, chat, rank, user),
        )

    async def _ch_admin_rights(self, call, name, rights, chat_id, rank, user_id):
        rights[name] = not rights.get(name, False)
        chat = await self.client.get_entity(chat_id)
        user = await self.client.get_entity(user_id)
        await call.edit(
            text=self.strings["promote.choose"].format(
                name=self._promote_name(user), user_id=user.id, rank=es(rank)
            ),
            reply_markup=self._promote_markup(rights, chat, rank, user),
        )

    async def _inline_promote(self, call, rights, chat_id, rank, user_id):
        chat = await self.client.get_entity(chat_id)
        user = await self.client.get_entity(user_id)
        try:
            await self._edit_admin(
                chat,
                user,
                types.ChatAdminRights(**{name: bool(rights.get(name)) for name in self._admin_right_names(chat)}),
                rank,
            )
        except errors.ChatAdminRequiredError:
            return await call.edit(text=self.strings["promote.no_rights"])
        except errors.RPCError as error:
            return await call.edit(text=self.strings["promote.rpc_error"].format(error=es(str(error))))
        await call.edit(
            text=self.strings["promote.promoted"].format(
                name=self._promote_name(user), user_id=user.id, rank=es(rank)
            )
        )

    @loader.command(ru_doc="<пользователь> <тег> или <тег> ответом — тег участника, не админка. Без аргументов или - снимает тег")
    async def settagcmd(self, message: Message):
        """<user> <tag> or <tag> in reply — member tag, not admin rights. No args or - removes it"""
        if message.is_private:
            return await utils.answer(message, self.strings["promote.tag_group_only"])
        chat = await message.get_chat()
        if getattr(chat, "broadcast", False):
            return await utils.answer(message, self.strings["promote.tag_group_only"])
        args = utils.get_args_raw(message).strip()
        reply = await message.get_reply_message()
        try:
            if reply:
                target, rank = reply.sender_id, args
            else:
                parts = args.split(maxsplit=1)
                if not parts:
                    return await utils.answer(
                        message,
                        self.strings["promote.tag_usage"].format(prefix=es(self.get_prefix())),
                    )
                target = parts[0]
                rank = parts[1] if len(parts) > 1 else ""
                if str(target).lstrip("-").isdigit():
                    target = int(target)
            if not target:
                return await utils.answer(
                    message,
                    self.strings["promote.tag_usage"].format(prefix=es(self.get_prefix())),
                )
            rank = "" if rank in ("", "-") else rank.strip()
            if len(rank) > 16:
                return await utils.answer(message, self.strings["promote.tag_invalid"])
            user = await message.client.get_entity(target)
            if not isinstance(user, User):
                return await utils.answer(message, self.strings["promote.no_user"])
            await message.client(EditChatParticipantRankRequest(
                peer=await message.get_input_chat(),
                participant=await message.client.get_input_entity(user),
                rank=rank,
            ))
        except (ValueError, TypeError):
            return await utils.answer(message, self.strings["promote.no_user"])
        except errors.RPCError as error:
            code = getattr(error, "message", "") or ""
            if isinstance(error, errors.ChatAdminRequiredError) or code in (
                "CHAT_ADMIN_REQUIRED", "CHAT_WRITE_FORBIDDEN", "CHAT_RESTRICTED",
            ):
                text = self.strings["promote.tag_no_rights"]
            elif "RANK" in code and ("INVALID" in code or "EMOJI" in code):
                text = self.strings["promote.tag_invalid"]
            else:
                text = self.strings["promote.rpc_error"].format(error=es(str(error)))
            return await utils.answer(message, text)
        await utils.answer(
            message,
            self.strings["promote.tag_updated" if rank else "promote.tag_removed"].format(
                name=self._promote_name(user), rank=es(rank)
            ),
        )
