import asyncio
from aiogram import Bot, Dispatcher, F
from aiogram.types import (
    Message, CallbackQuery,
    InlineKeyboardButton, InlineKeyboardMarkup,
    ReplyKeyboardMarkup, KeyboardButton
)
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State

import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
GROUP_ID = int(os.getenv("GROUP_ID"))

# ================== НАСТРОЙКИ ==================

bot = Bot(BOT_TOKEN)
dp = Dispatcher()

# ================== КЛАВИАТУРЫ ==================

def start_button_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="🚀 Старт")]],
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
    [InlineKeyboardButton(text="🚰 Сантехніка", callback_data="plumbing")],
    [InlineKeyboardButton(text="⚡ Електрика", callback_data="electricity")],
    [InlineKeyboardButton(text="❄️ Кондиціонування/опалення", callback_data="climate")],
    [InlineKeyboardButton(text="🧱 Стіни/підлога/стеля", callback_data="walls")],
    [InlineKeyboardButton(text="❓ Інше", callback_data="other")],
    [InlineKeyboardButton(text="⬅️ Назад", callback_data="back")]
])

parking_action_keyboard = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="Додати / оновити", callback_data="add")],
    [InlineKeyboardButton(text="Видалити", callback_data="remove")],
    [InlineKeyboardButton(text="Інше", callback_data="other")],
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
    if message.photo:
        await state.update_data(
            media_type="photo",
            media_id=message.photo[-1].file_id
        )

    elif message.video:
        await state.update_data(
            media_type="video",
            media_id=message.video.file_id
        )

    elif message.document:
        filename = message.document.file_name.lower()
        allowed_ext = (".xls", ".xlsx", ".doc", ".docx", ".pdf")

        if not filename.endswith(allowed_ext):
            await message.answer("❌ Дозволені файли: Excel, Word або PDF")
            return False

        await state.update_data(
            media_type="document",
            media_id=message.document.file_id,
            media_name=message.document.file_name
        )

    else:
        await message.answer("❌ Непідтримуваний формат")
        return False

    return True

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
            "Номер карти\nДержномер\nПІБ\nДата",
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

@dp.message(BuildingForm.media, F.photo | F.video | F.document)
async def building_media(message: Message, state: FSMContext):
    if await handle_media(message, state):
        await send_building(message, state)

@dp.callback_query(BuildingForm.media, F.data == "skip")
async def building_skip(callback: CallbackQuery, state: FSMContext):
    await send_building(callback.message, state)

async def send_building(message: Message, state: FSMContext):
    d = await state.get_data()

    text = (
        f"🏢 Заявка (Приміщення)\n\n"
        f"👤 {d['name']}\n"
        f"📞 {d['phone']}\n"
        f"🏢 {d['company']}\n"
        f"🚪 Приміщення: {d['room']}\n"
        f"🛠 Тип проблеми: {d['problem']}\n"
        f"📝 Опис:\n{d['description']}"
    )

    # 👤 пользователю
    await send_result(message.chat.id, text, d)
    # 👥 в группу
    await send_result(GROUP_ID, text, d)
    await state.clear()
    await message.answer(
        "✅ Заявку успішно надіслано\n\nХочете створити нову?",
        reply_markup=start_button_keyboard()
    )


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
    await state.update_data(user_info=message.text)
    await set_state_with_history(state, ParkingForm.action)
    await message.answer("Оберіть дію:", reply_markup=parking_action_keyboard)

@dp.callback_query(ParkingForm.action)
async def parking_action(callback: CallbackQuery, state: FSMContext):
    await state.update_data(action=callback.data)
    await set_state_with_history(state, ParkingForm.cars)
    await callback.message.answer(
        "Номер карти\nДержномер\nПІБ\nДата",
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

@dp.message(ParkingForm.media, F.photo | F.video | F.document)
async def parking_media(message: Message, state: FSMContext):
    if await handle_media(message, state):
        await send_parking(message, state)

@dp.callback_query(ParkingForm.media, F.data == "skip")
async def parking_skip(callback: CallbackQuery, state: FSMContext):
    await send_parking(callback.message, state)

async def send_parking(message: Message, state: FSMContext):
    d = await state.get_data()

    text = (
        f"🅿️ Заявка (Паркінг)\n\n"
        f"👤 {d['user_info']}\n"
        f"⚙️ Дія: {d['action']}\n"
        f"🚗 Дані авто:\n{d['cars']}"
    )

    # 👤 пользователю
    await send_result(message.chat.id, text, d)
    # 👥 в группу
    await send_result(GROUP_ID, text, d)
    await state.clear()
    await message.answer(
        "✅ Заявку успішно надіслано\n\nХочете створити нову?",
        reply_markup=start_button_keyboard()
    )


# ================== SEND TO GROUP ==================
async def send_result(chat_id: int, text: str, data: dict):
    if data.get("media_type") == "photo":
        await bot.send_photo(chat_id, data["media_id"], caption=text)

    elif data.get("media_type") == "video":
        await bot.send_video(chat_id, data["media_id"], caption=text)

    elif data.get("media_type") == "document":
        await bot.send_document(
            chat_id,
            data["media_id"],
            caption=f"{text}\n\n📎 {data.get('media_name', '')}"
        )

    else:
        await bot.send_message(chat_id, text)

# ================== RUN ==================

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
