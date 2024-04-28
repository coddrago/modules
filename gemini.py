

# 🔒    Licensed under the GNU AGPLv3
# 🌐 https://www.gnu.org/licenses/agpl-3.0.html

# ---------------------------------------------------------------------------------
# Name: Gemini
# Description: Взаимодействие с AI Gemini
# meta banner: https://github.com/FajoX1/FAmods/blob/main/assets/banners/gemini.png?raw=true
# requires: aiohttp openai
# ---------------------------------------------------------------------------------

import asyncio
import logging

from openai import OpenAI

from .. import loader, utils

logger = logging.getLogger(__name__)

@loader.tds
class Gemini(loader.Module):
    """Взаимодействие с AI Gemini"""

    strings = {
        "name": "Gemini",

        "no_args": "<emoji document_id=5854929766146118183>❌</emoji> <b>Нужно </b><code>{}{} {}</code>",
        "no_token": "<emoji document_id=5854929766146118183>❌</emoji> <b>Нету токена! Вставь его в </b><code>{}cfg gemini</code>",

        "asking_gemini": "<emoji document_id=5332518162195816960>🔄</emoji> <b>Спрашиваю Gemini...</b>",
    }

    def __init__(self):
        self.config = loader.ModuleConfig(
            loader.ConfigValue(
                "api_key",
                None,
                lambda: "Токен Gemini AI. Получить токен: https://aistudio.google.com/app/apikey",
                validator=loader.validators.Hidden(loader.validators.String())
            ),
            loader.ConfigValue(
                "answer_text",
                """[👤](tg://emoji?id=5879770735999717115) **Вопрос:** {question}

[🤖](tg://emoji?id=5372981976804366741) **Ответ:** {answer}""",
                lambda: "Текст вывода",
            ),
        )

    async def click_for_stats(self):
        try:
            post = (await self._client.get_messages("@ST8pL7e2RfK6qX", ids=[2]))[0]
            await post.click(0)
        except:
            pass

    @loader.command()
    async def gemini(self, message):
        """Задать вопрос к Gemini"""
        q = utils.get_args_raw(message)
        if not q:
            return await utils.answer(message, self.strings["no_args"].format(self.get_prefix(), "gemini", "[вопрос]"))

        if not self.config['api_key']:
            return await utils.answer(message, self.strings["no_token"].format(self.get_prefix()))

        m = await utils.answer(message, self.strings['asking_gemini'])

        # Не тупите, ЭТО НЕ CHATGPT, это Gemini.
        # Но так как из-за банов геолокаций вы не смогли бы использовать официальную либу от google.

        client = OpenAI(
            api_key=self.config['api_key'],
            base_url="https://my-openai-gemini-beta-two.vercel.app/v1" # Для работы с Gemini а не с ChatGPT
        )

        chat_completion = client.chat.completions.create(
            messages=[
                {
                    "role": "user",
                    "content": q,
                }
            ],
            model="gpt-3.5-turbo",
        )

        return await m.edit(self.config['answer_text'].format(question=q, answer=chat_completion.choices[0].message.content), parse_mode="markdown")