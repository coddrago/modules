# ---------------------------------------------------------------------------------
# ░█▀▄░▄▀▀▄░█▀▄░█▀▀▄░█▀▀▄░█▀▀▀░▄▀▀▄░░░█▀▄▀█
# ░█░░░█░░█░█░█░█▄▄▀░█▄▄█░█░▀▄░█░░█░░░█░▀░█
# ░▀▀▀░░▀▀░░▀▀░░▀░▀▀░▀░░▀░▀▀▀▀░░▀▀░░░░▀░░▒▀
# Name: SkyBlockHelper
# Description: Ultimate Hypixel SkyBlock suite: Bazaar, Auctions, Items, Events, Elections, Kat & Calculations
# Author: @codrago_m
# ---------------------------------------------------------------------------------
# 🔒    Licensed under the GNU AGPLv3
# 🌐 https://www.gnu.org/licenses/agpl-3.0.html
# ---------------------------------------------------------------------------------
# Author: @codrago
# Commands: bz, bztrack, bzuntrack, mayor, sbitem, sbevents, sbfiresale, sbah, sbkat, sbexp
# scope: heroku_only
# meta developer: @codrago_m
# meta banner: https://raw.githubusercontent.com/coddrago/modules/refs/heads/main/banner.png
# ---------------------------------------------------------------------------------

__version__ = (2, 5)

import asyncio
import re
import time
import aiohttp
from herokutl.custom import Message

from .. import loader, utils
from ..types import BotInlineCall

SB_EPOCH = 1560275700
SB_DAY_SECONDS = 1200
SB_MONTH_DAYS = 31
SB_YEAR_MONTHS = 12
SB_YEAR_SECONDS = SB_DAY_SECONDS * SB_MONTH_DAYS * SB_YEAR_MONTHS

SKILL_EXP_TABLE = [
    0, 50, 175, 375, 675, 1175, 1925, 2925, 4425, 6425, 9925, 14925, 22425,
    32425, 47425, 67425, 97425, 147425, 222425, 322425, 522425, 822425,
    1222425, 1722425, 2322425, 3022425, 3822425, 4722425, 5722425, 6822425,
    8022425, 9322425, 10722425, 12222425, 13822425, 15522425, 17322425,
    19222425, 21222425, 23322425, 25522425, 27822425, 30222425, 32722425,
    35322425, 38072425, 40972425, 44072425, 47472425, 51172425, 55172425,
    59472425, 64072425, 68972425, 74172425, 79672425, 85472425, 91572425,
    97972425, 104672425, 111672425
]

KAT_TIERS = {
    "Common ➔ Uncommon": {"coins": 10000, "time": "6h"},
    "Uncommon ➔ Rare": {"coins": 50000, "time": "1d"},
    "Rare ➔ Epic": {"coins": 250000, "time": "3d"},
    "Epic ➔ Legendary": {"coins": 1000000, "time": "8d"},
    "Legendary ➔ Mythic": {"coins": 5000000, "time": "14d"},
}


@loader.tds
class SkyBlockHelperMod(loader.Module):
    """Hypixel SkyBlock suite: Bazaar, Auctions, Items, Events, Elections, Kat & Calculations"""

    strings = {
        "name": "SkyBlockHelper",
        "topic_description": "Системный журнал цен Базара и игровых событий Hypixel SkyBlock",
        "loading": "<b>[SkyBlock]</b> Получение данных с Hypixel API...",
        "no_args": "<b>[SkyBlock]</b> Укажите аргументы команды.",
        "not_found": "<b>[SkyBlock]</b> Объект <code>{query}</code> не найден.",
        "api_error": "<b>[SkyBlock]</b> Ошибка при обращении к Hypixel API.",
        "btn_refresh": "🔄 Обновить котировки",
        "coins_unit": "монет",
        "votes_unit": "голосов",
        "pcs_unit": "шт.",
        "total_label": "Итого",
        "not_for_sale": "Не продается",
        "base_stats_header": "• <b>Базовые статы:</b>\n",
        "enchanted_glint": "• <i>Предмет имеет зачарованное свечение</i>\n",
        "dungeon_item_tag": "• <i>Предмет Подземелий</i>\n",
        "no_active_perks": "Нет активных перков",
        "election_header": "🗳 Текущие выборы (Кандидаты):",
        "active_now": "<b>Идет прямо сейчас!</b>",
        "waiting": "Ожидание",
        "finishing_in": "Завершение через {time}",
        "firesale_starts_in": "Начало через <code>{time}</code>",
        "firesale_active": "<b>АКТИВНА</b> (Конец через <code>{time}</code>)",
        "firesale_empty": "<b>[SkyBlock]</b> На данный момент нет активных или анонсированных Firesales.",
        "track_added": "<b>[SkyBlock]</b> Предмет <code>{item}</code> добавлен в почасовой трекер цен.",
        "track_already": "<b>[SkyBlock]</b> Предмет <code>{item}</code> уже находится в списке отслеживания.",
        "track_removed": "<b>[SkyBlock]</b> Предмет <code>{item}</code> удален из списка отслеживания.",
        "track_not_in_list": "<b>[SkyBlock]</b> Предмет <code>{item}</code> отсутствует в списке отслеживания.",
        "track_empty": "<b>[SkyBlock]</b> Список отслеживаемых предметов пуст. Добавьте: <code>.bztrack &lt;название&gt;</code>",
        "track_list": "<b>[SkyBlock]</b> Отслеживаемые предметы ({count}):\n{items}",
        "month_names": "Ранняя Весна,Весна,Поздняя Весна,Раннее Лето,Лето,Позднее Лето,Ранняя Осень,Осень,Поздняя Осень,Ранняя Зима,Зима,Поздняя Зима",
        "hourly_report_header": (
            "<tg-emoji emoji-id=5253864872780769235>📊</tg-emoji> "
            "<b>[SkyBlock Tracker] Почасовой отчет котировок Базара:</b>\n"
        ),
        "bazaar_card": (
            "<tg-emoji emoji-id=5253864872780769235>📈</tg-emoji> "
            "<b>[Bazaar]</b> <code>{item_id}</code>{qty_header}\n\n"
            "• <b>Buy (Мгновенно):</b> <code>{buy_price:,.1f}</code> {coins_unit}{total_buy}\n"
            "• <b>Sell (Мгновенно):</b> <code>{sell_price:,.1f}</code> {coins_unit}{total_sell}\n"
            "• <b>Маржа (Флип):</b> <code>{margin:,.1f}</code> {coins_unit} ({margin_percent:.2f}%){total_margin}\n\n"
            "• <b>Объем покупки (Buy Volume):</b> <code>{buy_volume:,}</code>\n"
            "• <b>Объем продажи (Sell Volume):</b> <code>{sell_volume:,}</code>"
        ),
        "mayor_card": (
            "<tg-emoji emoji-id=5253864872780769235>🏛</tg-emoji> "
            "<b>[SkyBlock Mayor]</b> Действующий мэр: <b>{name}</b>\n\n"
            "<b>Активные перки:</b>\n{perks}\n"
            "{election_info}"
        ),
        "item_card": (
            "<tg-emoji emoji-id=5253864872780769235>🗡</tg-emoji> "
            "<b>[Item Info] {name}</b> (<code>{item_id}</code>)\n\n"
            "• <b>Редкость:</b> {tier} | <b>Категория:</b> {category}\n"
            "{stats}"
            "• <b>NPC Sell Price:</b> <code>{npc_price}</code> {coins_unit}\n"
            "{extra_info}"
        ),
        "events_card": (
            "<tg-emoji emoji-id=5253864872780769235>⏳</tg-emoji> "
            "<b>[SkyBlock Calendar & Timers]</b>\n\n"
            "📅 <b>Текущая дата:</b> Year {year}, {month} {day}-е\n\n"
            "• <b>Dark Auction:</b> через <code>{da_timer}</code>\n"
            "• <b>Jacob's Farming Contest:</b> {jacob_status} (через <code>{jacob_timer}</code>)\n"
            "• <b>Spooky Festival:</b> через <code>{spooky_timer}</code>\n"
            "• <b>Season of Jerry:</b> через <code>{jerry_timer}</code>\n"
            "• <b>Traveling Zoo:</b> через <code>{zoo_timer}</code>\n"
            "• <b>New Year Century:</b> через <code>{ny_timer}</code>"
        ),
        "firesale_header": (
            "<tg-emoji emoji-id=5253864872780769235>🔥</tg-emoji> "
            "<b>[SkyBlock Firesales] Распродажи скинов и косметики:</b>\n\n"
        ),
        "ah_card": (
            "<tg-emoji emoji-id=5253864872780769235>🏷</tg-emoji> "
            "<b>[Auction House] Лоты по запросу:</b> <code>{query}</code>\n\n"
            "• <b>Найдено активных BIN лотов:</b> <code>{count}</code>\n"
            "• <b>Lowest BIN (Минимальный выкуп):</b> <code>{lowest_bin:,.1f}</code> {coins_unit}\n"
            "• <b>Средняя цена (BIN Avg):</b> <code>{avg_bin:,.1f}</code> {coins_unit}\n\n"
            "<b>Топ дешевых предложений:</b>\n{top_lots}"
        ),
        "ah_empty": "<b>[Auction House]</b> Активных BIN аукционов по запросу <code>{query}</code> не найдено.",
        "kat_card": (
            "<tg-emoji emoji-id=5253864872780769235>🐱</tg-emoji> "
            "<b>[Kat Pet Care] Базовая стоимость улучшения питомцев:</b>\n\n"
            "{tiers}\n\n"
            "<i>(Время и стоимость снижаются в зависимости от уровня питомца и уровня навыка Taming).</i>"
        ),
        "exp_card": (
            "<tg-emoji emoji-id=5253864872780769235>📈</tg-emoji> "
            "<b>[Skill XP Calculator] Прогресс уровня {target_lvl}</b>\n\n"
            "• <b>Суммарный опыт для уровня {target_lvl}:</b> <code>{total_exp:,}</code> XP\n"
            "• <b>Опыт от предыдущего уровня ({prev_lvl}):</b> <code>{diff_exp:,}</code> XP"
        ),
        "exp_invalid": "<b>[Skill XP]</b> Укажите уровень навыка от 1 до 60. Пример: <code>.sbexp 50</code>",
    }

    strings_en = {
        "name": "SkyBlockHelper",
        "topic_description": "Hypixel SkyBlock Bazaar price tracking and game events log",
        "loading": "<b>[SkyBlock]</b> Fetching data from Hypixel API...",
        "no_args": "<b>[SkyBlock]</b> Please provide command arguments.",
        "not_found": "<b>[SkyBlock]</b> Target <code>{query}</code> not found.",
        "api_error": "<b>[SkyBlock]</b> Failed to fetch data from Hypixel API.",
        "btn_refresh": "🔄 Refresh Quotes",
        "coins_unit": "coins",
        "votes_unit": "votes",
        "pcs_unit": "pcs",
        "total_label": "Total",
        "not_for_sale": "Not for sale",
        "base_stats_header": "• <b>Base Stats:</b>\n",
        "enchanted_glint": "• <i>Item has Enchanted Glint</i>\n",
        "dungeon_item_tag": "• <i>Dungeon Item</i>\n",
        "no_active_perks": "No active perks",
        "election_header": "🗳 Current Election (Candidates):",
        "active_now": "<b>Active Now!</b>",
        "waiting": "Waiting",
        "finishing_in": "Ends in {time}",
        "firesale_starts_in": "Starts in <code>{time}</code>",
        "firesale_active": "<b>ACTIVE</b> (Ends in <code>{time}</code>)",
        "firesale_empty": "<b>[SkyBlock]</b> No active or upcoming firesales found.",
        "track_added": "<b>[SkyBlock]</b> Item <code>{item}</code> added to hourly price tracker.",
        "track_already": "<b>[SkyBlock]</b> Item <code>{item}</code> is already being tracked.",
        "track_removed": "<b>[SkyBlock]</b> Item <code>{item}</code> removed from tracking list.",
        "track_not_in_list": "<b>[SkyBlock]</b> Item <code>{item}</code> is not in the tracking list.",
        "track_empty": "<b>[SkyBlock]</b> Tracking list is empty. Add items using: <code>.bztrack &lt;name&gt;</code>",
        "track_list": "<b>[SkyBlock]</b> Tracked items ({count}):\n{items}",
        "month_names": "Early Spring,Spring,Late Spring,Early Summer,Summer,Late Summer,Early Autumn,Autumn,Late Autumn,Early Winter,Winter,Late Winter",
        "hourly_report_header": (
            "<tg-emoji emoji-id=5253864872780769235>📊</tg-emoji> "
            "<b>[SkyBlock Tracker] Hourly Bazaar Price Report:</b>\n"
        ),
        "bazaar_card": (
            "<tg-emoji emoji-id=5253864872780769235>📈</tg-emoji> "
            "<b>[Bazaar]</b> <code>{item_id}</code>{qty_header}\n\n"
            "• <b>Instant Buy:</b> <code>{buy_price:,.1f}</code> {coins_unit}{total_buy}\n"
            "• <b>Instant Sell:</b> <code>{sell_price:,.1f}</code> {coins_unit}{total_sell}\n"
            "• <b>Flip Margin:</b> <code>{margin:,.1f}</code> {coins_unit} ({margin_percent:.2f}%){total_margin}\n\n"
            "• <b>Buy Volume:</b> <code>{buy_volume:,}</code>\n"
            "• <b>Sell Volume:</b> <code>{sell_volume:,}</code>"
        ),
        "mayor_card": (
            "<tg-emoji emoji-id=5253864872780769235>🏛</tg-emoji> "
            "<b>[SkyBlock Mayor]</b> Active Mayor: <b>{name}</b>\n\n"
            "<b>Active Perks:</b>\n{perks}\n"
            "{election_info}"
        ),
        "item_card": (
            "<tg-emoji emoji-id=5253864872780769235>🗡</tg-emoji> "
            "<b>[Item Info] {name}</b> (<code>{item_id}</code>)\n\n"
            "• <b>Rarity:</b> {tier} | <b>Category:</b> {category}\n"
            "{stats}"
            "• <b>NPC Sell Price:</b> <code>{npc_price}</code> {coins_unit}\n"
            "{extra_info}"
        ),
        "events_card": (
            "<tg-emoji emoji-id=5253864872780769235>⏳</tg-emoji> "
            "<b>[SkyBlock Calendar & Timers]</b>\n\n"
            "📅 <b>Current Date:</b> Year {year}, {month} {day}\n\n"
            "• <b>Dark Auction:</b> in <code>{da_timer}</code>\n"
            "• <b>Jacob's Farming Contest:</b> {jacob_status} (in <code>{jacob_timer}</code>)\n"
            "• <b>Spooky Festival:</b> in <code>{spooky_timer}</code>\n"
            "• <b>Season of Jerry:</b> in <code>{jerry_timer}</code>\n"
            "• <b>Traveling Zoo:</b> in <code>{zoo_timer}</code>\n"
            "• <b>New Year Century:</b> in <code>{ny_timer}</code>"
        ),
        "firesale_header": (
            "<tg-emoji emoji-id=5253864872780769235>🔥</tg-emoji> "
            "<b>[SkyBlock Firesales] Active and upcoming firesales:</b>\n\n"
        ),
        "ah_card": (
            "<tg-emoji emoji-id=5253864872780769235>🏷</tg-emoji> "
            "<b>[Auction House] Listings for:</b> <code>{query}</code>\n\n"
            "• <b>Active BIN listings found:</b> <code>{count}</code>\n"
            "• <b>Lowest BIN:</b> <code>{lowest_bin:,.1f}</code> {coins_unit}\n"
            "• <b>Average BIN:</b> <code>{avg_bin:,.1f}</code> {coins_unit}\n\n"
            "<b>Top cheapest listings:</b>\n{top_lots}"
        ),
        "ah_empty": "<b>[Auction House]</b> No active BIN listings found matching <code>{query}</code>.",
        "kat_card": (
            "<tg-emoji emoji-id=5253864872780769235>🐱</tg-emoji> "
            "<b>[Kat Pet Care] Pet Tier Upgrade Pricing Table:</b>\n\n"
            "{tiers}\n\n"
            "<i>(Time and coins are reduced based on pet level and Taming skill).</i>"
        ),
        "exp_card": (
            "<tg-emoji emoji-id=5253864872780769235>📈</tg-emoji> "
            "<b>[Skill XP Calculator] Level {target_lvl} Progress</b>\n\n"
            "• <b>Total cumulative XP for level {target_lvl}:</b> <code>{total_exp:,}</code> XP\n"
            "• <b>XP needed from previous level ({prev_lvl}):</b> <code>{diff_exp:,}</code> XP"
        ),
        "exp_invalid": "<b>[Skill XP]</b> Please specify a skill level between 1 and 60. Example: <code>.sbexp 50</code>",
    }

    def __init__(self):
        self._poll_task = None
        self._items_cache = None
        self.config = loader.ModuleConfig(
            loader.ConfigValue(
                "interval",
                3600,
                "Interval in seconds between price checks",
                validator=loader.validators.Integer(minimum=60),
            ),
            loader.ConfigValue(
                "tracked_items",
                [],
                "List of item IDs tracked in the hourly forum topic report",
                validator=loader.validators.Series(
                    loader.validators.String(),
                ),
            ),
        )

    async def client_ready(self):
        self.heroku_forum = self._db.get("heroku.forums", "channel_id", 0)
        self.assets_topic = await utils.asset_forum_topic(
            self.client,
            self.db,
            self.heroku_forum,
            self.strings("name"),
            self.strings("topic_description"),
            icon_emoji_id=5253952855185829086,
        )
        self._poll_task = asyncio.create_task(self._hourly_tracker_loop())

    async def on_unload(self):
        if self._poll_task and not self._poll_task.done():
            self._poll_task.cancel()

    def _strip_formatting(self, text: str) -> str:
        """Remove Minecraft color codes and formatting artifacts"""
        match bool(text):
            case True:
                return re.sub(r"§[0-9a-zA-Z]", "", text).strip()
            case _:
                return ""

    def _format_time(self, seconds: int) -> str:
        """Format seconds into human-readable duration"""
        match seconds <= 0:
            case True:
                return "0m 00s"
            case _:
                d, rem = divmod(int(seconds), 86400)
                h, rem = divmod(rem, 3600)
                m, s = divmod(rem, 60)
                if d > 0:
                    return f"{d}d {h:02d}h {m:02d}m"
                if h > 0:
                    return f"{h:02d}h {m:02d}m {s:02d}s"
                return f"{m:02d}m {s:02d}s"

    async def _fetch_bazaar(self) -> dict | None:
        """Fetch latest market data from Hypixel Bazaar API"""
        url = "https://api.hypixel.net/v2/skyblock/bazaar"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=10) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        match data.get("success", False):
                            case True:
                                return data.get("products", {})
                            case _:
                                return None
        except Exception:
            return None
        return None

    async def _fetch_auctions(self) -> list[dict] | None:
        """Fetch active auctions from Hypixel API"""
        url = "https://api.hypixel.net/v2/skyblock/auctions?page=0"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=12) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        match data.get("success", False):
                            case True:
                                return data.get("auctions", [])
                            case _:
                                return None
        except Exception:
            return None
        return None

    async def _get_all_items(self) -> list[dict] | None:
        """Fetch and cache items database from Hypixel API"""
        if self._items_cache:
            return self._items_cache
        url = "https://api.hypixel.net/v2/resources/skyblock/items"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=15) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        if data.get("success", False):
                            self._items_cache = data.get("items", [])
                            return self._items_cache
        except Exception:
            return None
        return None

    def _parse_query_and_count(self, raw_args: str) -> tuple[str, int]:
        """Extract item name and optional quantity from command arguments"""
        parts = raw_args.strip().split()
        if not parts:
            return "", 1

        count = 1
        if parts[0].isdigit() and len(parts) > 1:
            count = max(1, int(parts[0]))
            return " ".join(parts[1:]), count

        if parts[-1].isdigit() and len(parts) > 1:
            count = max(1, int(parts[-1]))
            return " ".join(parts[:-1]), count

        return raw_args.strip(), count

    def _find_bazaar_item(self, query: str, products: dict) -> tuple[str, dict] | tuple[None, None]:
        """Find matching item identifier in Bazaar products dictionary"""
        clean_query = query.strip().upper().replace(" ", "_").replace("-", "_")

        if clean_query in products:
            return clean_query, products[clean_query]

        for item_id, data in products.items():
            if clean_query in item_id:
                return item_id, data

        return None, None

    def _build_bazaar_card(self, item_id: str, item_data: dict, count: int = 1) -> str:
        """Construct formatted Bazaar price overview"""
        quick_status = item_data.get("quick_status", {})
        buy_price = quick_status.get("buyPrice", 0.0)
        sell_price = quick_status.get("sellPrice", 0.0)
        margin = buy_price - sell_price
        margin_percent = (margin / sell_price * 100) if sell_price > 0 else 0.0

        coins_unit = self.strings("coins_unit")
        total_lbl = self.strings("total_label")

        qty_header = f" <b>(x{count:,})</b>" if count > 1 else ""
        total_buy = f" ({total_lbl}: <code>{buy_price * count:,.1f}</code> {coins_unit})" if count > 1 else ""
        total_sell = f" ({total_lbl}: <code>{sell_price * count:,.1f}</code> {coins_unit})" if count > 1 else ""
        total_margin = f" ({total_lbl}: <code>{margin * count:,.1f}</code> {coins_unit})" if count > 1 else ""

        return self.strings("bazaar_card").format(
            item_id=item_id,
            qty_header=qty_header,
            buy_price=buy_price,
            total_buy=total_buy,
            sell_price=sell_price,
            total_sell=total_sell,
            margin=margin,
            total_margin=total_margin,
            margin_percent=margin_percent,
            coins_unit=coins_unit,
            buy_volume=quick_status.get("buyVolume", 0),
            sell_volume=quick_status.get("sellVolume", 0),
        )

    def _build_events_card(self) -> tuple[str, list[list[dict]]]:
        """Construct SkyBlock calendar dates and active timers"""
        now = time.time()
        passed_seconds = max(0, now - SB_EPOCH)

        sb_years, rem_year = divmod(passed_seconds, SB_YEAR_SECONDS)
        current_year = int(sb_years) + 1

        months_list = self.strings("month_names").split(",")
        sb_month_idx, rem_month = divmod(rem_year, SB_DAY_SECONDS * SB_MONTH_DAYS)
        current_month = months_list[int(sb_month_idx) % 12]
        current_day = int(rem_month // SB_DAY_SECONDS) + 1

        now_dt = time.gmtime(now)
        da_minutes_left = (55 - now_dt.tm_min) % 60
        da_seconds_left = (da_minutes_left * 60) - now_dt.tm_sec
        if da_seconds_left <= 0:
            da_seconds_left += 3600
        da_timer = self._format_time(da_seconds_left)

        jacob_min = (15 - now_dt.tm_min) % 60
        jacob_sec = (jacob_min * 60) - now_dt.tm_sec
        if jacob_sec <= 0:
            jacob_sec += 3600

        if 15 <= now_dt.tm_min < 35:
            jacob_status = self.strings("active_now")
            active_left = ((35 - now_dt.tm_min) * 60) - now_dt.tm_sec
            jacob_timer = self.strings("finishing_in").format(time=self._format_time(active_left))
        else:
            jacob_status = self.strings("waiting")
            jacob_timer = self._format_time(jacob_sec)

        spooky_start_sec = (7 * SB_MONTH_DAYS + 28) * SB_DAY_SECONDS
        spooky_wait = (spooky_start_sec - rem_year) if rem_year < spooky_start_sec else (SB_YEAR_SECONDS - rem_year + spooky_start_sec)
        spooky_timer = self._format_time(spooky_wait)

        jerry_start_sec = (11 * SB_MONTH_DAYS + 23) * SB_DAY_SECONDS
        jerry_wait = (jerry_start_sec - rem_year) if rem_year < jerry_start_sec else (SB_YEAR_SECONDS - rem_year + jerry_start_sec)
        jerry_timer = self._format_time(jerry_wait)

        zoo_start_sec = (3 * SB_MONTH_DAYS + 0) * SB_DAY_SECONDS
        zoo_wait = (zoo_start_sec - rem_year) if rem_year < zoo_start_sec else (SB_YEAR_SECONDS - rem_year + zoo_start_sec)
        zoo_timer = self._format_time(zoo_wait)

        ny_start_sec = (11 * SB_MONTH_DAYS + 28) * SB_DAY_SECONDS
        ny_wait = (ny_start_sec - rem_year) if rem_year < ny_start_sec else (SB_YEAR_SECONDS - rem_year + ny_start_sec)
        ny_timer = self._format_time(ny_wait)

        text = self.strings("events_card").format(
            year=current_year,
            month=current_month,
            day=current_day,
            da_timer=da_timer,
            jacob_status=jacob_status,
            jacob_timer=jacob_timer,
            spooky_timer=spooky_timer,
            jerry_timer=jerry_timer,
            zoo_timer=zoo_timer,
            ny_timer=ny_timer,
        )

        markup = [
            [
                {
                    "text": self.strings("btn_refresh"),
                    "callback": self._handle_refresh_events,
                    "style": "primary",
                }
            ]
        ]
        return text, markup

    async def _build_mayor_card(self) -> tuple[str, list[list[dict]]] | tuple[None, None]:
        """Construct active Mayor breakdown and election candidate data"""
        url = "https://api.hypixel.net/v2/resources/skyblock/election"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=10) as resp:
                    if resp.status != 200:
                        return None, None
                    data = await resp.json()
        except Exception:
            return None, None

        mayor = data.get("mayor", {})
        name = self._strip_formatting(mayor.get("name", "Unknown"))
        perks_list = mayor.get("perks", [])

        formatted_perks = ""
        for perk in perks_list:
            p_name = self._strip_formatting(perk.get("name", "Unknown Perk"))
            p_desc = self._strip_formatting(perk.get("description", ""))
            formatted_perks += f"• <b>{p_name}</b>: {p_desc}\n"

        if not formatted_perks:
            formatted_perks = f"• <i>{self.strings('no_active_perks')}</i>"

        current_election = data.get("current", {})
        candidates = current_election.get("candidates", [])
        election_info = ""

        if candidates:
            total_votes = sum(c.get("votes", 0) for c in candidates)
            cand_lines = []
            votes_unit = self.strings("votes_unit")
            for c in sorted(candidates, key=lambda x: x.get("votes", 0), reverse=True):
                c_name = self._strip_formatting(c.get("name", "Candidate"))
                c_votes = c.get("votes", 0)
                pct = (c_votes / total_votes * 100) if total_votes > 0 else 0
                cand_lines.append(f"• <b>{c_name}</b>: <code>{c_votes:,}</code> {votes_unit} ({pct:.1f}%)")

            election_info = f"\n<b>{self.strings('election_header')}</b>\n" + "\n".join(cand_lines)

        text = self.strings("mayor_card").format(
            name=name,
            perks=formatted_perks.strip(),
            election_info=election_info,
        )

        markup = [
            [
                {
                    "text": self.strings("btn_refresh"),
                    "callback": self._handle_refresh_mayor,
                    "style": "primary",
                }
            ]
        ]
        return text, markup

    async def _build_firesale_card(self) -> tuple[str, list[list[dict]]] | tuple[None, None]:
        """Construct active and upcoming cosmetic Firesales overview"""
        url = "https://api.hypixel.net/v2/skyblock/firesales"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=10) as resp:
                    if resp.status != 200:
                        return None, None
                    data = await resp.json()
        except Exception:
            return None, None

        sales = data.get("sales", [])
        if not sales:
            return self.strings("firesale_empty"), []

        now_ms = int(time.time() * 1000)
        lines = []
        pcs_unit = self.strings("pcs_unit")

        for sale in sales:
            item_id = sale.get("item_id", "Unknown")
            price = sale.get("price", 0)
            amount = sale.get("amount", 0)
            start_ms = sale.get("start", 0)
            end_ms = sale.get("end", 0)

            if now_ms < start_ms:
                status = self.strings("firesale_starts_in").format(time=self._format_time((start_ms - now_ms) // 1000))
            elif start_ms <= now_ms <= end_ms:
                status = self.strings("firesale_active").format(time=self._format_time((end_ms - now_ms) // 1000))
            else:
                continue

            lines.append(
                f"• <b>{item_id}</b>\n"
                f"  - <code>{price:,}</code> Gems | <code>{amount:,}</code> {pcs_unit}\n"
                f"  - {status}"
            )

        if not lines:
            return self.strings("firesale_empty"), []

        text = self.strings("firesale_header") + "\n\n".join(lines)
        markup = [
            [
                {
                    "text": self.strings("btn_refresh"),
                    "callback": self._handle_refresh_firesale,
                    "style": "primary",
                }
            ]
        ]
        return text, markup

    def _build_ah_card(self, query: str, matched: list[dict]) -> tuple[str, list[list[dict]]]:
        """Construct Auction House results with refresh action"""
        total_lots = len(matched)
        prices = [x.get("starting_bid", 0) for x in matched]
        lowest_bin = prices[0]
        avg_bin = sum(prices) / len(prices)
        coins_unit = self.strings("coins_unit")

        top_lots = matched[:5]
        lot_lines = []
        for lot in top_lots:
            name = self._strip_formatting(lot.get("item_name", "Item"))
            price = lot.get("starting_bid", 0)
            lot_lines.append(f"• <b>{name}</b>: <code>{price:,.1f}</code> {coins_unit}")

        text = self.strings("ah_card").format(
            query=query,
            count=total_lots,
            lowest_bin=lowest_bin,
            avg_bin=avg_bin,
            coins_unit=coins_unit,
            top_lots="\n".join(lot_lines),
        )

        buttons = [
            [
                {
                    "text": self.strings("btn_refresh"),
                    "callback": self._handle_refresh_ah,
                    "args": (query,),
                    "style": "primary",
                }
            ]
        ]
        return text, buttons

    async def _hourly_tracker_loop(self):
        """Background loop checking watched Bazaar prices every interval"""
        while True:
            await asyncio.sleep(self.config["interval"])
            tracked = self.config["tracked_items"]
            if not tracked or not self.assets_topic:
                continue

            products = await self._fetch_bazaar()
            if not products:
                continue

            lines = []
            coins_unit = self.strings("coins_unit")
            for item_id in tracked:
                if item_id in products:
                    qs = products[item_id].get("quick_status", {})
                    buy_price = qs.get("buyPrice", 0.0)
                    sell_price = qs.get("sellPrice", 0.0)
                    lines.append(
                        f"• <code>{item_id}</code>: Buy <code>{buy_price:,.1f}</code> | Sell <code>{sell_price:,.1f}</code> {coins_unit}"
                    )

            if lines:
                report_text = self.strings("hourly_report_header") + "\n".join(lines)
                await self.inline.bot.send_message(
                    self.heroku_forum,
                    report_text,
                    message_thread_id=self.assets_topic.id,
                    link_preview=False,
                )

    async def bzcmd(self, message: Message):
        """Look up item prices and total quantity costs on Hypixel Bazaar"""
        args = utils.get_args_raw(message)
        if not args:
            return await utils.answer(message, self.strings("no_args"))

        query, count = self._parse_query_and_count(args)
        if not query:
            return await utils.answer(message, self.strings("no_args"))

        products = await self._fetch_bazaar()
        if not products:
            return await utils.answer(message, self.strings("api_error"))

        item_id, item_data = self._find_bazaar_item(query, products)
        if not item_id:
            return await utils.answer(message, self.strings("not_found").format(query=query))

        text = self._build_bazaar_card(item_id, item_data, count)

        await self.inline.form(
            message=message,
            text=text,
            reply_markup=[
                [
                    {
                        "text": self.strings("btn_refresh"),
                        "callback": self._handle_refresh_bz,
                        "args": (item_id, count),
                        "style": "primary",
                    }
                ]
            ],
        )

    async def _handle_refresh_bz(self, call: BotInlineCall, item_id: str, count: int = 1):
        products = await self._fetch_bazaar()
        if not products or item_id not in products:
            return await call.answer(self.strings("api_error"), show_alert=True)

        text = self._build_bazaar_card(item_id, products[item_id], count)

        await call.edit(
            text=text,
            reply_markup=[
                [
                    {
                        "text": self.strings("btn_refresh"),
                        "callback": self._handle_refresh_bz,
                        "args": (item_id, count),
                        "style": "primary",
                    }
                ]
            ],
        )

    async def bztrackcmd(self, message: Message):
        """Add an item to the hourly tracker or list all tracked items"""
        args = utils.get_args_raw(message)
        if not args:
            tracked = self.config["tracked_items"]
            if not tracked:
                return await utils.answer(message, self.strings("track_empty"))
            items_fmt = "\n".join(f"• <code>{item}</code>" for item in tracked)
            return await utils.answer(
                message,
                self.strings("track_list").format(count=len(tracked), items=items_fmt),
            )

        products = await self._fetch_bazaar()
        if not products:
            return await utils.answer(message, self.strings("api_error"))

        item_id, _ = self._find_bazaar_item(args, products)
        if not item_id:
            return await utils.answer(message, self.strings("not_found").format(query=query))

        if item_id in self.config["tracked_items"]:
            return await utils.answer(message, self.strings("track_already").format(item=item_id))

        self.config["tracked_items"] = self.config["tracked_items"] + [item_id]
        await utils.answer(message, self.strings("track_added").format(item=item_id))

    async def bzuntrackcmd(self, message: Message):
        """Remove an item from the hourly price tracker"""
        args = utils.get_args_raw(message)
        if not args:
            return await utils.answer(message, self.strings("no_args"))

        clean_query = args.strip().upper().replace(" ", "_").replace("-", "_")
        target_item = None

        for item in self.config["tracked_items"]:
            if clean_query in item:
                target_item = item
                break

        if not target_item:
            return await utils.answer(message, self.strings("track_not_in_list").format(item=args))

        updated_list = [item for item in self.config["tracked_items"] if item != target_item]
        self.config["tracked_items"] = updated_list
        await utils.answer(message, self.strings("track_removed").format(item=target_item))

    async def mayorcmd(self, message: Message):
        """Fetch current active SkyBlock Mayor, perks, and live election breakdown"""
        text, markup = await self._build_mayor_card()
        if not text:
            return await utils.answer(message, self.strings("api_error"))

        await self.inline.form(
            message=message,
            text=text,
            reply_markup=markup,
        )

    async def _handle_refresh_mayor(self, call: BotInlineCall):
        text, markup = await self._build_mayor_card()
        if not text:
            return await call.answer(self.strings("api_error"), show_alert=True)
        await call.edit(text=text, reply_markup=markup)

    async def sbitemcmd(self, message: Message):
        """Look up stats, rarity, and details for any SkyBlock item"""
        query = utils.get_args_raw(message)
        if not query:
            return await utils.answer(message, self.strings("no_args"))

        items = await self._get_all_items()
        if not items:
            return await utils.answer(message, self.strings("api_error"))

        clean_q = query.strip().lower()
        matched_item = None

        for item in items:
            item_id = item.get("id", "").lower()
            name = self._strip_formatting(item.get("name", "")).lower()
            if clean_q == item_id or clean_q == name:
                matched_item = item
                break
            if clean_q in item_id or clean_q in name:
                matched_item = item

        if not matched_item:
            return await utils.answer(message, self.strings("not_found").format(query=query))

        name = self._strip_formatting(matched_item.get("name", matched_item.get("id", "Unknown")))
        item_id = matched_item.get("id", "UNKNOWN")
        tier = matched_item.get("tier", "COMMON")
        category = matched_item.get("category", "MISC")
        npc_price = matched_item.get("npc_sell_price", 0)

        stats_data = matched_item.get("stats", {})
        stats_lines = ""
        if stats_data:
            stats_formatted = [
                f"  - {k.replace('_', ' ').title()}: <code>+{v}</code>"
                for k, v in stats_data.items()
            ]
            stats_lines = self.strings("base_stats_header") + "\n".join(stats_formatted) + "\n"

        extra_info = ""
        if matched_item.get("glowing", False):
            extra_info += self.strings("enchanted_glint")
        if matched_item.get("dungeon_item", False):
            extra_info += self.strings("dungeon_item_tag")

        text = self.strings("item_card").format(
            name=name,
            item_id=item_id,
            tier=tier,
            category=category,
            stats=stats_lines,
            npc_price=f"{npc_price:,.1f}" if npc_price else self.strings("not_for_sale"),
            coins_unit=self.strings("coins_unit"),
            extra_info=extra_info,
        )

        await utils.answer(message, text)

    async def sbeventscmd(self, message: Message):
        """Show current SkyBlock date and upcoming global event timers"""
        text, markup = self._build_events_card()
        await self.inline.form(
            message=message,
            text=text,
            reply_markup=markup,
        )

    async def _handle_refresh_events(self, call: BotInlineCall):
        text, markup = self._build_events_card()
        await call.edit(text=text, reply_markup=markup)

    async def sbfiresalecmd(self, message: Message):
        """List active and upcoming cosmetic Firesales"""
        text, markup = await self._build_firesale_card()
        if not text:
            return await utils.answer(message, self.strings("api_error"))

        if not markup:
            return await utils.answer(message, text)

        await self.inline.form(
            message=message,
            text=text,
            reply_markup=markup,
        )

    async def _handle_refresh_firesale(self, call: BotInlineCall):
        text, markup = await self._build_firesale_card()
        if not text:
            return await call.answer(self.strings("api_error"), show_alert=True)
        await call.edit(text=text, reply_markup=markup)

    async def sbahcmd(self, message: Message):
        """Search active Auction House lots and lowest BIN prices"""
        query = utils.get_args_raw(message)
        if not query:
            return await utils.answer(message, self.strings("no_args"))

        auctions = await self._fetch_auctions()
        if not auctions:
            return await utils.answer(message, self.strings("api_error"))

        clean_q = query.strip().lower()
        matched = []

        for auc in auctions:
            item_name = self._strip_formatting(auc.get("item_name", "")).lower()
            if clean_q in item_name and auc.get("bin", False):
                matched.append(auc)

        if not matched:
            return await utils.answer(message, self.strings("ah_empty").format(query=query))

        matched.sort(key=lambda x: x.get("starting_bid", 0))
        text, markup = self._build_ah_card(query, matched)

        await self.inline.form(
            message=message,
            text=text,
            reply_markup=markup,
        )

    async def _handle_refresh_ah(self, call: BotInlineCall, query: str):
        auctions = await self._fetch_auctions()
        if not auctions:
            return await call.answer(self.strings("api_error"), show_alert=True)

        clean_q = query.strip().lower()
        matched = []

        for auc in auctions:
            item_name = self._strip_formatting(auc.get("item_name", "")).lower()
            if clean_q in item_name and auc.get("bin", False):
                matched.append(auc)

        if not matched:
            return await call.edit(self.strings("ah_empty").format(query=query))

        matched.sort(key=lambda x: x.get("starting_bid", 0))
        text, markup = self._build_ah_card(query, matched)
        await call.edit(text=text, reply_markup=markup)

    async def sbkatcmd(self, message: Message):
        """Display all Kat pet rarity upgrade costs and base durations"""
        coins_unit = self.strings("coins_unit")
        lines = [
            f"• <b>{tier}</b>:\n  - <code>{data['coins']:,}</code> {coins_unit} | <code>{data['time']}</code>"
            for tier, data in KAT_TIERS.items()
        ]
        text = self.strings("kat_card").format(tiers="\n".join(lines))
        await utils.answer(message, text)

    async def sbexpcmd(self, message: Message):
        """Calculate cumulative skill XP requirement for any level from 1 to 60"""
        args = utils.get_args_raw(message)
        if not args or not args.strip().isdigit():
            return await utils.answer(message, self.strings("exp_invalid"))

        lvl = int(args.strip())
        match (1 <= lvl <= 60):
            case True:
                pass
            case _:
                return await utils.answer(message, self.strings("exp_invalid"))

        total_exp = SKILL_EXP_TABLE[lvl]
        diff_exp = total_exp - SKILL_EXP_TABLE[lvl - 1]

        text = self.strings("exp_card").format(
            target_lvl=lvl,
            prev_lvl=lvl - 1,
            total_exp=total_exp,
            diff_exp=diff_exp,
        )

        await utils.answer(message, text)
