from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Optional

from sqlalchemy import Date, DateTime, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class CreatorOutreachContact(Base):
    __tablename__ = "creator_outreach_contacts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    handle: Mapped[str] = mapped_column(Text, nullable=False, default="")
    email: Mapped[str] = mapped_column(Text, nullable=False, default="")
    platform: Mapped[str] = mapped_column(String, nullable=False, default="instagram")
    profile_url: Mapped[str] = mapped_column(Text, nullable=False, default="")
    content_url: Mapped[str] = mapped_column(Text, nullable=False, default="")
    wave: Mapped[str] = mapped_column(String, nullable=False, default="search")
    status: Mapped[str] = mapped_column(String, nullable=False, default="to_contact")
    message_sent: Mapped[str] = mapped_column(Text, nullable=False, default="")
    promo_code: Mapped[str] = mapped_column(Text, nullable=False, default="")
    notes: Mapped[str] = mapped_column(Text, nullable=False, default="")
    contacted_at: Mapped[Optional[date]] = mapped_column(Date)
    replied_at: Mapped[Optional[date]] = mapped_column(Date)
    last_email_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    last_email_subject: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_by: Mapped[str] = mapped_column(Text, nullable=False, default="")
    updated_by: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
