"""Квест дня (мотивация 2.0, 4/4): выбор 1 из 3 лёгких заданий, без штрафа за невыполнение.

Без ввода-вывода. Задания — данные (коды; тексты отдаёт интерфейс по словарю `daily.<code>`).
Выбор трёх вариантов детерминирован парой (владелец, дата): без случайности и состояния —
у одного пользователя в один день варианты одни и те же, завтра — другие.
"""

from dataclasses import dataclass
from datetime import date

from ._quests import QUESTS

DAILY_QUEST_XP = 10  # выполнение задания дня (один раз в день)
KIND_DAILY_QUEST = "daily_quest"  # события XP и серии не продлевает (как квесты и квизы)

# пул лёгких заданий: короткое действие на день, без «должен» и давления (ADR 0006)
DAILY_POOL: tuple[str, ...] = (
    "water",  # выпить стакан воды
    "stretch",  # минута потянуться
    "breathe",  # три медленных вдоха-выдоха
    "step_out",  # выйти на минуту на улицу
    "note_good",  # отметить одну хорошую мелочь
    "text_someone",  # написать близкому человеку
    "tiny_tidy",  # разобрать одну маленькую вещь
    "music",  # включить любимую музыку
    "window",  # выглянуть в окно и разглядеть детали
)
DAILY_OPTIONS = 3


@dataclass(frozen=True)
class DailyState:
    options: tuple[str, ...]  # три кода на сегодня
    picked: str | None  # выбранный код (выбор один раз в день)
    done: bool  # выполнено ли выбранное задание


def _shift(seed: int) -> int:
    """Линейный конгруэнтный сдвиг: детерминирован и одинаков у всех запусков."""
    return (seed * 110_351_5245 + 12_345) % 2**31


def options_for(owner_id: int, day: date) -> tuple[str, ...]:
    """Три задания дня: детерминированный сдвиг по (владелец, дата), каждый день новый."""
    seed = owner_id * 1_000_007 + day.toordinal()
    pool = list(DAILY_POOL)
    chosen: list[str] = []
    for _ in range(DAILY_OPTIONS):
        seed = _shift(seed)
        idx = seed % len(pool)
        chosen.append(pool.pop(idx))
    return tuple(chosen)


def weekly_recommendation(owner_id: int, week: str, open_codes: frozenset[str]) -> str | None:
    """Квест недели от наставника: детерминированный по (владелец, ISO-неделя), не из уже
    принятых незавершённых; в библиотеке нет свободных — None (давления не будет)."""
    candidates = tuple(q.code for q in QUESTS if not q.challenge and q.code not in open_codes)
    if not candidates:
        return None
    year, number = week.split("-W")  # «2026-W37»
    seed = owner_id * 1_000_007 + int(year) * 100 + int(number)
    return candidates[_shift(seed) % len(candidates)]
