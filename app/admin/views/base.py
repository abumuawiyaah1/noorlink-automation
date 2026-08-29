from __future__ import annotations

from typing import Any, Iterable, Optional

from sqladmin import ModelView
from starlette.requests import Request

from app.admin.audit import write_audit_log
from app.admin.roles import has_role, session_role, session_username
from app.db.engine import get_session_factory


def _client_ip(request: Request) -> Optional[str]:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return None


class AuditedModelView(ModelView):
    """Base view with role gate + audit trail on mutations."""

    allowed_roles: Iterable[str] = ("admin",)

    def is_accessible(self, request: Request) -> bool:
        return has_role(request, self.allowed_roles)

    def is_visible(self, request: Request) -> bool:
        return self.is_accessible(request)

    def _audit(
        self,
        request: Request,
        *,
        action: str,
        record_id: Optional[str],
        old_values: Optional[dict[str, Any]] = None,
        new_values: Optional[dict[str, Any]] = None,
    ) -> None:
        session_factory = get_session_factory()
        if session_factory is None:
            return
        with session_factory() as session:
            write_audit_log(
                session,
                admin_user_id=request.session.get("admin_user_id"),
                admin_username=session_username(request),
                action=action,
                table_name=self.model.__tablename__,
                record_id=record_id,
                old_values=old_values,
                new_values=new_values,
                ip_address=_client_ip(request),
            )

    async def insert_model(self, request: Request, data: dict) -> Any:
        result = await super().insert_model(request, data)
        record_id = getattr(result, "id", None) or getattr(result, "slug", None)
        self._audit(
            request,
            action="create",
            record_id=str(record_id) if record_id is not None else None,
            new_values={k: str(v) for k, v in data.items() if k != "password_hash"},
        )
        return result

    async def update_model(self, request: Request, pk: str, data: dict) -> Any:
        result = await super().update_model(request, pk, data)
        self._audit(
            request,
            action="update",
            record_id=str(pk),
            new_values={k: str(v) for k, v in data.items() if k != "password_hash"},
        )
        return result

    async def delete_model(self, request: Request, pk: str) -> None:
        await super().delete_model(request, pk)
        self._audit(request, action="delete", record_id=str(pk))
