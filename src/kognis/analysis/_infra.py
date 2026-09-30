"""Хранение анализов (таблица `analyses` принадлежит модулю analysis)."""

from dataclasses import replace
from datetime import UTC, date, datetime

from sqlalchemy import (
    JSON,
    Column,
    Date,
    DateTime,
    Integer,
    String,
    Table,
    Text,
    delete,
    insert,
    select,
    update,
)
from sqlalchemy.engine import Row
from sqlalchemy.orm import Session

from kognis.db import metadata

from ._domain import Analysis, AnalysisResult

analyses_table = Table(
    "analyses",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    # владелец — id пользователя из users (без внешнего ключа: таблицей users владеет другой модуль)
    Column("owner_id", Integer, nullable=False, index=True),
    Column("parent_id", Integer, nullable=True),
    Column("direction", String(32), nullable=False),
    Column("period_start", Date, nullable=False),
    Column("period_end", Date, nullable=False),
    Column("status", String(16), nullable=False),
    Column("result", JSON, nullable=True),
    Column("answers", JSON, nullable=False),
    Column("created_at", DateTime, nullable=False),
)


# «память» ИИ о пользователе: один сжатый дайджест на владельца (ADR 0005)
memory_table = Table(
    "analysis_memory",
    metadata,
    Column("owner_id", Integer, primary_key=True, autoincrement=False),
    Column("digest", Text, nullable=False),
    Column("updated_at", DateTime, nullable=False),
)


def _to_analysis(row: Row[tuple[object, ...]]) -> Analysis:
    return Analysis(
        id=row.id,
        owner_id=row.owner_id,
        parent_id=row.parent_id,
        direction=row.direction,
        start=row.period_start,
        end=row.period_end,
        status=row.status,
        result=AnalysisResult.model_validate(row.result) if row.result else None,
        answers=tuple(row.answers),
        created_at=row.created_at,
    )


class AnalysisRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, analysis: Analysis) -> Analysis:
        """Сохранить анализ (его `id` игнорируется) и вернуть с присвоенным `id`."""
        analysis_id = self._session.execute(
            insert(analyses_table)
            .values(
                owner_id=analysis.owner_id,
                parent_id=analysis.parent_id,
                direction=analysis.direction,
                period_start=analysis.start,
                period_end=analysis.end,
                status=analysis.status,
                result=analysis.result.model_dump() if analysis.result else None,
                answers=list(analysis.answers),
                created_at=datetime.now(UTC).replace(tzinfo=None),
            )
            .returning(analyses_table.c.id)
        ).scalar_one()
        return replace(analysis, id=int(analysis_id))

    def get(self, owner_id: int, analysis_id: int) -> Analysis | None:
        row = self._session.execute(
            select(analyses_table).where(
                analyses_table.c.id == analysis_id, analyses_table.c.owner_id == owner_id
            )
        ).first()
        return _to_analysis(row) if row else None

    def list_for(self, owner_id: int, *, limit: int, offset: int) -> list[Analysis]:
        """Страница анализов владельца, новые первыми."""
        stmt = (
            select(analyses_table)
            .where(analyses_table.c.owner_id == owner_id)
            .order_by(analyses_table.c.id.desc())
            .limit(limit)
            .offset(offset)
        )
        return [_to_analysis(r) for r in self._session.execute(stmt).all()]

    def delete(self, owner_id: int, analysis_id: int) -> bool:
        """Удалить анализ владельца; чужой или несуществующий — `False`."""
        deleted = self._session.execute(
            delete(analyses_table)
            .where(analyses_table.c.id == analysis_id, analyses_table.c.owner_id == owner_id)
            .returning(analyses_table.c.id)
        ).first()
        return deleted is not None

    def has_any(self, owner_id: int) -> bool:
        return (
            self._session.execute(
                select(analyses_table.c.id).where(analyses_table.c.owner_id == owner_id).limit(1)
            ).first()
            is not None
        )

    def last_done(self, owner_id: int, *, direction: str | None = None) -> Analysis | None:
        """Последний завершённый анализ владельца (по концу периода); `direction` сужает выбор."""
        stmt = select(analyses_table).where(
            analyses_table.c.owner_id == owner_id, analyses_table.c.status == "done"
        )
        if direction is not None:
            stmt = stmt.where(analyses_table.c.direction == direction)
        row = self._session.execute(
            stmt.order_by(analyses_table.c.period_end.desc(), analyses_table.c.id.desc()).limit(1)
        ).first()
        return _to_analysis(row) if row else None

    def exists_done(self, owner_id: int, direction: str, start: date, end: date) -> int | None:
        """id завершённого разбора (не продолжения) того же направления и периода."""
        return self._session.execute(
            select(analyses_table.c.id)
            .where(
                analyses_table.c.owner_id == owner_id,
                analyses_table.c.direction == direction,
                analyses_table.c.period_start == start,
                analyses_table.c.period_end == end,
                analyses_table.c.status == "done",
                analyses_table.c.parent_id.is_(None),
            )
            .limit(1)
        ).scalar()

    def get_memory(self, owner_id: int) -> tuple[str, datetime] | None:
        row = self._session.execute(
            select(memory_table.c.digest, memory_table.c.updated_at).where(
                memory_table.c.owner_id == owner_id
            )
        ).first()
        return (row.digest, row.updated_at) if row else None

    def set_memory(self, owner_id: int, digest: str) -> None:
        now = datetime.now(UTC).replace(tzinfo=None)
        updated = self._session.execute(
            update(memory_table)
            .where(memory_table.c.owner_id == owner_id)
            .values(digest=digest, updated_at=now)
            .returning(memory_table.c.owner_id)
        ).first()
        if updated is None:
            self._session.execute(
                insert(memory_table).values(owner_id=owner_id, digest=digest, updated_at=now)
            )

    def clear_memory(self, owner_id: int) -> None:
        self._session.execute(delete(memory_table).where(memory_table.c.owner_id == owner_id))
