import asyncio
from aiogram import Bot, Dispatcher, F
from aiogram.types import (
    Message, CallbackQuery,
    InlineKeyboardButton, InlineKeyboardMarkup,
    ReplyKeyboardMarkup, KeyboardButton,
    InputMediaPhoto, InputMediaVideo, InputMediaDocument
)
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State

import os
from dotenv import load_dotenv
import logging

# Настройка логирования (вывод в терминал + файл bot.log)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),                    # в терминал
        logging.FileHandler("bot.log", encoding="utf-8")  # в файл
    ]
)
logger = logging.getLogger(__name__)

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
GROUP_ID = int(os.getenv("GROUP_ID"))

# ================== COUNTER ==================
COUNTER_FILE = "request_counter.txt"

if os.path.exists(COUNTER_FILE):
    try:
        with open(COUNTER_FILE, "r", encoding="utf-8") as f:
            REQUEST_COUNTER = int(f.read().strip())
    except (ValueError, IOError):
        REQUEST_COUNTER = 0
        logger.warning("Помилка читання request_counter.txt — скинуто до 0")
else:
    REQUEST_COUNTER = 0
    logger.info("Файл request_counter.txt не знайдено — починаємо з 0")


def get_next_request_number():
    global REQUEST_COUNTER
    REQUEST_COUNTER += 1
    try:
        with open(COUNTER_FILE, "w", encoding="utf-8") as f:
            f.write(str(REQUEST_COUNTER))
        logger.debug(f"Збережено номер заявки: {REQUEST_COUNTER}")
    except IOError as e:
        logger.error(f"Помилка запису в request_counter.txt: {e}")
    return REQUEST_COUNTER


# ================== НАСТРОЙКИ ==================

bot = Bot(BOT_TOKEN)
dp = Dispatcher()

MEDIA_TIMEOUT_SECONDS = 1.8

# ================== КЛАВИАТУРЫ ==================

def start_button_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🚀 Старт")],
            [KeyboardButton(text="💬 Коментар")]
        ],
        resize_keyboard=True
    )

def start_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🅿️ Паркінг", callback_data="start_parking")],
        [InlineKeyboardButton(text="🏢 Приміщення", callback_data="start_building")]
    ])

def back_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="⬅️ Назад", callback_data="back")]]
    )

skip_keyboard = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="➡️ Пропустити", callback_data="skip")],
    [InlineKeyboardButton(text="⬅️ Назад", callback_data="back")]
])

problem_keyboard = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="🚰 Сантехніка", callback_data="Сантехніка")],
    [InlineKeyboardButton(text="⚡ Електрика", callback_data="Електрика")],
    [InlineKeyboardButton(text="❄️ Кондиціонування/опалення", callback_data="Кондиціонування/опалення")],
    [InlineKeyboardButton(text="🧱 Стіни/підлога/стеля", callback_data="Стіни/підлога/стеля")],
    [InlineKeyboardButton(text="❓ Звернення до адміністрації стадіону", callback_data="Звернення")],
    [InlineKeyboardButton(text="⬅️ Назад", callback_data="back")]
])

parking_action_keyboard = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="Додати/оновити паркомісце", callback_data="Додати паркомісце")],
    [InlineKeyboardButton(text="Видалили паркомісце", callback_data="Видалити паркомісце")],
    [InlineKeyboardButton(text="Інше (проблема/питання с карткою)", callback_data="Інше")],
    [InlineKeyboardButton(text="⬅️ Назад", callback_data="back")]
])

# ================== FSM ==================

class BuildingForm(StatesGroup):
    details = State()
    problem_type = State()
    problem_description = State()
    media = State()

class ParkingForm(StatesGroup):
    user_info = State()
    action = State()
    cars = State()
    media = State()


class CommentForm(StatesGroup):
    text = State()

# ================== FSM HISTORY ==================

async def set_state_with_history(state: FSMContext, new_state: State):
    data = await state.get_data()
    history = data.get("history", [])
    current = await state.get_state()
    if current:
        history.append(current)
    await state.update_data(history=history)
    await state.set_state(new_state)

# ================== UNIVERSAL MEDIA HANDLER ==================
async def handle_media(message: Message, state: FSMContext) -> bool:
    data = await state.get_data()
    media_list = data.get("media_list", [])
    media_types = set(m["type"] for m in media_list)

    new_type = None
    if message.photo:
        new_type = "photo"
    elif message.video:
        new_type = "video"
    elif message.document:
        new_type = "document"
    else:
        await message.answer("❌ Непідтримуваний формат")
        return False

    if media_types:
        if (new_type in ["photo", "video"] and "document" in media_types) or \
           (new_type == "document" and any(t in ["photo", "video"] for t in media_types)):
            await message.answer("❌ Не можна змішувати фото/відео з документами. Надсилайте окремо.")
            return False

    if len(media_list) >= 10:
        await message.answer("❌ Максимум 10 файлів (фото/відео або документів)")
        return False

    if message.photo:
        media_list.append({
            "type": "photo",
            "id": message.photo[-1].file_id,
            "name": None
        })
    elif message.video:
        media_list.append({
            "type": "video",
            "id": message.video.file_id,
            "name": None
        })
    elif message.document:
        filename = message.document.file_name.lower()
        allowed_ext = (".xls", ".xlsx", ".doc", ".docx", ".pdf")
        if not filename.endswith(allowed_ext):
            await message.answer("❌ Дозволені файли: Excel, Word або PDF")
            return False
        media_list.append({
            "type": "document",
            "id": message.document.file_id,
            "name": message.document.file_name
        })

    logger.info(f"Отримано медіа: тип={new_type}, всього елементів={len(media_list)}")
    await state.update_data(media_list=media_list)
    return True

# ================== DEBOUNCE ФУНКЦІЯ ==================
async def delayed_send(state: FSMContext, send_func, message: Message):
    await asyncio.sleep(MEDIA_TIMEOUT_SECONDS)

    current_data = await state.get_data()
    if current_data.get("media_timeout_active", False):
        logger.info("Таймер спрацював — запускаємо відправку заявки")
        await send_func(message, state)
        await state.update_data(
            media_timeout_active=False,
            media_timeout_task=None
        )
# ================== START ==================

@dp.message(CommandStart())
async def start_cmd(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "Вітаю! Натисніть «Старт», щоб почати 👇",
        reply_markup=start_button_keyboard()
    )

@dp.message(F.text == "🚀 Старт")
async def start_pressed(message: Message):
    await message.answer(
        "Оберіть тип заявки:",
        reply_markup=start_keyboard()
    )

@dp.message(F.text == "💬 Коментар")
async def comment_start(message: Message, state: FSMContext):
    await state.set_state(CommentForm.text)
    await message.answer(
        "Обовʼязково вкажіть номер заявки № та напишіть ваш коментар.\nПриклад:\n№145\nВаш коментар",
        reply_markup=back_keyboard()
    )


@dp.message(CommentForm.text)
async def comment_receive(message: Message, state: FSMContext):
    text = (
        f"💬 Коментар\n\n"
        f"📝 {message.text}"
    )

    await bot.send_message(message.chat.id, "✅ Коментар надіслано")
    await bot.send_message(GROUP_ID, text)

    await state.clear()

    await message.answer(
        "Хочете створити заявку?",
        reply_markup=start_button_keyboard()
    )

# ================== BACK ==================

@dp.callback_query(F.data == "back")
async def go_back(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    history = data.get("history", [])

    if not history:
        await callback.answer("Це перший крок")
        return

    prev = history.pop()
    await state.update_data(history=history)
    await state.set_state(prev)

    texts = {
        BuildingForm.details.state:
            "Введіть одним повідомленням:\nІмʼя\nТелефон\nПідприємство\nНомер приміщення",
        BuildingForm.problem_type.state:
            "Оберіть тип проблеми:",
        BuildingForm.problem_description.state:
            "Опишіть проблему:",
        BuildingForm.media.state:
            "Додайте фото / відео / файл:",
        ParkingForm.user_info.state:
            "Вкажіть:\nІмʼя\nКонтакти\nПідприємство",
        ParkingForm.action.state:
            "Що потрібно зробити зі списком авто?",
        ParkingForm.cars.state:
            "Номер карти\nДержномер\nПІБ\nДата додавання авто",
        ParkingForm.media.state:
            "Додайте фото / відео / файл"
    }

    keyboards = {
        BuildingForm.problem_type.state: problem_keyboard,
        ParkingForm.action.state: parking_action_keyboard
    }

    await callback.message.answer(
        texts.get(prev, "Повернення"),
        reply_markup=keyboards.get(prev, back_keyboard())
    )

# ================== BUILDING FLOW ==================

@dp.callback_query(F.data == "start_building")
async def building_start(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer(
        "Введіть одним повідомленням:\n"
        "Імʼя та прізвище\nТелефон\nПідприємство / ФОП\nНомер приміщення",
        reply_markup=back_keyboard()
    )
    await set_state_with_history(state, BuildingForm.details)

@dp.message(BuildingForm.details)
async def building_details(message: Message, state: FSMContext):
    parts = message.text.split("\n")
    if len(parts) < 4:
        await message.answer("❌ Заповніть всі 4 рядки")
        return

    await state.update_data(
        name=parts[0], phone=parts[1],
        company=parts[2], room=parts[3]
    )

    await set_state_with_history(state, BuildingForm.problem_type)
    await message.answer("Оберіть тип проблеми:", reply_markup=problem_keyboard)

@dp.callback_query(BuildingForm.problem_type)
async def building_problem(callback: CallbackQuery, state: FSMContext):
    await state.update_data(problem=callback.data)
    await set_state_with_history(state, BuildingForm.problem_description)
    await callback.message.answer("Опишіть проблему:", reply_markup=back_keyboard())

@dp.message(BuildingForm.problem_description)
async def building_desc(message: Message, state: FSMContext):
    await state.update_data(description=message.text)
    await set_state_with_history(state, BuildingForm.media)
    await message.answer(
        "Додайте фото / відео / Excel / Word / PDF (за бажанням):",
        reply_markup=skip_keyboard
    )

@dp.message(BuildingForm.media)
async def building_media(message: Message, state: FSMContext):
    if not await handle_media(message, state):
        return

    data = await state.get_data()

    task = data.get("media_timeout_task")
    if task is not None and not task.done():
        task.cancel()

    if not message.media_group_id:
        logger.info("Одиночне медіа — відправляємо заявку одразу")
        await send_building(message, state)
        return

    new_task = asyncio.create_task(
        delayed_send(state, send_building, message)
    )

    await state.update_data(
        media_timeout_task=new_task,
        media_timeout_active=True,
        last_media_chat_id=message.chat.id,
        last_media_message_id=message.message_id
    )

    await message.answer("📸 Отримано. Чекаємо інші файли або натисніть «Пропустити»")


@dp.callback_query(BuildingForm.media, F.data == "skip")
async def building_skip(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    task = data.get("media_timeout_task")
    if task is not None and not task.done():
        task.cancel()
    await state.update_data(media_timeout_active=False, media_timeout_task=None)

    logger.info("Користувач натиснув 'Пропустити' — відправляємо заявку")
    await send_building(callback.message, state)
    await callback.answer("Заявку надіслано!")


async def send_building(message: Message, state: FSMContext):
    d = await state.get_data()
    number = get_next_request_number()

    text = (
        f"🏢 Заявка №{number} (Приміщення)\n\n"
        f"👤 Імʼя: {d.get('name', '—')}\n"
        f"📞 Контакти: {d.get('phone', '—')}\n"
        f"🏢 Підприємство/ФОП: {d.get('company', '—')}\n"
        f"🚪 Приміщення: {d.get('room', '—')}\n"
        f"🛠 Тип проблеми: {d.get('problem', '—')}\n"
        f"📝 Опис:\n{d.get('description', '—')}"
    )

    try:
        logger.info(f"[ЗАЯВКА {number}] Початок відправки в ЛС {message.chat.id} та групу {GROUP_ID}")
        logger.info(f"Текст заявки: {text[:100]}...")

        await send_result(message.chat.id, text, d)
        await send_result(GROUP_ID, text, d)

        logger.info(f"[ЗАЯВКА {number}] Успішно відправлено в обидва чати")

        await message.answer(
            "✅ Заявку успішно надіслано\n\nХочете створити нову?",
            reply_markup=start_button_keyboard()
        )
    except Exception as e:
        logger.error(f"[ЗАЯВКА {number}] Помилка відправки: {e}", exc_info=True)
        await message.answer("❌ Виникла помилка при відправці заявки. Спробуйте ще раз або зверніться до адміністратора.")
        return  # не очищаємо стан — можна повторити

    # Успішне завершення — очищаємо
    await state.update_data(
        media_list=[],
        sent_albums=[],
        media_timeout_active=False,
        media_timeout_task=None
    )
    await state.clear()
# ================== PARKING FLOW ==================

@dp.callback_query(F.data == "start_parking")
async def parking_start(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer(
        "Вкажіть одним повідомленням:\n"
        "Імʼя та прізвище\nКонтакти\nПідприємство",
        reply_markup=back_keyboard()
    )
    await set_state_with_history(state, ParkingForm.user_info)

@dp.message(ParkingForm.user_info)
async def parking_user(message: Message, state: FSMContext):
    parts = message.text.split("\n")
    if len(parts) < 3:
        await message.answer("❌ Заповніть всі 3 рядки")
        return

    await state.update_data(
        name=parts[0], phone=parts[1],
        company=parts[2]
    )
    await set_state_with_history(state, ParkingForm.action)
    await message.answer("Оберіть дію:", reply_markup=parking_action_keyboard)

@dp.callback_query(ParkingForm.action)
async def parking_action(callback: CallbackQuery, state: FSMContext):
    await state.update_data(action=callback.data)

    if callback.data == "Інше":
        await set_state_with_history(state, ParkingForm.cars)
        await callback.message.answer(
            "Номер картки\nОпишіть проблему",
            reply_markup=back_keyboard()
        )
        return

    await set_state_with_history(state, ParkingForm.cars)
    await callback.message.answer(
        "Номер карти\nДержномер\nПІБ\nДата додавання авто",
        reply_markup=back_keyboard()
    )

@dp.message(ParkingForm.cars)
async def parking_cars(message: Message, state: FSMContext):
    await state.update_data(cars=message.text)
    await set_state_with_history(state, ParkingForm.media)
    await message.answer(
        "Додайте файл / фото / відео (Excel, Word, PDF):",
        reply_markup=skip_keyboard
    )


@dp.message(ParkingForm.media)
async def parking_media(message: Message, state: FSMContext):
    if not await handle_media(message, state):
        return

    data = await state.get_data()

    task = data.get("media_timeout_task")
    if task is not None and not task.done():
        task.cancel()

    if not message.media_group_id:
        await send_parking(message, state)
        return

    new_task = asyncio.create_task(
        delayed_send(state, send_parking, message)
    )

    await state.update_data(
        media_timeout_task=new_task,
        media_timeout_active=True,
        last_media_chat_id=message.chat.id,
        last_media_message_id=message.message_id
    )

    await message.answer("📸 Отримано. Чекаємо інші файли або натисніть «Пропустити»")

@dp.callback_query(ParkingForm.media, F.data == "skip")
async def parking_skip(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    task = data.get("media_timeout_task")
    if task is not None and not task.done():
        task.cancel()
    await state.update_data(media_timeout_active=False, media_timeout_task=None)
    await send_parking(callback.message, state)
    await callback.answer("Заявку надіслано!")

async def send_parking(message: Message, state: FSMContext):
    d = await state.get_data()
    number = get_next_request_number()

    text = (
        f"🅿️ Заявка №{number} (Паркінг)\n\n"
        f"👤 Імʼя: {d.get('name', '—')}\n"
        f"📞 Контакти: {d.get('phone', '—')}\n"
        f"🏢 Підприємство: {d.get('company', '—')}\n"
        f"⚙️ Дія: {d.get('action', '—')}\n"
        f"🚗 Дані авто:\n{d.get('cars', '—')}"
    )

    try:
        logger.info(f"[ЗАЯВКА {number}] Початок відправки в ЛС {message.chat.id} та групу {GROUP_ID}")
        logger.info(f"Текст заявки: {text[:100]}...")

        await send_result(message.chat.id, text, d)
        await send_result(GROUP_ID, text, d)

        logger.info(f"[ЗАЯВКА {number}] Успішно відправлено в обидва чати")

        await message.answer(
            "✅ Заявку успішно надіслано\n\nХочете створити нову?",
            reply_markup=start_button_keyboard()
        )
    except Exception as e:
        logger.error(f"[ЗАЯВКА {number}] Помилка відправки: {e}", exc_info=True)
        await message.answer("❌ Виникла помилка при відправці заявки. Спробуйте ще раз або зверніться до адміністратора.")
        return

    await state.update_data(
        media_list=[],
        sent_albums=[],
        media_timeout_active=False,
        media_timeout_task=None
    )
    await state.clear()
# ================== SEND RESULT ==================

async def send_result(chat_id: int, text: str, data: dict):
    media_list = data.get("media_list", [])

    logger.info(f"send_result → чат {chat_id} | медіа: {len(media_list)} | текст: {text[:60]}...")

    if not media_list:
        try:
            await bot.send_message(chat_id, text)
            logger.info(f"Текстове повідомлення успішно відправлено в {chat_id}")
        except Exception as e:
            logger.error(f"Помилка відправки тексту в {chat_id}: {e}")
        return

    media_type = media_list[0]["type"] if media_list else None
    logger.info(f"Тип медіа: {media_type}, кількість: {len(media_list)}")

    input_media = []
    for m in media_list:
        if m["type"] in ["photo", "video"]:
            if m["type"] == "photo":
                input_media.append(InputMediaPhoto(media=m["id"]))
            elif m["type"] == "video":
                input_media.append(InputMediaVideo(media=m["id"]))
        elif m["type"] == "document":
            input_media.append(InputMediaDocument(media=m["id"]))

    if input_media:
        input_media[0].caption = text

    try:
        for i in range(0, len(input_media), 10):
            chunk = input_media[i:i + 10]
            if i > 0:
                chunk[0].caption = "Продовження до заявки"
            await bot.send_media_group(chat_id, chunk)
            logger.info(f"Медіа-група {i // 10 + 1} успішно відправлена в {chat_id}")
    except Exception as e:
        logger.error(f"Помилка відправки медіа-групи в {chat_id}: {e}")
# ================== RUN ==================

async def main():
    logger.info("Бот запущено. Очікуємо оновлень...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())