from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Optional

from sqlalchemy import Boolean, Date, DateTime, Integer, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    order_number: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True))
    package_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True))
    email: Mapped[str] = mapped_column(String, nullable=False)
    country: Mapped[str] = mapped_column(String, nullable=False)
    flag_emoji: Mapped[Optional[str]] = mapped_column(Text)
    package_name: Mapped[str] = mapped_column(String, nullable=False)
    amount_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    status: Mapped[str] = mapped_column(String, nullable=False, default="pending")
    travel_date: Mapped[Optional[date]] = mapped_column(Date)
    stripe_checkout_session_id: Mapped[Optional[str]] = mapped_column(Text)
    stripe_payment_intent_id: Mapped[Optional[str]] = mapped_column(Text)
    stripe_customer_id: Mapped[Optional[str]] = mapped_column(Text)
    qr_code_url: Mapped[Optional[str]] = mapped_column(Text)
    activation_code: Mapped[Optional[str]] = mapped_column(Text)
    iccid: Mapped[Optional[str]] = mapped_column(Text)
    smdp_address: Mapped[Optional[str]] = mapped_column(Text)
    lpa_string: Mapped[Optional[str]] = mapped_column(Text)
    data_limit_bytes: Mapped[Optional[int]] = mapped_column(Integer)
    data_used_gb: Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 2), default=0)
    data_total_gb: Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 2))
    paid_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    fulfilled_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    refunded_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    metadata_: Mapped[dict[str, Any]] = mapped_column("metadata", JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    def as_resend_dict(self) -> dict[str, Any]:
        return {
            "order_number": self.order_number,
            "email": self.email,
            "country": self.country,
            "flag_emoji": self.flag_emoji,
            "package_name": self.package_name,
            "status": self.status,
            "qr_code_url": self.qr_code_url,
            "activation_code": self.activation_code,
            "metadata": self.metadata_ or {},
        }


class PromoCode(Base):
    __tablename__ = "promo_codes"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    code: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    label: Mapped[Optional[str]] = mapped_column(Text)
    percent_off: Mapped[Optional[int]] = mapped_column(Integer)
    amount_off_cents: Mapped[Optional[int]] = mapped_column(Integer)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    max_redemptions: Mapped[Optional[int]] = mapped_column(Integer)
    redemption_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    min_order_cents: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    insider_issue_slug: Mapped[Optional[str]] = mapped_column(Text)
    admin_approved: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    admin_approved_by: Mapped[Optional[str]] = mapped_column(Text)
    admin_approved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class InsiderIssue(Base):
    __tablename__ = "insider_issues"

    slug: Mapped[str] = mapped_column(String, primary_key=True)
    subject: Mapped[str] = mapped_column(String, nullable=False)
    preview: Mapped[Optional[str]] = mapped_column(Text)
    hero_image_url: Mapped[Optional[str]] = mapped_column(Text)
    web_path: Mapped[Optional[str]] = mapped_column(Text)
    promo_code: Mapped[Optional[str]] = mapped_column(String)
    send_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, default="scheduled")
    sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    send_error: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
