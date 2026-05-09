import asyncio
import logging
import os
import random
from datetime import datetime, timezone

import requests
from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import Command, CommandObject
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

# ====================== НАСТРОЙКИ ======================

BOT_TOKEN = "8703666493:AAFzQyIbJ4Rs5_9lHir9zbb1MYfiA12Smxo"
FIREBASE_URL = "https://pythonconnectsite-default-rtdb.europe-west1.firebasedatabase.app"
ADMIN_CODE = "2222"  # Код для доступа к админ-панели

# Храним ID админов в памяти (кто уже ввёл код)
admin_users = set()

# Логирование
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# ====================== FIREBASE КЛИЕНТ ======================
class FirebaseDB:
    """Простая обёртка для работы с REST API Firebase Realtime Database."""

    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")

    def _request(self, method: str, path: str, json_data: dict = None) -> dict | list | None:
        url = f"{self.base_url}/{path}.json"
        try:
            resp = requests.request(method, url, json=json_data, timeout=10)
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as e:
            logger.error(f"Firebase request failed: {e}")
            return None

    # ---------- Студенты ----------
    def get_all_students(self) -> dict:
        """Возвращает словарь {uid: данные студента}."""
        data = self._request("GET", "students")
        return data if isinstance(data, dict) else {}

    def get_student(self, uid: str) -> dict | None:
        data = self._request("GET", f"students/{uid}")
        return data if isinstance(data, dict) else None

    def add_student(self, name: str) -> str | None:
        """Добавляет студента и возвращает его UID."""
        student_data = {
            "name": name,
            "isDuty": False,
            "lastDutyDate": None,
            "totalDutyCount": 0,
            "createdAt": int(datetime.now(timezone.utc).timestamp() * 1000)
        }
        resp = requests.post(
            f"{self.base_url}/students.json", json=student_data, timeout=10
        )
        if resp.status_code == 200:
            return resp.json().get("name")  # Firebase возвращает {"name": "uid"}
        return None

    def delete_student(self, uid: str) -> bool:
        """Удаляет студента по UID."""
        resp = requests.delete(
            f"{self.base_url}/students/{uid}.json", timeout=10
        )
        return resp.status_code == 200

    def update_student(self, uid: str, updates: dict) -> bool:
        """Обновить только переданные поля (PATCH)."""
        resp = requests.patch(
            f"{self.base_url}/students/{uid}.json", json=updates, timeout=10
        )
        return resp.status_code == 200

    def search_students(self, query: str) -> dict:
        """Поиск студентов по имени (регистронезависимый)."""
        all_students = self.get_all_students()
        query = query.lower()
        return {
            uid: data for uid, data in all_students.items()
            if query in data.get("name", "").lower()
        }

    # ---------- История дежурств ----------
    def add_history_record(self, record: dict) -> bool:
        """Добавить запись в /history (POST – авто‑ID)."""
        resp = requests.post(
            f"{self.base_url}/history.json", json=record, timeout=10
        )
        return resp.status_code == 200

    def get_history(self) -> list | None:
        data = self._request("GET", "history")
        if isinstance(data, dict):
            return list(data.values())
        return []

    def delete_history(self) -> bool:
        """Очистить всю историю."""
        resp = requests.delete(
            f"{self.base_url}/history.json", timeout=10
        )
        return resp.status_code == 200

    # ---------- Настройки ----------
    def get_settings(self) -> dict:
        data = self._request("GET", "settings")
        return data if isinstance(data, dict) else {}

    def get_admins(self) -> list:
        settings = self.get_settings()
        return settings.get("adminIds", [])

db = FirebaseDB(FIREBASE_URL)

# ====================== FSM ДЛЯ АДМИНКИ ======================
class AdminStates(StatesGroup):
    waiting_for_code = State()
    waiting_for_student_add = State()
    waiting_for_student_delete = State()
    waiting_for_student_search = State()
    waiting_for_assign_duty = State()

# ====================== КНОПКИ И КЛАВИАТУРЫ ======================
def main_keyboard() -> InlineKeyboardMarkup:
    """Главное меню."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🎯 Случайный дежурный", callback_data="duty_random")],
            [InlineKeyboardButton(text="📋 Список студентов", callback_data="students_list")],
            [InlineKeyboardButton(text="📊 История дежурств", callback_data="duty_history")],
            [InlineKeyboardButton(text="🔍 Поиск студента", callback_data="search_student")],
            [InlineKeyboardButton(text="🔐 Админ-панель", callback_data="admin_panel")],
            [InlineKeyboardButton(text="ℹ️ Помощь", callback_data="help")],
        ]
    )

def back_keyboard() -> InlineKeyboardMarkup:
    """Кнопка возврата в меню."""
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="🔙 В главное меню", callback_data="main_menu")]]
    )

def admin_keyboard() -> InlineKeyboardMarkup:
    """Кнопки админ-панели."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="➕ Добавить студента", callback_data="admin_add_student")],
            [InlineKeyboardButton(text="➖ Удалить студента", callback_data="admin_delete_student")],
            [InlineKeyboardButton(text="👥 Все студенты", callback_data="admin_all_students")],
            [InlineKeyboardButton(text="🔄 Сбросить дежурства", callback_data="admin_reset_duty")],
            [InlineKeyboardButton(text="🗑️ Очистить историю", callback_data="admin_clear_history")],
            [InlineKeyboardButton(text="📊 Админ-статистика", callback_data="admin_stats")],
            [InlineKeyboardButton(text="🔙 Главное меню", callback_data="main_menu")],
        ]
    )

# ====================== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ======================
def is_admin(user_id: int) -> bool:
    """Проверка, является ли пользователь админом."""
    return user_id in admin_users

async def assign_random_duty() -> tuple[str, str | None]:
    """
    Выбирает случайного студента, обновляет его поля в Firebase.
    Возвращает (текст_результата, uid_студента)
    """
    students = db.get_all_students()
    if not students:
        return "❌ Список студентов пуст.", None

    uid, student = random.choice(list(students.items()))
    now = datetime.now(timezone.utc).isoformat()

    success = db.update_student(
        uid,
        {
            "isDuty": True,
            "lastDutyDate": now,
            "totalDutyCount": student.get("totalDutyCount", 0) + 1,
        },
    )
    if not success:
        logger.error(f"Не удалось обновить данные студента {uid}")
        return "⚠️ Ошибка при назначении дежурного.", None

    record = {
        "student_name": student["name"],
        "student_id": uid,
        "assigned_at": now,
    }
    db.add_history_record(record)

    return f"✅ Дежурный сегодня: <b>{student['name']}</b>", uid

def reset_duty_for_all() -> str:
    """Сбрасывает флаг isDuty у всех студентов."""
    students = db.get_all_students()
    if not students:
        return "⚠️ Нет студентов для сброса."
    
    count = 0
    for uid in students:
        if db.update_student(uid, {"isDuty": False}):
            count += 1
    
    return f"🔄 Флаги дежурств сброшены у {count} студентов."

# ====================== ХЕНДЛЕРЫ ======================
router = Router()

# ------------------ Базовые команды ------------------
@router.message(Command("start"))
async def start_command(message: Message):
    await message.answer(
        "👋 Привет! Я бот для выбора дежурного.\n\n"
        "Выбери действие:",
        reply_markup=main_keyboard(),
    )

@router.message(Command("help"))
async def help_message(message: Message):
    text = (
        "ℹ️ <b>Доступные команды:</b>\n\n"
        "/start – главное меню\n"
        "/admin – админ-панель (код: 2222)\n\n"
        "<b>Возможности:</b>\n"
        "• Случайный выбор дежурного\n"
        "• Просмотр списка студентов\n"
        "• История дежурств\n"
        "• Поиск студентов\n"
        "• Админ-панель для управления"
    )
    await message.answer(text, parse_mode="HTML")

# ------------------ Главное меню (callback) ------------------
@router.callback_query(F.data == "main_menu")
async def main_menu_callback(call: CallbackQuery):
    await call.message.edit_text("Главное меню:", reply_markup=main_keyboard())
    await call.answer()

@router.callback_query(F.data == "duty_random")
async def duty_random_callback(call: CallbackQuery):
    result, _ = await assign_random_duty()
    await call.message.edit_text(result, reply_markup=back_keyboard(), parse_mode="HTML")
    await call.answer()

@router.callback_query(F.data == "students_list")
async def students_list_callback(call: CallbackQuery):
    students = db.get_all_students()
    if not students:
        text = "📭 Список пуст."
    else:
        text = "👥 <b>Студенты:</b>\n\n"
        for i, (uid, s) in enumerate(students.items(), 1):
            duty_status = "🟢" if s.get('isDuty') else "⚪"
            text += f"{i}. {duty_status} {s['name']} – дежурств: {s.get('totalDutyCount', 0)}\n"
    
    if len(text) > 4000:
        # Разбиваем на страницы, если много студентов
        text = text[:4000] + "\n\n⚠️ Список обрезан. Используйте поиск."
    
    await call.message.edit_text(text, reply_markup=back_keyboard(), parse_mode="HTML")
    await call.answer()

@router.callback_query(F.data == "duty_history")
async def duty_history_callback(call: CallbackQuery):
    history = db.get_history()
    if not history:
        text = "📭 История дежурств пуста."
    else:
        text = "📊 <b>Последние дежурства:</b>\n\n"
        for rec in history[-15:][::-1]:
            name = rec.get("student_name", "?")
            when = rec.get("assigned_at", "?")[:19]
            text += f"🔹 {name} — {when}\n"
    
    if len(text) > 4000:
        text = text[:4000] + "\n... (обрезано)"
    
    await call.message.edit_text(text, reply_markup=back_keyboard(), parse_mode="HTML")
    await call.answer()

@router.callback_query(F.data == "search_student")
async def search_student_callback(call: CallbackQuery, state: FSMContext):
    await call.message.edit_text(
        "🔍 Введите имя студента для поиска (или часть имени):",
        reply_markup=back_keyboard()
    )
    await state.set_state(AdminStates.waiting_for_student_search)
    await call.answer()

@router.callback_query(F.data == "help")
async def help_callback(call: CallbackQuery):
    text = (
        "ℹ️ <b>Справка</b>\n\n"
        "/start – открыть меню\n"
        "/admin – админ-панель (код 1234)\n\n"
        "<b>Админ-панель позволяет:</b>\n"
        "➕ Добавлять студентов\n"
        "➖ Удалять студентов\n"
        "🔄 Сбрасывать дежурства\n"
        "🗑️ Очищать историю\n\n"
        "Бот автоматически ведёт учёт дежурств и историю."
    )
    await call.message.edit_text(text, reply_markup=back_keyboard(), parse_mode="HTML")
    await call.answer()

# ------------------ Админ-панель ------------------
@router.message(Command("admin"))
async def admin_command(message: Message, state: FSMContext):
    await message.answer("🔐 Введите код доступа к админ-панели:")
    await state.set_state(AdminStates.waiting_for_code)

@router.callback_query(F.data == "admin_panel")
async def admin_panel_callback(call: CallbackQuery, state: FSMContext):
    if is_admin(call.from_user.id):
        await call.message.edit_text("🔐 Админ-панель:", reply_markup=admin_keyboard())
    else:
        await call.message.edit_text("🔐 Введите код доступа к админ-панели:", reply_markup=back_keyboard())
        await state.set_state(AdminStates.waiting_for_code)
    await call.answer()

@router.message(AdminStates.waiting_for_code)
async def check_admin_code(message: Message, state: FSMContext):
    if message.text == ADMIN_CODE:
        admin_users.add(message.from_user.id)
        await message.answer("✅ Доступ разрешён! Админ-панель:", reply_markup=admin_keyboard())
        await state.clear()
    else:
        await message.answer("❌ Неверный код! Попробуйте снова или /start")
        await state.set_state(AdminStates.waiting_for_code)

# ------------------ Админ-панель: действия ------------------
@router.callback_query(F.data == "admin_add_student")
async def admin_add_student_callback(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        await call.answer("⛔ Нет доступа!", show_alert=True)
        return
    
    await call.message.edit_text(
        "➕ Введите имя нового студента (или /cancel для отмены):",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="🔙 К админ-панели", callback_data="admin_panel")]]
        )
    )
    await state.set_state(AdminStates.waiting_for_student_add)
    await call.answer()

@router.callback_query(F.data == "admin_delete_student")
async def admin_delete_student_callback(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        await call.answer("⛔ Нет доступа!", show_alert=True)
        return
    
    students = db.get_all_students()
    if not students:
        await call.message.edit_text("📭 Список студентов пуст.", reply_markup=admin_keyboard())
        await call.answer()
        return
    
    keyboard = []
    for uid, student in list(students.items())[:20]:  # Показываем первых 20
        keyboard.append([InlineKeyboardButton(
            text=f"❌ {student['name']}", 
            callback_data=f"confirm_delete_{uid}"
        )])
    
    keyboard.append([InlineKeyboardButton(text="🔙 К админ-панели", callback_data="admin_panel")])
    
    await call.message.edit_text(
        "➖ Выберите студента для удаления:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
    )
    await call.answer()

@router.callback_query(F.data.startswith("confirm_delete_"))
async def confirm_delete_callback(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        await call.answer("⛔ Нет доступа!", show_alert=True)
        return
    
    uid = call.data.split("confirm_delete_")[1]
    student = db.get_student(uid)
    
    if not student:
        await call.answer("Студент не найден!", show_alert=True)
        return
    
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Да, удалить", callback_data=f"delete_{uid}"),
                InlineKeyboardButton(text="❌ Нет", callback_data="admin_delete_student"),
            ]
        ]
    )
    
    await call.message.edit_text(
        f"Вы уверены, что хотите удалить студента:\n\n"
        f"<b>{student['name']}</b>\n\n"
        f"Дежурств: {student.get('totalDutyCount', 0)}",
        reply_markup=keyboard,
        parse_mode="HTML"
    )
    await call.answer()

@router.callback_query(F.data.startswith("delete_"))
async def delete_student_callback(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        await call.answer("⛔ Нет доступа!", show_alert=True)
        return
    
    uid = call.data.split("delete_")[1]
    student = db.get_student(uid)
    
    if not student:
        await call.answer("Студент не найден!", show_alert=True)
        return
    
    if db.delete_student(uid):
        await call.message.edit_text(
            f"✅ Студент <b>{student['name']}</b> удалён!",
            reply_markup=admin_keyboard(),
            parse_mode="HTML"
        )
    else:
        await call.message.edit_text(
            "❌ Ошибка при удалении!",
            reply_markup=admin_keyboard()
        )
    await call.answer()

@router.callback_query(F.data == "admin_all_students")
async def admin_all_students_callback(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        await call.answer("⛔ Нет доступа!", show_alert=True)
        return
    
    students = db.get_all_students()
    if not students:
        await call.message.edit_text("📭 Список пуст.", reply_markup=admin_keyboard())
    else:
        text = "👥 <b>Все студенты (админ):</b>\n\n"
        for i, (uid, s) in enumerate(students.items(), 1):
            duty_status = "🟢" if s.get('isDuty') else "⚪"
            text += f"{i}. {duty_status} {s['name']} [ID: {uid}]\n"
            text += f"   Дежурств: {s.get('totalDutyCount', 0)} | "
            text += f"Последнее: {s.get('lastDutyDate', 'нет')}\n"
        
        if len(text) > 4000:
            text = text[:4000] + "\n\n⚠️ Список обрезан."
        
        await call.message.edit_text(text, reply_markup=admin_keyboard(), parse_mode="HTML")
    await call.answer()

@router.callback_query(F.data == "admin_reset_duty")
async def admin_reset_duty_callback(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        await call.answer("⛔ Нет доступа!", show_alert=True)
        return
    
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Да, сбросить", callback_data="confirm_reset"),
                InlineKeyboardButton(text="❌ Нет", callback_data="admin_panel"),
            ]
        ]
    )
    
    await call.message.edit_text(
        "⚠️ Вы уверены, что хотите сбросить все флаги дежурств?",
        reply_markup=keyboard
    )
    await call.answer()

@router.callback_query(F.data == "confirm_reset")
async def confirm_reset_callback(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        await call.answer("⛔ Нет доступа!", show_alert=True)
        return
    
    result = reset_duty_for_all()
    await call.message.edit_text(result, reply_markup=admin_keyboard())
    await call.answer()

@router.callback_query(F.data == "admin_clear_history")
async def admin_clear_history_callback(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        await call.answer("⛔ Нет доступа!", show_alert=True)
        return
    
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Да, очистить", callback_data="confirm_clear_history"),
                InlineKeyboardButton(text="❌ Нет", callback_data="admin_panel"),
            ]
        ]
    )
    
    await call.message.edit_text(
        "⚠️ Вы уверены, что хотите полностью очистить историю дежурств?",
        reply_markup=keyboard
    )
    await call.answer()

@router.callback_query(F.data == "confirm_clear_history")
async def confirm_clear_history_callback(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        await call.answer("⛔ Нет доступа!", show_alert=True)
        return
    
    if db.delete_history():
        await call.message.edit_text("🗑️ История дежурств очищена!", reply_markup=admin_keyboard())
    else:
        await call.message.edit_text("❌ Ошибка при очистке!", reply_markup=admin_keyboard())
    await call.answer()

@router.callback_query(F.data == "admin_stats")
async def admin_stats_callback(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        await call.answer("⛔ Нет доступа!", show_alert=True)
        return
    
    students = db.get_all_students()
    history = db.get_history()
    
    total_students = len(students)
    total_duties = sum(s.get("totalDutyCount", 0) for s in students.values())
    total_history = len(history) if history else 0
    current_duty = [s for s in students.values() if s.get("isDuty")]
    
    text = (
        "📊 <b>Админ-статистика</b>\n\n"
        f"👥 Всего студентов: {total_students}\n"
        f"📋 Всего дежурств назначено: {total_duties}\n"
        f"📝 Записей в истории: {total_history}\n"
        f"🟢 Текущий дежурный: {current_duty[0]['name'] if current_duty else 'не назначен'}\n"
        f"🛡️ Админов в сессии: {len(admin_users)}"
    )
    
    await call.message.edit_text(text, reply_markup=admin_keyboard(), parse_mode="HTML")
    await call.answer()

# ------------------ Обработка текстовых сообщений ------------------
@router.message(AdminStates.waiting_for_student_add)
async def process_student_add(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        await message.answer("⛔ Нет доступа!")
        await state.clear()
        return
    
    if message.text == "/cancel":
        await message.answer("❌ Добавление отменено.", reply_markup=admin_keyboard())
        await state.clear()
        return
    
    name = message.text.strip()
    if len(name) < 2:
        await message.answer("❌ Имя слишком короткое! Минимум 2 символа.")
        return
    
    uid = db.add_student(name)
    if uid:
        await message.answer(f"✅ Студент <b>{name}</b> добавлен! ID: {uid}", reply_markup=admin_keyboard(), parse_mode="HTML")
    else:
        await message.answer("❌ Ошибка при добавлении!", reply_markup=admin_keyboard())
    
    await state.clear()

@router.message(AdminStates.waiting_for_student_search)
async def process_student_search(message: Message, state: FSMContext):
    query = message.text.strip()
    if not query:
        await message.answer("❌ Введите имя для поиска!")
        return
    
    results = db.search_students(query)
    if not results:
        await message.answer("🔍 Ничего не найдено.", reply_markup=main_keyboard())
    else:
        text = f"🔍 <b>Результаты поиска по '{query}':</b>\n\n"
        for i, (uid, s) in enumerate(results.items(), 1):
            duty_status = "🟢" if s.get('isDuty') else "⚪"
            text += f"{i}. {duty_status} {s['name']} – дежурств: {s.get('totalDutyCount', 0)}\n"
        
        await message.answer(text, reply_markup=main_keyboard(), parse_mode="HTML")
    
    await state.clear()

@router.message(Command("cancel"))
async def cancel_command(message: Message, state: FSMContext):
    current_state = await state.get_state()
    if current_state:
        await state.clear()
        await message.answer("❌ Действие отменено.", reply_markup=main_keyboard())
    else:
        await message.answer("Нет активных действий для отмены.")

@router.message()
async def fallback(message: Message):
    await message.answer(
        "Я не понимаю текстовые команды. Используйте /start или кнопки меню.",
        reply_markup=main_keyboard()
    )

# ====================== ЗАПУСК ======================
async def main():
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(router)

    logger.info("Бот запущен")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())