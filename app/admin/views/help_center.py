from __future__ import annotations

from starlette.requests import Request
from starlette.responses import RedirectResponse
from sqladmin import BaseView, expose

from app.admin.nav_catalog import HELP_CATEGORY
from app.admin.roles import ALL_ROLES, ROLE_ADMIN, ROLE_OWNER, session_role
from app.services.admin_help_playbooks import (
    PLAYBOOKS,
    get_doc_meta,
    list_doc_summaries,
    load_doc_markdown,
    markdown_to_safe_html,
    search_docs,
    search_playbooks,
)


class HelpCenterView(BaseView):
    name = "Help"
    icon = "fa-solid fa-circle-question"
    category = HELP_CATEGORY

    def is_accessible(self, request: Request) -> bool:
        return session_role(request) in ALL_ROLES

    def is_visible(self, request: Request) -> bool:
        return self.is_accessible(request)

    @expose("/help", identity="help-center", methods=["GET"])
    async def center(self, request: Request):
        role = session_role(request)
        query = request.query_params.get("q", "").strip()
        doc_slug = request.query_params.get("doc", "").strip()

        doc_raw = None
        doc_html = None
        doc_title = None
        doc_meta = None
        if doc_slug:
            doc_meta = get_doc_meta(doc_slug)
            if doc_meta and (doc_meta.audience != "dev" or role in (ROLE_ADMIN, ROLE_OWNER)):
                doc_raw = load_doc_markdown(doc_slug, role=role)
                if doc_raw:
                    doc_title = doc_meta.title
                    doc_html = markdown_to_safe_html(doc_raw)
            elif doc_slug == "developer-codebase" and role not in (ROLE_ADMIN, ROLE_OWNER):
                request.session["flash_error"] = "Developer documentation is admin-only."
                return RedirectResponse(request.url_for("admin:help-center"), status_code=302)

        playbooks = search_playbooks(query, role=role) if query else search_playbooks("", role=role)
        doc_hits = search_docs(query, role=role) if query else []
        pinned_docs = [d for d in list_doc_summaries(role=role) if d.get("pinned")]

        return await self.templates.TemplateResponse(
            request,
            "help_center.html",
            {
                "query": query,
                "playbooks": playbooks,
                "doc_hits": doc_hits,
                "pinned_docs": pinned_docs,
                "docs": list_doc_summaries(role=role),
                "doc_slug": doc_slug,
                "doc_title": doc_title,
                "doc_meta": doc_meta,
                "doc_raw": doc_raw,
                "doc_html": doc_html,
                "is_admin": role in (ROLE_ADMIN, ROLE_OWNER),
                "flash_error": request.session.pop("flash_error", None),
            },
        )
