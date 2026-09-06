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

BOT_TOKEN = os.getenv("BOT_TOKEN")
HF_API_TOKEN = os.getenv("HF_API_TOKEN")
HF_API_URL = "https://api-inference.huggingface.co/models/stabilityai/stable-diffusion-xl-base-1.0"

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN не задан")

logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)
users = {}

# ---------- ТЕКСТЫ РАСКЛАДОВ (полные, 10 на каждую категорию) ----------
card_of_day = [
    {"title": "Солнце", "short": "Яркий свет освещает твой путь", "full": "Сегодня Вселенная дарит тебе энергию радости и успеха. Всё, за что ты возьмёшься, будет спориться. Доверься внутреннему свету — он приведёт к нужным людям и событиям.", "end": "Поделись этим светом с близкими и возвращайся за новым раскладом!"},
    {"title": "Луна", "short": "Тайные знаки укажут верное направление", "full": "Твой день окутан лёгкой тайной. Прислушайся к интуиции — она подскажет, как избежать сомнений. Вечером откройся для приятных неожиданностей.", "end": "Загадай желание на ночь и поделись раскладом с другом!"},
    {"title": "Звезда", "short": "Надежда ведёт к исполнению мечты", "full": "Сегодня ты почувствуешь прилив вдохновения. Звёзды благосклонны: любая цель станет ближе, если сделаешь первый шаг. Верь в себя — это твой главный козырь.", "end": "Поделись этой звёздной энергией — отправь расклад в сторис!"},
    {"title": "Колесо Фортуны", "short": "Судьба делает неожиданный поворот", "full": "В твоей жизни наступает момент удачных перемен. Не бойся нового — оно принесёт ценный опыт. Будь открыта к возможностям, которые появятся в течение дня.", "end": "Поделись этим знаком с тем, кто ждёт перемен!"},
    {"title": "Маг", "short": "Ты обладаешь силой творить реальность", "full": "Сегодня твои мысли особенно материальны. Сосредоточься на желаемом, а не на страхах. Вселенная поддержит любую конструктивную идею.", "end": "Используй свою магию и отправь этот расклад другу!"},
    {"title": "Императрица", "short": "Забота и изобилие наполнят день", "full": "День принесёт тепло, уют и приятные заботы. Ты будешь источником поддержки для окружающих, и это вернётся сторицей. Не забывай баловать себя.", "end": "Поделись этим тёплым прогнозом с мамой или подругой!"},
    {"title": "Влюблённые", "short": "Сердце подскажет правильный выбор", "full": "Сегодня важные решения будут даваться легко, если прислушаешься к чувствам. В отношениях возможен приятный сюрприз. Доверься тому, что тебя вдохновляет.", "end": "Отправь этот знак тому, кто тебе дорог!"},
    {"title": "Отшельник", "short": "Время для мудрого уединения", "full": "Не бойся побыть наедине с собой. В тишине придёт ответ на давний вопрос. Вечером проявится ясность в том, что раньше казалось запутанным.", "end": "Поделись этим прогнозом с тем, кто ищет ответы!"},
    {"title": "Сила", "short": "Внутренняя мощь пробуждается", "full": "Сегодня ты способна преодолеть любые преграды. Твоя мягкость и настойчивость приведут к победе. Не сомневайся в своих ресурсах — их более чем достаточно.", "end": "Поделись этой силой — отправь расклад тому, кто нуждается в поддержке!"},
    {"title": "Справедливость", "short": "Всё встанет на свои места", "full": "День принесёт ясность и честные решения. Если ты действовала правильно, получишь заслуженное признание. Будь объективна к себе и другим.", "end": "Поделись этим знаком справедливости с коллегой!"},
]

love = [
    {"title": "Две чаши", "short": "Энергии сердец сливаются", "full": "В твоих отношениях наступает период гармонии. Если ты одинока, скоро появится человек, с которым будет легко и тепло. Открой сердце для нежности.", "end": "Поделись этим предсказанием с тем, кто тебе нравится!"},
    {"title": "Королева Кубков", "short": "Любовь течёт через тебя", "full": "Ты источаешь притягательную эмоциональную глубину. Партнёр ценит твою заботу, а если ты в поиске — именно эта энергия привлечёт достойного человека.", "end": "Отправь этот расклад подруге, которая верит в любовь!"},
    {"title": "Рыцарь Жезлов", "short": "Страсть разгорается", "full": "Твои отношения наполнятся яркими эмоциями и спонтанностью. Не бойся проявлять инициативу — это оценят. Одиноким звёзды сулят головокружительное знакомство.", "end": "Поделись этой страстью с тем, кто тебе интересен!"},
    {"title": "Десятка Кубков", "short": "Семейное счастье рядом", "full": "Ты движешься к глубокой эмоциональной связи. Возможны важные разговоры о будущем, которые укрепят союз. Если ты свободна, Вселенная готовит встречу с «твоим» человеком.", "end": "Отправь этот знак тому, с кем хочешь разделить счастье!"},
    {"title": "Туз Кубков", "short": "Новое чувство зарождается", "full": "В твою жизнь входит свежая волна любви. Это может быть новое знакомство или возрождение прежних чувств. Будь открыта и не прячь эмоции.", "end": "Поделись этим предсказанием и будь готова к чуду!"},
    {"title": "Повешенный", "short": "Время переосмыслить отношения", "full": "Возможно, в союзе нужно взглянуть на ситуацию под другим углом. Пауза пойдёт на пользу: вы лучше поймёте друг друга. Одиноким стоит отпустить прошлое.", "end": "Поделись этим раскладом с тем, кто важен для тебя!"},
    {"title": "Мир", "short": "Гармония в паре", "full": "Твои отношения выходят на новый уровень доверия. Если ты одна, то скоро обретёшь внутреннюю целостность, которая притянет идеального партнёра.", "end": "Поделись этой гармонией с близким человеком!"},
    {"title": "Император", "short": "Надёжность и защита", "full": "В отношениях появится стабильность и уверенность в завтрашнем дне. Партнёр проявит заботу, а одиноким встретится человек, на которого можно положиться.", "end": "Поделись этим прогнозом с тем, кто ценит надёжность!"},
    {"title": "Шестёрка Кубков", "short": "Тёплые воспоминания и нежность", "full": "В твоей жизни появится человек из прошлого или возникнет ситуация, которая напомнит о чистой любви. Это принесёт радость и понимание.", "end": "Поделись этим тёплым прогнозом с другом детства!"},
    {"title": "Звезда", "short": "Надежда на любовь", "full": "Твоя вера в настоящие чувства будет вознаграждена. Откройся новым знакомствам и не бойся показать свою уязвимость — это привлечёт искренность.", "end": "Отправь этот знак тому, кто ищет любовь!"},
]

career = [
    {"title": "Туз Пентаклей", "short": "Новые возможности для роста", "full": "В твоей карьере открывается перспективное направление. Возможно, поступит выгодное предложение или появится шанс проявить себя. Не упусти момент.", "end": "Поделись этим знаком с коллегой, которая ждёт прорыва!"},
    {"title": "Король Пентаклей", "short": "Финансовая стабильность близко", "full": "Твои усилия начинают приносить плоды. В ближайшее время ожидается укрепление материального положения. Будь практична и не бойся брать ответственность.", "end": "Отправь этот расклад тому, кто строит карьеру!"},
    {"title": "Восьмёрка Пентаклей", "short": "Мастерство принесёт доход", "full": "Ты на верном пути: упорный труд и оттачивание навыков скоро будут вознаграждены. Возможно, предложат повышение или новый проект.", "end": "Поделись этим прогнозом с тем, кто много работает!"},
    {"title": "Колесо Фортуны", "short": "Карьерный поворот к лучшему", "full": "В твоей профессиональной жизни грядут перемены. Не сопротивляйся — они приведут к большему успеху. Финансовый поток тоже ускорится.", "end": "Поделись этим знаком перемен с командой!"},
    {"title": "Шестёрка Пентаклей", "short": "Денежная помощь и признание", "full": "Вселенная щедра: возможны премии, подарки или возврат долгов. Также ты можешь получить поддержку от влиятельного человека.", "end": "Отправь этот расклад тому, кто ждёт финансовых новостей!"},
    {"title": "Император", "short": "Власть и карьерный рост", "full": "Ты готова занять лидирующую позицию. Прояви инициативу, и руководство это заметит. В финансах наведи порядок — это принесёт прибыль.", "end": "Поделись этим прогнозом с амбициозной подругой!"},
    {"title": "Тройка Пентаклей", "short": "Совместный проект принесёт успех", "full": "Работа в команде сейчас особенно эффективна. Твои идеи оценят, а сотрудничество приведёт к выгодным контрактам.", "end": "Поделись этим знаком с партнёрами по проекту!"},
    {"title": "Девятка Пентаклей", "short": "Финансовая независимость", "full": "Ты движешься к достатку, который позволит жить в удовольствие. Не останавливайся: твоя цель уже близка.", "end": "Отправь этот расклад тому, кто мечтает о свободе!"},
    {"title": "Паж Пентаклей", "short": "Обучение для будущих доходов", "full": "Сейчас благоприятно учиться новому, инвестировать в знания. Это заложит фундамент для будущих заработков.", "end": "Поделись этим прогнозом с тем, кто любит учиться!"},
    {"title": "Семёрка Пентаклей", "short": "Терпение принесёт урожай", "full": "Твои вложения (время, силы, деньги) скоро окупятся. Не сдавайся, осталось немного. Финансовый результат порадует.", "end": "Поделись этим знаком с тем, кто на пути к цели!"},
]

month_advice = [
    {"title": "Мудрость Луны", "short": "Доверься своей интуиции", "full": "В этом месяце твоя интуиция будет главным компасом. Обращай внимание на сны и знаки — они укажут верное направление. Не принимай поспешных решений.", "end": "Поделись этим советом с тем, кто ищет ответы!"},
    {"title": "Энергия Солнца", "short": "Действуй с оптимизмом", "full": "Твой месяц будет наполнен светом, если ты сохранишь позитивный настрой. Смело берись за новые проекты — успех гарантирован.", "end": "Отправь этот совет тому, кому нужен заряд бодрости!"},
    {"title": "Урок Отшельника", "short": "Найди время для себя", "full": "В этом месяце важно побыть в тишине, чтобы услышать свои истинные желания. Откажись от лишней суеты — это принесёт ясность.", "end": "Поделись этим мудрым советом с подругой!"},
    {"title": "Сила Влюблённых", "short": "Слушай своё сердце", "full": "При принятии решений в этом месяце отдавай приоритет чувствам, а не холодному расчёту. Любовь к себе и другим станет источником силы.", "end": "Отправь этот знак тому, кто тебе дорог!"},
    {"title": "Колесо года", "short": "Принимай перемены с благодарностью", "full": "В этом месяце жизнь может подкинуть неожиданные повороты. Не цепляйся за старое — впереди более интересный этап.", "end": "Поделись этим прогнозом с тем, кто боится перемен!"},
    {"title": "Звезда Надежды", "short": "Верь в свою мечту", "full": "Твои желания в этом месяце особенно сильны. Визуализируй цель и делай маленькие шаги каждый день — результат не заставит ждать.", "end": "Поделись этой звёздной энергией с другом!"},
    {"title": "Маг Реальности", "short": "Твои мысли материальны", "full": "Следи за тем, что говоришь и думаешь в этом месяце. Позитивные установки привлекут удачу, а сомнения лучше отбросить.", "end": "Отправь этот совет тому, кто верит в силу мысли!"},
    {"title": "Гармония Мира", "short": "Баланс во всём", "full": "В этом месяце старайся соблюдать равновесие между работой, отдыхом и отношениями. Тогда энергия будет бить ключом.", "end": "Поделись этим советом с тем, кто живёт в стрессе!"},
    {"title": "Терпение Императрицы", "short": "Заботься о себе и близких", "full": "Месяц благоприятен для укрепления семейных уз и уюта. Не забывай наполнять свой ресурс — только так сможешь отдавать другим.", "end": "Отправь этот тёплый совет маме или сестре!"},
    {"title": "Решительность Рыцаря", "short": "Не откладывай важное", "full": "В этом месяце Вселенная поддерживает смелые шаги. Если давно хочешь что-то начать — сейчас лучшее время.", "end": "Поделись этим знаком с тем, кто откладывает мечты!"},
]

year_prediction = [
    {"title": "Год Солнца", "short": "Яркий период успеха", "full": "Этот год станет для тебя временем расцвета. Ожидаются крупные достижения в карьере и личной жизни. Твоя уверенность притянет нужных людей.", "end": "Поделись этим прогнозом на год с близкими!"},
    {"title": "Год Колеса", "short": "Время больших перемен", "full": "Предстоящий год принесёт значительные изменения, которые в итоге приведут к росту. Будь готова отпустить старое и впустить новое.", "end": "Отправь этот годовой расклад тому, кто ждёт перемен!"},
    {"title": "Год Звезды", "short": "Исполнение заветных желаний", "full": "В этом году твои мечты начнут сбываться. Главное — не переставать верить и действовать. Поддержка Вселенной будет на твоей стороне.", "end": "Поделись этой звёздной перспективой с другом!"},
    {"title": "Год Влюблённых", "short": "Время любви и партнёрства", "full": "Этот год будет наполнен романтикой и укреплением отношений. Если ты одинока, высока вероятность встретить свою половинку.", "end": "Отправь этот прогноз тому, кто ждёт любовь!"},
    {"title": "Год Императора", "short": "Стабильность и карьерный рост", "full": "В этом году ты заложишь прочный фундамент для будущего. Возможны повышение, создание семьи или крупная покупка. Действуй решительно.", "end": "Поделись этим солидным прогнозом с коллегой!"},
    {"title": "Год Отшельника", "short": "Год самопознания", "full": "Этот год подарит тебе глубокое понимание себя. Возможна смена приоритетов, которая приведёт к внутренней гармонии. Не бойся уединения.", "end": "Поделись этим мудрым прогнозом с тем, кто ищет себя!"},
    {"title": "Год Мага", "short": "Ты творец своей судьбы", "full": "В этом году ты обретёшь большую власть над своей жизнью. Любые начинания будут успешны, если направить энергию в нужное русло.", "end": "Отправь этот мощный прогноз тому, кто готов творить!"},
    {"title": "Год Императрицы", "short": "Забота, семья и изобилие", "full": "Этот год принесёт тепло, уют и материальное благополучие. Возможно пополнение в семье или улучшение жилищных условий.", "end": "Поделись этим тёплым прогнозом с семьёй!"},
    {"title": "Год Справедливости", "short": "Всё будет по заслугам", "full": "В этом году ты получишь результаты своих прошлых усилий. Будь честна с собой и другими, и тогда удача не обойдёт стороной.", "end": "Отправь этот прогноз тому, кто ценит справедливость!"},
    {"title": "Год Мира", "short": "Гармония и завершение цикла", "full": "Этот год принесёт ощущение целостности и удовлетворения. Закончатся затянувшиеся ситуации, наступит долгожданный покой и радость.", "end": "Поделись этим мирным прогнозом с другом!"},
]

compatibility = [
    {"title": "Две звезды", "short": "Ваши пути освещены одним светом", "full": "{name1} и {name2}, ваша совместимость очень высока! Вы словно две звезды, которые нашли друг друга в бескрайнем космосе. Вместе вы способны преодолеть любые трудности, так как ваши энергии гармонично дополняются.", "end": "Поделитесь этим результатом, чтобы закрепить союз!"},
    {"title": "Огонь и вода", "short": "Страсть, требующая баланса", "full": "{name1} и {name2}, вы притягиваетесь как противоположности. Один из вас дарит страсть, другой — глубину. Если научитесь уважать различия, ваш союз станет нерушимым.", "end": "Отправьте этот расклад друг другу!"},
    {"title": "Родственные души", "short": "Вы нашли свою половину", "full": "{name1} и {name2}, вы удивительно похожи в главном. Ваша связь настолько глубока, что кажется, будто вы знакомы вечность. Вместе вы растёте и вдохновляете друг друга.", "end": "Поделитесь этим знаком с близкими!"},
    {"title": "Ключ и замок", "short": "Вы идеально дополняете друг друга", "full": "{name1} и {name2}, ваши характеры складываются как пазл: то, чего не хватает одному, в избытке у другого. Это очень перспективный союз для долгих отношений.", "end": "Отправьте этот прогноз тому, кто вас познакомил!"},
    {"title": "Магнит", "short": "Непреодолимое притяжение", "full": "{name1} и {name2}, между вами искрит с первого взгляда. Ваша страсть может быть очень яркой, но важно научиться слушать и слышать друг друга.", "end": "Поделитесь этим раскладом и проверьте силу притяжения!"},
    {"title": "Спокойная гавань", "short": "Нежность и взаимопонимание", "full": "{name1} и {name2}, ваши отношения похожи на тихую бухту, где можно укрыться от бурь. Вы цените заботу и стабильность, и это основа вашего счастья.", "end": "Отправьте этот тёплый результат тому, кто ищет покой!"},
    {"title": "Учитель и ученик", "short": "Вы растёте благодаря друг другу", "full": "{name1} и {name2}, ваша связь несёт в себе уроки, которые помогают обоим становиться лучше. Возможны периоды непонимания, но они лишь укрепят союз.", "end": "Поделитесь этим мудрым прогнозом с другом!"},
    {"title": "Творческий тандем", "short": "Вместе вы создаёте шедевры", "full": "{name1} и {name2}, ваша пара полна идей и вдохновения. Совместные проекты будут особенно успешными, а общие мечты — достижимыми.", "end": "Отправьте этот знак тому, кто верит в вашу пару!"},
    {"title": "Две половинки луны", "short": "Вы дополняете друг друга до целого", "full": "{name1} и {name2}, вы словно две части одного целого. Ваши недостатки и достоинства идеально балансируются, создавая гармоничный союз.", "end": "Поделитесь этим результатом с близкими!"},
    {"title": "Испытание временем", "short": "Ваша связь проверена свыше", "full": "{name1} и {name2}, ваша совместимость может проявиться не сразу, но со временем вы поймёте, что созданы друг для друга. Доверьтесь судьбе и не торопитесь.", "end": "Отправьте этот прогноз друг другу и обсудите!"},
]

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
        users[user_id] = {"free_uses": 0, "premium": False, "referrer": None, "promocodes_used": [], "daily_reminder_enabled": True, "free_uses_before_first_reading": True}
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
def main_menu_keyboard():
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
    if len(args) > 1 and args[1].isdigit():
        referrer_id = int(args[1])
        if referrer_id != user_id and referrer_id in users:
            user_data["referrer"] = referrer_id

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

class Promo(StatesGroup):
    waiting_for_code = State()

@dp.callback_query(F.data == "promo")
async def ask_promo(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.edit_text("Введи промокод:")
    await state.set_state(Promo.waiting_for_code)
    await callback.answer()

@dp.message(Promo.waiting_for_code)
async def process_promo(message: types.Message, state: FSMContext):
    code = message.text.strip().upper()
    user_id = message.from_user.id
    user_data = get_user(user_id)
    promo_dict = {"START": 1, "FRIEND": 1, "LOVE": 2, "MYSTIC": 3}
    if code in promo_dict:
        if code in user_data.get("promocodes_used", []):
            await message.answer("Этот промокод уже использован.")
        else:
            bonus = promo_dict[code]
            user_data["free_uses"] = max(0, user_data["free_uses"] - bonus)
            if "promocodes_used" not in user_data:
                user_data["promocodes_used"] = []
            user_data["promocodes_used"].append(code)
            await message.answer(f"Промокод принят! Ты получила +{bonus} бесплатных раскладов 🎉")
    else:
        await message.answer("Неверный промокод. Попробуй ещё раз.")
    await state.clear()

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

    # Бонус рефереру за первый расклад
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

# Ежедневные напоминания (простая реализация)
async def daily_reminder():
    while True:
        now = datetime.now()
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
    asyncio.create_task(daily_reminder())
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())