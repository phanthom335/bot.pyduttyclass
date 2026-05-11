#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════════╗
║           PDP SCHOOL ECOSYSTEM PLATFORM — ЕДИНЫЙ ФАЙЛ (v2.0)      ║
║   Учебный год 2025–2026                                            ║
║   Telegram-бот для управления классом: дежурства, расписание,     ║
║   новости, опросы, викторины, рейтинги, мини-игры и многое другое.║
╚══════════════════════════════════════════════════════════════════════╝
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import logging.handlers
import math
import os
import random
import sys
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Awaitable, Callable, Final, Optional, TypeVar

import aiohttp
from aiogram import BaseMiddleware, Bot, Dispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramAPIError
from aiogram.filters import Command, CommandObject, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
    TelegramObject,
)
from dotenv import load_dotenv

# ══════════════════════════════════════════════════════════════════════
# 0. ИНИЦИАЛИЗАЦИЯ ОКРУЖЕНИЯ
# ══════════════════════════════════════════════════════════════════════

BASE_DIR: Final[Path] = Path(__file__).parent
load_dotenv(BASE_DIR / ".env")

# ── Константы подключения ────────────────────────────────────────────
BOT_TOKEN: Final[str] = "8703666493:AAFzQyIbJ4Rs5_9lHir9zbb1MYfiA12Smxo"
FIREBASE_URL: Final[str] = "https://pythonconnectsite-default-rtdb.europe-west1.firebasedatabase.app"
ADMIN_CODE: Final[str] = "2222"

OWNER_ID: Final[int] = int(os.getenv("5616034990", "0"))

CLASS_NAME: Final[str]   = os.getenv("CLASS_NAME", "6-А")
CLASS_SCHOOL: Final[str] = os.getenv("CLASS_SCHOOL", "PDP School")
CLASS_YEAR: Final[str]   = os.getenv("CLASS_YEAR", "2025–2026")

# ── Rate-limit ───────────────────────────────────────────────────────
RATE_LIMIT_MESSAGES: Final[int] = 5
RATE_LIMIT_WINDOW:   Final[int] = 8
RATE_LIMIT_COOLDOWN: Final[int] = 30

# ── Pagination ───────────────────────────────────────────────────────
PAGE_SIZE_STUDENTS: Final[int] = 10
PAGE_SIZE_HISTORY:  Final[int] = 10
PAGE_SIZE_NEWS:     Final[int] = 5
PAGE_SIZE_HOMEWORK: Final[int] = 8

# ── Cache TTL ────────────────────────────────────────────────────────
CACHE_TTL_STUDENTS:  Final[int] = 60
CACHE_TTL_SCHEDULE:  Final[int] = 300
CACHE_TTL_NEWS:      Final[int] = 120
CACHE_TTL_SETTINGS:  Final[int] = 600

# ── XP / Gamification ────────────────────────────────────────────────
XP_FOR_DUTY:        Final[int] = 20
XP_FOR_DAILY_LOGIN: Final[int] = 5
XP_FOR_QUIZ_RIGHT:  Final[int] = 15
XP_FOR_QUIZ_WRONG:  Final[int] = 2
XP_FOR_POLL_VOTE:   Final[int] = 3

LEVEL_THRESHOLDS: Final[list[int]] = [
    0, 50, 120, 220, 350, 520, 730, 990, 1300, 1680, 2150,
    2720, 3410, 4230, 5200, 6340, 7670, 9210, 11000, 13000,
]

LEVEL_TITLES: Final[list[str]] = [
    "🔘 Новичок",      "⚪ Ученик",       "🔵 Активный",    "🟢 Старательный",
    "🟡 Отличник",     "🟠 Умник",        "🔴 Эксперт",     "🟣 Мастер",
    "💎 Элита",        "👑 Легенда",       "🌟 Чемпион",     "⚡ Гений",
    "🔥 Феномен",      "🌌 Астронавт",     "🏆 Победитель",  "🎓 Академик",
    "💫 Виртуоз",      "🚀 Пионер",        "🌈 Уникум",      "👑 Непревзойдённый",
]

# ── Scheduler ────────────────────────────────────────────────────────
MORNING_NOTIFY_HOUR:   Final[int] = 7
MORNING_NOTIFY_MINUTE: Final[int] = 30
TIMEZONE: Final[str] = "Asia/Tashkent"

# ── Firebase paths ───────────────────────────────────────────────────
class FB:
    STUDENTS:   Final[str] = "students"
    HISTORY:    Final[str] = "history"
    SETTINGS:   Final[str] = "settings"
    SCHEDULE:   Final[str] = "schedule"
    NEWS:       Final[str] = "news"
    HOMEWORKS:  Final[str] = "homeworks"
    EVENTS:     Final[str] = "events"
    POLLS:      Final[str] = "polls"
    ANONYMOUS:  Final[str] = "anonymous_messages"
    BIRTHDAYS:  Final[str] = "birthdays"
    RATINGS:    Final[str] = "ratings"
    QUIZZES:    Final[str] = "quizzes"
    CLASS_INFO: Final[str] = "class_info"
    USERS:      Final[str] = "users"
    MODERATORS: Final[str] = "moderators"
    BROADCASTS: Final[str] = "broadcasts"
    DUTY_QUEUE: Final[str] = "duty_queue"

# ── Logging ──────────────────────────────────────────────────────────
LOG_LEVEL:  Final[str] = os.getenv("LOG_LEVEL", "INFO")
LOG_FILE:   Final[Path] = BASE_DIR / "logs" / "bot.log"
LOG_FORMAT: Final[str] = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
LOG_MAX_BYTES: Final[int] = 5 * 1024 * 1024
LOG_BACKUP_COUNT: Final[int] = 3

LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format=LOG_FORMAT,
    handlers=[
        logging.StreamHandler(),
        logging.handlers.RotatingFileHandler(
            LOG_FILE, maxBytes=LOG_MAX_BYTES, backupCount=LOG_BACKUP_COUNT, encoding="utf-8"
        ),
    ] if LOG_FILE else [logging.StreamHandler()],
)
logger = logging.getLogger(__name__)

# ── Days of week ─────────────────────────────────────────────────────
DAYS_RU: Final[list[str]] = [
    "Понедельник", "Вторник", "Среда",
    "Четверг", "Пятница", "Суббота", "Воскресенье",
]
DAYS_SHORT: Final[list[str]] = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
DAYS_KEYS:  Final[list[str]] = [
    "monday", "tuesday", "wednesday",
    "thursday", "friday", "saturday", "sunday",
]

# ── UI constants ─────────────────────────────────────────────────────
SEPARATOR: Final[str]      = "━" * 28
SEPARATOR_THIN: Final[str] = "─" * 28

ROLE_ICONS: Final[dict[str, str]] = {
    "owner":     "👑",
    "moderator": "🛡️",
    "student":   "👨‍🎓",
}

MEDAL_ICONS: Final[list[str]] = ["🥇", "🥈", "🥉"]

DOTS:   Final[str] = "◆"
ARROW_R: Final[str] = "▸"
STAR:   Final[str] = "✦"

T = TypeVar("T")

# ══════════════════════════════════════════════════════════════════════
# 1. ENUMS
# ══════════════════════════════════════════════════════════════════════

class UserRole(str, Enum):
    OWNER     = "owner"
    MODERATOR = "moderator"
    STUDENT   = "student"


class NewsCategory(str, Enum):
    URGENT     = "urgent"
    GENERAL    = "general"
    SCHEDULE   = "schedule"
    EXAM       = "exam"
    EVENT      = "event"
    HOMEWORK   = "homework"
    CONTEST    = "contest"
    VOTE       = "vote"
    OTHER      = "other"


class GameType(str, Enum):
    QUIZ        = "quiz"
    COIN_FLIP   = "coin_flip"
    DICE        = "dice"
    WHEEL       = "wheel"
    TRUTH_DARE  = "truth_dare"
    RPG         = "rpg"


class DayOfWeek(str, Enum):
    MONDAY    = "monday"
    TUESDAY   = "tuesday"
    WEDNESDAY = "wednesday"
    THURSDAY  = "thursday"
    FRIDAY    = "friday"
    SATURDAY  = "saturday"
    SUNDAY    = "sunday"


class PollStatus(str, Enum):
    ACTIVE   = "active"
    CLOSED   = "closed"
    ARCHIVED = "archived"


# ══════════════════════════════════════════════════════════════════════
# 2. DATA MODELS (dataclasses)
# ══════════════════════════════════════════════════════════════════════

@dataclass
class Student:
    uid:             str
    name:            str
    is_duty:         bool          = False
    last_duty_date:  Optional[str] = None
    total_duty_count:int           = 0
    created_at:      int           = 0
    xp:              int           = 0
    level:           int           = 1
    streak:          int           = 0
    last_active:     Optional[str] = None
    emoji:           str           = "👤"
    bio:             str           = ""
    birthday:        Optional[str] = None
    telegram_id:     Optional[int] = None
    quiz_correct:    int           = 0
    quiz_total:      int           = 0
    games_played:    int           = 0
    polls_voted:     int           = 0

    @classmethod
    def from_dict(cls, uid: str, data: dict[str, Any]) -> "Student":
        return cls(
            uid              = uid,
            name             = data.get("name", "Неизвестный"),
            is_duty          = data.get("isDuty", False),
            last_duty_date   = data.get("lastDutyDate"),
            total_duty_count = data.get("totalDutyCount", 0),
            created_at       = data.get("createdAt", 0),
            xp               = data.get("xp", 0),
            level            = data.get("level", 1),
            streak           = data.get("streak", 0),
            last_active      = data.get("lastActive"),
            emoji            = data.get("emoji", "👤"),
            bio              = data.get("bio", ""),
            birthday         = data.get("birthday"),
            telegram_id      = data.get("telegramId"),
            quiz_correct     = data.get("quizCorrect", 0),
            quiz_total       = data.get("quizTotal", 0),
            games_played     = data.get("gamesPlayed", 0),
            polls_voted      = data.get("pollsVoted", 0),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "name":            self.name,
            "isDuty":          self.is_duty,
            "lastDutyDate":    self.last_duty_date,
            "totalDutyCount":  self.total_duty_count,
            "createdAt":       self.created_at,
            "xp":              self.xp,
            "level":           self.level,
            "streak":          self.streak,
            "lastActive":      self.last_active,
            "emoji":           self.emoji,
            "bio":             self.bio,
            "birthday":        self.birthday,
            "telegramId":      self.telegram_id,
            "quizCorrect":     self.quiz_correct,
            "quizTotal":       self.quiz_total,
            "gamesPlayed":     self.games_played,
            "pollsVoted":      self.polls_voted,
        }

    @property
    def duty_rate(self) -> float:
        return self.total_duty_count

    @property
    def quiz_accuracy(self) -> float:
        if self.quiz_total == 0:
            return 0.0
        return round(self.quiz_correct / self.quiz_total * 100, 1)


@dataclass
class DutyRecord:
    student_name: str
    student_id:   str
    assigned_at:  str
    assigned_by:  str   = "system"

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DutyRecord":
        return cls(
            student_name = data.get("student_name", "?"),
            student_id   = data.get("student_id", ""),
            assigned_at  = data.get("assigned_at", ""),
            assigned_by  = data.get("assigned_by", "system"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "student_name": self.student_name,
            "student_id":   self.student_id,
            "assigned_at":  self.assigned_at,
            "assigned_by":  self.assigned_by,
        }


@dataclass
class Lesson:
    number:  int
    subject: str
    teacher: str = ""
    room:    str = ""
    note:    str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Lesson":
        return cls(
            number  = data.get("number", 0),
            subject = data.get("subject", ""),
            teacher = data.get("teacher", ""),
            room    = data.get("room", ""),
            note    = data.get("note", ""),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "number":  self.number,
            "subject": self.subject,
            "teacher": self.teacher,
            "room":    self.room,
            "note":    self.note,
        }


@dataclass
class DaySchedule:
    day:     str
    lessons: list[Lesson] = field(default_factory=list)

    @classmethod
    def from_dict(cls, day: str, data: dict[str, Any]) -> "DaySchedule":
        lessons = []
        for item in (data.get("lessons") or {}).values():
            lessons.append(Lesson.from_dict(item))
        lessons.sort(key=lambda l: l.number)
        return cls(day=day, lessons=lessons)


@dataclass
class NewsItem:
    uid:        str
    title:      str
    body:       str
    category:   str   = NewsCategory.GENERAL
    author:     str   = "Администратор"
    created_at: str   = ""
    pinned:     bool  = False
    views:      int   = 0

    @classmethod
    def from_dict(cls, uid: str, data: dict[str, Any]) -> "NewsItem":
        return cls(
            uid        = uid,
            title      = data.get("title", "Без заголовка"),
            body       = data.get("body", ""),
            category   = data.get("category", NewsCategory.GENERAL),
            author     = data.get("author", "Администратор"),
            created_at = data.get("createdAt", ""),
            pinned     = data.get("pinned", False),
            views      = data.get("views", 0),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "title":     self.title,
            "body":      self.body,
            "category":  self.category,
            "author":    self.author,
            "createdAt": self.created_at,
            "pinned":    self.pinned,
            "views":     self.views,
        }

    @property
    def category_icon(self) -> str:
        icons = {
            NewsCategory.URGENT:   "🚨",
            NewsCategory.GENERAL:  "📢",
            NewsCategory.SCHEDULE: "📚",
            NewsCategory.EXAM:     "📝",
            NewsCategory.EVENT:    "🎉",
            NewsCategory.HOMEWORK: "📖",
            NewsCategory.CONTEST:  "🏆",
            NewsCategory.VOTE:     "🗳️",
            NewsCategory.OTHER:    "📌",
        }
        return icons.get(self.category, "📢")


@dataclass
class HomeworkItem:
    uid:        str
    subject:    str
    task:       str
    due_date:   str
    created_at: str   = ""
    author:     str   = "Учитель"
    priority:   str   = "normal"

    @classmethod
    def from_dict(cls, uid: str, data: dict[str, Any]) -> "HomeworkItem":
        return cls(
            uid        = uid,
            subject    = data.get("subject", ""),
            task       = data.get("task", ""),
            due_date   = data.get("dueDate", ""),
            created_at = data.get("createdAt", ""),
            author     = data.get("author", "Учитель"),
            priority   = data.get("priority", "normal"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "subject":   self.subject,
            "task":      self.task,
            "dueDate":   self.due_date,
            "createdAt": self.created_at,
            "author":    self.author,
            "priority":  self.priority,
        }

    @property
    def priority_icon(self) -> str:
        return {"low": "🟢", "normal": "🟡", "high": "🔴"}.get(self.priority, "🟡")


@dataclass
class ClassEvent:
    uid:         str
    title:       str
    description: str
    date:        str
    time:        str    = ""
    location:    str    = ""
    created_at:  str    = ""

    @classmethod
    def from_dict(cls, uid: str, data: dict[str, Any]) -> "ClassEvent":
        return cls(
            uid         = uid,
            title       = data.get("title", ""),
            description = data.get("description", ""),
            date        = data.get("date", ""),
            time        = data.get("time", ""),
            location    = data.get("location", ""),
            created_at  = data.get("createdAt", ""),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "title":       self.title,
            "description": self.description,
            "date":        self.date,
            "time":        self.time,
            "location":    self.location,
            "createdAt":   self.created_at,
        }


@dataclass
class PollOption:
    text:  str
    votes: int = 0

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PollOption":
        return cls(text=data.get("text", ""), votes=data.get("votes", 0))

    def to_dict(self) -> dict[str, Any]:
        return {"text": self.text, "votes": self.votes}


@dataclass
class Poll:
    uid:        str
    question:   str
    options:    list[PollOption] = field(default_factory=list)
    status:     str              = PollStatus.ACTIVE
    created_at: str              = ""
    author:     str              = "Администратор"
    voters:     list[int]        = field(default_factory=list)

    @classmethod
    def from_dict(cls, uid: str, data: dict[str, Any]) -> "Poll":
        raw_opts = data.get("options") or {}
        options = [PollOption.from_dict(v) for v in raw_opts.values()]
        return cls(
            uid        = uid,
            question   = data.get("question", ""),
            options    = options,
            status     = data.get("status", PollStatus.ACTIVE),
            created_at = data.get("createdAt", ""),
            author     = data.get("author", "Администратор"),
            voters     = data.get("voters") or [],
        )

    @property
    def total_votes(self) -> int:
        return sum(o.votes for o in self.options)


@dataclass
class QuizQuestion:
    uid:            str
    question:       str
    options:        list[str]
    correct_index:  int
    explanation:    str = ""
    category:       str = "general"

    @classmethod
    def from_dict(cls, uid: str, data: dict[str, Any]) -> "QuizQuestion":
        return cls(
            uid           = uid,
            question      = data.get("question", ""),
            options       = data.get("options") or [],
            correct_index = data.get("correctIndex", 0),
            explanation   = data.get("explanation", ""),
            category      = data.get("category", "general"),
        )


@dataclass
class AnonMessage:
    uid:         str
    text:        str
    created_at:  str
    sender_hash: str   = ""
    approved:    bool  = True

    @classmethod
    def from_dict(cls, uid: str, data: dict[str, Any]) -> "AnonMessage":
        return cls(
            uid         = uid,
            text        = data.get("text", ""),
            created_at  = data.get("createdAt", ""),
            sender_hash = data.get("senderHash", ""),
            approved    = data.get("approved", True),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "text":        self.text,
            "createdAt":   self.created_at,
            "senderHash":  self.sender_hash,
            "approved":    self.approved,
        }


@dataclass
class Page:
    items:       list[Any]
    page:        int
    total_pages: int
    total_items: int

    @property
    def has_prev(self) -> bool:
        return self.page > 1

    @property
    def has_next(self) -> bool:
        return self.page < self.total_pages


# ══════════════════════════════════════════════════════════════════════
# 3. FSM STATES
# ══════════════════════════════════════════════════════════════════════

class AdminStates(StatesGroup):
    waiting_for_code          = State()
    waiting_for_student_add   = State()
    waiting_for_student_delete= State()
    waiting_for_student_search= State()
    waiting_for_assign_duty   = State()


class StudentStates(StatesGroup):
    adding_name       = State()
    adding_birthday   = State()
    adding_emoji      = State()
    editing_name      = State()
    editing_bio       = State()
    searching         = State()
    deleting_confirm  = State()


class ScheduleStates(StatesGroup):
    choosing_day      = State()
    entering_lesson   = State()
    editing_lesson    = State()
    confirm_clear_day = State()


class NewsStates(StatesGroup):
    choosing_category = State()
    entering_title    = State()
    entering_body     = State()
    confirm_publish   = State()
    editing_news      = State()


class HomeworkStates(StatesGroup):
    entering_subject  = State()
    entering_task     = State()
    entering_due_date = State()
    entering_priority = State()


class EventStates(StatesGroup):
    entering_title    = State()
    entering_desc     = State()
    entering_date     = State()
    entering_time     = State()
    entering_location = State()


class PollStates(StatesGroup):
    entering_question = State()
    entering_options  = State()
    confirm_create    = State()


class AnonStates(StatesGroup):
    entering_message  = State()
    confirm_send      = State()


class QuizBuilderStates(StatesGroup):
    entering_question   = State()
    entering_options    = State()
    entering_correct    = State()
    entering_explanation = State()


class BroadcastStates(StatesGroup):
    entering_message  = State()
    confirm_send      = State()


class DutyStates(StatesGroup):
    manual_choosing   = State()


class ClassInfoStates(StatesGroup):
    editing_name      = State()
    editing_motto     = State()
    editing_teacher   = State()
    editing_room      = State()


# ══════════════════════════════════════════════════════════════════════
# 4. FIREBASE ASYNC CLIENT
# ══════════════════════════════════════════════════════════════════════

class _CacheEntry:
    __slots__ = ("value", "expires_at")

    def __init__(self, value: Any, ttl: int):
        self.value      = value
        self.expires_at = time.monotonic() + ttl


class SimpleCache:
    def __init__(self) -> None:
        self._store: dict[str, _CacheEntry] = {}
        self._lock  = asyncio.Lock()

    async def get(self, key: str) -> Optional[Any]:
        async with self._lock:
            entry = self._store.get(key)
            if entry and time.monotonic() < entry.expires_at:
                return entry.value
            self._store.pop(key, None)
            return None

    async def set(self, key: str, value: Any, ttl: int) -> None:
        async with self._lock:
            self._store[key] = _CacheEntry(value, ttl)

    async def invalidate(self, key: str) -> None:
        async with self._lock:
            self._store.pop(key, None)

    async def invalidate_prefix(self, prefix: str) -> None:
        async with self._lock:
            keys = [k for k in self._store if k.startswith(prefix)]
            for k in keys:
                del self._store[k]


class FirebaseDB:
    MAX_RETRIES    = 3
    RETRY_DELAY    = 1.5

    def __init__(self, base_url: str) -> None:
        self._base = base_url.rstrip("/")
        self._session: Optional[aiohttp.ClientSession] = None
        self.cache = SimpleCache()

    async def init(self) -> None:
        if not self._session or self._session.closed:
            timeout = aiohttp.ClientTimeout(total=15, connect=5)
            self._session = aiohttp.ClientSession(timeout=timeout)
            logger.info("Firebase async session initialised")

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()
            logger.info("Firebase async session closed")

    async def _request(
        self, method: str, path: str, json_data: Any = None,
    ) -> Optional[Any]:
        if not self._session or self._session.closed:
            await self.init()

        url = f"{self._base}/{path}.json"
        for attempt in range(1, self.MAX_RETRIES + 1):
            try:
                async with self._session.request(method, url, json=json_data) as resp:
                    if resp.status == 200:
                        return await resp.json()
                    if resp.status == 404:
                        return None
                    logger.warning(
                        "Firebase %s %s → HTTP %s (attempt %d/%d)",
                        method, path, resp.status, attempt, self.MAX_RETRIES,
                    )
            except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
                logger.warning(
                    "Firebase %s %s → %s (attempt %d/%d)",
                    method, path, exc, attempt, self.MAX_RETRIES,
                )
            if attempt < self.MAX_RETRIES:
                await asyncio.sleep(self.RETRY_DELAY * attempt)
        logger.error("Firebase %s %s failed after %d attempts", method, path, self.MAX_RETRIES)
        return None

    async def get(self, path: str) -> Optional[Any]:
        return await self._request("GET", path)

    async def put(self, path: str, data: Any) -> Optional[Any]:
        return await self._request("PUT", path, data)

    async def post(self, path: str, data: Any) -> Optional[str]:
        result = await self._request("POST", path, data)
        if isinstance(result, dict):
            return result.get("name")
        return None

    async def patch(self, path: str, data: dict[str, Any]) -> bool:
        result = await self._request("PATCH", path, data)
        return result is not None

    async def delete(self, path: str) -> bool:
        result = await self._request("DELETE", path)
        return result is None or result is True

    # ── Students ──────────────────────────────────────────────────────
    async def get_all_students(self, use_cache: bool = True) -> dict[str, Any]:
        cache_key = "students:all"
        if use_cache:
            cached = await self.cache.get(cache_key)
            if cached is not None:
                return cached
        data = await self.get(FB.STUDENTS)
        result = data if isinstance(data, dict) else {}
        await self.cache.set(cache_key, result, CACHE_TTL_STUDENTS)
        return result

    async def get_student(self, uid: str) -> Optional[dict[str, Any]]:
        data = await self.get(f"{FB.STUDENTS}/{uid}")
        return data if isinstance(data, dict) else None

    async def add_student(self, student_data: dict[str, Any]) -> Optional[str]:
        uid = await self.post(FB.STUDENTS, student_data)
        if uid:
            await self.cache.invalidate("students:all")
        return uid

    async def update_student(self, uid: str, updates: dict[str, Any]) -> bool:
        ok = await self.patch(f"{FB.STUDENTS}/{uid}", updates)
        if ok:
            await self.cache.invalidate("students:all")
        return ok

    async def delete_student(self, uid: str) -> bool:
        ok = await self.delete(f"{FB.STUDENTS}/{uid}")
        if ok:
            await self.cache.invalidate("students:all")
        return ok

    async def search_students(self, query: str) -> dict[str, Any]:
        all_s = await self.get_all_students()
        q = query.lower()
        return {uid: d for uid, d in all_s.items() if q in d.get("name", "").lower()}

    # ── Duty History ──────────────────────────────────────────────────
    async def add_history_record(self, record: dict[str, Any]) -> bool:
        uid = await self.post(FB.HISTORY, record)
        return uid is not None

    async def get_history(self) -> list[dict[str, Any]]:
        data = await self.get(FB.HISTORY)
        if isinstance(data, dict):
            return list(data.values())
        return []

    async def delete_history(self) -> bool:
        return await self.delete(FB.HISTORY)

    # ── Schedule ──────────────────────────────────────────────────────
    async def get_schedule(self) -> dict[str, Any]:
        cache_key = "schedule:full"
        cached = await self.cache.get(cache_key)
        if cached is not None:
            return cached
        data = await self.get(FB.SCHEDULE)
        result = data if isinstance(data, dict) else {}
        await self.cache.set(cache_key, result, CACHE_TTL_SCHEDULE)
        return result

    async def get_day_schedule(self, day: str) -> dict[str, Any]:
        data = await self.get(f"{FB.SCHEDULE}/{day}")
        return data if isinstance(data, dict) else {}

    async def set_day_schedule(self, day: str, schedule_data: dict[str, Any]) -> bool:
        ok = await self.put(f"{FB.SCHEDULE}/{day}", schedule_data)
        await self.cache.invalidate("schedule:full")
        return ok is not None

    async def add_lesson(self, day: str, lesson_data: dict[str, Any]) -> Optional[str]:
        uid = await self.post(f"{FB.SCHEDULE}/{day}/lessons", lesson_data)
        await self.cache.invalidate("schedule:full")
        return uid

    async def delete_day_schedule(self, day: str) -> bool:
        ok = await self.delete(f"{FB.SCHEDULE}/{day}")
        await self.cache.invalidate("schedule:full")
        return ok

    # ── News ──────────────────────────────────────────────────────────
    async def get_all_news(self, use_cache: bool = True) -> dict[str, Any]:
        cache_key = "news:all"
        if use_cache:
            cached = await self.cache.get(cache_key)
            if cached is not None:
                return cached
        data = await self.get(FB.NEWS)
        result = data if isinstance(data, dict) else {}
        await self.cache.set(cache_key, result, CACHE_TTL_NEWS)
        return result

    async def add_news(self, news_data: dict[str, Any]) -> Optional[str]:
        uid = await self.post(FB.NEWS, news_data)
        if uid:
            await self.cache.invalidate("news:all")
        return uid

    async def delete_news(self, uid: str) -> bool:
        ok = await self.delete(f"{FB.NEWS}/{uid}")
        if ok:
            await self.cache.invalidate("news:all")
        return ok

    async def update_news(self, uid: str, updates: dict[str, Any]) -> bool:
        ok = await self.patch(f"{FB.NEWS}/{uid}", updates)
        if ok:
            await self.cache.invalidate("news:all")
        return ok

    async def increment_news_views(self, uid: str) -> None:
        try:
            data = await self.get(f"{FB.NEWS}/{uid}/views")
            current = data if isinstance(data, int) else 0
            await self.patch(f"{FB.NEWS}/{uid}", {"views": current + 1})
            await self.cache.invalidate("news:all")
        except Exception:
            pass

    # ── Homework ──────────────────────────────────────────────────────
    async def get_all_homework(self) -> dict[str, Any]:
        data = await self.get(FB.HOMEWORKS)
        return data if isinstance(data, dict) else {}

    async def add_homework(self, hw_data: dict[str, Any]) -> Optional[str]:
        return await self.post(FB.HOMEWORKS, hw_data)

    async def delete_homework(self, uid: str) -> bool:
        return await self.delete(f"{FB.HOMEWORKS}/{uid}")

    # ── Events ────────────────────────────────────────────────────────
    async def get_all_events(self) -> dict[str, Any]:
        data = await self.get(FB.EVENTS)
        return data if isinstance(data, dict) else {}

    async def add_event(self, event_data: dict[str, Any]) -> Optional[str]:
        return await self.post(FB.EVENTS, event_data)

    async def delete_event(self, uid: str) -> bool:
        return await self.delete(f"{FB.EVENTS}/{uid}")

    # ── Polls ─────────────────────────────────────────────────────────
    async def get_all_polls(self) -> dict[str, Any]:
        data = await self.get(FB.POLLS)
        return data if isinstance(data, dict) else {}

    async def add_poll(self, poll_data: dict[str, Any]) -> Optional[str]:
        return await self.post(FB.POLLS, poll_data)

    async def update_poll(self, uid: str, updates: dict[str, Any]) -> bool:
        return await self.patch(f"{FB.POLLS}/{uid}", updates)

    async def delete_poll(self, uid: str) -> bool:
        return await self.delete(f"{FB.POLLS}/{uid}")

    # ── Anonymous Messages ────────────────────────────────────────────
    async def get_anon_messages(self) -> dict[str, Any]:
        data = await self.get(FB.ANONYMOUS)
        return data if isinstance(data, dict) else {}

    async def add_anon_message(self, msg_data: dict[str, Any]) -> Optional[str]:
        return await self.post(FB.ANONYMOUS, msg_data)

    async def delete_anon_message(self, uid: str) -> bool:
        return await self.delete(f"{FB.ANONYMOUS}/{uid}")

    # ── Quiz ──────────────────────────────────────────────────────────
    async def get_all_quizzes(self) -> dict[str, Any]:
        data = await self.get(FB.QUIZZES)
        return data if isinstance(data, dict) else {}

    async def add_quiz(self, quiz_data: dict[str, Any]) -> Optional[str]:
        return await self.post(FB.QUIZZES, quiz_data)

    async def delete_quiz(self, uid: str) -> bool:
        return await self.delete(f"{FB.QUIZZES}/{uid}")

    # ── Class Info ────────────────────────────────────────────────────
    async def get_class_info(self) -> dict[str, Any]:
        cache_key = "class_info"
        cached = await self.cache.get(cache_key)
        if cached is not None:
            return cached
        data = await self.get(FB.CLASS_INFO)
        result = data if isinstance(data, dict) else {}
        await self.cache.set(cache_key, result, CACHE_TTL_SETTINGS)
        return result

    async def set_class_info(self, info: dict[str, Any]) -> bool:
        ok = await self.patch(FB.CLASS_INFO, info)
        await self.cache.invalidate("class_info")
        return ok

    # ── Settings / Moderators ─────────────────────────────────────────
    async def get_settings(self) -> dict[str, Any]:
        cache_key = "settings:all"
        cached = await self.cache.get(cache_key)
        if cached is not None:
            return cached
        data = await self.get(FB.SETTINGS)
        result = data if isinstance(data, dict) else {}
        await self.cache.set(cache_key, result, CACHE_TTL_SETTINGS)
        return result

    async def update_settings(self, updates: dict[str, Any]) -> bool:
        ok = await self.patch(FB.SETTINGS, updates)
        await self.cache.invalidate("settings:all")
        return ok

    async def get_moderators(self) -> list[int]:
        data = await self.get(FB.MODERATORS)
        if isinstance(data, dict):
            return [int(v) for v in data.values() if v]
        if isinstance(data, list):
            return [int(v) for v in data if v]
        return []

    async def add_moderator(self, user_id: int) -> bool:
        uid = await self.post(FB.MODERATORS, user_id)
        return uid is not None

    async def remove_moderator(self, user_id: int) -> bool:
        data = await self.get(FB.MODERATORS)
        if not isinstance(data, dict):
            return False
        for key, val in data.items():
            if int(val) == user_id:
                return await self.delete(f"{FB.MODERATORS}/{key}")
        return False

    # ── User Profiles ─────────────────────────────────────────────────
    async def get_user_profile(self, telegram_id: int) -> dict[str, Any]:
        data = await self.get(f"{FB.USERS}/{telegram_id}")
        return data if isinstance(data, dict) else {}

    async def update_user_profile(self, telegram_id: int, updates: dict[str, Any]) -> bool:
        return await self.patch(f"{FB.USERS}/{telegram_id}", updates)

    # ── Duty Queue ────────────────────────────────────────────────────
    async def get_duty_queue(self) -> list[str]:
        data = await self.get(FB.DUTY_QUEUE)
        if isinstance(data, list):
            return [str(v) for v in data if v]
        if isinstance(data, dict):
            return list(data.values())
        return []

    async def set_duty_queue(self, queue: list[str]) -> bool:
        result = await self.put(FB.DUTY_QUEUE, queue)
        return result is not None


# Global singleton
db = FirebaseDB(FIREBASE_URL)

# ══════════════════════════════════════════════════════════════════════
# 5. MIDDLEWARES
# ══════════════════════════════════════════════════════════════════════

class _UserBucket:
    __slots__ = ("timestamps", "cooldown_until")

    def __init__(self) -> None:
        self.timestamps:    list[float] = []
        self.cooldown_until: float      = 0.0

    def is_allowed(self) -> bool:
        now = time.monotonic()
        if now < self.cooldown_until:
            return False
        cutoff = now - RATE_LIMIT_WINDOW
        self.timestamps = [t for t in self.timestamps if t > cutoff]
        if len(self.timestamps) >= RATE_LIMIT_MESSAGES:
            self.cooldown_until = now + RATE_LIMIT_COOLDOWN
            logger.warning("Rate limit triggered for bucket")
            return False
        self.timestamps.append(now)
        return True

    @property
    def cooldown_remaining(self) -> int:
        remaining = self.cooldown_until - time.monotonic()
        return max(0, int(remaining))


class AntiSpamMiddleware(BaseMiddleware):
    def __init__(self) -> None:
        self._buckets: dict[int, _UserBucket] = defaultdict(_UserBucket)

    async def __call__(
        self,
        handler:  Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event:    TelegramObject,
        data:     dict[str, Any],
    ) -> Any:
        user_id: int | None = None
        if isinstance(event, Message):
            user_id = event.from_user.id if event.from_user else None
        elif isinstance(event, CallbackQuery):
            user_id = event.from_user.id if event.from_user else None

        if user_id is None or user_id == 5616034990:
            return await handler(event, data)

        bucket = self._buckets[user_id]
        if bucket.is_allowed():
            return await handler(event, data)

        secs = bucket.cooldown_remaining
        if isinstance(event, Message):
            await event.answer(
                f"⏳ <b>Слишком быстро!</b>\nПодождите <b>{secs}с</b> перед следующим действием.",
                parse_mode="HTML",
            )
        elif isinstance(event, CallbackQuery):
            await event.answer(
                f"⏳ Подождите {secs}с — слишком много запросов!",
                show_alert=True,
            )
        return None


class LoggingMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler:  Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event:    TelegramObject,
        data:     dict[str, Any],
    ) -> Any:
        if isinstance(event, Message):
            user = event.from_user
            logger.info(
                "MSG  uid=%-12s name=%-20s text=%s",
                user.id if user else "?",
                user.full_name if user else "?",
                (event.text or "")[:80],
            )
        elif isinstance(event, CallbackQuery):
            user = event.from_user
            logger.info(
                "CLBK uid=%-12s name=%-20s data=%s",
                user.id if user else "?",
                user.full_name if user else "?",
                event.data,
            )
        return await handler(event, data)


class RoleMiddleware(BaseMiddleware):
    def __init__(self, moderator_ids_getter: Callable) -> None:
        self._get_mods = moderator_ids_getter

    async def __call__(
        self,
        handler:  Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event:    TelegramObject,
        data:     dict[str, Any],
    ) -> Any:
        user_id: int | None = None
        if isinstance(event, (Message, CallbackQuery)):
            user = event.from_user
            user_id = user.id if user else None

        is_owner = (user_id == OWNER_ID) if user_id else False
        is_mod   = False

        if not is_owner and user_id:
            try:
                mod_ids = await self._get_mods()
                is_mod  = user_id in mod_ids
            except Exception:
                pass

        data["is_owner"]     = is_owner
        data["is_moderator"] = is_mod
        data["user_role"]    = (
            "owner" if is_owner else ("moderator" if is_mod else "student")
        )

        return await handler(event, data)


# ══════════════════════════════════════════════════════════════════════
# 6. KEYBOARDS
# ══════════════════════════════════════════════════════════════════════

def _btn(text: str, data: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(text=text, callback_data=data)

def _row(*btns: InlineKeyboardButton) -> list[InlineKeyboardButton]:
    return list(btns)

def _back(target: str = "main_menu", label: str = "🔙 Назад") -> list[list[InlineKeyboardButton]]:
    return [[_btn(label, target)]]

# ── Main Menu ────────────────────────────────────────────────────────
def kb_main(is_owner: bool = False, is_mod: bool = False) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = [
        [_btn("🏫 Наш класс",        "class_info"),
         _btn("👥 Ученики",          "students_list:0")],
        [_btn("📚 Расписание",       "schedule_menu"),
         _btn("📝 Домашка",          "homework_list:0")],
        [_btn("🎯 Дежурство",        "duty_menu"),
         _btn("📊 Статистика",       "stats_menu")],
        [_btn("🏆 Рейтинг",         "rating_menu"),
         _btn("🎮 Мини-игры",        "games_menu")],
        [_btn("📰 Новости",          "news_list:0"),
         _btn("📅 События",          "events_list")],
        [_btn("🗳️ Опросы",          "polls_list"),
         _btn("💬 Анонимно",         "anon_menu")],
        [_btn("🎉 Дни рождения",     "birthdays_menu"),
         _btn("🧠 Викторина",        "quiz_start")],
        [_btn("📖 Полезности",       "useful_menu"),
         _btn("⚙️ Настройки",       "settings_menu")],
        [_btn("ℹ️ Помощь",           "help")],
    ]
    if is_owner or is_mod:
        rows.append([_btn("🔐 Админ-панель", "admin_panel")])
    if is_owner:
        rows.append([_btn("👑 OWNER PANEL", "owner_panel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

def kb_back(target: str = "main_menu", label: str = "🔙 Назад") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=_back(target, label))

def kb_back_main() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[_btn("🔙 В главное меню", "main_menu")]])

def kb_confirm(yes_data: str, no_data: str, yes_label: str = "✅ Да", no_label: str = "❌ Нет") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[_btn(yes_label, yes_data), _btn(no_label, no_data)]])

# ── Students ─────────────────────────────────────────────────────────
def kb_students_list(students: dict, page: int, total_pages: int) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    items = list(students.items())
    start = page * PAGE_SIZE_STUDENTS
    slice_ = items[start : start + PAGE_SIZE_STUDENTS]

    for uid, s in slice_:
        icon = "🟢" if s.get("isDuty") else "⚪"
        rows.append([_btn(f"{icon} {s['name']}", f"student_profile:{uid}")])

    nav: list[InlineKeyboardButton] = []
    if page > 0:
        nav.append(_btn("◀ Пред.", f"students_list:{page-1}"))
    nav.append(_btn(f"{page+1}/{total_pages}", "noop"))
    if page + 1 < total_pages:
        nav.append(_btn("След. ▶", f"students_list:{page+1}"))
    if nav:
        rows.append(nav)

    rows.append([_btn("🔍 Поиск", "search_student"), _btn("🔙 Меню", "main_menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

def kb_student_profile(uid: str, is_admin: bool = False) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = [
        [_btn("📊 Статистика", f"student_stats:{uid}")],
        [_btn("🔙 Назад", "students_list:0")],
    ]
    if is_admin:
        rows.insert(1, [
            _btn("✏️ Ред.", f"student_edit:{uid}"),
            _btn("❌ Удалить", f"student_del_confirm:{uid}"),
        ])
    return InlineKeyboardMarkup(inline_keyboard=rows)

# ── Duty ─────────────────────────────────────────────────────────────
def kb_duty_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [_btn("🎯 Случайный выбор",    "duty_random")],
        [_btn("📋 Текущий дежурный",   "duty_current")],
        [_btn("📊 История дежурств",   "duty_history:0")],
        [_btn("📅 Расписание дежурств","duty_schedule_view")],
        [_btn("🔙 Меню",               "main_menu")],
    ])

def kb_duty_result(uid: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [_btn("🔄 Выбрать другого", "duty_random"),
         _btn("👤 Профиль", f"student_profile:{uid}")],
        [_btn("🔙 Меню", "main_menu")],
    ])

def kb_duty_history(page: int, total_pages: int) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    nav: list[InlineKeyboardButton] = []
    if page > 0:
        nav.append(_btn("◀", f"duty_history:{page-1}"))
    nav.append(_btn(f"{page+1}/{max(total_pages,1)}", "noop"))
    if page + 1 < total_pages:
        nav.append(_btn("▶", f"duty_history:{page+1}"))
    if nav:
        rows.append(nav)
    rows.append([_btn("🔙 Дежурство", "duty_menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

# ── Schedule ─────────────────────────────────────────────────────────
def kb_schedule_menu() -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for i in range(0, 6, 2):
        row = []
        for j in [i, i+1]:
            if j < len(DAYS_RU):
                row.append(_btn(DAYS_RU[j], f"schedule_day:{DAYS_KEYS[j]}"))
        rows.append(row)
    rows.append([_btn("📅 Вся неделя", "schedule_week")])
    rows.append([_btn("🔙 Меню", "main_menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

def kb_schedule_day(day_key: str, is_owner: bool = False) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    if is_owner:
        rows.append([
            _btn("✏️ Редактировать", f"owner_schedule_edit:{day_key}"),
            _btn("🗑️ Очистить", f"owner_schedule_clear:{day_key}"),
        ])
    rows.append([_btn("🔙 Расписание", "schedule_menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

# ── News ─────────────────────────────────────────────────────────────
def kb_news_list(news_items: list, page: int, total_pages: int) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    start = page * PAGE_SIZE_NEWS
    for item in news_items[start : start + PAGE_SIZE_NEWS]:
        rows.append([_btn(f"{item.category_icon} {item.title[:32]}", f"news_view:{item.uid}")])

    nav: list[InlineKeyboardButton] = []
    if page > 0:
        nav.append(_btn("◀", f"news_list:{page-1}"))
    nav.append(_btn(f"{page+1}/{max(total_pages,1)}", "noop"))
    if page + 1 < total_pages:
        nav.append(_btn("▶", f"news_list:{page+1}"))
    if nav:
        rows.append(nav)
    rows.append([_btn("🔙 Меню", "main_menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

def kb_news_view(uid: str, is_owner: bool = False) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    if is_owner:
        rows.append([
            _btn("📌 Закрепить", f"owner_news_pin:{uid}"),
            _btn("🗑️ Удалить",  f"owner_news_delete:{uid}"),
        ])
    rows.append([_btn("🔙 Новости", "news_list:0")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

def kb_news_categories() -> InlineKeyboardMarkup:
    cat_map = {
        NewsCategory.URGENT:   "🚨 Срочно",
        NewsCategory.GENERAL:  "📢 Общее",
        NewsCategory.SCHEDULE: "📚 Расписание",
        NewsCategory.EXAM:     "📝 Экзамен",
        NewsCategory.EVENT:    "🎉 Мероприятие",
        NewsCategory.HOMEWORK: "📖 Домашка",
        NewsCategory.CONTEST:  "🏆 Конкурс",
        NewsCategory.VOTE:     "🗳️ Голосование",
        NewsCategory.OTHER:    "📌 Другое",
    }
    rows = []
    items = list(cat_map.items())
    for i in range(0, len(items), 2):
        row = []
        for cat, label in items[i:i+2]:
            row.append(_btn(label, f"owner_news_cat:{cat}"))
        rows.append(row)
    rows.append([_btn("❌ Отмена", "owner_panel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

# ── Homework ─────────────────────────────────────────────────────────
def kb_homework_list(items: list, page: int, total_pages: int, is_owner: bool = False) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    start = page * PAGE_SIZE_HOMEWORK
    for hw in items[start : start + PAGE_SIZE_HOMEWORK]:
        icon = hw.priority_icon
        rows.append([_btn(f"{icon} {hw.subject}: {hw.task[:28]}", f"hw_view:{hw.uid}")])

    nav: list[InlineKeyboardButton] = []
    if page > 0:
        nav.append(_btn("◀", f"homework_list:{page-1}"))
    nav.append(_btn(f"{page+1}/{max(total_pages,1)}", "noop"))
    if page + 1 < total_pages:
        nav.append(_btn("▶", f"homework_list:{page+1}"))
    if nav:
        rows.append(nav)

    if is_owner:
        rows.append([_btn("➕ Добавить ДЗ", "owner_hw_add")])
    rows.append([_btn("🔙 Меню", "main_menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

# ── Events ───────────────────────────────────────────────────────────
def kb_events_list(events: list, is_owner: bool = False) -> InlineKeyboardMarkup:
    rows = []
    for ev in events[:15]:
        rows.append([_btn(f"📅 {ev.date} — {ev.title[:30]}", f"event_view:{ev.uid}")])
    if is_owner:
        rows.append([_btn("➕ Добавить событие", "owner_event_add")])
    rows.append([_btn("🔙 Меню", "main_menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

# ── Polls ──────────────────────────────────────────────────────────
def kb_polls_list(polls: list, is_owner: bool = False) -> InlineKeyboardMarkup:
    rows = []
    for p in polls[:10]:
        icon = "🟢" if p.status == "active" else "🔴"
        rows.append([_btn(f"{icon} {p.question[:35]}", f"poll_view:{p.uid}")])
    if is_owner:
        rows.append([_btn("➕ Создать опрос", "owner_poll_create")])
    rows.append([_btn("🔙 Меню", "main_menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

def kb_poll_vote(poll: "Poll") -> InlineKeyboardMarkup:
    rows = []
    for i, opt in enumerate(poll.options):
        rows.append([_btn(f"{opt.text}  ({opt.votes})", f"poll_vote:{poll.uid}:{i}")])
    rows.append([_btn("🔙 Опросы", "polls_list")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

# ── Games ──────────────────────────────────────────────────────────
def kb_games_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [_btn("🧠 Викторина",            "quiz_start")],
        [_btn("🪙 Орёл или решка",       "game_coin"),
         _btn("🎲 Кубик",                "game_dice")],
        [_btn("🎡 Рулетка имён",         "game_wheel")],
        [_btn("😈 Правда или действие",  "game_truth_dare")],
        [_btn("🔙 Меню",                 "main_menu")],
    ])

# ── Rating ─────────────────────────────────────────────────────────
def kb_rating_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [_btn("🏆 Топ по XP",            "rating_xp")],
        [_btn("🎯 Топ по дежурствам",    "rating_duty")],
        [_btn("🧠 Топ викторины",        "rating_quiz")],
        [_btn("📅 Недельный ТОП",        "rating_weekly")],
        [_btn("🔙 Меню",                 "main_menu")],
    ])

# ── Stats ──────────────────────────────────────────────────────────
def kb_stats_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [_btn("📊 Общая статистика",   "stats_general")],
        [_btn("📈 Активность класса",  "stats_activity")],
        [_btn("🎯 Статистика дежурств","stats_duty")],
        [_btn("🔙 Меню",               "main_menu")],
    ])

# ── Anonymous ──────────────────────────────────────────────────────
def kb_anon_menu(is_owner: bool = False) -> InlineKeyboardMarkup:
    rows = [
        [_btn("✍️ Написать анонимно",    "anon_write")],
        [_btn("📬 Последние сообщения", "anon_view")],
    ]
    if is_owner:
        rows.append([_btn("🗑️ Модерация", "owner_anon_moderate")])
    rows.append([_btn("🔙 Меню", "main_menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

# ── Admin Panel ────────────────────────────────────────────────────
def kb_admin_panel(is_owner: bool = False) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = [
        [_btn("➕ Добавить ученика",    "admin_add_student"),
         _btn("➖ Удалить ученика",     "admin_delete_student")],
        [_btn("👥 Все ученики",         "admin_all_students")],
        [_btn("🔄 Сбросить дежурства", "admin_reset_duty")],
        [_btn("🗑️ Очистить историю",  "admin_clear_history")],
        [_btn("📊 Статистика",         "admin_stats")],
        [_btn("🎯 Назначить дежурного","admin_assign_duty")],
    ]
    if is_owner:
        rows.append([_btn("👑 Owner Panel", "owner_panel")])
    rows.append([_btn("🔙 Меню", "main_menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

# ── Owner Panel ────────────────────────────────────────────────────
def kb_owner_panel() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [_btn("📢 Создать объявление",   "owner_news_create")],
        [_btn("📚 Изменить расписание",  "owner_schedule_menu")],
        [_btn("📖 Управление ДЗ",        "owner_hw_menu")],
        [_btn("📅 Управление событиями", "owner_events_menu")],
        [_btn("🗳️ Создать опрос",       "owner_poll_create")],
        [_btn("👥 Управление учениками", "admin_panel")],
        [_btn("🛡️ Модераторы",          "owner_moderators")],
        [_btn("📨 Broadcast",            "owner_broadcast")],
        [_btn("🧠 Добавить вопрос",      "owner_quiz_add")],
        [_btn("📊 Аналитика",            "owner_analytics")],
        [_btn("⚙️ Настройки класса",    "owner_class_settings")],
        [_btn("🗑️ Модерация анонимок", "owner_anon_moderate")],
        [_btn("🔙 Меню",                "main_menu")],
    ])

def kb_owner_schedule_menu() -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for i in range(0, 6, 2):
        row = []
        for j in [i, i+1]:
            if j < len(DAYS_RU):
                row.append(_btn(f"✏️ {DAYS_RU[j]}", f"owner_schedule_edit:{DAYS_KEYS[j]}"))
        rows.append(row)
    rows.append([_btn("🔙 Owner Panel", "owner_panel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

def kb_owner_moderators(mods: list[int]) -> InlineKeyboardMarkup:
    rows = []
    for uid in mods:
        rows.append([_btn(f"❌ Удалить {uid}", f"owner_mod_remove:{uid}")])
    rows.append([_btn("➕ Добавить модератора", "owner_mod_add")])
    rows.append([_btn("🔙 Owner Panel", "owner_panel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

# ── Useful / Settings ──────────────────────────────────────────────
def kb_useful_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [_btn("⏰ Таймер урока",         "useful_timer")],
        [_btn("🌍 Время в мире",         "useful_worldtime")],
        [_btn("📐 Калькулятор оценок",   "useful_calc")],
        [_btn("🎲 Генератор случайного", "useful_random")],
        [_btn("🔙 Меню",                 "main_menu")],
    ])

def kb_settings_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [_btn("🔔 Уведомления",   "settings_notifications")],
        [_btn("👤 Мой профиль",   "settings_profile")],
        [_btn("🎨 Мой эмодзи",   "settings_emoji")],
        [_btn("🔙 Меню",          "main_menu")],
    ])

# ── Quiz ───────────────────────────────────────────────────────────
def kb_quiz_options(question_uid: str, options: list[str]) -> InlineKeyboardMarkup:
    rows = []
    letters = ["А", "Б", "В", "Г"]
    for i, opt in enumerate(options[:4]):
        rows.append([_btn(f"{letters[i]}) {opt}", f"quiz_answer:{question_uid}:{i}")])
    rows.append([_btn("⏩ Пропустить", "quiz_skip"), _btn("🔙 Меню", "main_menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

# ── Birthdays ──────────────────────────────────────────────────────
def kb_birthdays_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [_btn("🎂 Ближайшие ДР",     "birthdays_upcoming")],
        [_btn("📅 Все дни рождения", "birthdays_all")],
        [_btn("✏️ Мой день рождения","birthdays_set_mine")],
        [_btn("🔙 Меню",             "main_menu")],
    ])

# ══════════════════════════════════════════════════════════════════════
# 7. UTILS
# ══════════════════════════════════════════════════════════════════════

def paginate(items: list[T], page: int, page_size: int) -> Page:
    total   = len(items)
    pages   = max(1, math.ceil(total / page_size))
    page    = max(0, min(page, pages - 1))
    start   = page * page_size
    return Page(
        items       = items[start : start + page_size],
        page        = page,
        total_pages = pages,
        total_items = total,
    )

def get_level(xp: int) -> int:
    for lvl, threshold in enumerate(LEVEL_THRESHOLDS):
        if xp < threshold:
            return max(1, lvl)
    return len(LEVEL_THRESHOLDS)

def get_level_title(xp: int) -> str:
    lvl = get_level(xp)
    idx = min(lvl - 1, len(LEVEL_TITLES) - 1)
    return LEVEL_TITLES[idx]

def xp_to_next_level(xp: int) -> int:
    lvl = get_level(xp)
    if lvl >= len(LEVEL_THRESHOLDS):
        return 0
    return LEVEL_THRESHOLDS[lvl] - xp

def xp_bar(xp: int, width: int = 10) -> str:
    lvl  = get_level(xp)
    if lvl <= 1:
        prev = 0
    else:
        prev = LEVEL_THRESHOLDS[lvl - 1]
    if lvl >= len(LEVEL_THRESHOLDS):
        return "█" * width + " MAX"
    nxt  = LEVEL_THRESHOLDS[lvl]
    pct  = (xp - prev) / max(1, nxt - prev)
    filled = round(pct * width)
    return "█" * filled + "░" * (width - filled)

def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

def now_ts_ms() -> int:
    return int(datetime.now(timezone.utc).timestamp() * 1000)

def fmt_datetime(iso: str | None, fmt: str = "%d.%m.%Y %H:%M") -> str:
    if not iso:
        return "—"
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        return dt.strftime(fmt)
    except Exception:
        return iso[:16] if iso else "—"

def fmt_date(iso: str | None) -> str:
    return fmt_datetime(iso, "%d.%m.%Y")

def days_until_birthday(bday_str: str) -> int:
    try:
        day, mon = map(int, bday_str.split("."))
        today    = date.today()
        target   = date(today.year, mon, day)
        if target < today:
            target = date(today.year + 1, mon, day)
        return (target - today).days
    except Exception:
        return 999

def hash_user_id(user_id: int) -> str:
    return hashlib.sha256(f"anon_{user_id}_salt42".encode()).hexdigest()[:16]

def fmt_header(title: str) -> str:
    return f"<b>◆ {title}</b>\n{SEPARATOR}\n"

def fmt_section(label: str) -> str:
    return f"\n<i>▸ {label}</i>\n"

def fmt_student_card(s: Student, rank: int | None = None) -> str:
    medal = MEDAL_ICONS[rank - 1] if rank and 1 <= rank <= 3 else (f"#{rank}" if rank else "")
    lvl   = get_level(s.xp)
    title = get_level_title(s.xp)
    bar   = xp_bar(s.xp)
    lines = [
        f"{medal} <b>{s.emoji} {s.name}</b>",
        f"   {title}  •  Ур. {lvl}",
        f"   XP: {s.xp:,}  [{bar}]",
        f"   Дежурств: {s.total_duty_count}",
    ]
    if s.bio:
        lines.append(f"   💬 {s.bio[:60]}")
    if s.birthday:
        lines.append(f"   🎂 {s.birthday}")
    return "\n".join(lines)

def fmt_duty_card(name: str, date_str: str, count: int) -> str:
    return (
        f"╔{'═'*22}╗\n"
        f"║  🎯 ДЕЖУРНЫЙ СЕГОДНЯ  ║\n"
        f"╚{'═'*22}╝\n\n"
        f"👤 <b>{name}</b>\n"
        f"📅 Дата: {date_str}\n"
        f"🔢 Дежурств всего: {count}\n"
    )

def fmt_announcement_card(title: str, body: str, author: str, date_str: str) -> str:
    return (
        f"╔{'═'*22}╗\n"
        f"║  📢 ОБЪЯВЛЕНИЕ  ║\n"
        f"╚{'═'*22}╝\n\n"
        f"<b>{title}</b>\n\n"
        f"{body}\n\n"
        f"{SEPARATOR_THIN}\n"
        f"👤 От: {author}\n"
        f"📅 {date_str}"
    )

def fmt_schedule_day(day_name: str, lessons: list) -> str:
    if not lessons:
        return f"📅 <b>{day_name}</b>\n\n<i>Уроки не заданы</i>"
    lines = [f"📅 <b>{day_name}</b>\n{SEPARATOR}"]
    for ls in lessons:
        room_str = f" · каб.{ls.room}" if ls.room else ""
        teacher_str = f"\n   <i>👨‍🏫 {ls.teacher}</i>" if ls.teacher else ""
        note_str = f" ⚠️ {ls.note}" if ls.note else ""
        lines.append(
            f"<b>{ls.number}.</b> {ls.subject}{note_str}{room_str}{teacher_str}"
        )
    return "\n".join(lines)

def fmt_news_item(item: NewsItem) -> str:
    return (
        f"{item.category_icon} <b>{item.title}</b>\n"
        f"{SEPARATOR_THIN}\n"
        f"{item.body}\n\n"
        f"<i>👤 {item.author} · 📅 {fmt_datetime(item.created_at)}</i>\n"
        f"<i>👁️ Просмотров: {item.views}</i>"
    )

def fmt_homework_item(hw: HomeworkItem) -> str:
    return (
        f"{hw.priority_icon} <b>{hw.subject}</b>\n"
        f"📝 {hw.task}\n"
        f"⏰ Сдать до: <b>{hw.due_date}</b>\n"
        f"<i>👤 {hw.author}</i>"
    )

def fmt_stats_overview(
    total_students: int,
    total_duties: int,
    total_history: int,
    current_duty: str,
    total_news: int,
    total_hw: int,
) -> str:
    return (
        f"{fmt_header('📊 Статистика класса')}"
        f"👥 Учеников: <b>{total_students}</b>\n"
        f"🎯 Назначено дежурств: <b>{total_duties}</b>\n"
        f"📝 Записей в истории: <b>{total_history}</b>\n"
        f"🟢 Дежурный сейчас: <b>{current_duty}</b>\n"
        f"📰 Новостей: <b>{total_news}</b>\n"
        f"📖 Домашних заданий: <b>{total_hw}</b>"
    )

def fmt_leaderboard(students: list[Student], top_n: int = 10, key: str = "xp") -> str:
    if key == "xp":
        sorted_s = sorted(students, key=lambda s: s.xp, reverse=True)
        val_fn   = lambda s: f"{s.xp:,} XP"
        title    = "🏆 Рейтинг по XP"
    elif key == "duty":
        sorted_s = sorted(students, key=lambda s: s.total_duty_count, reverse=True)
        val_fn   = lambda s: f"{s.total_duty_count} деж."
        title    = "🎯 Рейтинг по дежурствам"
    elif key == "quiz":
        sorted_s = sorted(students, key=lambda s: s.quiz_correct, reverse=True)
        val_fn   = lambda s: f"{s.quiz_correct} прав."
        title    = "🧠 Рейтинг викторины"
    else:
        sorted_s = students
        val_fn   = lambda s: ""
        title    = "📊 Рейтинг"

    lines = [f"{fmt_header(title)}"]
    for i, s in enumerate(sorted_s[:top_n], 1):
        medal = MEDAL_ICONS[i-1] if i <= 3 else f"{i}."
        lvl   = get_level(s.xp)
        lines.append(
            f"{medal} <b>{s.name}</b>  —  {val_fn(s)}"
            f"  <i>(Ур.{lvl})</i>"
        )
    return "\n".join(lines)

def fmt_class_info(info: dict, class_name: str, school: str, year: str) -> str:
    motto   = info.get("motto",   "«Знания — сила!»")
    teacher = info.get("teacher", "Классный руководитель")
    room    = info.get("room",    "—")
    desc    = info.get("desc",    "Дружный, активный класс.")
    return (
        f"╔{'═'*24}╗\n"
        f"║   🏫 НАШ КЛАСС   ║\n"
        f"╚{'═'*24}╝\n\n"
        f"🔷 Класс: <b>{class_name}</b>\n"
        f"🏛️ Школа: <b>{school}</b>\n"
        f"📅 Год: <b>{year}</b>\n"
        f"🚪 Кабинет: <b>{room}</b>\n"
        f"👩‍🏫 Кл. руководитель: <b>{teacher}</b>\n\n"
        f"✨ Девиз:\n<i>{motto}</i>\n\n"
        f"📝 {desc}"
    )

TRUTH_QUESTIONS: list[str] = [
    "Кому в классе ты завидуешь больше всего?",
    "Какую тройку ты получил(а) незаслуженно?",
    "Какой предмет ты тайно любишь, хотя говоришь, что нет?",
    "Кому ты списывал(а) домашку последний раз?",
    "Что ты никогда не скажешь учителю?",
    "Какая твоя самая большая школьная ложь?",
    "Кто из одноклассников тебя вдохновляет?",
    "Какой твой самый неловкий момент в школе?",
]

DARE_ACTIONS: list[str] = [
    "Напиши комплимент каждому в классе (в чат).",
    "Расскажи анекдот прямо сейчас.",
    "Изобрази своего любимого учителя.",
    "Напиши стихотворение про класс за 2 минуты.",
    "Произнеси скороговорку 3 раза подряд.",
    "Спой куплет любой песни.",
    "Назови 5 столиц за 10 секунд.",
    "Сделай 10 приседаний.",
]

def random_truth() -> str:
    return random.choice(TRUTH_QUESTIONS)

def random_dare() -> str:
    return random.choice(DARE_ACTIONS)

def coin_flip() -> str:
    return random.choice(["ОРЁЛ 🦅", "РЕШКА 🌟"])

def roll_dice(sides: int = 6) -> int:
    return random.randint(1, sides)

WORLD_TIMES: list[tuple[str, str, int]] = [
    ("🇷🇺 Москва",     "Europe/Moscow",       +3),
    ("🇺🇿 Ташкент",    "Asia/Tashkent",        +5),
    ("🇬🇧 Лондон",     "Europe/London",        0),
    ("🇩🇪 Берлин",     "Europe/Berlin",        +1),
    ("🇺🇸 Нью-Йорк",  "America/New_York",     -5),
    ("🇯🇵 Токио",      "Asia/Tokyo",          +9),
    ("🇨🇳 Пекин",      "Asia/Shanghai",       +8),
    ("🇦🇪 Дубай",      "Asia/Dubai",           +4),
]

# ══════════════════════════════════════════════════════════════════════
# 8. HANDLERS
# ══════════════════════════════════════════════════════════════════════

router = Router()

# ── Helper check ─────────────────────────────────────────────────────
async def _check_code_for_admin(message: Message, state: FSMContext) -> None:
    if message.text == ADMIN_CODE:
        await db.add_moderator(message.from_user.id)
        await state.clear()
        await message.answer(
            "✅ Доступ разрешён! Админ-панель:",
            reply_markup=kb_admin_panel(is_owner=False)
        )
    else:
        await message.answer("❌ Неверный код! Попробуйте снова или /start")
        await state.set_state(AdminStates.waiting_for_code)

# ── /start ───────────────────────────────────────────────────────────
@router.message(Command("start"))
async def start_command(message: Message):
    user_id = message.from_user.id
    is_owner = (user_id == OWNER_ID)
    is_mod = user_id in await db.get_moderators()

    await message.answer(
        f"👋 Привет! Я бот <b>PDP School</b> ({CLASS_YEAR})\n"
        f"Помогу с расписанием, дежурствами, новостями и многим другим!\n\n"
        f"Выбери действие:",
        reply_markup=kb_main(is_owner=is_owner, is_mod=is_mod),
        parse_mode="HTML",
    )

# ── /help ────────────────────────────────────────────────────────────
@router.message(Command("help"))
async def help_command(message: Message):
    text = (
        "ℹ️ <b>Доступные команды:</b>\n\n"
        "/start – главное меню\n"
        "/admin – админ-панель (код: 2222)\n\n"
        "<b>Возможности:</b>\n"
        "• Случайный выбор дежурного\n"
        "• Просмотр списка студентов\n"
        "• История дежурств\n"
        "• Поиск студентов\n"
        "• Админ-панель для управления\n"
        "• Расписание уроков\n"
        "• Новости и объявления\n"
        "• Домашние задания\n"
        "• Опросы и голосования\n"
        "• Викторины и мини-игры\n"
        "• Рейтинги и статистика\n"
        "• Анонимные сообщения"
    )
    await message.answer(text, parse_mode="HTML")

# ── /admin ───────────────────────────────────────────────────────────
@router.message(Command("admin"))
async def admin_command(message: Message, state: FSMContext):
    await message.answer("🔐 Введите код доступа к админ-панели:")
    await state.set_state(AdminStates.waiting_for_code)

# ── Main menu callback ───────────────────────────────────────────────
@router.callback_query(F.data == "main_menu")
async def main_menu_callback(call: CallbackQuery):
    user_id = call.from_user.id
    is_owner = (user_id == OWNER_ID)
    is_mod = user_id in await db.get_moderators()
    await call.message.edit_text("Главное меню:", reply_markup=kb_main(is_owner=is_owner, is_mod=is_mod))
    await call.answer()

# ── Admin Code Entry ─────────────────────────────────────────────────
@router.message(AdminStates.waiting_for_code)
async def admin_code_handler(message: Message, state: FSMContext):
    await _check_code_for_admin(message, state)

# ── Admin Panel Callback ─────────────────────────────────────────────
@router.callback_query(F.data == "admin_panel")
async def admin_panel_callback(call: CallbackQuery, state: FSMContext):
    user_id = call.from_user.id
    is_owner = (user_id == OWNER_ID)
    is_mod = user_id in await db.get_moderators()
    if is_owner or is_mod:
        await call.message.edit_text("🔐 Админ-панель:", reply_markup=kb_admin_panel(is_owner=is_owner))
    else:
        await call.message.edit_text("🔐 Введите код доступа к админ-панели:", reply_markup=kb_back_main())
        await state.set_state(AdminStates.waiting_for_code)
    await call.answer()

# ── Duty Random ──────────────────────────────────────────────────────
@router.callback_query(F.data == "duty_random")
async def duty_random_callback(call: CallbackQuery):
    students = await db.get_all_students()
    if not students:
        await call.message.edit_text("❌ Список студентов пуст.", reply_markup=kb_back_main())
        await call.answer()
        return

    uid, student = random.choice(list(students.items()))
    now = now_iso()

    await db.update_student(uid, {
        "isDuty": True,
        "lastDutyDate": now,
        "totalDutyCount": student.get("totalDutyCount", 0) + 1,
    })

    record = {
        "student_name": student["name"],
        "student_id": uid,
        "assigned_at": now,
    }
    await db.add_history_record(record)

    await call.message.edit_text(
        f"✅ Дежурный сегодня: <b>{student['name']}</b>",
        reply_markup=kb_duty_result(uid),
        parse_mode="HTML",
    )
    await call.answer()

# ── Duty Current ─────────────────────────────────────────────────────
@router.callback_query(F.data == "duty_current")
async def duty_current_callback(call: CallbackQuery):
    students = await db.get_all_students()
    current = [(uid, s) for uid, s in students.items() if s.get("isDuty")]
    if not current:
        await call.message.edit_text("🟢 Сейчас нет назначенного дежурного.", reply_markup=kb_duty_menu())
    else:
        uid, s = current[0]
        await call.message.edit_text(
            fmt_duty_card(s['name'], s.get('lastDutyDate', '?')[:19], s.get('totalDutyCount', 0)),
            reply_markup=kb_duty_result(uid),
            parse_mode="HTML",
        )
    await call.answer()

# ── Duty Menu ────────────────────────────────────────────────────────
@router.callback_query(F.data == "duty_menu")
async def duty_menu_callback(call: CallbackQuery):
    await call.message.edit_text("🎯 Дежурство:", reply_markup=kb_duty_menu())
    await call.answer()

# ── Duty History ─────────────────────────────────────────────────────
@router.callback_query(F.data.startswith("duty_history"))
async def duty_history_callback(call: CallbackQuery):
    parts = call.data.split(":")
    page = int(parts[1]) if len(parts) > 1 else 0

    history = await db.get_history()
    if not history:
        await call.message.edit_text("📭 История дежурств пуста.", reply_markup=kb_back("duty_menu"))
        await call.answer()
        return

    history.reverse()
    paginated = paginate(history, page, PAGE_SIZE_HISTORY)

    text = "📊 <b>История дежурств:</b>\n\n"
    for rec in paginated.items:
        name = rec.get("student_name", "?")
        when = rec.get("assigned_at", "?")[:19]
        text += f"🔹 {name} — {when}\n"

    await call.message.edit_text(
        text,
        reply_markup=kb_duty_history(paginated.page, paginated.total_pages),
        parse_mode="HTML",
    )
    await call.answer()

# ── Students List ────────────────────────────────────────────────────
@router.callback_query(F.data.startswith("students_list"))
async def students_list_callback(call: CallbackQuery):
    parts = call.data.split(":")
    page = int(parts[1]) if len(parts) > 1 else 0

    students = await db.get_all_students()
    if not students:
        await call.message.edit_text("📭 Список пуст.", reply_markup=kb_back_main())
        await call.answer()
        return

    total_pages = max(1, math.ceil(len(students) / PAGE_SIZE_STUDENTS))
    await call.message.edit_text(
        "👥 <b>Студенты:</b>",
        reply_markup=kb_students_list(students, page, total_pages),
        parse_mode="HTML",
    )
    await call.answer()

# ── Student Profile ──────────────────────────────────────────────────
@router.callback_query(F.data.startswith("student_profile:"))
async def student_profile_callback(call: CallbackQuery):
    uid = call.data.split(":")[1]
    data = await db.get_student(uid)
    if not data:
        await call.answer("Студент не найден!", show_alert=True)
        return

    s = Student.from_dict(uid, data)
    user_id = call.from_user.id
    is_owner = (user_id == OWNER_ID)
    is_mod = user_id in await db.get_moderators()

    await call.message.edit_text(
        fmt_student_card(s),
        reply_markup=kb_student_profile(uid, is_admin=(is_owner or is_mod)),
        parse_mode="HTML",
    )
    await call.answer()

# ── Search Student ───────────────────────────────────────────────────
@router.callback_query(F.data == "search_student")
async def search_student_callback(call: CallbackQuery, state: FSMContext):
    await call.message.edit_text(
        "🔍 Введите имя студента для поиска (или часть имени):",
        reply_markup=kb_back("students_list:0"),
    )
    await state.set_state(AdminStates.waiting_for_student_search)
    await call.answer()

@router.message(AdminStates.waiting_for_student_search)
async def process_student_search(message: Message, state: FSMContext):
    query = message.text.strip()
    if not query:
        await message.answer("❌ Введите имя для поиска!")
        return

    results = await db.search_students(query)
    if not results:
        await message.answer("🔍 Ничего не найдено.", reply_markup=kb_main())
    else:
        text = f"🔍 <b>Результаты поиска по '{query}':</b>\n\n"
        for i, (uid, s) in enumerate(results.items(), 1):
            icon = "🟢" if s.get("isDuty") else "⚪"
            text += f"{i}. {icon} {s['name']} – дежурств: {s.get('totalDutyCount', 0)}\n"
        await message.answer(text, reply_markup=kb_main(), parse_mode="HTML")

    await state.clear()

# ── Admin: Add Student ───────────────────────────────────────────────
@router.callback_query(F.data == "admin_add_student")
async def admin_add_student_callback(call: CallbackQuery, state: FSMContext):
    await call.message.edit_text(
        "➕ Введите имя нового студента (или /cancel для отмены):",
        reply_markup=kb_back("admin_panel"),
    )
    await state.set_state(AdminStates.waiting_for_student_add)
    await call.answer()

@router.message(AdminStates.waiting_for_student_add)
async def process_student_add(message: Message, state: FSMContext):
    if message.text == "/cancel":
        await message.answer("❌ Добавление отменено.", reply_markup=kb_admin_panel())
        await state.clear()
        return

    name = message.text.strip()
    if len(name) < 2:
        await message.answer("❌ Имя слишком короткое! Минимум 2 символа.")
        return

    student_data = {
        "name": name,
        "isDuty": False,
        "lastDutyDate": None,
        "totalDutyCount": 0,
        "createdAt": now_ts_ms(),
        "xp": 0,
        "level": 1,
        "streak": 0,
        "emoji": "👤",
        "bio": "",
        "quizCorrect": 0,
        "quizTotal": 0,
        "gamesPlayed": 0,
        "pollsVoted": 0,
    }
    uid = await db.add_student(student_data)
    if uid:
        await message.answer(f"✅ Студент <b>{name}</b> добавлен! ID: {uid}", reply_markup=kb_admin_panel(), parse_mode="HTML")
    else:
        await message.answer("❌ Ошибка при добавлении!", reply_markup=kb_admin_panel())

    await state.clear()

# ── Admin: Delete Student ────────────────────────────────────────────
@router.callback_query(F.data == "admin_delete_student")
async def admin_delete_student_callback(call: CallbackQuery, state: FSMContext):
    students = await db.get_all_students()
    if not students:
        await call.message.edit_text("📭 Список студентов пуст.", reply_markup=kb_admin_panel())
        await call.answer()
        return

    keyboard = []
    for uid, student in list(students.items())[:20]:
        keyboard.append([_btn(f"❌ {student['name']}", f"confirm_delete_{uid}")])

    keyboard.append([_btn("🔙 К админ-панели", "admin_panel")])

    await call.message.edit_text(
        "➖ Выберите студента для удаления:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard),
    )
    await call.answer()

@router.callback_query(F.data.startswith("confirm_delete_"))
async def confirm_delete_callback(call: CallbackQuery):
    uid = call.data.split("confirm_delete_")[1]
    student = await db.get_student(uid)
    if not student:
        await call.answer("Студент не найден!", show_alert=True)
        return

    await call.message.edit_text(
        f"Вы уверены, что хотите удалить студента:\n\n"
        f"<b>{student['name']}</b>\n\n"
        f"Дежурств: {student.get('totalDutyCount', 0)}",
        reply_markup=kb_confirm(f"delete_{uid}", "admin_delete_student"),
        parse_mode="HTML",
    )
    await call.answer()

@router.callback_query(F.data.startswith("delete_"))
async def delete_student_callback(call: CallbackQuery):
    uid = call.data.split("delete_")[1]
    student = await db.get_student(uid)
    if not student:
        await call.answer("Студент не найден!", show_alert=True)
        return

    if await db.delete_student(uid):
        await call.message.edit_text(
            f"✅ Студент <b>{student['name']}</b> удалён!",
            reply_markup=kb_admin_panel(),
            parse_mode="HTML",
        )
    else:
        await call.message.edit_text("❌ Ошибка при удалении!", reply_markup=kb_admin_panel())
    await call.answer()

# ── Admin: All Students (Admin view) ─────────────────────────────────
@router.callback_query(F.data == "admin_all_students")
async def admin_all_students_callback(call: CallbackQuery):
    students = await db.get_all_students()
    if not students:
        await call.message.edit_text("📭 Список пуст.", reply_markup=kb_admin_panel())
    else:
        text = "👥 <b>Все студенты (админ):</b>\n\n"
        for i, (uid, s) in enumerate(students.items(), 1):
            icon = "🟢" if s.get('isDuty') else "⚪"
            text += f"{i}. {icon} {s['name']} [ID: {uid}]\n"
            text += f"   Дежурств: {s.get('totalDutyCount', 0)} | "
            text += f"Посл.: {s.get('lastDutyDate', 'нет')[:10]}\n"
        if len(text) > 4000:
            text = text[:4000] + "\n\n⚠️ Список обрезан."
        await call.message.edit_text(text, reply_markup=kb_admin_panel(), parse_mode="HTML")
    await call.answer()

# ── Admin: Reset Duty ────────────────────────────────────────────────
@router.callback_query(F.data == "admin_reset_duty")
async def admin_reset_duty_callback(call: CallbackQuery):
    await call.message.edit_text(
        "⚠️ Вы уверены, что хотите сбросить все флаги дежурств?",
        reply_markup=kb_confirm("confirm_reset", "admin_panel"),
    )
    await call.answer()

@router.callback_query(F.data == "confirm_reset")
async def confirm_reset_callback(call: CallbackQuery):
    students = await db.get_all_students()
    count = 0
    for uid in students:
        if await db.update_student(uid, {"isDuty": False}):
            count += 1
    await call.message.edit_text(f"🔄 Флаги дежурств сброшены у {count} студентов.", reply_markup=kb_admin_panel())
    await call.answer()

# ── Admin: Clear History ─────────────────────────────────────────────
@router.callback_query(F.data == "admin_clear_history")
async def admin_clear_history_callback(call: CallbackQuery):
    await call.message.edit_text(
        "⚠️ Вы уверены, что хотите полностью очистить историю дежурств?",
        reply_markup=kb_confirm("confirm_clear_history", "admin_panel"),
    )
    await call.answer()

@router.callback_query(F.data == "confirm_clear_history")
async def confirm_clear_history_callback(call: CallbackQuery):
    if await db.delete_history():
        await call.message.edit_text("🗑️ История дежурств очищена!", reply_markup=kb_admin_panel())
    else:
        await call.message.edit_text("❌ Ошибка при очистке!", reply_markup=kb_admin_panel())
    await call.answer()

# ── Admin Stats ──────────────────────────────────────────────────────
@router.callback_query(F.data == "admin_stats")
async def admin_stats_callback(call: CallbackQuery):
    students = await db.get_all_students()
    history = await db.get_history()
    news = await db.get_all_news()
    hw = await db.get_all_homework()

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
        f"📰 Новостей: {len(news)}\n"
        f"📖 Домашних заданий: {len(hw)}"
    )
    await call.message.edit_text(text, reply_markup=kb_admin_panel(), parse_mode="HTML")
    await call.answer()

# ── Schedule Menu ────────────────────────────────────────────────────
@router.callback_query(F.data == "schedule_menu")
async def schedule_menu_callback(call: CallbackQuery):
    await call.message.edit_text("📚 <b>Расписание:</b>", reply_markup=kb_schedule_menu(), parse_mode="HTML")
    await call.answer()

# ── Schedule Day ─────────────────────────────────────────────────────
@router.callback_query(F.data.startswith("schedule_day:"))
async def schedule_day_callback(call: CallbackQuery):
    day_key = call.data.split(":")[1]
    day_name = DAYS_RU[DAYS_KEYS.index(day_key)] if day_key in DAYS_KEYS else day_key

    raw = await db.get_day_schedule(day_key)
    schedule = DaySchedule.from_dict(day_key, raw)
    lessons = schedule.lessons

    user_id = call.from_user.id
    is_owner = (user_id == OWNER_ID)

    text = fmt_schedule_day(day_name, lessons)
    await call.message.edit_text(text, reply_markup=kb_schedule_day(day_key, is_owner=is_owner), parse_mode="HTML")
    await call.answer()

# ── Schedule Week ────────────────────────────────────────────────────
@router.callback_query(F.data == "schedule_week")
async def schedule_week_callback(call: CallbackQuery):
    schedule = await db.get_schedule()
    if not schedule:
        await call.message.edit_text("📭 Расписание не задано.", reply_markup=kb_back("schedule_menu"))
        await call.answer()
        return

    lines = ["📅 <b>Расписание на неделю</b>\n" + SEPARATOR]
    for i, day_key in enumerate(DAYS_KEYS):
        raw = schedule.get(day_key, {})
        ds = DaySchedule.from_dict(day_key, raw)
        lines.append(f"\n<b>{DAYS_RU[i]}:</b>")
        if ds.lessons:
            for ls in ds.lessons:
                lines.append(f"  {ls.number}. {ls.subject}")
        else:
            lines.append("  <i>уроков нет</i>")

    text = "\n".join(lines)
    if len(text) > 4000:
        text = text[:4000] + "\n... (обрезано)"

    await call.message.edit_text(text, reply_markup=kb_back("schedule_menu"), parse_mode="HTML")
    await call.answer()

# ── Homework List ────────────────────────────────────────────────────
@router.callback_query(F.data.startswith("homework_list"))
async def homework_list_callback(call: CallbackQuery):
    parts = call.data.split(":")
    page = int(parts[1]) if len(parts) > 1 else 0

    raw = await db.get_all_homework()
    items = [HomeworkItem.from_dict(uid, d) for uid, d in raw.items()]
    items.sort(key=lambda h: h.created_at, reverse=True)

    if not items:
        await call.message.edit_text("📖 Домашних заданий нет.", reply_markup=kb_back_main())
        await call.answer()
        return

    paginated = paginate(items, page, PAGE_SIZE_HOMEWORK)
    user_id = call.from_user.id
    is_owner = (user_id == OWNER_ID)

    text = "📝 <b>Домашние задания:</b>\n\n"
    for hw in paginated.items:
        text += f"{hw.priority_icon} <b>{hw.subject}</b> — {hw.task[:40]}...\n"

    await call.message.edit_text(
        text,
        reply_markup=kb_homework_list(paginated.items, paginated.page, paginated.total_pages, is_owner=is_owner),
        parse_mode="HTML",
    )
    await call.answer()

@router.callback_query(F.data.startswith("hw_view:"))
async def hw_view_callback(call: CallbackQuery):
    uid = call.data.split(":")[1]
    raw = await db.get_all_homework()
    if uid not in raw:
        await call.answer("ДЗ не найдено!", show_alert=True)
        return

    hw = HomeworkItem.from_dict(uid, raw[uid])
    await call.message.edit_text(
        fmt_homework_item(hw),
        reply_markup=kb_back("homework_list:0"),
        parse_mode="HTML",
    )
    await call.answer()

# ── News List ────────────────────────────────────────────────────────
@router.callback_query(F.data.startswith("news_list"))
async def news_list_callback(call: CallbackQuery):
    parts = call.data.split(":")
    page = int(parts[1]) if len(parts) > 1 else 0

    raw = await db.get_all_news()
    items = [NewsItem.from_dict(uid, d) for uid, d in raw.items()]
    items.sort(key=lambda n: (not n.pinned, n.created_at), reverse=False)
    items.sort(key=lambda n: n.pinned, reverse=True)

    if not items:
        await call.message.edit_text("📰 Новостей пока нет.", reply_markup=kb_back_main())
        await call.answer()
        return

    paginated = paginate(items, page, PAGE_SIZE_NEWS)
    text = "📰 <b>Новости:</b>\n\n"
    for n in paginated.items:
        pin = "📌 " if n.pinned else ""
        text += f"{pin}{n.category_icon} <b>{n.title[:30]}</b>\n"

    await call.message.edit_text(
        text,
        reply_markup=kb_news_list(paginated.items, paginated.page, paginated.total_pages),
        parse_mode="HTML",
    )
    await call.answer()

@router.callback_query(F.data.startswith("news_view:"))
async def news_view_callback(call: CallbackQuery):
    uid = call.data.split(":")[1]
    raw = await db.get_all_news()
    if uid not in raw:
        await call.answer("Новость не найдена!", show_alert=True)
        return

    item = NewsItem.from_dict(uid, raw[uid])
    await db.increment_news_views(uid)

    user_id = call.from_user.id
    is_owner = (user_id == OWNER_ID)

    await call.message.edit_text(
        fmt_news_item(item),
        reply_markup=kb_news_view(uid, is_owner=is_owner),
        parse_mode="HTML",
    )
    await call.answer()

# ── Events List ──────────────────────────────────────────────────────
@router.callback_query(F.data == "events_list")
async def events_list_callback(call: CallbackQuery):
    raw = await db.get_all_events()
    items = [ClassEvent.from_dict(uid, d) for uid, d in raw.items()]
    items.sort(key=lambda e: e.date)

    user_id = call.from_user.id
    is_owner = (user_id == OWNER_ID)

    if not items:
        await call.message.edit_text("📅 Событий пока нет.", reply_markup=kb_back_main())
    else:
        text = "📅 <b>События:</b>\n\n"
        for ev in items[:15]:
            text += f"📅 {ev.date} — <b>{ev.title[:30]}</b>\n"
        await call.message.edit_text(text, reply_markup=kb_events_list(items, is_owner=is_owner), parse_mode="HTML")
    await call.answer()

@router.callback_query(F.data.startswith("event_view:"))
async def event_view_callback(call: CallbackQuery):
    uid = call.data.split(":")[1]
    raw = await db.get_all_events()
    if uid not in raw:
        await call.answer("Событие не найдено!", show_alert=True)
        return

    ev = ClassEvent.from_dict(uid, raw[uid])
    text = (
        f"📅 <b>{ev.title}</b>\n"
        f"{SEPARATOR_THIN}\n"
        f"📝 {ev.description}\n\n"
        f"📅 Дата: {ev.date}\n"
        f"⏰ Время: {ev.time or '—'}\n"
        f"📍 Место: {ev.location or '—'}"
    )
    await call.message.edit_text(text, reply_markup=kb_back("events_list"), parse_mode="HTML")
    await call.answer()

# ── Polls List ───────────────────────────────────────────────────────
@router.callback_query(F.data == "polls_list")
async def polls_list_callback(call: CallbackQuery):
    raw = await db.get_all_polls()
    items = [Poll.from_dict(uid, d) for uid, d in raw.items()]
    user_id = call.from_user.id
    is_owner = (user_id == OWNER_ID)

    if not items:
        await call.message.edit_text("🗳️ Опросов пока нет.", reply_markup=kb_back_main())
    else:
        text = "🗳️ <b>Опросы:</b>\n\n"
        for p in items[:10]:
            icon = "🟢" if p.status == "active" else "🔴"
            text += f"{icon} {p.question[:35]} — {p.total_votes} голосов\n"
        await call.message.edit_text(text, reply_markup=kb_polls_list(items, is_owner=is_owner), parse_mode="HTML")
    await call.answer()

@router.callback_query(F.data.startswith("poll_view:"))
async def poll_view_callback(call: CallbackQuery):
    uid = call.data.split(":")[1]
    raw = await db.get_all_polls()
    if uid not in raw:
        await call.answer("Опрос не найден!", show_alert=True)
        return

    poll = Poll.from_dict(uid, raw[uid])
    text = f"🗳️ <b>{poll.question}</b>\n\n"
    for i, opt in enumerate(poll.options):
        pct = (opt.votes / max(poll.total_votes, 1)) * 100
        bar_len = int(pct / 10)
        text += f"▸ {opt.text} — {opt.votes} голосов [{''.join(['█' for _ in range(bar_len)])}] {pct:.1f}%\n"

    text += f"\n<i>Всего голосов: {poll.total_votes}</i>"

    await call.message.edit_text(
        text,
        reply_markup=kb_poll_vote(poll) if poll.status == "active" else kb_back("polls_list"),
        parse_mode="HTML",
    )
    await call.answer()

@router.callback_query(F.data.startswith("poll_vote:"))
async def poll_vote_callback(call: CallbackQuery):
    _, poll_uid, opt_idx = call.data.split(":")
    opt_idx = int(opt_idx)

    raw = await db.get_all_polls()
    if poll_uid not in raw:
        await call.answer("Опрос не найден!", show_alert=True)
        return

    poll_data = raw[poll_uid]
    poll = Poll.from_dict(poll_uid, poll_data)

    if call.from_user.id in poll.voters:
        await call.answer("Вы уже голосовали!", show_alert=True)
        return

    if opt_idx >= len(poll.options):
        await call.answer("Неверный вариант!", show_alert=True)
        return

    poll.options[opt_idx].votes += 1
    poll.voters.append(call.from_user.id)

    # Save back
    update_data = {
        "options": {str(i): o.to_dict() for i, o in enumerate(poll.options)},
        "voters": poll.voters,
    }
    await db.update_poll(poll_uid, update_data)

    await call.answer("✅ Голос учтён!", show_alert=True)
    # Refresh
    await poll_view_callback(call)

# ── Games Menu ───────────────────────────────────────────────────────
@router.callback_query(F.data == "games_menu")
async def games_menu_callback(call: CallbackQuery):
    await call.message.edit_text("🎮 <b>Мини-игры</b>", reply_markup=kb_games_menu(), parse_mode="HTML")
    await call.answer()

@router.callback_query(F.data == "game_coin")
async def game_coin_callback(call: CallbackQuery):
    result = coin_flip()
    await call.message.edit_text(
        f"🪙 <b>Орёл или решка:</b>\n\nРезультат: <b>{result}</b>",
        reply_markup=kb_games_menu(),
        parse_mode="HTML",
    )
    await call.answer()

@router.callback_query(F.data == "game_dice")
async def game_dice_callback(call: CallbackQuery):
    result = roll_dice()
    await call.message.edit_text(
        f"🎲 <b>Бросок кубика:</b> <b>{result}</b>",
        reply_markup=kb_games_menu(),
        parse_mode="HTML",
    )
    await call.answer()

@router.callback_query(F.data == "game_wheel")
async def game_wheel_callback(call: CallbackQuery):
    students = await db.get_all_students()
    if not students:
        await call.message.edit_text("Список пуст.", reply_markup=kb_games_menu())
        await call.answer()
        return

    name = random.choice(list(students.values()))["name"]
    await call.message.edit_text(
        f"🎡 <b>Рулетка имён:</b> выбран(а) <b>{name}</b>!",
        reply_markup=kb_games_menu(),
        parse_mode="HTML",
    )
    await call.answer()

@router.callback_query(F.data == "game_truth_dare")
async def game_truth_dare_callback(call: CallbackQuery):
    if random.choice([True, False]):
        text = f"😈 <b>Правда:</b>\n\n{random_truth()}"
    else:
        text = f"😈 <b>Действие:</b>\n\n{random_dare()}"
    await call.message.edit_text(text, reply_markup=kb_games_menu(), parse_mode="HTML")
    await call.answer()

# ── Quiz Start ───────────────────────────────────────────────────────
@router.callback_query(F.data == "quiz_start")
async def quiz_start_callback(call: CallbackQuery):
    raw = await db.get_all_quizzes()
    if not raw:
        await call.message.edit_text("🧠 Викторина: вопросов пока нет.", reply_markup=kb_back_main())
        await call.answer()
        return

    uid, data = random.choice(list(raw.items()))
    q = QuizQuestion.from_dict(uid, data)

    # Shuffle options
    options = q.options[:]
    correct = q.correct_index
    correct_text = options[correct]
    random.shuffle(options)
    new_correct = options.index(correct_text)

    await call.message.edit_text(
        f"🧠 <b>Викторина:</b>\n\n{q.question}",
        reply_markup=kb_quiz_options(uid, options),
        parse_mode="HTML",
    )
    await call.answer()

@router.callback_query(F.data.startswith("quiz_answer:"))
async def quiz_answer_callback(call: CallbackQuery):
    _, question_uid, answer_idx = call.data.split(":")
    answer_idx = int(answer_idx)

    raw = await db.get_all_quizzes()
    if question_uid not in raw:
        await call.answer("Вопрос не найден!", show_alert=True)
        return

    q = QuizQuestion.from_dict(question_uid, raw[question_uid])
    is_correct = (answer_idx == q.correct_index)

    if is_correct:
        await call.answer("✅ Правильно! +15 XP", show_alert=True)
    else:
        await call.answer(f"❌ Неправильно! Правильный: {q.options[q.correct_index]}", show_alert=True)

    await quiz_start_callback(call)

@router.callback_query(F.data == "quiz_skip")
async def quiz_skip_callback(call: CallbackQuery):
    await quiz_start_callback(call)

# ── Anonymous Menu ──────────────────────────────────────────────────
@router.callback_query(F.data == "anon_menu")
async def anon_menu_callback(call: CallbackQuery):
    user_id = call.from_user.id
    is_owner = (user_id == OWNER_ID)
    await call.message.edit_text("💬 <b>Анонимные сообщения</b>", reply_markup=kb_anon_menu(is_owner=is_owner), parse_mode="HTML")
    await call.answer()

@router.callback_query(F.data == "anon_write")
async def anon_write_callback(call: CallbackQuery, state: FSMContext):
    await call.message.edit_text(
        "✍️ Напишите анонимное сообщение (оно будет видно всем):",
        reply_markup=kb_back("anon_menu"),
    )
    await state.set_state(AnonStates.entering_message)
    await call.answer()

@router.message(AnonStates.entering_message)
async def process_anon_message(message: Message, state: FSMContext):
    text = message.text.strip()
    if not text:
        await message.answer("❌ Введите текст сообщения!")
        return

    msg_data = {
        "text": text,
        "createdAt": now_iso(),
        "senderHash": hash_user_id(message.from_user.id),
        "approved": True,
    }
    uid = await db.add_anon_message(msg_data)
    if uid:
        await message.answer("✅ Анонимное сообщение отправлено!", reply_markup=kb_main())
    else:
        await message.answer("❌ Ошибка при отправке!", reply_markup=kb_main())
    await state.clear()

@router.callback_query(F.data == "anon_view")
async def anon_view_callback(call: CallbackQuery):
    messages = await db.get_anon_messages()
    if not messages:
        await call.message.edit_text("📬 Анонимных сообщений пока нет.", reply_markup=kb_back("anon_menu"))
    else:
        text = "📬 <b>Последние анонимные сообщения:</b>\n\n"
        msgs = list(messages.values())[-10:]
        for msg in msgs:
            text += f"💬 {msg.get('text', '?')[:100]}\n"
            text += f"   <i>{msg.get('createdAt', '?')[:19]}</i>\n\n"

        if len(text) > 4000:
            text = text[:4000] + "\n... (обрезано)"

        await call.message.edit_text(text, reply_markup=kb_back("anon_menu"), parse_mode="HTML")
    await call.answer()

# ── Useful Menu ──────────────────────────────────────────────────────
@router.callback_query(F.data == "useful_menu")
async def useful_menu_callback(call: CallbackQuery):
    await call.message.edit_text("📖 <b>Полезности</b>", reply_markup=kb_useful_menu(), parse_mode="HTML")
    await call.answer()

@router.callback_query(F.data == "useful_worldtime")
async def useful_worldtime_callback(call: CallbackQuery):
    text = "🌍 <b>Время в мире:</b>\n\n"
    from datetime import timezone, timedelta
    now_utc = datetime.now(timezone.utc)
    for flag, tz_name, offset in WORLD_TIMES:
        local = now_utc + timedelta(hours=offset)
        text += f"{flag} <b>{tz_name.split('/')[-1]}</b>: {local.strftime('%H:%M')}\n"
    await call.message.edit_text(text, reply_markup=kb_useful_menu(), parse_mode="HTML")
    await call.answer()

# ── Settings Menu ────────────────────────────────────────────────────
@router.callback_query(F.data == "settings_menu")
async def settings_menu_callback(call: CallbackQuery):
    await call.message.edit_text("⚙️ <b>Настройки</b>", reply_markup=kb_settings_menu(), parse_mode="HTML")
    await call.answer()

# ── Class Info ───────────────────────────────────────────────────────
@router.callback_query(F.data == "class_info")
async def class_info_callback(call: CallbackQuery):
    info = await db.get_class_info()
    text = fmt_class_info(info, CLASS_NAME, CLASS_SCHOOL, CLASS_YEAR)
    await call.message.edit_text(text, reply_markup=kb_back_main(), parse_mode="HTML")
    await call.answer()

# ── Birthdays Menu ──────────────────────────────────────────────────
@router.callback_query(F.data == "birthdays_menu")
async def birthdays_menu_callback(call: CallbackQuery):
    await call.message.edit_text("🎉 <b>Дни рождения</b>", reply_markup=kb_birthdays_menu(), parse_mode="HTML")
    await call.answer()

@router.callback_query(F.data == "birthdays_upcoming")
async def birthdays_upcoming_callback(call: CallbackQuery):
    students = await db.get_all_students()
    upcoming = []
    for uid, s in students.items():
        bday = s.get("birthday")
        if bday:
            days = days_until_birthday(bday)
            if days <= 30:
                upcoming.append((days, s["name"], bday))

    upcoming.sort()
    if not upcoming:
        text = "🎂 В ближайшие 30 дней дней рождения нет."
    else:
        text = "🎂 <b>Ближайшие дни рождения:</b>\n\n"
        for days, name, bday in upcoming[:10]:
            text += f"🎂 {bday} — <b>{name}</b> (через {days} дн.)\n"

    await call.message.edit_text(text, reply_markup=kb_back("birthdays_menu"), parse_mode="HTML")
    await call.answer()

@router.callback_query(F.data == "birthdays_all")
async def birthdays_all_callback(call: CallbackQuery):
    students = await db.get_all_students()
    bdays = []
    for uid, s in students.items():
        bday = s.get("birthday")
        if bday:
            bdays.append((bday, s["name"]))

    bdays.sort(key=lambda x: (int(x[0].split(".")[1]), int(x[0].split(".")[0])))
    if not bdays:
        text = "🎂 Дни рождения не указаны."
    else:
        text = "📅 <b>Все дни рождения:</b>\n\n"
        for bday, name in bdays:
            text += f"🎂 {bday} — <b>{name}</b>\n"

    if len(text) > 4000:
        text = text[:4000] + "\n... (обрезано)"

    await call.message.edit_text(text, reply_markup=kb_back("birthdays_menu"), parse_mode="HTML")
    await call.answer()

@router.callback_query(F.data == "birthdays_set_mine")
async def birthdays_set_mine_callback(call: CallbackQuery, state: FSMContext):
    await call.message.edit_text(
        "🎂 Введите ваш день рождения в формате ДД.ММ (например, 15.05):",
        reply_markup=kb_back("birthdays_menu"),
    )
    await state.set_state(StudentStates.adding_birthday)
    await call.answer()

@router.message(StudentStates.adding_birthday)
async def process_birthday(message: Message, state: FSMContext):
    bday = message.text.strip()
    import re
    if not re.match(r"^\d{2}\.\d{2}$", bday):
        await message.answer("❌ Неверный формат! Используйте ДД.ММ (например, 15.05)")
        return

    await db.update_user_profile(message.from_user.id, {"birthday": bday})
    await message.answer(f"✅ День рождения <b>{bday}</b> сохранён!", reply_markup=kb_main(), parse_mode="HTML")
    await state.clear()

# ── Rating Menu ─────────────────────────────────────────────────────
@router.callback_query(F.data == "rating_menu")
async def rating_menu_callback(call: CallbackQuery):
    await call.message.edit_text("🏆 <b>Рейтинги</b>", reply_markup=kb_rating_menu(), parse_mode="HTML")
    await call.answer()

@router.callback_query(F.data == "rating_xp")
async def rating_xp_callback(call: CallbackQuery):
    students = await db.get_all_students()
    student_objs = [Student.from_dict(uid, d) for uid, d in students.items()]
    text = fmt_leaderboard(student_objs, top_n=10, key="xp")
    await call.message.edit_text(text, reply_markup=kb_back("rating_menu"), parse_mode="HTML")
    await call.answer()

@router.callback_query(F.data == "rating_duty")
async def rating_duty_callback(call: CallbackQuery):
    students = await db.get_all_students()
    student_objs = [Student.from_dict(uid, d) for uid, d in students.items()]
    text = fmt_leaderboard(student_objs, top_n=10, key="duty")
    await call.message.edit_text(text, reply_markup=kb_back("rating_menu"), parse_mode="HTML")
    await call.answer()

@router.callback_query(F.data == "rating_quiz")
async def rating_quiz_callback(call: CallbackQuery):
    students = await db.get_all_students()
    student_objs = [Student.from_dict(uid, d) for uid, d in students.items()]
    text = fmt_leaderboard(student_objs, top_n=10, key="quiz")
    await call.message.edit_text(text, reply_markup=kb_back("rating_menu"), parse_mode="HTML")
    await call.answer()

# ── Stats Menu ──────────────────────────────────────────────────────
@router.callback_query(F.data == "stats_menu")
async def stats_menu_callback(call: CallbackQuery):
    await call.message.edit_text("📊 <b>Статистика</b>", reply_markup=kb_stats_menu(), parse_mode="HTML")
    await call.answer()

@router.callback_query(F.data == "stats_general")
async def stats_general_callback(call: CallbackQuery):
    students = await db.get_all_students()
    history = await db.get_history()
    news = await db.get_all_news()
    hw = await db.get_all_homework()

    total_students = len(students)
    total_duties = sum(s.get("totalDutyCount", 0) for s in students.values())
    total_history = len(history) if history else 0
    current_duty = [s for s in students.values() if s.get("isDuty")]

    text = fmt_stats_overview(
        total_students, total_duties, total_history,
        current_duty[0]['name'] if current_duty else "не назначен",
        len(news), len(hw),
    )
    await call.message.edit_text(text, reply_markup=kb_back("stats_menu"), parse_mode="HTML")
    await call.answer()

# ── Owner Panel ─────────────────────────────────────────────────────
@router.callback_query(F.data == "owner_panel")
async def owner_panel_callback(call: CallbackQuery):
    await call.message.edit_text("👑 <b>OWNER PANEL</b>", reply_markup=kb_owner_panel(), parse_mode="HTML")
    await call.answer()

# ── Owner: News Create ──────────────────────────────────────────────
@router.callback_query(F.data == "owner_news_create")
async def owner_news_create_callback(call: CallbackQuery, state: FSMContext):
    await call.message.edit_text("📢 Выберите категорию новости:", reply_markup=kb_news_categories())
    await state.set_state(NewsStates.choosing_category)
    await call.answer()

@router.callback_query(F.data.startswith("owner_news_cat:"), NewsStates.choosing_category)
async def owner_news_cat_callback(call: CallbackQuery, state: FSMContext):
    cat = call.data.split(":")[1]
    await state.update_data(category=cat)
    await call.message.edit_text("📢 Введите заголовок новости:", reply_markup=kb_back("owner_panel"))
    await state.set_state(NewsStates.entering_title)
    await call.answer()

@router.message(NewsStates.entering_title)
async def process_news_title(message: Message, state: FSMContext):
    title = message.text.strip()
    if not title:
        await message.answer("❌ Введите заголовок!")
        return
    await state.update_data(title=title)
    await message.answer("📢 Введите текст новости:")
    await state.set_state(NewsStates.entering_body)

@router.message(NewsStates.entering_body)
async def process_news_body(message: Message, state: FSMContext):
    body = message.text.strip()
    if not body:
        await message.answer("❌ Введите текст!")
        return

    data = await state.get_data()
    news_data = {
        "title": data["title"],
        "body": body,
        "category": data.get("category", "general"),
        "author": "Администратор",
        "createdAt": now_iso(),
        "pinned": False,
        "views": 0,
    }
    uid = await db.add_news(news_data)
    if uid:
        await message.answer("✅ Новость опубликована!", reply_markup=kb_owner_panel())
    else:
        await message.answer("❌ Ошибка при публикации!", reply_markup=kb_owner_panel())
    await state.clear()

# ── Owner: Delete News ──────────────────────────────────────────────
@router.callback_query(F.data.startswith("owner_news_delete:"))
async def owner_news_delete_callback(call: CallbackQuery):
    uid = call.data.split(":")[1]
    if await db.delete_news(uid):
        await call.answer("Новость удалена!", show_alert=True)
        await news_list_callback(call)
    else:
        await call.answer("Ошибка при удалении!", show_alert=True)

# ── Owner: Pin News ─────────────────────────────────────────────────
@router.callback_query(F.data.startswith("owner_news_pin:"))
async def owner_news_pin_callback(call: CallbackQuery):
    uid = call.data.split(":")[1]
    raw = await db.get_all_news()
    if uid not in raw:
        await call.answer("Новость не найдена!", show_alert=True)
        return

    current = raw[uid].get("pinned", False)
    await db.update_news(uid, {"pinned": not current})
    await call.answer(f"{'Закреплена' if not current else 'Откреплена'}!", show_alert=True)
    await news_view_callback(call)

# ── Owner: Schedule Edit ────────────────────────────────────────────
@router.callback_query(F.data == "owner_schedule_menu")
async def owner_schedule_menu_callback(call: CallbackQuery):
    await call.message.edit_text("📚 <b>Редактор расписания</b>", reply_markup=kb_owner_schedule_menu(), parse_mode="HTML")
    await call.answer()

@router.callback_query(F.data.startswith("owner_schedule_edit:"))
async def owner_schedule_edit_callback(call: CallbackQuery, state: FSMContext):
    day_key = call.data.split(":")[1]
    await state.update_data(day_key=day_key)
    await call.message.edit_text(
        f"📚 Введите урок для <b>{DAYS_RU[DAYS_KEYS.index(day_key)]}</b>\n\n"
        f"Формат: <code>Номер. Предмет, Учитель, Каб.</code>\n"
        f"Пример: <code>1. Математика, Иванов, 301</code>\n\n"
        f"Отправляйте по одному уроку, /done когда закончите.",
        reply_markup=kb_back("owner_schedule_menu"),
        parse_mode="HTML",
    )
    await state.set_state(ScheduleStates.entering_lesson)
    await call.answer()

@router.message(ScheduleStates.entering_lesson)
async def process_lesson_entry(message: Message, state: FSMContext):
    if message.text == "/done":
        await message.answer("✅ Расписание сохранено!", reply_markup=kb_owner_panel())
        await state.clear()
        return

    data = await state.get_data()
    day_key = data["day_key"]
    lessons = data.get("lessons", {})

    try:
        parts = message.text.split(".", 1)
        num = int(parts[0].strip())
        rest = parts[1].split(",") if len(parts) > 1 else [""]
        subject = rest[0].strip() if len(rest) > 0 else ""
        teacher = rest[1].strip() if len(rest) > 1 else ""
        room = rest[2].strip() if len(rest) > 2 else ""

        lesson_data = {
            "number": num,
            "subject": subject,
            "teacher": teacher,
            "room": room,
            "note": "",
        }
        key = str(len(lessons))
        lessons[key] = lesson_data
        await state.update_data(lessons=lessons)

        await db.put(f"{FB.SCHEDULE}/{day_key}", {"lessons": lessons})
        await message.answer(f"✅ Урок {num}. <b>{subject}</b> добавлен! Продолжайте или /done", parse_mode="HTML")
    except Exception as e:
        await message.answer(f"❌ Ошибка формата! Используйте: 1. Математика, Иванов, 301\n{e}")

# ── Owner: Clear Day Schedule ───────────────────────────────────────
@router.callback_query(F.data.startswith("owner_schedule_clear:"))
async def owner_schedule_clear_callback(call: CallbackQuery):
    day_key = call.data.split(":")[1]
    if await db.delete_day_schedule(day_key):
        await call.answer("Расписание очищено!", show_alert=True)
    else:
        await call.answer("Ошибка!", show_alert=True)
    await owner_schedule_menu_callback(call)

# ── Owner: Moderators ───────────────────────────────────────────────
@router.callback_query(F.data == "owner_moderators")
async def owner_moderators_callback(call: CallbackQuery):
    mods = await db.get_moderators()
    await call.message.edit_text(
        f"🛡️ <b>Модераторы:</b> {len(mods)}",
        reply_markup=kb_owner_moderators(mods),
        parse_mode="HTML",
    )
    await call.answer()

@router.callback_query(F.data == "owner_mod_add")
async def owner_mod_add_callback(call: CallbackQuery, state: FSMContext):
    await call.message.edit_text("🛡️ Введите Telegram ID модератора:", reply_markup=kb_back("owner_moderators"))
    await state.set_state(DutyStates.manual_choosing)  # reuse
    await call.answer()

@router.message(DutyStates.manual_choosing)
async def process_mod_add(message: Message, state: FSMContext):
    try:
        uid = int(message.text.strip())
        await db.add_moderator(uid)
        await message.answer(f"✅ Модератор {uid} добавлен!", reply_markup=kb_owner_panel())
    except ValueError:
        await message.answer("❌ Введите числовой Telegram ID!")
    await state.clear()

@router.callback_query(F.data.startswith("owner_mod_remove:"))
async def owner_mod_remove_callback(call: CallbackQuery):
    uid = int(call.data.split(":")[1])
    if await db.remove_moderator(uid):
        await call.answer(f"Модератор {uid} удалён!", show_alert=True)
    else:
        await call.answer("Ошибка!", show_alert=True)
    await owner_moderators_callback(call)

# ── Owner: Broadcast ────────────────────────────────────────────────
@router.callback_query(F.data == "owner_broadcast")
async def owner_broadcast_callback(call: CallbackQuery, state: FSMContext):
    await call.message.edit_text("📨 Введите сообщение для рассылки:", reply_markup=kb_back("owner_panel"))
    await state.set_state(BroadcastStates.entering_message)
    await call.answer()

@router.message(BroadcastStates.entering_message)
async def process_broadcast_message(message: Message, state: FSMContext):
    text = message.text.strip()
    if not text:
        await message.answer("❌ Введите текст!")
        return

    await state.update_data(broadcast_text=text)
    await message.answer(
        f"📨 <b>Подтвердите рассылку:</b>\n\n{text[:200]}",
        reply_markup=kb_confirm("broadcast_confirm", "owner_panel"),
        parse_mode="HTML",
    )
    await state.set_state(BroadcastStates.confirm_send)

@router.callback_query(F.data == "broadcast_confirm", BroadcastStates.confirm_send)
async def broadcast_confirm_callback(call: CallbackQuery, state: FSMContext, bot: Bot):
    data = await state.get_data()
    text = data["broadcast_text"]
    await state.clear()

    # This is a simplified broadcast — in production, queue it
    await call.message.edit_text("📨 Рассылка выполняется...", reply_markup=kb_owner_panel())
    await call.answer("Рассылка запущена!", show_alert=True)
    # Actual broadcast would require storing all user IDs

# ── Owner: Quiz Add ─────────────────────────────────────────────────
@router.callback_query(F.data == "owner_quiz_add")
async def owner_quiz_add_callback(call: CallbackQuery, state: FSMContext):
    await call.message.edit_text("🧠 Введите вопрос викторины:", reply_markup=kb_back("owner_panel"))
    await state.set_state(QuizBuilderStates.entering_question)
    await call.answer()

@router.message(QuizBuilderStates.entering_question)
async def process_quiz_question(message: Message, state: FSMContext):
    question = message.text.strip()
    if not question:
        await message.answer("❌ Введите вопрос!")
        return
    await state.update_data(question=question)
    await message.answer("📝 Введите варианты ответов, каждый с новой строки (до 4):")
    await state.set_state(QuizBuilderStates.entering_options)

@router.message(QuizBuilderStates.entering_options)
async def process_quiz_options(message: Message, state: FSMContext):
    options = [opt.strip() for opt in message.text.strip().split("\n") if opt.strip()]
    if len(options) < 2:
        await message.answer("❌ Минимум 2 варианта!")
        return

    await state.update_data(options=options)
    opts_text = "\n".join(f"{i+1}. {opt}" for i, opt in enumerate(options))
    await message.answer(f"📝 Варианты:\n{opts_text}\n\nУкажите номер правильного ответа:")
    await state.set_state(QuizBuilderStates.entering_correct)

@router.message(QuizBuilderStates.entering_correct)
async def process_quiz_correct(message: Message, state: FSMContext):
    try:
        correct = int(message.text.strip()) - 1
        data = await state.get_data()
        options = data["options"]
        if correct < 0 or correct >= len(options):
            raise ValueError

        quiz_data = {
            "question": data["question"],
            "options": options,
            "correctIndex": correct,
            "explanation": "",
            "category": "general",
        }
        uid = await db.add_quiz(quiz_data)
        if uid:
            await message.answer("✅ Вопрос добавлен!", reply_markup=kb_owner_panel())
        else:
            await message.answer("❌ Ошибка!", reply_markup=kb_owner_panel())
        await state.clear()
    except ValueError:
        _data = await state.get_data()
        await message.answer(f"❌ Введите номер от 1 до {len(_data.get('options', []))}!")

# ── Owner: Class Settings ───────────────────────────────────────────
@router.callback_query(F.data == "owner_class_settings")
async def owner_class_settings_callback(call: CallbackQuery):
    info = await db.get_class_info()
    text = (
        f"⚙️ <b>Настройки класса:</b>\n\n"
        f"🏫 Школа: <b>{CLASS_SCHOOL}</b>\n"
        f"🔷 Класс: <b>{CLASS_NAME}</b>\n"
        f"📅 Год: <b>{CLASS_YEAR}</b>\n"
        f"👩‍🏫 Учитель: <b>{info.get('teacher', '—')}</b>\n"
        f"✨ Девиз: <i>{info.get('motto', '—')}</i>\n"
        f"🚪 Кабинет: <b>{info.get('room', '—')}</b>"
    )
    await call.message.edit_text(text, reply_markup=kb_back("owner_panel"), parse_mode="HTML")
    await call.answer()

# ── Owner: Anonymous Moderation ─────────────────────────────────────
@router.callback_query(F.data == "owner_anon_moderate")
async def owner_anon_moderate_callback(call: CallbackQuery):
    messages = await db.get_anon_messages()
    if not messages:
        await call.message.edit_text("Нет сообщений для модерации.", reply_markup=kb_back("anon_menu"))
        await call.answer()
        return

    text = "🗑️ <b>Модерация анонимок:</b>\n\n"
    rows = []
    for uid, msg in list(messages.items())[:10]:
        text += f"💬 {msg.get('text', '?')[:50]}...\n"
        rows.append([_btn(f"❌ Удалить", f"owner_anon_del:{uid}")])

    keyboard = InlineKeyboardMarkup(inline_keyboard=rows + [[_btn("🔙 Анонимки", "anon_menu")]])
    await call.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await call.answer()

@router.callback_query(F.data.startswith("owner_anon_del:"))
async def owner_anon_del_callback(call: CallbackQuery):
    uid = call.data.split(":")[1]
    if await db.delete_anon_message(uid):
        await call.answer("Сообщение удалено!", show_alert=True)
    else:
        await call.answer("Ошибка!", show_alert=True)
    await owner_anon_moderate_callback(call)

# ── Help Callback ────────────────────────────────────────────────────
@router.callback_query(F.data == "help")
async def help_callback(call: CallbackQuery):
    await call.answer()
    await help_command(call.message)

# ── Cancel ───────────────────────────────────────────────────────────
@router.message(Command("cancel"))
async def cancel_command(message: Message, state: FSMContext):
    current_state = await state.get_state()
    if current_state:
        await state.clear()
        await message.answer("❌ Действие отменено.", reply_markup=kb_main())
    else:
        await message.answer("Нет активных действий для отмены.", reply_markup=kb_main())

# ── Fallback ─────────────────────────────────────────────────────────
@router.message()
async def fallback(message: Message):
    await message.answer(
        "Я не понимаю текстовые команды. Используйте /start или кнопки меню.",
        reply_markup=kb_main(),
    )

# ══════════════════════════════════════════════════════════════════════
# 9. MAIN / ENTRY POINT
# ══════════════════════════════════════════════════════════════════════

async def main():
    # Init Firebase
    await db.init()

    # Bot & Dispatcher
    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher(storage=MemoryStorage())

    # Middlewares
    dp.update.middleware(LoggingMiddleware())
    dp.update.middleware(AntiSpamMiddleware())
    dp.update.middleware(RoleMiddleware(lambda: db.get_moderators()))

    # Router
    dp.include_router(router)

    logger.info(
        "🚀 Бот PDP School (%s, %s) запущен",
        CLASS_SCHOOL, CLASS_YEAR,
    )

    try:
        await dp.start_polling(bot)
    finally:
        await db.close()
        await bot.session.close()

if __name__ == "__main__":
    asyncio.run(main())