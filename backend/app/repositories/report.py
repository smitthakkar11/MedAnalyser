"""Data access for uploaded reports and their extracted values.

Every read takes a `user_id` and filters on it, so no query here can return
another user's medical document.
"""

from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.report import MedicalReport, ReportValue


class ReportRepository:
    """Reads and writes for `medical_reports` and `report_values`."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_for_user(self, report_id: uuid.UUID, user_id: uuid.UUID) -> MedicalReport | None:
        """Fetch one report **owned by** *user_id*.

        Ownership is part of the query, so a missing report and someone else's
        report are indistinguishable to the caller.
        """
        result = await self._session.execute(
            select(MedicalReport).where(
                MedicalReport.id == report_id, MedicalReport.user_id == user_id
            )
        )
        return result.scalar_one_or_none()

    async def list_for_user(
        self, user_id: uuid.UUID, *, limit: int = 50, offset: int = 0
    ) -> list[MedicalReport]:
        result = await self._session.execute(
            select(MedicalReport)
            .where(MedicalReport.user_id == user_id)
            .order_by(MedicalReport.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())

    async def count_for_user(self, user_id: uuid.UUID) -> int:
        result = await self._session.execute(
            select(func.count()).select_from(MedicalReport).where(MedicalReport.user_id == user_id)
        )
        return int(result.scalar_one())

    async def find_by_checksum(self, user_id: uuid.UUID, checksum: str) -> MedicalReport | None:
        """Detect a re-upload of a file this user already has."""
        result = await self._session.execute(
            select(MedicalReport).where(
                MedicalReport.user_id == user_id, MedicalReport.checksum == checksum
            )
        )
        return result.scalars().first()

    async def values_for_user(
        self, user_id: uuid.UUID, *, analyte: str | None = None
    ) -> list[ReportValue]:
        """Every value this user has, optionally for one analyte.

        The basis of the medical timeline in a later phase.
        """
        query = select(ReportValue).where(ReportValue.user_id == user_id)
        if analyte:
            query = query.where(ReportValue.analyte == analyte)
        result = await self._session.execute(query.order_by(ReportValue.created_at))
        return list(result.scalars().all())

    def add(self, report: MedicalReport) -> MedicalReport:
        self._session.add(report)
        return report

    def add_values(self, values: list[ReportValue]) -> None:
        self._session.add_all(values)

    async def delete(self, report: MedicalReport) -> None:
        await self._session.delete(report)
