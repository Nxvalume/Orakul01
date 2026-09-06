import asyncio
import random
import logging
import os
import io
import aiohttp
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, BufferedInputFile
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

# ---------- НАСТРОЙКИ ----------
BOT_TOKEN = os.getenv("BOT_TOKEN")
HF_API_TOKEN = os.getenv("HF_API_TOKEN")
HF_API_URL = "https://api-inference.huggingface.co/models/stabilityai/stable-diffusion-xl-base-1.0"
ADMIN_ID = os.getenv("ADMIN_ID")  # необязательно, для будущего

logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# «База данных»: user_id -> {"free_uses", "premium", "referrer", "last_reminder", "promocodes_used"}
users = {}
# Список действующих промокодов: код -> количество даруемых раскладов
PROMOCODES = {
    "START": 1,
    "FRIEND": 1,
    "LOVE": 2,
    "MYSTIC": 3,
}

# ---------- ТЕКСТЫ РАСКЛАДОВ (вставьте полные списки из предыдущего ответа) ----------
# Для краткости здесь показаны только заглушки; скопируйте весь контент из последней версии
card_of_day = [
    {"title": "Солнце", "short": "Яркий свет освещает твой путь", "full": "Сегодня Вселенная дарит тебе энергию радости и успеха...", "end": "Поделись этим светом с близкими!"},
    # ... ещё 9
]
love = [ ... ]
career = [ ... ]
month_advice = [ ... ]
year_prediction = [ ... ]
compatibility = [ ... ]

categories = {
    "card_day": card_of_day,
    "love": love,
    "career": career,
    "month": month_advice,
    "year": year_prediction,
}

# ---------- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ----------
def get_user(user_id):
    if user_id not in users:
        users[user_id] = {
            "free_uses": 0,
            "premium": False,
            "referrer": None,
            "last_reminder": None,
            "promocodes_used": [],
            "daily_reminder_enabled": True,
        }
    return users[user_id]

def has_free_uses(user_data):
    return user_data["free_uses"] < 3 or user_data["premium"]

def increment_usage(user_data):
    if not user_data["premium"]:
        user_data["free_uses"] += 1

async def generate_image(prompt: str) -> bytes | None:
    if not HF_API_TOKEN:
        return None
    headers = {"Authorization": f"Bearer {HF_API_TOKEN}"}
    payload = {"inputs": prompt}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(HF_API_URL, headers=headers, json=payload, timeout=30) as resp:
                if resp.status == 200:
                    return await resp.read()
                else:
                    logging.warning(f"HF API error: {resp.status}")
                    return None
    except Exception as e:
        logging.error(f"Image generation failed: {e}")
        return None

# ---------- КЛАВИАТУРЫ ----------
def main_menu_keyboard(user_id=None):
    builder = InlineKeyboardBuilder()
    builder.button(text="🔮 Получить расклад", callback_data="menu_categories")
    builder.button(text="ℹ️ О боте", callback_data="about")
    builder.button(text="💎 Премиум", callback_data="premium_info")
    builder.button(text="🎁 +1 расклад за друга", callback_data="invite")
    builder.button(text="🔑 Ввести промокод", callback_data="promo")
    builder.adjust(1)
    return builder.as_markup()

def categories_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text="☀️ Карта дня", callback_data="cat_card_day")
    builder.button(text="❤️ Любовь и отношения", callback_data="cat_love")
    builder.button(text="💼 Карьера и финансы", callback_data="cat_career")
    builder.button(text="🌙 Совет на месяц", callback_data="cat_month")
    builder.button(text="📅 Предсказание на год", callback_data="cat_year")
    builder.button(text="💞 Совместимость", callback_data="cat_compat")
    builder.button(text="⬅️ Назад", callback_data="back_to_main")
    builder.adjust(1)
    return builder.as_markup()

def after_reading_keyboard():
    builder = InlineKeyboardBuilder()
    # Кнопка "Поделиться" теперь вызывает Telegram-меню выбора чата
    builder.button(text="📤 Поделиться", switch_inline_query="")
    builder.button(text="🔮 Ещё расклад", callback_data="menu_categories")
    builder.button(text="🏠 В главное меню", callback_data="back_to_main")
    builder.adjust(1)
    return builder.as_markup()

# ---------- ОБРАБОТЧИКИ КОМАНД ----------
@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    user_data = get_user(user_id)
    args = message.text.split()
    # Обработка реферальной ссылки (формат /start ref123)
    if len(args) > 1 and args[1].isdigit():
        referrer_id = int(args[1])
        if referrer_id != user_id and referrer_id in users:
            user_data["referrer"] = referrer_id
            # Бонус пригласившему начислим после первого расклада нового пользователя
            # Пока просто запоминаем, что он приглашён

    await message.answer(
        "✨ Добро пожаловать в «Мистический оракул»! ✨\n\n"
        "Я — твой проводник в мир тайн и предсказаний. Здесь ты можешь получить ответы на волнующие вопросы, заглянуть в будущее и лучше понять себя.\n\n"
        "🔮 Что я умею:\n"
        "— Карта дня\n"
        "— Любовь и отношения\n"
        "— Карьера и финансы\n"
        "— Совет на месяц\n"
        "— Предсказание на год\n"
        "— Совместимость по именам\n\n"
        f"У тебя есть {3 - user_data['free_uses']} бесплатных раскладов, чтобы познакомиться с магией.\n\n"
        "🎁 Пригласи друга и получи ещё один бесплатный расклад!\n"
        "🔑 Введи промокод START и получи +1 расклад!",
        reply_markup=main_menu_keyboard()
    )

@dp.message(Command("premium"))
async def premium_command(message: types.Message):
    user_id = message.from_user.id
    user_data = get_user(user_id)
    user_data["premium"] = True
    await message.answer("💎 Премиум активирован! Теперь у тебя безлимитные расклады. Наслаждайся ✨")

@dp.message(Command("help"))
async def help_command(message: types.Message):
    await message.answer(
        "Доступные команды:\n"
        "/start – перезапустить бота\n"
        "/premium – активировать премиум (заглушка)\n"
        "/help – помощь\n"
        "Также работают кнопки в меню."
    )

# Обработка промокода
@dp.callback_query(F.data == "promo")
async def ask_promo(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.edit_text("Введи промокод:")
    await state.set_state(Promo.waiting_for_code)
    await callback.answer()

class Promo(StatesGroup):
    waiting_for_code = State()

@dp.message(Promo.waiting_for_code)
async def process_promo(message: types.Message, state: FSMContext):
    code = message.text.strip().upper()
    user_id = message.from_user.id
    user_data = get_user(user_id)
    if code in PROMOCODES:
        if code in user_data["promocodes_used"]:
            await message.answer("Этот промокод уже использован.")
        else:
            bonus = PROMOCODES[code]
            # Уменьшаем счётчик использованных раскладов (даём дополнительные)
            user_data["free_uses"] = max(0, user_data["free_uses"] - bonus)
            user_data["promocodes_used"].append(code)
            await message.answer(f"Промокод принят! Ты получила +{bonus} бесплатных раскладов 🎉")
    else:
        await message.answer("Неверный промокод. Попробуй ещё раз.")
    await state.clear()

# ---------- КНОПКИ МЕНЮ ----------
@dp.callback_query(F.data == "menu_categories")
async def show_categories(callback: types.CallbackQuery):
    await callback.message.edit_text("Выбери категорию расклада:", reply_markup=categories_keyboard())
    await callback.answer()

@dp.callback_query(F.data == "about")
async def about_bot(callback: types.CallbackQuery):
    await callback.message.edit_text(
        "«Мистический оракул» — развлекательный бот предсказаний на основе карт Таро и астрологии. Все расклады носят общий позитивный характер и созданы для вдохновения.\n\n"
        "Поделись ботом с подругами и получай бесплатные расклады!",
        reply_markup=main_menu_keyboard()
    )
    await callback.answer()

@dp.callback_query(F.data == "premium_info")
async def premium_info(callback: types.CallbackQuery):
    await callback.message.edit_text(
        "💎 Премиум-подписка (199 ₽/мес) даёт:\n"
        "— Безлимитные расклады всех категорий\n"
        "— Эксклюзивная категория «Совет от звёзд»\n"
        "— История раскладов\n"
        "— Отключение рекламы\n\n"
        "Для активации отправьте /premium (заглушка, в реальном боте здесь будет кнопка оплаты).",
        reply_markup=main_menu_keyboard()
    )
    await callback.answer()

@dp.callback_query(F.data == "invite")
async def invite_friend(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    bot_username = (await bot.get_me()).username
    ref_link = f"https://t.me/{bot_username}?start={user_id}"
    await callback.message.edit_text(
        f"🎁 Пригласи друга по ссылке, и когда он сделает свой первый расклад, ты получишь +1 бесплатный расклад!\n\n"
        f"Твоя ссылка:\n{ref_link}\n\n"
        f"Просто отправь её другу или размести в соцсетях.",
        reply_markup=main_menu_keyboard()
    )
    await callback.answer()

@dp.callback_query(F.data == "back_to_main")
async def back_to_main(callback: types.CallbackQuery):
    await callback.message.edit_text("Главное меню:", reply_markup=main_menu_keyboard())
    await callback.answer()

# ---------- ОБРАБОТКА КАТЕГОРИЙ ----------
@dp.callback_query(F.data.startswith("cat_"))
async def process_category(callback: types.CallbackQuery, state: FSMContext):
    category_key = callback.data[4:]
    user_id = callback.from_user.id
    user_data = get_user(user_id)

    if category_key == "compat":
        await callback.message.edit_text("Введите первое имя:")
        await state.set_state(Compatibility.waiting_for_first_name)
        await callback.answer()
        return

    if not has_free_uses(user_data):
        await callback.message.edit_text(
            "🔮 Ты использовала все бесплатные расклады, но магия не заканчивается!\n\n"
            "Варианты:\n"
            "💎 Премиум — 199 ₽/мес (безлимит)\n"
            "✨ Разовый расклад — 49 ₽\n"
            "🌟 Глубокий анализ — 149 ₽\n"
            "❤️ Совместимость — 249 ₽\n\n"
            "🎁 Пригласи друга и получи ещё бесплатный расклад!",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="💳 Оформить Премиум", callback_data="premium_info")],
                [InlineKeyboardButton(text="🏠 В меню", callback_data="back_to_main")]
            ])
        )
        await callback.answer()
        return

    reading = random.choice(categories[category_key])
    full_text = reading["full"].replace("{name}", callback.from_user.first_name)
    short_text = reading["short"]
    increment_usage(user_data)

    # Начисляем бонус пригласившему, если этот пользователь был приглашён и это его первый расклад
    if user_data.get("referrer") and user_data.get("free_uses_before_first_reading", True):
        referrer_id = user_data["referrer"]
        if referrer_id in users:
            users[referrer_id]["free_uses"] = max(0, users[referrer_id]["free_uses"] - 1)  # +1 расклад
            try:
                await bot.send_message(referrer_id, "🎉 Твой друг сделал первый расклад! Ты получила +1 бесплатный расклад.")
            except:
                pass
        user_data["free_uses_before_first_reading"] = False  # бонус только за первый расклад

    message_text = (
        f"<b>{reading['title']}</b>\n"
        f"<i>{short_text}</i>\n\n"
        f"{full_text}\n\n"
        f"{reading['end']}"
    )

    # Генерируем картинку
    image_prompt = f"Tarot card {reading['title']}, dark purple background, gold accents, mystical, digital art, 1080x1080"
    image_bytes = await generate_image(image_prompt)

    if image_bytes:
        await callback.message.answer_photo(
            photo=BufferedInputFile(image_bytes, filename="tarot.jpg"),
            caption=message_text,
            parse_mode="HTML",
            reply_markup=after_reading_keyboard()
        )
        await callback.message.delete()
    else:
        await callback.message.edit_text(message_text, parse_mode="HTML", reply_markup=after_reading_keyboard())
    await callback.answer()

# Кнопка "Поделиться" использует switch_inline_query, поэтому отдельного обработчика не нужно.
# Но можно добавить, если нужно кастомное поведение.

# ---------- СОВМЕСТИМОСТЬ ----------
class Compatibility(StatesGroup):
    waiting_for_first_name = State()
    waiting_for_second_name = State()

@dp.message(Compatibility.waiting_for_first_name)
async def get_first_name(message: types.Message, state: FSMContext):
    await state.update_data(name1=message.text)
    await message.answer("Теперь введите второе имя:")
    await state.set_state(Compatibility.waiting_for_second_name)

@dp.message(Compatibility.waiting_for_second_name)
async def get_second_name(message: types.Message, state: FSMContext):
    data = await state.get_data()
    name1 = data.get("name1")
    name2 = message.text
    user_id = message.from_user.id
    user_data = get_user(user_id)

    if not has_free_uses(user_data):
        await message.answer(
            "У тебя закончились бесплатные расклады. Для совместимости нужно оплатить 249 ₽ или оформить Премиум.",
            reply_markup=main_menu_keyboard()
        )
        await state.clear()
        return

    reading = random.choice(compatibility)
    full_text = reading["full"].format(name1=name1, name2=name2)
    short_text = reading["short"]
    increment_usage(user_data)

    # Бонус рефереру (аналогично)
    if user_data.get("referrer") and user_data.get("free_uses_before_first_reading", True):
        referrer_id = user_data["referrer"]
        if referrer_id in users:
            users[referrer_id]["free_uses"] = max(0, users[referrer_id]["free_uses"] - 1)
            try:
                await bot.send_message(referrer_id, "🎉 Твой друг сделал первый расклад! Ты получила +1 бесплатный расклад.")
            except:
                pass
        user_data["free_uses_before_first_reading"] = False

    message_text = (
        f"<b>{reading['title']}</b>\n"
        f"<i>{short_text}</i>\n\n"
        f"{full_text}\n\n"
        f"{reading['end']}"
    )

    image_prompt = f"Tarot card for couple {name1} and {name2}, love, mystical, dark purple, gold"
    image_bytes = await generate_image(image_prompt)

    if image_bytes:
        await message.answer_photo(
            photo=BufferedInputFile(image_bytes, filename="tarot.jpg"),
            caption=message_text,
            parse_mode="HTML",
            reply_markup=after_reading_keyboard()
        )
    else:
        await message.answer(message_text, parse_mode="HTML", reply_markup=after_reading_keyboard())
    await state.clear()

# ---------- Ежедневные напоминания ----------
async def daily_reminder():
    while True:
        now = datetime.now()
        # Отправляем в 10:00 утра
        target = now.replace(hour=10, minute=0, second=0, microsecond=0)
        if now > target:
            target += timedelta(days=1)
        await asyncio.sleep((target - now).total_seconds())
        for user_id, data in users.items():
            if data.get("daily_reminder_enabled", True) and not data.get("premium", False):
                try:
                    await bot.send_message(
                        user_id,
                        "🌙 Доброе утро! Звёзды уже готовы рассказать тебе о сегодняшнем дне. Сделай свой расклад дня, пока энергия сильна!",
                        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                            [InlineKeyboardButton(text="🔮 Сделать расклад", callback_data="menu_categories")]
                        ])
                    )
                except:
                    pass

async def main():
    # Запускаем фоновую задачу для рассылки
    asyncio.create_task(daily_reminder())
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
