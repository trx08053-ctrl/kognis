"""Бизнес-правила: без ввода-вывода. Детектор — детерминированный, по фразам (RU/EN), без ИИ."""

import re
from dataclasses import dataclass

# Данные-конфигурация детектора. Расширять здесь; каждая новая фраза — с примером в tests/safety.
# Отрицательные lookbehind/lookahead отсекают «не хочу умереть», «умираю от смеха» и подобное.
CRISIS_PATTERNS: tuple[str, ...] = (
    # русский
    r"(?<!не )хочу умереть",
    r"хочу сдохнуть",
    r"хочется (?:умереть|сдохнуть)",
    r"умереть хочу",
    r"не хочу просыпаться",
    r"нет смысла в жизни",
    r"перерезать вены",
    r"выброситься из окна",
    r"не хочу (?:больше )?жить(?! (?:в|во|здесь|там|с|со|у|на|рядом|так|как)\b)",
    r"жить не хочу",
    r"(?:нет|не вижу) смысла (?:больше )?жить",
    r"покончить с собой",
    r"покончу с собой",
    r"убить себя",
    r"убью себя",
    r"свести счеты с жизнью",
    r"лучше бы (?:я )?(?:умер|умерла|не родился|не родилась)",
    r"суицид\w*",
    r"самоубийств\w*",
    r"повеситься",
    r"вскрыть вены",
    r"наглотаться таблеток",
    # английский
    r"kill myself",
    r"killing myself(?! laughing)",
    r"(?<!not )(?<!n't )want to die(?! of\b)",
    r"end my (?:own )?life",
    r"take my own life",
    r"suicid\w*",
    r"better off dead",
    r"(?:do not|don't|dont) want to (?:live|be alive)(?! (?:in|here|there|with|like|this way)\b)",
    r"no reason to live",
    r"hang myself",
    r"wanna die",
    r"wish i (?:was|were) dead",
    r"end it all",
)

_COMPILED = tuple(re.compile(rf"\b(?:{p})\b") for p in CRISIS_PATTERNS)


def normalize(text: str) -> str:
    """Нижний регистр, ё→е, единые апострофы и пробелы, без знаков препинания."""
    lowered = text.lower().replace("ё", "е").replace("’", "'").replace("`", "'")
    # знак препинания — граница клаузы: «не хочу жить, с меня хватит» не то же, что «жить с мамой»
    marked = re.sub(r"[^\w\s']", " | ", lowered)
    return re.sub(r"\s+", " ", marked).strip()


@dataclass(frozen=True)
class Assessment:
    crisis: bool

    @property
    def allows_rewards(self) -> bool:
        """Запись с кризисным сигналом не даёт XP и не порождает квестов (D5)."""
        return not self.crisis


def assess(text: str) -> Assessment:
    normalized = normalize(text)
    return Assessment(crisis=any(p.search(normalized) for p in _COMPILED))


@dataclass(frozen=True)
class Contact:
    name: str
    phone: str
    note: str = ""


DEFAULT_CONTACTS: tuple[Contact, ...] = (
    Contact("Единый номер экстренных служб", "112", "бесплатно, круглосуточно"),
)

SUPPORT_MESSAGE = (
    "Похоже, вам сейчас очень тяжело. Вы не одни: если есть угроза вашей жизни, "
    "позвоните по номеру помощи или обратитесь к близкому человеку. "
    "Это приложение — не медицинская помощь."
)

DISCLAIMER = "Kognis — не медицинская помощь и не заменяет специалиста."
