#!/usr/bin/env python3
"""Засев «года работы пользователя» на окружение — для замеров `just perf` (kognis-3mh).

Идёт через публичный API (регистрация → записи → итоги дня), поэтому годится для любого окружения:
    python3 scripts/seed_perf.py --url http://127.0.0.1:18000
    just perf /api/entries --cookie "$(python3 scripts/seed_perf.py --url … --print-cookie)"

По умолчанию 365 дней × 3 записи = 1095 записей и 365 итогов дня — объём из ARCHITECTURE.md (НФТ).
Пользователь замера: perf@example.com; повторный запуск входит под ним и дозасевает данные.
Пароль — из `--password` или PERF_PASSWORD (не пишите настоящие пароли в историю команд).
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
import urllib.error
import urllib.request
from http import HTTPStatus
from http.cookiejar import CookieJar

COOKIE = "kognis_session"
TAGS = ["работа", "семья", "сон", "спорт", "учёба", "друзья"]
EMOTIONS = ["тревога", "радость", "усталость", "спокойствие", "злость"]


class Client:
    def __init__(self, base: str) -> None:
        if not base.startswith(("http://", "https://")):
            sys.exit("--url: нужен http:// или https:// адрес окружения")
        self.base = base.rstrip("/")
        self.jar = CookieJar()
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.jar))

    def call(self, method: str, path: str, body: dict[str, object] | None = None) -> int:
        data = json.dumps(body).encode() if body is not None else None
        request = urllib.request.Request(  # noqa: S310  justified: kognis-3mh схему http/https проверяет Client.__init__
            self.base + path,
            data=data,
            method=method,
            headers={"Content-Type": "application/json"},
        )
        try:
            with self.opener.open(request, timeout=30) as response:
                return int(response.status)
        except urllib.error.HTTPError as err:
            return int(err.code)

    def cookie(self) -> str:
        return next((f"{c.name}={c.value}" for c in self.jar if c.name == COOKIE), "")


def sign_in(client: Client, email: str, password: str) -> None:
    credentials: dict[str, object] = {"email": email, "password": password}
    if client.call("POST", "/api/auth/register", credentials) == HTTPStatus.CREATED:
        return
    if client.call("POST", "/api/auth/login", credentials) != HTTPStatus.OK:
        sys.exit("не удалось ни зарегистрироваться, ни войти (пароль верный?)")


def seed(client: Client, days: int, per_day: int, today: dt.date) -> tuple[int, int]:
    entries = reviews = 0
    for offset in range(days):
        day = today - dt.timedelta(days=offset)
        for n in range(per_day):
            i = offset * per_day + n
            entry: dict[str, object] = {
                "text": f"Запись {i}: обычный день, немного мыслей о работе и отдыхе.",
                "date": str(day),
                "tags": [TAGS[i % len(TAGS)], TAGS[(i + 2) % len(TAGS)]],
                "emotions": [EMOTIONS[i % len(EMOTIONS)]],
            }
            if client.call("POST", "/api/entries", entry) != HTTPStatus.CREATED:
                sys.exit(f"запись {i} не создана")
            entries += 1
        review: dict[str, object] = {
            "wellbeing": 1 + offset % 10,
            "mood": 1 + (offset * 3) % 10,
            "reflection": f"Итог дня {day}: всё в порядке.",
        }
        if client.call("PUT", f"/api/day-reviews/{day}", review) != HTTPStatus.OK:
            sys.exit(f"итог за {day} не сохранён")
        reviews += 1
    return entries, reviews


def main() -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").split("\n")[0])
    parser.add_argument("--url", default="http://127.0.0.1:18000", help="база окружения")
    parser.add_argument("--email", default="perf@example.com")
    parser.add_argument("--password", default=os.environ.get("PERF_PASSWORD", ""))
    parser.add_argument("--days", type=int, default=365)
    parser.add_argument("--per-day", type=int, default=3)
    parser.add_argument("--print-cookie", action="store_true", help="только войти и вывести cookie")
    args = parser.parse_args()
    if not args.password:
        sys.exit("нужен пароль: --password или PERF_PASSWORD (не короче 8 символов)")
    client = Client(args.url)
    sign_in(client, args.email, args.password)
    if not args.print_cookie:
        entries, reviews = seed(client, args.days, args.per_day, dt.datetime.now(dt.UTC).date())
        print(f"засеяно: {entries} записей, {reviews} итогов дня ({args.email})", file=sys.stderr)
    print(client.cookie())
    return 0


if __name__ == "__main__":
    sys.exit(main())
