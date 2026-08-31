"""Tests for social media hub service helpers."""

from app.services.admin_social_media import (
    STORAGE_QUOTA_BYTES,
    can_manage_social_media,
    storage_usage_summary,
)
from app.admin.roles import ROLE_MARKETING, ROLE_SUPPORT


def test_can_manage_social_media_roles():
    assert can_manage_social_media(ROLE_MARKETING) is True
    assert can_manage_social_media(ROLE_SUPPORT) is False


def test_storage_usage_summary_shape():
    summary = storage_usage_summary()
    assert summary["quota_bytes"] == STORAGE_QUOTA_BYTES
    assert "used_label" in summary
    assert "percent" in summary
