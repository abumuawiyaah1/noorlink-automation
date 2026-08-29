from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any, Optional

from sqlalchemy import Boolean, Date, DateTime, Integer, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class EsimPackage(Base):
    __tablename__ = "esim_packages"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    slug: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    country: Mapped[str] = mapped_column(String, nullable=False)
    country_code: Mapped[Optional[str]] = mapped_column(String(2))
    region: Mapped[str] = mapped_column(String, nullable=False, default="Americas")
    flag_emoji: Mapped[Optional[str]] = mapped_column(Text)
    description: Mapped[Optional[str]] = mapped_column(Text)
    data_label: Mapped[str] = mapped_column(String, nullable=False, default="10GB")
    data_total_gb: Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 2))
    validity_days: Mapped[int] = mapped_column(Integer, nullable=False, default=15)
    price_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    stripe_product_id: Mapped[Optional[str]] = mapped_column(Text)
    stripe_price_id: Mapped[Optional[str]] = mapped_column(Text)
    provider_sku: Mapped[Optional[str]] = mapped_column(Text)
    network_label: Mapped[Optional[str]] = mapped_column(Text)
    image_url: Mapped[Optional[str]] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_featured: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_managed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    tier: Mapped[Optional[str]] = mapped_column(Text)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    admin_approved: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    admin_approved_by: Mapped[Optional[str]] = mapped_column(Text)
    admin_approved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    pending_price_cents: Mapped[Optional[int]] = mapped_column(Integer)
    metadata_: Mapped[dict[str, Any]] = mapped_column("metadata", JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class PlanFulfillmentMap(Base):
    __tablename__ = "plan_fulfillment_map"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    catalog_key: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    package_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True))
    country_code: Mapped[Optional[str]] = mapped_column(String(2))
    country_slug: Mapped[Optional[str]] = mapped_column(Text)
    data_gb: Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 2))
    validity_days: Mapped[Optional[int]] = mapped_column(Integer)
    provider: Mapped[str] = mapped_column(String, nullable=False)
    provider_sku: Mapped[str] = mapped_column(String, nullable=False)
    provider_slug: Mapped[Optional[str]] = mapped_column(Text)
    wholesale_cents: Mapped[Optional[int]] = mapped_column(Integer)
    period_num: Mapped[Optional[int]] = mapped_column(Integer)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    admin_approved: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    admin_approved_by: Mapped[Optional[str]] = mapped_column(Text)
    admin_approved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    notes: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
