"""Настройки бота. Всё, что меняется под клиента, лежит здесь и в .env."""
import os
from dataclasses import dataclass, field

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Service:
    code: str
    title: str
    duration_min: int
    price: int


@dataclass(frozen=True)
class Config:
    bot_token: str = os.getenv("BOT_TOKEN", "")
    # ID администраторов через запятую: 12345,67890
    admin_ids: tuple[int, ...] = tuple(
        int(x) for x in os.getenv("ADMIN_IDS", "").replace(" ", "").split(",") if x
    )
    db_path: str = os.getenv("DB_PATH", "bookings.db")
    business_name: str = os.getenv("BUSINESS_NAME", "Студия «Аврора»")

    work_start: int = 10          # начало рабочего дня, час
    work_end: int = 20            # конец рабочего дня, час
    slot_step_min: int = 60       # шаг сетки записи, минут
    days_ahead: int = 7           # на сколько дней вперёд можно записаться
    days_off: tuple[int, ...] = (6,)  # выходные: 0=пн ... 6=вс

    services: tuple[Service, ...] = field(default_factory=lambda: (
        Service("haircut", "Стрижка", 60, 1500),
        Service("coloring", "Окрашивание", 120, 4000),
        Service("manicure", "Маникюр", 60, 1800),
        Service("brows", "Брови", 60, 900),
    ))

    def service(self, code: str) -> Service | None:
        return next((s for s in self.services if s.code == code), None)


config = Config()
