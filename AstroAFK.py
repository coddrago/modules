__version__ = (2, 1, 7)
# 	
# 	 @@@@@@    @@@@@@   @@@@@@@  @@@@@@@    @@@@@@   @@@@@@@@@@    @@@@@@   @@@@@@@   @@@  @@@  @@@       @@@@@@@@   @@@@@@
# 	@@@@@@@@  @@@@@@@   @@@@@@@  @@@@@@@@  @@@@@@@@  @@@@@@@@@@@  @@@@@@@@  @@@@@@@@  @@@  @@@  @@@       @@@@@@@@  @@@@@@@
# 	@@!  @@@  !@@         @@!    @@!  @@@  @@!  @@@  @@! @@! @@!  @@!  @@@  @@!  @@@  @@!  @@@  @@!       @@!       !@@
# 	!@!  @!@  !@!         !@!    !@!  @!@  !@!  @!@  !@! !@! !@!  !@!  @!@  !@!  @!@  !@!  @!@  !@!       !@!       !@!
# 	@!@!@!@!  !!@@!!      @!!    @!@!!@!   @!@  !@!  @!! !!@ @!@  @!@  !@!  @!@  !@!  @!@  !@!  @!!       @!!!:!    !!@@!!
# 	!!!@!!!!   !!@!!!     !!!    !!@!@!    !@!  !!!  !@!   ! !@!  !@!  !!!  !@!  !!!  !@!  !!!  !!!       !!!!!:     !!@!!!
# 	!!:  !!!       !:!    !!:    !!: :!!   !!:  !!!  !!:     !!:  !!:  !!!  !!:  !!!  !!:  !!!  !!:       !!:            !:!
# 	:!:  !:!      !:!     :!:    :!:  !:!  :!:  !:!  :!:     :!:  :!:  !:!  :!:  !:!  :!:  !:!   :!:      :!:           !:!
# 	::   :::  :::: ::      ::    ::   :::  ::::: ::  :::     ::   ::::: ::   :::: ::  ::::: ::   :: ::::   :: ::::  :::: ::
# 	 :   : :  :: : :       :      :   : :   : :  :    :      :     : :  :   :: :  :    : :  :   : :: : :  : :: ::   :: : :
# 	
#                                             © Copyright 2023
#
#                                    https://t.me/Den4ikSuperOstryyPer4ik
#                                                  and
#                                          https://t.me/ToXicUse
#
#                                    🔒 Licensed under the GNU AGPLv3
#                                 https://www.gnu.org/licenses/agpl-3.0.html
#
# meta banner: https://0x0.st/oFwG.jpg                                                                                            
# meta developer: @AstroModules

import time
import datetime
import asyncio
from telethon import types
from .. import loader, utils
from ..inline.types import InlineCall
from telethon.tl.functions.users import GetFullUserRequest
from telethon.tl.functions.account import UpdateProfileRequest

class AstroAfkMod(loader.Module):
	'''Fully customizable module for going into AFK mode!'''

	async def client_ready(self, client, db):
		self._db = db
		self._me = await client.get_me()

	strings = {
		"name": "AstroAFK",

		"lname": "| afk.",

		"bt_off_afk": "<emoji document_id=5465665476971471368>❌</emoji> <b>AFK</b> mode has been successfully <b>turned off</b> !",

		"_cfg_cst_btn": "Link to the chat, which will be located under the AFK text. To remove it completely, write None",
		"feedback_bot__text": "Username of your feedback bot. If not, don't touch it",
		"button__text": "Add an inline button to disable AFK mode?",
		"custom_text__afk_text": "Custom afk text. Use {time} to display the last time you were online and {reason} to indicate the reason for leaving AFK",
	}

	def render_settings(self):
		'''Settings message'''

		active = self._db.get(__name__, 'afk')
		if active == True:
			a_active = "Включен ✅"
		else:
			a_active = 'Выключен 🚫'
		change_bio = self._db.get(__name__, 'change_bio')
		if change_bio == True:
			a_change_bio = 'Да'
		else:
			a_change_bio = 'Нет'
		change_name = self._db.get(__name__, 'change_name')
		if change_name == True:
			a_change_name = 'Да'
		else:
			a_change_name = 'Нет'
		fb = self.config['feedback']
		text = (
			f'🎆 <b>AstroAfk</b>\n'
			f'<b>├{a_active}</b>\n'
			f'<b>├Смена биографии:</b> <code>{a_change_bio}</code> 📖\n'
			f'<b>├Смена префикса:</b> <code>{a_change_name}</code> 📝\n'
			f'<b>└Бот для связи:</b> <code>@{fb}</code> 🤖'
		)
		return text


	def __init__(self):
		self.config = loader.ModuleConfig(
			loader.ConfigValue(
				"prefix",
				'| afk.',
				doc=lambda: 'Префикс, который будет добавляться к вашему имени во время входа в АФК'
			),
			loader.ConfigValue(
				"feedback",
				None,
				doc=lambda: self.strings("feedback_bot__text"),
			),
			loader.ConfigValue(
				'about_text',
				None,
				doc=lambda: 'Текст, который будет выставляться в био при входе в АФК. Используйте {bot} для указания фидбэк бота и {reason} для причины.'
			),
			loader.ConfigValue(
				"afk_text",
				"None",
				doc=lambda: self.strings("custom_text__afk_text"),
			),
			loader.ConfigValue(
				"link_button",
				None,
				lambda: self.strings("_cfg_cst_btn"),
				validator=loader.validators.Union(
					loader.validators.Series(fixed_len=2),
					loader.validators.NoneType()
				),
			),
			loader.ConfigValue(
				"ignore_chats",
				[],
				lambda: "Чаты, в которых AstroAfk не будет срабатывать",
				validator=loader.validators.Series(
                    validator=loader.validators.Union(
                        loader.validators.TelegramID(),
                        loader.validators.RegExp("[0-9]"),
                    ),
                ),
			),
			loader.ConfigValue(
				"button",
				True,
				doc=lambda: self.strings("button__text"),
				validator=loader.validators.Boolean(),
			)

		)

	def _afk_custom_text(self) -> str:
		'''Custom text afk'''

		now = datetime.datetime.now().replace(microsecond=0)
		gone = datetime.datetime.fromtimestamp(
			self._db.get(__name__, "gone")
		).replace(microsecond=0)

		time = now - gone
		reason = self._db.get(__name__, 'reason')

		return (
			"<b> </b>\n"
			+ self.config["afk_text"].format(
				time=time,
				reason=reason,
			)
		)

	def _afk_about_text(self) -> str:
		'''Custom text about'''

		bot = self.config['feedback']
		reason = self._db.get(__name__, 'reason')
		return (
			""
			+ self.config['about_text'].format(
				bot=bot,
				reason=reason
			)
		)

	@loader.command()
	async def asst(self, message):
		"""- open module settings """

		await self.inline.form(
			message=message, 
			text='<b>⚙️ Open settings</b>', 
			reply_markup=[{'text': '🔴 Open', 'callback': self.settings}],
			silent=True
		)

	@loader.command()
	async def goafk(self, message):
		""" <reason/empty> - enter AFK mode"""

		reason = utils.get_args_raw(message)
		if '-n' in reason:
			reason = reason.replace('-n', '')
			self._db.set(__name__, 'force', True)

		if not reason:
			self._db.set(__name__, 'reason', '­')
		else:
			self._db.set(__name__, 'reason', reason)
		try:
			user_id = (
				(
					(
						await self._client.get_entity(
							args if not args.isdigit() else int(args)
						)
					).id
				)
				if args
				else reply.sender_id
			)
		except Exception:
			user_id = self._tg_id
		user = await self._client(GetFullUserRequest(user_id))
		
		self._db.set(__name__, "afk", True)
		self._db.set(__name__, "gone", time.time())
		self._db.set(__name__, "ratelimit", [])
		change_bio = self._db.get(__name__, "change_bio")
		change_name = self._db.get(__name__, "change_name")
		
		about = user.full_user.about

		self._db.set(__name__, 'about', about)

		if change_name == True:
			prefix = self.config['prefix']
			await message.client(UpdateProfileRequest(last_name=prefix))

		if change_bio == True:
			cfg_bio = self.config['about_text']
			if cfg_bio == None:
				await message.client(UpdateProfileRequest(about="Нахожусь в афк."))
			else:
				bio = self._afk_about_text()
				await message.client(UpdateProfileRequest(about=bio))

		m = await utils.answer(message, '<emoji document_id=5188391205909569136>✅</emoji> <b>AFK</b> was successfully <b>enabled</b> !')
		await asyncio.sleep(5)
		await m.delete()
		

	@loader.command()
	async def ungoafk(self, message):
		"""- leave AFK mode"""

		self._db.set(__name__, "afk", False)
		self._db.set(__name__, "gone", None)
		self._db.set(__name__, "ratelimit", [])
		change_bio = self._db.get(__name__, "change_bio")
		change_name = self._db.get(__name__, "change_name")

		if self._db.get(__name__, 'force') == True:
			self._db.set(__name__, 'force', False)

		if change_name == True:
			await message.client(UpdateProfileRequest(last_name=' '))

		if change_bio == True:
			try:
				await message.client(UpdateProfileRequest(about=f'{self.db.get(__name__, "about")}'))
			except:
				await message.client(UpdateProfileRequest(about="@AstroOfftop - лучший чат для общения."))
		m = await utils.answer(message, '<emoji document_id=5465665476971471368>❌</emoji> <b>AFK</b> mode has been successfully <b>turned off</b> !')
		await self.allmodules.log("AstroAfk now stoped.")
		await asyncio.sleep(5)
		await m.delete()


	@loader.watcher()
	async def watcher(self, message):

		if not isinstance(message, types.Message):
			return

		if utils.get_chat_id(message) in self.config['ignore_chats']: 
			return

		if message.mentioned or getattr(message.to_id, "user_id", None) == self._me.id:
			afk_state = self.get_afk()
			if not afk_state:
				return

			ratelimit = self._db.get(__name__, "ratelimit", [])
			if utils.get_chat_id(message) in ratelimit:
				return
			else:
				self._db.setdefault(__name__, {}).setdefault("ratelimit", []).append(
					utils.get_chat_id(message)
				)
				self._db.save()
			user = await utils.get_user(message)

			if user.is_self or user.bot or user.verified:
				return

			if self.get_afk() is False:
				return

			now = datetime.datetime.now().replace(microsecond=0)
			gone = datetime.datetime.fromtimestamp(
				self._db.get(__name__, "gone")
			).replace(microsecond=0)

			time = now - gone
			reason = self._db.get(__name__, 'reason')
			if self._db.get(__name__, 'force') == False:
				if self.config['link_button'] == None:
					if self.config["button"] == False:
						if self.config["afk_text"] == None:
							await self.inline.form(
								message=message, 
								text=f"<emoji document_id=5372923973271034075>😴</emoji> I'm in AFK mode now\n<emoji document_id=5841359499146825803>⌨️</emoji> Was online: {time} ago.\n<emoji document_id=4974551780743447211>🛑</emoji> Left for the reason: {reason}", 
								reply_markup=[
									{
										'text': '🚫 Close', 
										'callback': self.callback_handler_ok,
										"args": (message.chat.id,)
									}
								],
								silent=True
							)
						else:
							await self.inline.form(
								message=message, 
								text=self._afk_custom_text(), 
								reply_markup=[
									{
										'text': '🚫 Close', 
										'callback': self.callback_handler_ok,
										"args": (message.chat.id, )
									}
								],
								silent=True
							)
					
					elif self.config['button'] == True:
						if self.config["afk_text"] == None:
							await self.inline.form(
								message=message, 
								text=f"<emoji document_id=5372923973271034075>😴</emoji> I'm in AFK mode now\n<emoji document_id=5841359499146825803>⌨️</emoji> Was online: {time} ago.\n<emoji document_id=4974551780743447211>🛑</emoji> Left for the reason: {reason}", 
								reply_markup=[
									[
										{
											"text": "🥱 Выйти из АФК", 
											"callback": self.button_cancel,
										}
									],
									[
	            						{
	                      					'text': '🚫 Close', 
											'callback': self.callback_handler_ok,
											"args": (message.chat.id,)
	          							}
	                  				]
								],
								silent=True
							)

						else:
							await self.inline.form(
								message=message, 
								text=self._afk_custom_text(), 
								reply_markup=[
									[
										{
											"text": "🥱 Выйти из АФК", 
											"callback": self.button_cancel,
										}
									],
									[
	            						{
	                      					'text': '🚫 Close', 
											'callback': self.callback_handler_ok,
											"args": (message.chat.id,)
	          							}
	                  				]
								],
								silent=True
							)
				else:
					if self.config["button"] == False:
						if self.config["afk_text"] == None:
							await self.inline.form(
								message=message, 
								text=f"<emoji document_id=5372923973271034075>😴</emoji> I'm in AFK mode now\n<emoji document_id=5841359499146825803>⌨️</emoji> Was online: {time} ago.\n<emoji document_id=4974551780743447211>🛑</emoji> Left for the reason: {reason}",
								reply_markup=[
									[
										{
											"text": self.config['link_button'][0], 
											"url": self.config['link_button'][1]
										}
									],
									[
	            						{
	                      					'text': '🚫 Close', 
											'callback': self.callback_handler_ok,
											"args": (message.chat.id, )
	          							}
	                  				]
								],
								silent=True
							)
						else:
							await self.inline.form(
								message=message, 
								text=self._afk_custom_text(), 
								reply_markup=[
									[
										{
											"text": self.config['link_button'][0], 
											"url": self.config['link_button'][1]
										}
									],
									[
	            						{
	                      					'text': '🚫 Close', 
											'callback': self.callback_handler_ok,
											"args": (message.chat.id,)
	          							}
	                  				]
								],
								silent=True
							)
					
					elif self.config['button'] == True:
						if self.config["afk_text"] == None:
							await self.inline.form(
								message=message, 
								text=f"<emoji document_id=5372923973271034075>😴</emoji> I'm in AFK mode now\n<emoji document_id=5841359499146825803>⌨️</emoji> Was online: {time} ago.\n<emoji document_id=4974551780743447211>🛑</emoji> Left for the reason: {reason}", 
								reply_markup=[
									[
										{
											"text": self.config['link_button'][0],
											"url": self.config['link_button'][1],
										}
									],
									[
										{
											"text": "🥱 Выйти из АФК", 
											"callback": self.button_cancel,
										}
									],
									[
	            						{
	                      					'text': '🚫 Close', 
											'callback': self.callback_handler_ok,
											"args": (message.chat.id,)
	          							}
	                  				]
								],
								silent=True
							)

						else:
							await self.inline.form(
								message=message, 
								text=self._afk_custom_text(), 
								reply_markup=[
									[
										{
											"text": self.config['link_button'][0],
											"url": self.config['link_button'][1],
										}
									],
									[
										{
											"text": "🥱 Выйти из АФК", 
											"callback": self.button_cancel,
										}
									],
									[
	            						{
	                      					'text': '🚫 Close', 
											'callback': self.callback_handler_ok,
											"args": (message.chat.id,)
	          							}
	                  				]
								],
								silent=True
							)
			else:
				if self.config["afk_text"] == None:
					await utils.answer(
						message,
						(
							"<emoji document_id=5372923973271034075>😴</emoji> I'm in <b>AFK</b> mode now\n"
							f"<emoji document_id=5841359499146825803>⌨️</emoji> Was <b>online</b>: <code>{time}"
							"</code> ago.\n<emoji document_id=4974551780743447211>🛑</emoji> Leave for <b>reason:"
							f"</b> {reason}"
						)
					)
				else:
					await utils.answer(message, self._afk_custom_text())

	async def button_cancel(self, call: InlineCall):
		'''Callback button'''

		self._db.set(__name__, "afk", False)
		self._db.set(__name__, "gone", None)
		self._db.set(__name__, "ratelimit", [])
		change_bio = self._db.get(__name__, "change_bio")
		change_name = self._db.get(__name__, "change_name")
		await self.allmodules.log("TxAFК now not working.")

		if change_name == False and change_bio == False:
			await call.edit(self.strings["bt_off_afk"])
			return

		if change_name == True:
			await self._client(UpdateProfileRequest(last_name=' '))

		if change_bio == True:
			try:
				await self._client(UpdateProfileRequest(about=self.db.get(__name__, "about")))
			except:
				await self._.client(UpdateProfileRequest(about="@AstroOfftop - лучший чат для общения."))

		await call.edit(self.strings["bt_off_afk"])

	async def settings(self, call: InlineCall):
		'''Callback button'''

		info = self.render_settings()
		await call.edit(
			text=info,
			reply_markup=[
				[
					{
						'text': "📖 Биография",
						'callback': self.settings_about
					},
					{
						'text': '📝 Префикс',
						'callback': self.settings_name
					}
				],
				[
					{
						"text": "🚫 Close",
						"action": 'close'
					}
				]
			]
		)

	async def settings_name(self, call: InlineCall):
		'''Callback button'''
		
		await call.edit(
			text=(
				f'<b>📖 Установка префикса</b>\n\n'
				+ '<i>❔ Хотите ли Вы, чтобы при входе в АФК режим к вашему '
				+ 'нику добавлялся префикс <code>| afk.</code> ?</i>\n\n'
				+ 'ℹ️ Так же Вы можете <b>изменить префикс</b>, '
				+ '<b>отменить</b> или <b>сделать</b> действие, нажав на <b>кнопки ниже</b>'
			),
			reply_markup=[
				[
					{
						'text': '✅ Да',
						"callback": self.name_yes
					},
					{
						"text": '🚫 Нет',
						"callback": self.name_no
					}
				],
				[{'text': '↩️ Назад', 'callback': self.settings}]
			]
		)
	async def name_yes(self, call: InlineCall):
		'''Callback button'''

		self._db.set(__name__, 'change_name', True)
		info = self.render_settings()
		await call.edit(
			text=info,
			reply_markup=[
				[
					{
						'text': "📖 Биография",
						'callback': self.settings_about
					},
					{
						'text': '📝 Префикс',
						'callback': self.settings_name
					}
				],
				[
					{
						"text": "🚫 Close",
						"action": 'close'
					}
				]
			]
		)
	async def name_no(self, call: InlineCall):
		'''Callback button'''
		
		self._db.set(__name__, 'change_name', False)
		info = self.render_settings()
		await call.edit(
			text=info,
			reply_markup=[
				[
					{
						'text': "📖 Биография",
						'callback': self.settings_about
					},
					{
						'text': '📝 Префикс',
						'callback': self.settings_name
					}
				],
				[
					{
						"text": "🚫 Close",
						"action": 'close'
					}
				]
			]
		)
	async def settings_about(self, call: InlineCall):
		'''Callback button'''
		
		if self.config['feedback'] == None:
			text = (
				f'📖 <b>Смена биографии</b>'
				+ '\n\n❔ <b>Хотите</b> ли Вы, чтобы при <b>входе в АФК</b> режим Ваша биография <b>менялась</b>'
				+ '  на "<code>Нахожусь в афк</code>"?\n\n'
				+ 'ℹ️ Так же Вы можете <b>изменить биографию</b> в <b>конфиге</b>. '
				+ 'Можно <b>отменить</b> или <b>сделать</b> действие, нажав на <b>кнопки ниже</b>'
			)
		else:
			text = (
				f'📖 <b>Смена биографии</b>'
				+ '\n\n❔ <b>Хотите</b> ли Вы, чтобы при <b>входе в АФК</b> режим '
				+ 'Ваша биография <b>менялась</b> на  "<code>Нет, на месте нахожусь в афк</code><code>.'
				+ f' Связь только через @{self.config["feedback"]}</code>"?\n🤖 <b>Бот для связи</b>: <code>@{self.config["feedback"]}</code>\n\n'
				+ 'ℹ️ Так же Вы можете <b>изменить биографию</b> в <b>конфиге</b>. '
				+ 'Можно <b>отменить</b> или <b>сделать</b> действие, нажав на <b>кнопки ниже</b>'
			)
		await call.edit(
			text=text,
			reply_markup=[
				[
					{
						'text': '✅ Да',
						"callback": self.bio
					},
					{
						"text": '🚫 Нет',
						"callback": self.bio_n
					}
				],
				[{'text': '↩️ Назад', 'callback': self.settings}]
			]
		)
	async def bio(self, call: InlineCall):
		'''Callback button'''
		
		self._db.set(__name__, 'change_bio', True)
		info = self.render_settings()
		await call.edit(
			text=info,
			reply_markup=[
				[
					{
						'text': "📖 Биография",
						'callback': self.settings_about
					},
					{
						'text': '📝 Префикс',
						'callback': self.settings_name
					}
				],
				[
					{
						"text": "🚫 Закрыть",
						"action": 'close'
					}
				]
			]
		)
	async def bio_n(self, call: InlineCall):
		'''Callback button'''
		
		self._db.set(__name__, 'change_bio', False)
		info = self.render_settings()
		await call.edit(
			text=info,
			reply_markup=[
				[
					{
						'text': "📖 Биография",
						'callback': self.settings_about
					},
					{
						'text': '📝 Префикс',
						'callback': self.settings_name
					}
				],
				[
					{
						"text": "🚫 Закрыть",
						"action": 'close'
					}
				]
			]
		)

	async def callback_handler_ok(self, call, chat_id: int):
		'''Callback button'''
		
		await call.delete()
		limit: list = self._db.get(__name__, 'ratelimit', [])
		limit.remove(chat_id)
		self._db.set(__name__, 'ratelimit', limit)
	
	def get_afk(self):
		return self._db.get(__name__, "afk", False)
