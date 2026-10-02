"""Работа с базой SQLite: записи клиентов."""
from datetime import datetime

import aiosqlite

from config import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS bookings (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL,
    username    TEXT,
    name        TEXT NOT NULL,
    phone       TEXT NOT NULL,
    service     TEXT NOT NULL,
    start_at    TEXT NOT NULL,          -- ISO: 2026-10-05T14:00
    end_at      TEXT NOT NULL,
    status      TEXT NOT NULL DEFAULT 'active',  -- active / cancelled
    reminded    INTEGER NOT NULL DEFAULT 0,
    created_at  TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_bookings_start ON bookings(start_at);
"""


async def init_db() -> None:
    async with aiosqlite.connect(config.db_path) as db:
        await db.executescript(SCHEMA)
        await db.commit()


async def busy_intervals(day: str) -> list[tuple[datetime, datetime]]:
    """Занятые интервалы на дату (YYYY-MM-DD)."""
    async with aiosqlite.connect(config.db_path) as db:
        cur = await db.execute(
            "SELECT start_at, end_at FROM bookings "
            "WHERE status='active' AND start_at LIKE ?",
            (f"{day}%",),
        )
        rows = await cur.fetchall()
    return [(datetime.fromisoformat(s), datetime.fromisoformat(e)) for s, e in rows]


async def create_booking(user_id: int, username: str | None, name: str, phone: str,
                         service: str, start: datetime, end: datetime) -> int | None:
    """Создаёт запись. Возвращает None, если слот уже заняли (защита от гонки)."""
    async with aiosqlite.connect(config.db_path) as db:
        await db.execute("BEGIN IMMEDIATE")
        cur = await db.execute(
            "SELECT 1 FROM bookings WHERE status='active' "
            "AND start_at < ? AND end_at > ?",
            (end.isoformat(timespec="minutes"), start.isoformat(timespec="minutes")),
        )
        if await cur.fetchone():
            await db.rollback()
            return None
        cur = await db.execute(
            "INSERT INTO bookings (user_id, username, name, phone, service, start_at, end_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (user_id, username, name, phone, service,
             start.isoformat(timespec="minutes"), end.isoformat(timespec="minutes")),
        )
        await db.commit()
        return cur.lastrowid


async def user_bookings(user_id: int) -> list[aiosqlite.Row]:
    now = datetime.now().isoformat(timespec="minutes")
    async with aiosqlite.connect(config.db_path) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT * FROM bookings WHERE user_id=? AND status='active' AND start_at >= ? "
            "ORDER BY start_at",
            (user_id, now),
        )
        return await cur.fetchall()


async def get_booking(booking_id: int) -> aiosqlite.Row | None:
    async with aiosqlite.connect(config.db_path) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT * FROM bookings WHERE id=?", (booking_id,))
        return await cur.fetchone()


async def cancel_booking(booking_id: int, user_id: int | None = None) -> bool:
    """Отменяет запись. Если передан user_id — только свою."""
    query = "UPDATE bookings SET status='cancelled' WHERE id=? AND status='active'"
    params: tuple = (booking_id,)
    if user_id is not None:
        query += " AND user_id=?"
        params += (user_id,)
    async with aiosqlite.connect(config.db_path) as db:
        cur = await db.execute(query, params)
        await db.commit()
        return cur.rowcount > 0


async def due_reminders(until: str) -> list[aiosqlite.Row]:
    """Активные записи, начинающиеся до `until`, по которым ещё не было напоминания."""
    now = datetime.now().isoformat(timespec="minutes")
    async with aiosqlite.connect(config.db_path) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT * FROM bookings WHERE status='active' AND reminded=0 "
            "AND start_at > ? AND start_at <= ?",
            (now, until),
        )
        return await cur.fetchall()


async def mark_reminded(booking_id: int) -> None:
    async with aiosqlite.connect(config.db_path) as db:
        await db.execute("UPDATE bookings SET reminded=1 WHERE id=?", (booking_id,))
        await db.commit()


async def bookings_between(start: str, end: str) -> list[aiosqlite.Row]:
    async with aiosqlite.connect(config.db_path) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT * FROM bookings WHERE status='active' AND start_at >= ? AND start_at < ? "
            "ORDER BY start_at",
            (start, end),
        )
        return await cur.fetchall()
