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
        custom_text = "🌘 Community-made modules\n💭 @hikarimods\n🦋 @morisummermods\n💚 @nalinormods\n🤩 @AstroModules\n🌚 @vsecoder_m\n☺️ @mm_mods\n😈 @apodiktum_modules\n😇 @wilsonmods\n👑 @DorotoroMods\n✌️ @HikkaFTGmods\n🎈 @nercymods\n🎄 @hikka_mods\n☀️ @sqlmerr_m"
        await m.edit(custom_text)
