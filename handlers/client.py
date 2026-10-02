"""Сценарий клиента: выбор услуги → даты → времени → контакты → подтверждение."""
import re
from datetime import date, datetime, timedelta

from aiogram import Bot, F, Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

import db
import keyboards as kb
from config import config
from slots import available_days, fmt_dt, free_slots_for

router = Router(name="client")

PHONE_RE = re.compile(r"^\+?[78]?[\s\-()]*\d[\d\s\-()]{8,14}$")


class Booking(StatesGroup):
    service = State()
    day = State()
    time = State()
    name = State()
    phone = State()
    confirm = State()


# ---------- меню ----------

@router.message(CommandStart())
async def start(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(
        f"Здравствуйте! Это бот записи в {config.business_name} 👋\n\n"
        "Здесь можно за минуту выбрать услугу и удобное время.",
        reply_markup=kb.main_menu,
    )


@router.message(F.text == kb.BTN_INFO)
async def info(message: Message) -> None:
    lines = [f"<b>{config.business_name}</b>",
             f"Работаем с {config.work_start}:00 до {config.work_end}:00\n",
             "<b>Услуги и цены:</b>"]
    lines += [f"• {s.title} — {s.price} ₽ ({s.duration_min} мин)" for s in config.services]
    await message.answer("\n".join(lines))


@router.message(F.text == kb.BTN_MY)
async def my_bookings(message: Message) -> None:
    rows = await db.user_bookings(message.from_user.id)
    if not rows:
        await message.answer("У вас нет предстоящих записей.")
        return
    for r in rows:
        svc = config.service(r["service"])
        await message.answer(
            f"<b>{svc.title if svc else r['service']}</b>\n"
            f"{fmt_dt(datetime.fromisoformat(r['start_at']))}",
            reply_markup=kb.cancel_booking_kb(r["id"]),
        )


@router.callback_query(F.data.startswith("cancel:"))
async def cancel(call: CallbackQuery, bot: Bot) -> None:
    booking_id = int(call.data.split(":")[1])
    row = await db.get_booking(booking_id)
    if not await db.cancel_booking(booking_id, call.from_user.id):
        await call.answer("Запись уже отменена", show_alert=True)
        return
    await call.message.edit_text(call.message.html_text + "\n\n❌ <i>Отменено</i>")
    await call.answer("Запись отменена")
    await notify_admins(bot, f"❌ Клиент отменил запись #{booking_id}: "
                             f"{row['name']}, {fmt_dt(datetime.fromisoformat(row['start_at']))}")


# ---------- сценарий записи ----------

@router.message(F.text == kb.BTN_BOOK)
async def choose_service(message: Message, state: FSMContext) -> None:
    await state.set_state(Booking.service)
    await message.answer("Выберите услугу:", reply_markup=kb.services_kb())


@router.callback_query(F.data == "back:services")
async def back_to_services(call: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(Booking.service)
    await call.message.edit_text("Выберите услугу:", reply_markup=kb.services_kb())
    await call.answer()


@router.callback_query(Booking.service, F.data.startswith("svc:"))
async def choose_day(call: CallbackQuery, state: FSMContext) -> None:
    svc = config.service(call.data.split(":")[1])
    if not svc:
        await call.answer("Услуга не найдена", show_alert=True)
        return
    await state.update_data(service=svc.code)
    await state.set_state(Booking.day)
    await call.message.edit_text(
        f"<b>{svc.title}</b> — {svc.price} ₽\n\nВыберите день:",
        reply_markup=kb.days_kb(available_days()),
    )
    await call.answer()


@router.callback_query(F.data == "back:days")
async def back_to_days(call: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(Booking.day)
    await call.message.edit_text("Выберите день:", reply_markup=kb.days_kb(available_days()))
    await call.answer()


@router.callback_query(Booking.day, F.data.startswith("day:"))
async def choose_time(call: CallbackQuery, state: FSMContext) -> None:
    day = date.fromisoformat(call.data.split(":")[1])
    data = await state.get_data()
    svc = config.service(data["service"])
    slots = await free_slots_for(day, svc.duration_min)
    if not slots:
        await call.answer("На этот день свободного времени нет, выберите другой", show_alert=True)
        return
    await state.update_data(day=day.isoformat())
    await state.set_state(Booking.time)
    await call.message.edit_text(
        f"<b>{svc.title}</b>, {day:%d.%m}\n\nСвободное время:",
        reply_markup=kb.times_kb(slots),
    )
    await call.answer()


@router.callback_query(Booking.time, F.data.startswith("time:"))
async def ask_name(call: CallbackQuery, state: FSMContext) -> None:
    hhmm = call.data.split(":")[1]
    await state.update_data(time=f"{hhmm[:2]}:{hhmm[2:]}")
    await state.set_state(Booking.name)
    await call.message.edit_text("Как к вам обращаться? Напишите имя.")
    await call.answer()


@router.message(Booking.name, F.text)
async def ask_phone(message: Message, state: FSMContext) -> None:
    name = message.text.strip()
    if not 2 <= len(name) <= 50:
        await message.answer("Пожалуйста, введите имя (от 2 до 50 символов).")
        return
    await state.update_data(name=name)
    await state.set_state(Booking.phone)
    await message.answer("Оставьте номер телефона — кнопкой ниже или текстом.",
                         reply_markup=kb.share_phone)


@router.message(Booking.phone, F.contact | F.text)
async def ask_confirm(message: Message, state: FSMContext) -> None:
    phone = message.contact.phone_number if message.contact else message.text.strip()
    if not message.contact and not PHONE_RE.match(phone):
        await message.answer("Не похоже на номер телефона. Пример: +7 900 123-45-67")
        return
    await state.update_data(phone=phone)
    await state.set_state(Booking.confirm)
    data = await state.get_data()
    svc = config.service(data["service"])
    start = datetime.fromisoformat(f"{data['day']}T{data['time']}")
    await message.answer("Почти готово!", reply_markup=kb.remove)
    await message.answer(
        "Проверьте запись:\n\n"
        f"Услуга: <b>{svc.title}</b> ({svc.price} ₽)\n"
        f"Когда: <b>{fmt_dt(start)}</b>\n"
        f"Имя: {data['name']}\nТелефон: {phone}",
        reply_markup=kb.confirm_kb(),
    )


@router.callback_query(Booking.confirm, F.data.startswith("confirm:"))
async def finish(call: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    if call.data == "confirm:no":
        await state.clear()
        await call.message.edit_text("Запись отменена. Можно начать заново в любой момент.")
        await call.message.answer("Главное меню", reply_markup=kb.main_menu)
        await call.answer()
        return

    data = await state.get_data()
    svc = config.service(data["service"])
    start = datetime.fromisoformat(f"{data['day']}T{data['time']}")
    end = start + timedelta(minutes=svc.duration_min)

    booking_id = await db.create_booking(
        call.from_user.id, call.from_user.username, data["name"], data["phone"],
        svc.code, start, end,
    )
    await state.clear()
    if booking_id is None:
        await call.message.edit_text("Увы, это время только что заняли 😔 Выберите другое.")
        await call.message.answer("Главное меню", reply_markup=kb.main_menu)
        await call.answer()
        return

    await call.message.edit_text(
        f"✅ Вы записаны!\n\n<b>{svc.title}</b>, {fmt_dt(start)}\n"
        "Мы напомним о визите за 2 часа."
    )
    await call.message.answer("Главное меню", reply_markup=kb.main_menu)
    await call.answer()

    user = f"@{call.from_user.username}" if call.from_user.username else f"id {call.from_user.id}"
    await notify_admins(
        bot,
        f"🆕 Новая запись #{booking_id}\n"
        f"{svc.title} — {fmt_dt(start)}\n"
        f"{data['name']}, {data['phone']} ({user})",
    )


async def notify_admins(bot: Bot, text: str) -> None:
    for admin_id in config.admin_ids:
        try:
            await bot.send_message(admin_id, text)
        except Exception:
            pass  # админ мог не запускать бота — не роняем сценарий клиента
