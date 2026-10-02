"""Фоновые напоминания клиентам за 2 часа до визита."""
import asyncio
import logging
from datetime import datetime, timedelta

from aiogram import Bot

import db
from config import config
from slots import fmt_dt

REMIND_BEFORE = timedelta(hours=2)
CHECK_EVERY_SEC = 60


async def reminder_loop(bot: Bot) -> None:
    while True:
        try:
            until = (datetime.now() + REMIND_BEFORE).isoformat(timespec="minutes")
            for r in await db.due_reminders(until):
                svc = config.service(r["service"])
                try:
                    await bot.send_message(
                        r["user_id"],
                        f"⏰ Напоминаем: {svc.title if svc else 'визит'} "
                        f"{fmt_dt(datetime.fromisoformat(r['start_at']))}.\n"
                        f"Ждём вас в {config.business_name}!",
                    )
                except Exception as e:
                    logging.warning("Не удалось отправить напоминание #%s: %s", r["id"], e)
                await db.mark_reminded(r["id"])
        except Exception:
            logging.exception("Ошибка в цикле напоминаний")
        await asyncio.sleep(CHECK_EVERY_SEC)
