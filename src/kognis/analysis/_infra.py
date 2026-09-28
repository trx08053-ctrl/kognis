"""Хранение анализов (таблица `analyses` принадлежит модулю analysis)."""

from dataclasses import replace
from datetime import UTC, datetime

from sqlalchemy import JSON, Column, Date, DateTime, Integer, String, Table, insert, select
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

    def list_for(self, owner_id: int) -> list[Analysis]:
        stmt = (
            select(analyses_table)
            .where(analyses_table.c.owner_id == owner_id)
            .order_by(analyses_table.c.id.desc())
        )
        return [_to_analysis(r) for r in self._session.execute(stmt).all()]
