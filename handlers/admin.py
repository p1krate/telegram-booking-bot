"""Команды администратора: расписание и отмена записей."""
from datetime import date, datetime, timedelta

from aiogram import Bot, F, Router
from aiogram.filters import Command, CommandObject
from aiogram.types import Message

import db
from config import config
from slots import fmt_dt

router = Router(name="admin")
router.message.filter(F.from_user.id.in_(set(config.admin_ids)))


def render(rows, title: str) -> str:
    if not rows:
        return f"<b>{title}</b>\nЗаписей нет."
    lines = [f"<b>{title}</b>"]
    for r in rows:
        svc = config.service(r["service"])
        lines.append(
            f"#{r['id']} · {fmt_dt(datetime.fromisoformat(r['start_at']))}\n"
            f"   {svc.title if svc else r['service']} — {r['name']}, {r['phone']}"
        )
    return "\n".join(lines)


@router.message(Command("admin"))
async def help_admin(message: Message) -> None:
    await message.answer(
        "<b>Админ-панель</b>\n"
        "/today — записи на сегодня\n"
        "/tomorrow — на завтра\n"
        "/week — на 7 дней\n"
        "/cancel_booking N — отменить запись #N (клиент получит уведомление)"
    )


@router.message(Command("today"))
async def today(message: Message) -> None:
    d = date.today()
    rows = await db.bookings_between(d.isoformat(), (d + timedelta(days=1)).isoformat())
    await message.answer(render(rows, f"Сегодня, {d:%d.%m}"))


@router.message(Command("tomorrow"))
async def tomorrow(message: Message) -> None:
    d = date.today() + timedelta(days=1)
    rows = await db.bookings_between(d.isoformat(), (d + timedelta(days=1)).isoformat())
    await message.answer(render(rows, f"Завтра, {d:%d.%m}"))


@router.message(Command("week"))
async def week(message: Message) -> None:
    d = date.today()
    rows = await db.bookings_between(d.isoformat(), (d + timedelta(days=8)).isoformat())
    await message.answer(render(rows, "Ближайшие 7 дней"))


@router.message(Command("cancel_booking"))
async def admin_cancel(message: Message, command: CommandObject, bot: Bot) -> None:
    if not command.args or not command.args.strip().isdigit():
        await message.answer("Использование: /cancel_booking 15")
        return
    booking_id = int(command.args.strip())
    row = await db.get_booking(booking_id)
    if not row or not await db.cancel_booking(booking_id):
        await message.answer("Активная запись с таким номером не найдена.")
        return
    await message.answer(f"Запись #{booking_id} отменена.")
    try:
        await bot.send_message(
            row["user_id"],
            f"К сожалению, ваша запись на {fmt_dt(datetime.fromisoformat(row['start_at']))} "
            "отменена администратором. Выберите, пожалуйста, другое время.",
        )
    except Exception:
        pass
