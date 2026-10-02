"""Клавиатуры бота."""
from datetime import date, datetime

from aiogram.types import (InlineKeyboardMarkup, KeyboardButton,
                           ReplyKeyboardMarkup, ReplyKeyboardRemove)
from aiogram.utils.keyboard import InlineKeyboardBuilder

from config import config
from slots import fmt_day

BTN_BOOK = "📅 Записаться"
BTN_MY = "🗂 Мои записи"
BTN_INFO = "ℹ️ О нас"

main_menu = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text=BTN_BOOK)],
              [KeyboardButton(text=BTN_MY), KeyboardButton(text=BTN_INFO)]],
    resize_keyboard=True,
)

share_phone = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="📱 Отправить номер", request_contact=True)]],
    resize_keyboard=True, one_time_keyboard=True,
)

remove = ReplyKeyboardRemove()


def services_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for s in config.services:
        kb.button(text=f"{s.title} — {s.price} ₽", callback_data=f"svc:{s.code}")
    kb.adjust(1)
    return kb.as_markup()


def days_kb(days: list[date]) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for d in days:
        kb.button(text=fmt_day(d), callback_data=f"day:{d.isoformat()}")
    kb.button(text="← Назад", callback_data="back:services")
    kb.adjust(3)
    return kb.as_markup()


def times_kb(slots: list[datetime]) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for t in slots:
        kb.button(text=f"{t:%H:%M}", callback_data=f"time:{t:%H%M}")
    kb.button(text="← Другой день", callback_data="back:days")
    kb.adjust(4)
    return kb.as_markup()


def confirm_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Подтвердить", callback_data="confirm:yes")
    kb.button(text="✖️ Отмена", callback_data="confirm:no")
    kb.adjust(2)
    return kb.as_markup()


def cancel_booking_kb(booking_id: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="Отменить запись", callback_data=f"cancel:{booking_id}")
    return kb.as_markup()
