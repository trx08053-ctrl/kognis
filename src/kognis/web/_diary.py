"""Записи дневника, в том числе «под замком» и приватные."""

import datetime as dt
from collections.abc import Callable, Generator
from contextlib import contextmanager
from http import HTTPStatus
from typing import Annotated, Any, Literal

from fastapi import APIRouter, HTTPException, Query, Response
from pydantic import BaseModel, Field
from sqlalchemy.engine import Engine

from kognis.db import transaction
from kognis.diary import (
    DEFAULT_PAGE_SIZE,
    MAX_PAGE_SIZE,
    DataKeyError,
    DiaryService,
    Entry,
    EntryDraft,
    EntryFilter,
    EntryUnreadableError,
    InvalidCursorError,
    WrongLockPasswordError,
)
from kognis.gameplay import (
    GameplayService,
)
from kognis.safety import HelpBlock, check_text
from kognis.users import (
    User,
)

from ._deps import NEXT_CURSOR_HEADER, Authed, HelpOut, Label, help_out
from ._limits import AttemptLimiter


class EntryIn(BaseModel):
    text: str = Field(default="", max_length=20_000)
    tags: list[Label] = Field(default_factory=list, max_length=20)
    emotions: list[Label] = Field(default_factory=list, max_length=20)
    date: dt.date | None = None
    protection: Literal["plain", "locked", "private"] = "plain"
    lock_password: str | None = Field(default=None, max_length=256)
    # `private`: конверт шифртекста, собранный в браузере (текст и пароль на сервер не идут)
    cipher: dict[str, Any] | None = None


class LockPassword(BaseModel):
    password: str = Field(max_length=256)


class LabelsOut(BaseModel):
    tags: list[str]
    emotions: list[str]


class EntryOut(BaseModel):
    id: int
    date: dt.date
    text: str
    tags: list[str]
    emotions: list[str]
    protection: str
    crisis: bool = False
    cipher: dict[str, Any] | None = None
    help: HelpOut | None = None


def entry_out(entry: Entry, block: HelpBlock | None = None) -> EntryOut:
    return EntryOut(
        id=entry.id,
        date=entry.entry_date,
        text=entry.text,
        tags=list(entry.tags),
        emotions=list(entry.emotions),
        protection=entry.protection,
        crisis=entry.crisis,
        cipher=entry.envelope,
        help=help_out(block),
    )


@contextmanager
def lock_errors() -> Generator[None]:
    """Ошибки записей «под замком» → понятные ответы без раскрытия текста."""
    try:
        yield
    except WrongLockPasswordError as err:
        raise HTTPException(status_code=403, detail=str(err)) from err
    except EntryUnreadableError as err:
        raise HTTPException(status_code=409, detail=str(err)) from err
    except DataKeyError as err:
        raise HTTPException(status_code=503, detail=str(err)) from err


def check_protection_fields(payload: EntryIn) -> None:
    """Поля режима защиты согласованы: `private` — только шифртекст, `locked` — с паролем замка."""
    if payload.protection == "private":
        if payload.cipher is None or payload.text or payload.lock_password:
            raise HTTPException(
                status_code=422, detail="приватная запись передаётся только шифртекстом"
            )
    elif payload.cipher is not None:
        raise HTTPException(status_code=422, detail="шифртекст только у приватной записи")
    if payload.protection == "locked" and not payload.lock_password:
        raise HTTPException(status_code=422, detail="для записи «под замком» нужен пароль замка")


def store_entry(diary: DiaryService, owner_id: int, payload: EntryIn, day: dt.date) -> Entry:
    if payload.cipher is not None:
        return diary.create_private_entry(
            owner_id, payload.cipher, payload.tags, payload.emotions, day
        )
    if payload.protection == "locked" and payload.lock_password:
        draft = EntryDraft(payload.text, payload.tags, payload.emotions, day)
        return diary.create_locked_entry(owner_id, draft, payload.lock_password)
    return diary.create_entry(owner_id, payload.text, payload.tags, payload.emotions, day)


class EntryPageQuery(BaseModel):
    """Параметры страницы записей: размер, курсор и отбор на стороне БД."""

    model_config = {"extra": "forbid"}

    limit: int = Field(default=DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE)
    cursor: str | None = Field(default=None, max_length=40)
    tag: Label | None = None
    emotion: Label | None = None
    date_from: dt.date | None = Field(default=None, alias="from")
    date_to: dt.date | None = Field(default=None, alias="to")


def add_entry_pages(router: APIRouter, db: Engine) -> None:
    """Список записей страницами и варианты фильтров — на роутер записей."""

    @router.get("")
    def list_entries(
        user: Authed, response: Response, q: Annotated[EntryPageQuery, Query()]
    ) -> list[EntryOut]:
        """Страница записей, новые первыми; следующая — по курсору из заголовка `X-Next-Cursor`."""
        where = EntryFilter(tag=q.tag, emotion=q.emotion, start=q.date_from, end=q.date_to)
        try:
            with transaction(db) as session:
                page = DiaryService(session).list_entries(
                    user.id, limit=q.limit, cursor=q.cursor, where=where
                )
        except InvalidCursorError as err:
            raise HTTPException(status_code=422, detail=str(err)) from err
        if page.next_cursor:
            response.headers[NEXT_CURSOR_HEADER] = page.next_cursor
        return [entry_out(e) for e in page.items]

    @router.get("/labels")
    def entry_labels(user: Authed) -> LabelsOut:
        """Все теги и эмоции владельца — варианты фильтров."""
        with transaction(db) as session:
            tags, emotions = DiaryService(session).entry_labels(user.id)
        return LabelsOut(tags=tags, emotions=emotions)


def diary_router(db: Engine, today: Callable[[User], dt.date], data_key: str | None) -> APIRouter:
    router = APIRouter(prefix="/api/entries")
    limiter = AttemptLimiter()

    def entry_action(
        user: User, entry_id: int, password: str, action: str, response: Response
    ) -> EntryOut:
        response.headers["Cache-Control"] = "no-store"
        key = (user.id, entry_id)
        limiter.check(key)
        try:
            with lock_errors(), transaction(db) as session:
                entry = getattr(DiaryService(session, data_key), action)(
                    user.id, entry_id, password
                )
        except HTTPException as err:
            if err.status_code == HTTPStatus.FORBIDDEN:
                limiter.fail(key)
            raise
        limiter.reset(key)
        if entry is None:  # чужая запись неотличима от несуществующей
            raise HTTPException(status_code=404, detail="запись не найдена")
        return entry_out(entry)

    @router.post("/{entry_id}/open")
    def open_entry(
        entry_id: int, payload: LockPassword, user: Authed, response: Response
    ) -> EntryOut:
        """Текст записи «под замком» — только в этом ответе, в БД он остаётся зашифрованным."""
        return entry_action(user, entry_id, payload.password, "open_entry", response)

    @router.post("/{entry_id}/lock")
    def lock_entry(
        entry_id: int, payload: LockPassword, user: Authed, response: Response
    ) -> EntryOut:
        try:
            return entry_action(user, entry_id, payload.password, "lock_entry", response)
        except ValueError as err:
            raise HTTPException(status_code=422, detail=str(err)) from err

    @router.post("/{entry_id}/unlock")
    def unlock_entry(
        entry_id: int, payload: LockPassword, user: Authed, response: Response
    ) -> EntryOut:
        return entry_action(user, entry_id, payload.password, "unlock_entry", response)

    @router.post("", status_code=201)
    def create_entry(payload: EntryIn, user: Authed) -> EntryOut:
        check_protection_fields(payload)
        try:
            # кризисный сигнал ищем локально (safety); запись сохраняется всегда.
            # У приватной текста на сервере нет — проверяются только теги и эмоции.
            assessment, block = check_text(
                " | ".join([payload.text, *payload.tags, *payload.emotions])
            )
            with lock_errors(), transaction(db) as session:
                diary = DiaryService(session, data_key)
                day = payload.date or today(user)
                entry = store_entry(diary, user.id, payload, day)
                if not assessment.allows_rewards:
                    # кризисная запись опыта не даёт (D5)
                    entry = diary.mark_crisis(user.id, entry.id) or entry
                else:
                    GameplayService(session).award_entry(
                        user.id, entry.id, entry.entry_date, today(user)
                    )
        except ValueError as err:
            raise HTTPException(status_code=422, detail=str(err)) from err
        return entry_out(entry, block)

    add_entry_pages(router, db)  # до «/{entry_id}»: «/labels» — не id

    @router.get("/{entry_id}")
    def get_entry(entry_id: int, user: Authed) -> EntryOut:
        with transaction(db) as session:
            entry = DiaryService(session).get_entry(user.id, entry_id)
        if entry is None:  # чужая запись неотличима от несуществующей
            raise HTTPException(status_code=404, detail="запись не найдена")
        return entry_out(entry)

    return router
