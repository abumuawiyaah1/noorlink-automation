"""Role helpers for SQLAdmin views."""

from __future__ import annotations

from typing import Iterable

ROLE_OWNER = "owner"
ROLE_ADMIN = "admin"
ROLE_SUPPORT = "support"
ROLE_CATALOG = "catalog"
ROLE_MARKETING = "marketing"
ROLE_FINANCE = "finance"
ROLE_LEGAL = "legal"

ALL_ROLES = {
    ROLE_OWNER,
    ROLE_ADMIN,
    ROLE_SUPPORT,
    ROLE_CATALOG,
    ROLE_MARKETING,
    ROLE_FINANCE,
    ROLE_LEGAL,
}

# Roles that can create/edit promo codes and extend validity
PROMO_MANAGER_ROLES = (ROLE_ADMIN, ROLE_CATALOG, ROLE_MARKETING)

# Roles that can edit catalog plans and fulfillment maps (approval rules apply)
CATALOG_MANAGER_ROLES = (ROLE_ADMIN, ROLE_CATALOG)

# Legal + accounting document vault (grow by adding roles here)
DOCUMENTS_VIEW_ROLES = (ROLE_ADMIN, ROLE_FINANCE, ROLE_LEGAL)
DOCUMENTS_UPLOAD_ROLES = (ROLE_ADMIN, ROLE_FINANCE, ROLE_LEGAL)
DOCUMENTS_DELETE_ROLES = (ROLE_ADMIN,)  # soft-delete stays admin-only for now
# Owner inherits admin access via has_role()

# Staff roles a normal admin may create (not admin/owner)
STAFF_CREATABLE_BY_ADMIN = {
    ROLE_SUPPORT,
    ROLE_CATALOG,
    ROLE_MARKETING,
    ROLE_FINANCE,
    ROLE_LEGAL,
}

# Owner may create any role including admin and a co-owner
STAFF_CREATABLE_BY_OWNER = set(ALL_ROLES)


def session_role(request) -> str:
    return str(request.session.get("admin_role") or "")


def session_username(request) -> str:
    return str(request.session.get("admin_username") or "")


def is_owner(request) -> bool:
    return session_role(request) == ROLE_OWNER


def has_role(request, allowed: Iterable[str]) -> bool:
    """
    Owner and admin both pass any gate that lists admin.
    Owner always has full access.
    """
    role = session_role(request)
    if role == ROLE_OWNER:
        return True
    if role == ROLE_ADMIN:
        # Admin still gets broad access; owner-only actions use is_owner() / OwnerGuard
        return True
    return role in allowed
