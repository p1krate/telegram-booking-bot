"""Расчёт свободных дат и времени."""
from datetime import date, datetime, timedelta

from config import config
import db

WEEKDAYS = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]


def available_days(today: date | None = None) -> list[date]:
    today = today or date.today()
    days = []
    for i in range(config.days_ahead + 1):
        d = today + timedelta(days=i)
        if d.weekday() not in config.days_off:
            days.append(d)
    return days


def free_slots(day: date, duration_min: int,
               busy: list[tuple[datetime, datetime]],
               now: datetime | None = None) -> list[datetime]:
    """Все начала слотов, куда помещается услуга и которые не пересекаются с занятыми."""
    now = now or datetime.now()
    start = datetime.combine(day, datetime.min.time()).replace(hour=config.work_start)
    day_end = start.replace(hour=config.work_end)
    step = timedelta(minutes=config.slot_step_min)
    length = timedelta(minutes=duration_min)

    result = []
    t = start
    while t + length <= day_end:
        if t > now and all(not (t < e and t + length > s) for s, e in busy):
            result.append(t)
        t += step
    return result


async def free_slots_for(day: date, duration_min: int) -> list[datetime]:
    busy = await db.busy_intervals(day.isoformat())
    return free_slots(day, duration_min, busy)


def fmt_day(d: date) -> str:
    return f"{WEEKDAYS[d.weekday()]} {d:%d.%m}"


def fmt_dt(dt: datetime) -> str:
    return f"{WEEKDAYS[dt.weekday()]} {dt:%d.%m} в {dt:%H:%M}"
