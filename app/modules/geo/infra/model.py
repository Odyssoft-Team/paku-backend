"""Geo infrastructure models.

SQLAlchemy models for the geo catalog tables.
NOTE: This model maps to the existing geo_districts table (managed by Alembic).
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.modules.iam.infra.models import Base, utcnow


class DistrictModel(Base):
    """District model mapping to geo_districts table.
    
    NOTE: The relationship with UserAddressModel is kept in the IAM module
    to avoid circular dependencies. Geo module is read-only for districts.
    """
    __tablename__ = "geo_districts"

    id: Mapped[str] = mapped_column(String(20), primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    province_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    department_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
