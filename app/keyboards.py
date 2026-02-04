from aiogram.types import (
    KeyboardButton,
    ReplyKeyboardMarkup
)

# ---------- МЕНЮ АДМИНА ----------
def admin_menu_kb():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📅 Просмотр записей"), KeyboardButton(text="⚙️ Настройки")],
            [KeyboardButton(text="➕ Добавить мастера"), KeyboardButton(text="➖ Удалить мастера")],
            [KeyboardButton(text="🧾 Просмотр заявок"), KeyboardButton(text="⭐ Просмотр отзывов")],
            [KeyboardButton(text="🧠 AI-помощник"), KeyboardButton(text="🏠 Главное меню")]
        ],
    resize_keyboard=True
    )
    
def settings_kb():
    buttons = [
        [KeyboardButton(text="🌴 Отправить мастера в отпуск"), KeyboardButton(text="🗓 Настроить дни/часы")],
        [KeyboardButton(text="🛠️ Настроить услуги"), KeyboardButton(text="Настроить обеденный перерыв")],
        [KeyboardButton(text="📍 Настроить код страны"), KeyboardButton(text="📤 Экспорт в CSV")],
        [KeyboardButton(text="⬅️ Назад в меню")]
    ]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)


# ---------- ГЛАВНОЕ МЕНЮ ----------
def main_menu_kb(is_owner=False):
    keyboard = [
        [KeyboardButton(text='🏢 О нас'), KeyboardButton(text='💬 Контакты')],
        [KeyboardButton(text='💇 Услуги'), KeyboardButton(text='📅 Мои записи')],
        [KeyboardButton(text='⭐ Отзывы'), KeyboardButton(text='🧠 AI-помощник')]
    ]
    if is_owner:
        keyboard.append([KeyboardButton(text="🏠 Админ-меню")])
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)