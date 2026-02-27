# meta developer: @codrago_m

import html
from .. import loader, utils


class DBMod(loader.Module):
    strings = {
        "name": "DBMod",
        "del_text": "<b>Database</b>\n\nSelect a key to view",
        "deleted": "🗑 Key {key} deleted",
        "deleted_all": "🗑 Deleted {count} keys",
        "close_btn": "❌ Close",
        "back_btn": "⬅ Back",
        "del_btn": "🗑 Delete",
        "del_all_btn": "❌ Delete all",
        "not_found": "🔍 Key {key} not found",
        "invalid_key": "⚠ Invalid key",
        "page": "📄 Page {current}/{total}",
        "module_not_found": "🔍 Module '{module}' not found in database",
        "confirm_delete": "⚠ Are you sure you want to delete this?",
        "view_path": "<b>Path: {path}</b>",
        "root_path": "Root",
        "value_display": "<b>Value:</b> <code>{value}</code>",
        "yes_btn": "✅ Yes",
        "no_btn": "❌ No",
        "list_item_display": "<b>List item [{index}]</b>",
    }

    strings_ru = {
        "del_text": "<b>База данных</b>\n\nВыберите ключ для просмотра",
        "deleted": "🗑 Ключ {key} удален",
        "deleted_all": "🗑 Удалено {count} ключей",
        "close_btn": "❌ Закрыть",
        "back_btn": "⬅ Назад",
        "del_btn": "🗑 Удалить",
        "del_all_btn": "❌ Удалить все",
        "not_found": "🔍 Ключ {key} не найден",
        "invalid_key": "⚠ Некорректный ключ",
        "page": "📄 Страница {current}/{total}",
        "module_not_found": "🔍 Модуль '{module}' не найден в базе данных",
        "confirm_delete": "⚠ Вы уверены, что хотите удалить это?",
        "view_path": "<b>Путь: {path}</b>",
        "root_path": "Корень",
        "value_display": "<b>Значение:</b> <code>{value}</code>",
        "yes_btn": "✅ Да",
        "no_btn": "❌ Нет",
        "list_item_display": "<b>Элемент списка [{index}]</b>",
    }

    async def client_ready(self):
        self.page_state = {}

    def _make_path_text(self, key_path):
        path = "/".join(map(str, key_path)) if key_path else self.strings["root_path"]
        return self.strings["view_path"].format(path=path)

    def _make_list_item_path_text(self, key_path, index):
        """Создает заголовок для элемента списка"""
        if key_path:
            path = "/".join(map(str, key_path)) + f"[{index}]"
        else:
            path = f"[{index}]"
        return self.strings["list_item_display"].format(index=index)

    async def show_menu(self, message, key_path=None, page=0):
        if key_path is None:
            key_path = []
        self.page_state[tuple(key_path)] = page

        current_data = self._db
        for key in key_path:
            if isinstance(current_data, (dict, list)):
                if isinstance(current_data, dict) and key in current_data:
                    current_data = current_data[key]
                elif (
                    isinstance(current_data, list)
                    and isinstance(key, int)
                    and 0 <= key < len(current_data)
                ):
                    current_data = current_data[key]
                else:
                    await utils.answer(message, self.strings["invalid_key"])
                    return
            else:
                await utils.answer(message, self.strings["invalid_key"])
                return

        header = self._make_path_text(key_path)

        if isinstance(current_data, (dict, list)) and current_data:
            markup = self.generate_nested_markup(current_data, key_path, page)
            await utils.answer(message, header, reply_markup=markup)
        else:
            text = f"{header}\n\n" + self.strings["value_display"].format(
                value=html.escape(str(current_data))
            )
            markup = self.generate_value_markup(key_path, page)
            await utils.answer(message, text, reply_markup=markup)

    async def navigate_db(self, call, key_path=None, page=0):
        if key_path is None:
            key_path = []
        self.page_state[tuple(key_path)] = page

        current_data = self._db
        for key in key_path:
            if isinstance(current_data, (dict, list)):
                if isinstance(current_data, dict) and key in current_data:
                    current_data = current_data[key]
                elif (
                    isinstance(current_data, list)
                    and isinstance(key, int)
                    and 0 <= key < len(current_data)
                ):
                    current_data = current_data[key]
                else:
                    await call.answer(self.strings["invalid_key"])
                    return
            else:
                await call.answer(self.strings["invalid_key"])
                return

        is_list_item = False
        if key_path:
            parent_data = self._db
            for key in key_path[:-1]:
                if isinstance(parent_data, (dict, list)):
                    if isinstance(parent_data, dict) and key in parent_data:
                        parent_data = parent_data[key]
                    elif (
                        isinstance(parent_data, list)
                        and isinstance(key, int)
                        and 0 <= key < len(parent_data)
                    ):
                        parent_data = parent_data[key]
                    else:
                        break

            if (
                isinstance(parent_data, list)
                and isinstance(key_path[-1], int)
                and 0 <= key_path[-1] < len(parent_data)
            ):
                is_list_item = True

        if is_list_item:
            header = self._make_list_item_path_text(key_path[:-1], key_path[-1])
            text = f"{header}\n\n" + self.strings["value_display"].format(
                value=html.escape(str(current_data))
            )
            await call.edit(
                text, reply_markup=self.generate_list_item_markup(key_path, page)
            )
        elif isinstance(current_data, (dict, list)) and current_data:
            header = self._make_path_text(key_path)
            await call.edit(
                header,
                reply_markup=self.generate_nested_markup(current_data, key_path, page),
            )
        else:
            header = self._make_path_text(key_path)
            text = f"{header}\n\n" + self.strings["value_display"].format(
                value=html.escape(str(current_data))
            )
            await call.edit(
                text, reply_markup=self.generate_value_markup(key_path, page)
            )

    def generate_nested_markup(self, data, key_path, page=0):
        if isinstance(data, list) and data:
            return self.generate_list_markup(data, key_path, page)

        items = list(data.items()) if isinstance(data, dict) else []
        items_per_page = 9
        total_pages = (len(items) + items_per_page - 1) // items_per_page
        start_idx = page * items_per_page
        end_idx = min(start_idx + items_per_page, len(items))
        page_items = items[start_idx:end_idx]

        markup = []
        row = []
        for i, (key, value) in enumerate(page_items):
            if i % 3 == 0 and row:
                markup.append(row)
                row = []
            row.append(
                {
                    "text": f"{key}",
                    "callback": self.navigate_db,
                    "args": [key_path + [key], 0],
                }
            )
        if row:
            markup.append(row)

        nav_buttons = []
        if key_path:
            parent_page = self.page_state.get(tuple(key_path[:-1]), 0)
            nav_buttons.append(
                {
                    "text": self.strings["back_btn"],
                    "callback": self.navigate_db,
                    "args": [key_path[:-1], parent_page],
                }
            )

        if total_pages > 1:
            if page > 0:
                nav_buttons.append(
                    {
                        "text": "◀️",
                        "callback": self.navigate_db,
                        "args": [key_path, page - 1],
                    }
                )
            nav_buttons.append(
                {
                    "text": self.strings["page"].format(
                        current=page + 1, total=total_pages
                    ),
                    "callback": self.navigate_db,
                    "args": [key_path, page],
                }
            )
            if page < total_pages - 1:
                nav_buttons.append(
                    {
                        "text": "▶️",
                        "callback": self.navigate_db,
                        "args": [key_path, page + 1],
                    }
                )
        if nav_buttons:
            markup.append(nav_buttons)

        if key_path:
            markup.append(
                [
                    {
                        "text": self.strings["del_all_btn"],
                        "callback": self.confirm_delete_all,
                        "style": "danger",
                        "args": [key_path],
                    }
                ]
            )

        if not key_path:
            markup.append([{"text": self.strings["close_btn"], "action": "close"}])
        return markup

    def generate_list_markup(self, data, key_path, page=0):
        """Генерирует разметку для списка, показывая элементы напрямую"""
        items_per_page = 9
        total_pages = (len(data) + items_per_page - 1) // items_per_page
        start_idx = page * items_per_page
        end_idx = min(start_idx + items_per_page, len(data))
        page_items = list(enumerate(data[start_idx:end_idx], start_idx))

        markup = []
        row = []
        for i, (index, value) in enumerate(page_items):
            if i % 3 == 0 and row:
                markup.append(row)
                row = []

            if isinstance(value, (dict, list)):
                btn_text = f"[{index}]"
            else:
                value_str = str(value)
                if len(value_str) > 10:
                    btn_text = f"{value_str[:10]}..."
                else:
                    btn_text = value_str

            row.append(
                {
                    "text": btn_text,
                    "callback": self.navigate_db,
                    "args": [key_path + [index], 0],
                }
            )
        if row:
            markup.append(row)

        nav_buttons = []
        if key_path:
            parent_page = self.page_state.get(tuple(key_path[:-1]), 0)
            nav_buttons.append(
                {
                    "text": self.strings["back_btn"],
                    "callback": self.navigate_db,
                    "style": "primary",
                    "args": [key_path[:-1], parent_page],
                }
            )

        if total_pages > 1:
            if page > 0:
                nav_buttons.append(
                    {
                        "text": "◀️",
                        "callback": self.navigate_db,
                        "args": [key_path, page - 1],
                    }
                )
            nav_buttons.append(
                {
                    "text": self.strings["page"].format(
                        current=page + 1, total=total_pages
                    ),
                    "callback": self.navigate_db,
                    "args": [key_path, page],
                }
            )
            if page < total_pages - 1:
                nav_buttons.append(
                    {
                        "text": "▶️",
                        "callback": self.navigate_db,
                        "args": [key_path, page + 1],
                    }
                )
        if nav_buttons:
            markup.append(nav_buttons)

        if key_path:
            markup.append(
                [
                    {
                        "text": self.strings["del_all_btn"],
                        "callback": self.confirm_delete_all,
                        "style": "danger",
                        "args": [key_path],
                    }
                ]
            )

        return markup

    def generate_list_item_markup(self, key_path, page=0):
        """Генерирует разметку для отдельного элемента списка"""
        parent_page = self.page_state.get(tuple(key_path[:-1]), 0)
        return [
            [
                {
                    "text": self.strings["del_btn"],
                    "callback": self.delete_key,
                    "styles": "danger",
                    "args": [key_path],
                }
            ],
            [
                {
                    "text": self.strings["back_btn"],
                    "style": "primary",
                    "callback": self.navigate_db,
                    "style": "primary",
                    "args": [key_path[:-1], parent_page],
                }
            ],
        ]

    def generate_value_markup(self, key_path, page=0):
        parent_page = self.page_state.get(tuple(key_path[:-1]), 0)
        return [
            [
                {
                    "text": self.strings["del_btn"],
                    "callback": self.delete_key,
                    "style": "danger",
                    "args": [key_path],
                }
            ],
            [
                {
                    "text": self.strings["back_btn"],
                    "callback": self.navigate_db,
                    "style": "primary",
                    "args": [key_path[:-1], parent_page],
                }
            ],
        ]

    async def confirm_delete_all(self, call, key_path):
        await call.edit(
            self.strings["confirm_delete"],
            reply_markup=[
                [
                    {
                        "text": self.strings["yes_btn"],
                        "callback": self.delete_all_keys,
                        "args": [key_path],
                    }
                ],
                [
                    {
                        "text": self.strings["no_btn"],
                        "callback": self.navigate_db,
                        "args": [
                            key_path,
                            self.page_state.get(tuple(key_path), 0),
                        ],
                    }
                ],
            ],
        )

    async def delete_all_keys(self, call, key_path):
        if not key_path:
            count = len(self._db)
            self._db.clear()
            self._db.save()
            await call.answer(self.strings["deleted_all"].format(count=count))
            await self.navigate_db(call, [], self.page_state.get((), 0))
        else:
            current = self._db
            for key in key_path[:-1]:
                if isinstance(current, (dict, list)):
                    if isinstance(current, dict) and key in current:
                        current = current[key]
                    elif (
                        isinstance(current, list)
                        and isinstance(key, int)
                        and 0 <= key < len(current)
                    ):
                        current = current[key]
                    else:
                        await call.answer(
                            self.strings["not_found"].format(key=key_path[-1])
                        )
                        return

            if isinstance(current, (dict, list)) and key_path[-1] in current:
                if isinstance(current[key_path[-1]], (dict, list)):
                    count = len(current[key_path[-1]])
                else:
                    count = 1
                del current[key_path[-1]]
                self._db.save()
                await call.answer(self.strings["deleted_all"].format(count=count))
                await self.navigate_db(
                    call,
                    key_path[:-1],
                    self.page_state.get(tuple(key_path[:-1]), 0),
                )
            else:
                await call.answer(self.strings["not_found"].format(key=key_path[-1]))

    async def delete_key(self, call, key_path):
        parent_page = self.page_state.get(tuple(key_path[:-1]), 0)

        if len(key_path) == 1:
            if key_path[0] in self._db:
                del self._db[key_path[0]]
                self._db.save()
                await call.answer(self.strings["deleted"].format(key=key_path[0]))
                await self.navigate_db(call, [], parent_page)
            else:
                await call.answer(self.strings["not_found"].format(key=key_path[0]))
        else:
            current = self._db
            for key in key_path[:-1]:
                if isinstance(current, (dict, list)):
                    if isinstance(current, dict) and key in current:
                        current = current[key]
                    elif (
                        isinstance(current, list)
                        and isinstance(key, int)
                        and 0 <= key < len(current)
                    ):
                        current = current[key]
                    else:
                        await call.answer(
                            self.strings["not_found"].format(key=key_path[-1])
                        )
                        return

            if isinstance(current, dict) and key_path[-1] in current:
                deleted_value = current[key_path[-1]]
                del current[key_path[-1]]
                key_display = key_path[-1]
                self._db.save()
                await call.answer(self.strings["deleted"].format(key=key_display))
                await self.navigate_db(call, key_path[:-1], parent_page)
            elif (
                isinstance(current, list)
                and isinstance(key_path[-1], int)
                and 0 <= key_path[-1] < len(current)
            ):
                deleted_value = current.pop(key_path[-1])
                key_display = f"[{key_path[-1]}] = {deleted_value}"
                self._db.save()
                await call.answer(self.strings["deleted"].format(key=key_display))
                await self.navigate_db(call, key_path[:-1], parent_page)
            else:
                await call.answer(self.strings["not_found"].format(key=key_path[-1]))

    def find_module_key(self, module_name):
        module_name_lower = module_name.lower()
        for key in self._db.keys():
            if key.lower() == module_name_lower:
                return key
        return None

    @loader.command(ru_doc="Просмотр базы данных")
    async def mydb(self, message):
        """Viewing the database"""
        args = utils.get_args_raw(message)
        if args:
            module_key = self.find_module_key(args)
            if module_key:
                await self.show_menu(
                    message, [module_key], self.page_state.get((module_key,), 0)
                )
                return
            else:
                await utils.answer(
                    message, self.strings["module_not_found"].format(module=args)
                )
                return
        await self.show_menu(message, [], self.page_state.get((), 0))