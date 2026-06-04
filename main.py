import asyncio
import os
import sqlite3
from datetime import date, timedelta
from pathlib import Path

from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)


BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "cat_poop_calendar.db"

dp = Dispatcher()


def init_db() -> None:
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS poop_marks (
                user_id INTEGER NOT NULL,
                mark_date TEXT NOT NULL,
                pooped INTEGER NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (user_id, mark_date)
            )
            """
        )


def save_mark(user_id: int, pooped: bool) -> None:
    today = date.today().isoformat()

    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            INSERT INTO poop_marks (user_id, mark_date, pooped)
            VALUES (?, ?, ?)
            ON CONFLICT(user_id, mark_date)
            DO UPDATE SET
                pooped = excluded.pooped,
                updated_at = CURRENT_TIMESTAMP
            """,
            (user_id, today, int(pooped)),
        )


def get_stats(user_id: int, days: int) -> dict:
    end_date = date.today()
    start_date = end_date - timedelta(days=days - 1)

    with sqlite3.connect(DB_PATH) as conn:
        rows = conn.execute(
            """
            SELECT mark_date, pooped
            FROM poop_marks
            WHERE user_id = ?
              AND mark_date BETWEEN ? AND ?
            ORDER BY mark_date
            """,
            (user_id, start_date.isoformat(), end_date.isoformat()),
        ).fetchall()

    marks_by_date = {row[0]: bool(row[1]) for row in rows}

    pooped_count = sum(1 for value in marks_by_date.values() if value)
    not_pooped_count = sum(1 for value in marks_by_date.values() if not value)
    missed_count = days - len(marks_by_date)

    return {
        "days": days,
        "start_date": start_date,
        "end_date": end_date,
        "pooped_count": pooped_count,
        "not_pooped_count": not_pooped_count,
        "missed_count": missed_count,
        "calendar": build_calendar_text(start_date, days, marks_by_date),
    }


def build_calendar_text(
    start_date: date,
    days: int,
    marks_by_date: dict[str, bool],
) -> str:
    lines = []

    for day_offset in range(days):
        current_date = start_date + timedelta(days=day_offset)
        date_key = current_date.isoformat()

        if date_key not in marks_by_date:
            icon = "⚪"
        elif marks_by_date[date_key]:
            icon = "✅"
        else:
            icon = "❌"

        lines.append(f"{icon} {current_date.strftime('%d.%m')}")

    return "\n".join(lines)


def main_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Покакал сегодня",
                    callback_data="mark:yes",
                )
            ],
            [
                InlineKeyboardButton(
                    text="❌ Не покакал сегодня",
                    callback_data="mark:no",
                )
            ],
            [
                InlineKeyboardButton(
                    text="📊 Неделя",
                    callback_data="stats:week",
                ),
                InlineKeyboardButton(
                    text="📊 Месяц",
                    callback_data="stats:month",
                ),
            ],
        ]
    )


def format_stats(stats: dict) -> str:
    return (
        f"📊 Статистика за {stats['days']} дней\n"
        f"Период: {stats['start_date'].strftime('%d.%m.%Y')} — "
        f"{stats['end_date'].strftime('%d.%m.%Y')}\n\n"
        f"✅ Покакал: {stats['pooped_count']}\n"
        f"❌ Не покакал: {stats['not_pooped_count']}\n"
        f"⚪ Нет отметки: {stats['missed_count']}\n\n"
        f"{stats['calendar']}"
    )


@dp.message(CommandStart())
async def start(message: Message) -> None:
    await message.answer(
        "🐈 Какательный календарь кота\n\n"
        "Отмечай каждый день, покакал кот или нет. "
        "Потом можно посмотреть статистику за неделю или месяц.",
        reply_markup=main_keyboard(),
    )


@dp.callback_query(F.data == "mark:yes")
async def mark_yes(callback: CallbackQuery) -> None:
    save_mark(callback.from_user.id, pooped=True)

    await callback.answer("Записал: сегодня покакал ✅")

    if callback.message:
        await callback.message.edit_text(
            "Сегодня отмечено: ✅ покакал",
            reply_markup=main_keyboard(),
        )


@dp.callback_query(F.data == "mark:no")
async def mark_no(callback: CallbackQuery) -> None:
    save_mark(callback.from_user.id, pooped=False)

    await callback.answer("Записал: сегодня не покакал ❌")

    if callback.message:
        await callback.message.edit_text(
            "Сегодня отмечено: ❌ не покакал",
            reply_markup=main_keyboard(),
        )


@dp.callback_query(F.data == "stats:week")
async def stats_week(callback: CallbackQuery) -> None:
    stats = get_stats(callback.from_user.id, days=7)

    await callback.answer()

    if callback.message:
        await callback.message.edit_text(
            format_stats(stats),
            reply_markup=main_keyboard(),
        )


@dp.callback_query(F.data == "stats:month")
async def stats_month(callback: CallbackQuery) -> None:
    stats = get_stats(callback.from_user.id, days=30)

    await callback.answer()

    if callback.message:
        await callback.message.edit_text(
            format_stats(stats),
            reply_markup=main_keyboard(),
        )


async def main() -> None:
    token = os.getenv("BOT_TOKEN")

    if not token:
        raise RuntimeError(
            "Не задан BOT_TOKEN. Выполни в терминале: "
            '$env:BOT_TOKEN="токен_бота"'
        )

    init_db()

    bot = Bot(token=token)

    print("Бот запущен. Открой Telegram и отправь ему /start")

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())