# meta developer: @codrago

from hikkatl.types import Message

from .. import loader, utils


@loader.tds
class ModulesList(loader.Module):
    """Модуль для быстрого доступа к каналам с модулями"""

    strings = {"name": "ModulesList", "example": "Модуль для личного использования."}
    strings_ru = {"example": "Модуль для быстрого доступа к каналам с модулями"}

    @loader.command(alias="moduleslist", ru_doc="| Быстрый доступ к каналам с модулями ")
    async def modlist(self, m: Message):
        """| quick access to channels with modules"""
        custom_text = "<emoji document_id=5188377234380954537>🌘</emoji> Community-made modules\n<emoji document_id=5370547013815376328>😶‍🌫️</emoji> @hikarimods\n<emoji document_id=5445096582238181549>🦋</emoji> @morisummermods\n<emoji document_id=5449380056201697322>💚</emoji> @nalinormods\n<emoji document_id=5373026167722876724>🤩</emoji> @AstroModules\n<emoji document_id=5249042457731024510>💪</emoji> @vsecoder_m\n<emoji document_id=5371037748188683677>☺️</emoji> @mm_mods\n<emoji document_id=5370856741086960948>😈</emoji> @apodiktum_modules\n<emoji document_id=5370947515220761242>😇</emoji> @wilsonmods\n<emoji document_id=5467406098367521267>👑</emoji> @DorotoroMods\n<emoji document_id=5469986291380657759>✌️</emoji> @HikkaFTGmods\n<emoji document_id=5472091323571903308>🎈</emoji> @nercymods\n<emoji document_id=5789790449594011537>🎈</emoji> @hikka_mods\n<emoji document_id=5298799263013151249>😐</emoji> @sqlmerr_m\n<emoji document_id=5296274178725396201>🥰</emoji> @AuroraModules\n<emoji document_id=5366217837104872614>⭐️</emoji> @shadow_modules\n<emoji document_id=5373141891321699086>😎</emoji> @famods"
        await m.edit(custom_text)
