"""Tests for legal/accounting document vault access rules."""

from unittest.mock import MagicMock, patch

import pytest

from app.services.admin_document_vault import (
    DocumentVaultError,
    can_delete_documents,
    can_upload_documents,
    can_view_document_row,
    can_view_documents,
    list_documents,
    soft_delete_document,
    upload_document,
)


def test_role_matrix():
    assert can_view_documents("admin")
    assert can_view_documents("finance")
    assert can_view_documents("legal")
    assert not can_view_documents("support")
    assert can_upload_documents("finance")
    assert not can_upload_documents("marketing")
    assert can_delete_documents("admin")
    assert not can_delete_documents("legal")


def test_admin_only_visibility():
    assert can_view_document_row(role="admin", access_level="admin_only")
    assert not can_view_document_row(role="finance", access_level="admin_only")
    assert can_view_document_row(role="legal", access_level="vault")


def test_upload_rejects_unsupported_type():
    with pytest.raises(DocumentVaultError, match="Unsupported"):
        upload_document(
            title="Test",
            category="legal",
            access_level="vault",
            description="",
            document_year=2026,
            filename="secret.exe",
            content_type="application/octet-stream",
            file_bytes=b"abc",
            uploaded_by="admin",
            role="admin",
        )


def test_upload_rejects_support_role():
    with pytest.raises(DocumentVaultError, match="permission"):
        upload_document(
            title="Test",
            category="legal",
            access_level="vault",
            description="",
            document_year=2026,
            filename="a.pdf",
            content_type="application/pdf",
            file_bytes=b"%PDF",
            uploaded_by="support",
            role="support",
        )


def test_list_denied_for_support():
    with pytest.raises(DocumentVaultError, match="access"):
        list_documents(role="support")


@patch("app.services.admin_document_vault.get_session_factory")
def test_soft_delete_admin_only(mock_factory):
    with pytest.raises(DocumentVaultError, match="admins"):
        soft_delete_document(document_id="x", role="finance", deleted_by="fin")


@patch("app.services.admin_document_vault.db.get_supabase_client")
@patch("app.services.admin_document_vault.get_session_factory")
def test_upload_happy_path(mock_factory, mock_client):
    storage = MagicMock()
    mock_client.return_value.storage.from_.return_value = storage

    session = MagicMock()
    factory = MagicMock()
    factory.return_value.__enter__.return_value = session
    factory.return_value.__exit__.return_value = None
    mock_factory.return_value = factory

    def _refresh(row):
        row.title = "Acme NDA"
        row.category = "contracts"
        row.access_level = "vault"
        row.description = None
        row.document_year = 2026
        row.original_filename = "nda.pdf"
        row.content_type = "application/pdf"
        row.file_size_bytes = 4
        row.uploaded_by = "admin"
        row.created_at = None
        row.deleted_at = None

    session.refresh.side_effect = _refresh

    result = upload_document(
        title="Acme NDA",
        category="contracts",
        access_level="vault",
        description="",
        document_year=2026,
        filename="nda.pdf",
        content_type="application/pdf",
        file_bytes=b"%PDF",
        uploaded_by="admin",
        role="admin",
    )
    assert result["title"] == "Acme NDA"
    assert result["category"] == "contracts"
    storage.upload.assert_called_once()
