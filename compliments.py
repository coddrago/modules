# ---------------------------------------------------------------------------------
#░█▀▄░▄▀▀▄░█▀▄░█▀▀▄░█▀▀▄░█▀▀▀░▄▀▀▄░░░█▀▄▀█
#░█░░░█░░█░█░█░█▄▄▀░█▄▄█░█░▀▄░█░░█░░░█░▀░█
#░▀▀▀░░▀▀░░▀▀░░▀░▀▀░▀░░▀░▀▀▀▀░░▀▀░░░░▀░░▒▀
# Name: Compliments
# Description: Compliments for your partner
# Author: @codrago_m
# ---------------------------------------------------------------------------------
# 🔒    Licensed under the GNU AGPLv3
# 🌐 https://www.gnu.org/licenses/agpl-3.0.html
# ---------------------------------------------------------------------------------
# Author: @codrago
# Commands: cg
# scope: hikka_only
# meta developer: @codrago_m
# ---------------------------------------------------------------------------------

__version__ = (1, 0, 0)

from .. import loader, utils
import asyncio

@loader.tds
class Compliments(loader.Module):
    """Compliments for your partner"""
    strings = {
    "name": "Compliments",
    "speed_cfg": "Delay between edits"
    }
    
    def __init__(self):
        self.config = loader.ModuleConfig(
            loader.ConfigValue(
                "speed",
                2,
                lambda: self.strings["speed_cfg"],
            ),
        )
    
    
    async def cgcmd(self, message):
        """Compliments for girl"""
        
        await utils.answer(message, "❤ | Знаешь..")
        await asyncio.sleep(self.config["speed"])
        await message.edit("❤ | Я всегда хотел тебе сказать, что...")
        await asyncio.sleep(self.config["speed"])
        await message.edit("❤ | 1. Ты прекрасна!")
        await asyncio.sleep(self.config["speed"])
        await message.edit("❤ | 2. Ты замечательна!")
        await asyncio.sleep(self.config["speed"])
        await message.edit("❤ | 3. Ты любимая!")
        await asyncio.sleep(self.config["speed"])
        await message.edit("❤ | 4. Ты желанная!")
        await asyncio.sleep(self.config["speed"])
        await message.edit("❤ | 5. Ты лучшая!")
        await asyncio.sleep(self.config["speed"])
        await message.edit("❤ | 6. Ты – дар, который нужно ценить.")
        await asyncio.sleep(self.config["speed"])
        await message.edit("❤ | 7. Ты – настоящая находка в этом мире.")
        await asyncio.sleep(self.config["speed"])
        await message.edit("❤ | 8. Ты – как весенний день, полный надежды.")
        await asyncio.sleep(self.config["speed"])
        await message.edit("❤ | 9. С тобой всегда интересно провести время.")
        await asyncio.sleep(self.config["speed"])
        await message.edit("❤ | 10. Ты умеешь делать даже обыденные вещи особенными.")
        await asyncio.sleep(self.config["speed"])
        await message.edit("❤ | 11. Твой смех – это музыка для ушей.")
        await asyncio.sleep(self.config["speed"])
        await message.edit("❤ | 12. Ты делаешь меня счастливым.")
        await asyncio.sleep(self.config["speed"])
        await message.edit("❤ | 13. Ты освещаешь даже самые серые дни.")
        await asyncio.sleep(self.config["speed"])
        await message.edit("❤ | 14. Твоя поддержка для меня очень важна.")
        await asyncio.sleep(self.config["speed"])
        await message.edit("❤ | 15. Ты пример для подражания.")
        await asyncio.sleep(self.config["speed"])
        await message.edit("❤ | 16. Ты понимаешь меня так, как никто другой.")
        await asyncio.sleep(self.config["speed"])
        await message.edit("❤ | 17. Ты – знаешь, как поддерживать в трудную минуту.")
        await asyncio.sleep(self.config["speed"])
        await message.edit("❤ | 18. Ты создаешь уют вокруг себя.")
        await asyncio.sleep(self.config["speed"])
        await message.edit("❤ | 19. Ты светишься, как звезда.")
        await asyncio.sleep(self.config["speed"])
        await message.edit("❤ | 20. Ты наполняешь каждый день смыслом.")
        await asyncio.sleep(self.config["speed"])
        await message.edit("❤ | 21. Ты — лучик света в пасмурный день.")
        await asyncio.sleep(self.config["speed"])
        await message.edit("❤ | 22. У тебя потрясающее чувство вкуса.")
        await asyncio.sleep(self.config["speed"])
        await message.edit("❤ | 23. Улыбка — твое самое красивое оружие.")
        await asyncio.sleep(self.config["speed"])
        await message.edit("❤ | 24. Ты — редкость в этом мире.")
        await asyncio.sleep(self.config["speed"])
        await message.edit("❤ | 25. Ты — самый яркий момент моего дня.")
        await asyncio.sleep(self.config["speed"])
        await message.edit("❤ | 26. Ты словно весна после зимы.")
        await asyncio.sleep(self.config["speed"])
        await message.edit("❤ | 27. Твоё чувство юмора — настоящее сокровище.")
        await asyncio.sleep(self.config["speed"])
        await message.edit("❤ | 28. Ты — истинная красота.")
        await asyncio.sleep(self.config["speed"])
        await message.edit("❤ | 29. Твои достижения впечатляют.")
        await asyncio.sleep(self.config["speed"])
        await message.edit("❤ | 30. Тебя легко любить.")
        await asyncio.sleep(self.config["speed"])
        await message.edit("❤ | 31. Ты — счастье в человеческом обличье.")
        await asyncio.sleep(self.config["speed"])
        await message.edit("❤ | 32. В тебе так много внутреннего света.")
        await asyncio.sleep(self.config["speed"])
        await message.edit("❤ | 33. Каждый разговор с тобой запоминается.")
        await asyncio.sleep(self.config["speed"])
        await message.edit("❤ | 34. У тебя невероятная сила характера.")
        await asyncio.sleep(self.config["speed"])
        await message.edit("❤ | 35. Ты вдохновляешь меня становиться лучше.")
        await asyncio.sleep(self.config["speed"])
        await message.edit("❤ | 36. Твоё обаяние просто нельзя игнорировать.")
        await asyncio.sleep(self.config["speed"])
        await message.edit("❤ | 37. Ты — победитель по жизни.")
        await asyncio.sleep(self.config["speed"])
        await message.edit("❤ | 38. Ты – словно поэма, полная эмоций.")
        await asyncio.sleep(self.config["speed"])
        await message.edit("❤ | 39. Ты создаёшь уютную атмосферу, куда бы ни шла.")
        await asyncio.sleep(self.config["speed"])
        await message.edit("❤ | 40. Ты стойка и непоколебима в сложные времена.")
        await asyncio.sleep(self.config["speed"])
        await message.edit("❤ | 41. Ты — положительный пример для всех нас.")
        await asyncio.sleep(self.config["speed"])
        await message.edit("❤ | 42. Твой характер прекрасен, как музыка арфы.")
        await asyncio.sleep(self.config["speed"])
        await message.edit("❤ | 43. Твои глаза прекрасны, как северное сияние.")
        await asyncio.sleep(self.config["speed"])
        await message.edit("❤ | 44. Ты – волшебница, делающая всё вокруг более ярким.")
        await asyncio.sleep(self.config["speed"])
        await message.edit("❤ | 45. Ты умеешь находить положительное даже в трудностях.")
        await asyncio.sleep(self.config["speed"])
        await message.edit("❤ | 46. Ты уникальна и неповторима.")
        await asyncio.sleep(self.config["speed"])
        await message.edit("❤ | 47. Твоя креативность вдохновляет на свершения.")
        await asyncio.sleep(self.config["speed"])
        await message.edit("❤ | 48. У тебя потрясающий талант к общению.")
        await asyncio.sleep(self.config["speed"])
        await message.edit("❤ | 49. Ты красива, даже когда не стараешься.")
        await asyncio.sleep(self.config["speed"])
        await message.edit("❤ | 50. У тебя есть дар — делать людей счастливыми. ")
        await asyncio.sleep(self.config["speed"])
        await message.edit("❤ | 51. Ты — олицетворение красоты.")
        await asyncio.sleep(self.config["speed"])
        await message.edit("❤ | 52. Ты обладаешь невероятной харизмой.")
        await asyncio.sleep(self.config["speed"])
        await message.edit("❤ | 53. Твои волосы выглядят великолепно.")
        await asyncio.sleep(self.config["speed"])
        await message.edit("❤ | 54. В твоем присутствии я чувствую себя комфортно.")
        await asyncio.sleep(self.config["speed"])
        await message.edit("❤ | 55. Ты — цветок в саду жизни.")
        await asyncio.sleep(self.config["speed"])
        await message.edit("❤ | 56. Ты — мечта, которая стала явью.")
        await asyncio.sleep(self.config["speed"])
        await message.edit("❤ | 57. Твоя энергия заряжает окружающих.")
        await asyncio.sleep(self.config["speed"])
        await message.edit("❤ | 58. Ты словно лучик солнца.")
        await asyncio.sleep(self.config["speed"])
        await message.edit("❤ | 59. Ты — невероятный человек.")
        await asyncio.sleep(self.config["speed"])
        await message.edit("❤ | 60. Ты умеешь видеть красоту в глупостях.")
        await asyncio.sleep(self.config["speed"])
        await message.edit("❤ | 61. Ты демонстрируешь мне невероятную смелость.")
        await asyncio.sleep(self.config["speed"])
        await message.edit("❤ | 62. Ты — источник вдохновения.")
        await asyncio.sleep(self.config["speed"])
        await message.edit("❤ | 63. Ты освещаешь каждый мой день, включая этот.")
        await asyncio.sleep(self.config["speed"])
        await message.edit("❤ | 64. Ты — загадка, которую интересно разгадать.")
        await asyncio.sleep(self.config["speed"])
        await message.edit("❤ | 65. Твои глаза как океан.")
        await asyncio.sleep(self.config["speed"])
        await message.edit("❤ | 66. Ты умеешь создавать уют.")
        await asyncio.sleep(self.config["speed"])
        await message.edit("❤ | 67. Ты — художник своей жизни.")
        await asyncio.sleep(self.config["speed"])
        await message.edit("❤ | 68. Ты даришь тепло и заботу.")
        await asyncio.sleep(self.config["speed"])
        await message.edit("❤ | 69. У тебя великолепный вкус в одежде.")
        await asyncio.sleep(self.config["speed"])
        await message.edit("❤ | 70. Ты — звезда в моем небе.")
        await asyncio.sleep(self.config["speed"])
        await message.edit("❤ | Моя любимая, все эти комплименты именно для тебя! Ведь... я люблю тебя. <emoji document_id=5287454910059654880>❤️</emoji>")
        
        
        
        