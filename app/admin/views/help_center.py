from __future__ import annotations

from starlette.requests import Request
from starlette.responses import RedirectResponse
from sqladmin import BaseView, expose

from app.admin.nav_catalog import HELP_CATEGORY
from app.admin.roles import ALL_ROLES, ROLE_ADMIN, ROLE_OWNER, session_role
from app.services.admin_help_playbooks import (
    PLAYBOOKS,
    filter_playbooks,
    get_doc_meta,
    get_playbook,
    list_doc_summaries,
    list_help_areas,
    load_doc_markdown,
    markdown_to_safe_html,
    popular_tags,
    search_docs,
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
        area = request.query_params.get("area", "").strip().lower()
        tag = request.query_params.get("tag", "").strip().lower()
        how_id = request.query_params.get("how", "").strip()
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

        how_to = get_playbook(how_id, role=role) if how_id else None
        playbooks = filter_playbooks(role=role, query=query, area=area, tag=tag)
        if not query and not area and not tag and not how_to and not doc_slug:
            # Home: curated short list — getting-started + common marketing/support tasks
            featured_order = (
                "notifications-daily",
                "monday-routine",
                "layout-shortcuts",
                "no-esim-after-payment",
                "support-ticket",
                "create-promo",
                "social-media-post",
                "creator-outreach-email",
                "order-lookup-howto",
            )
            by_id = {p.id: p for p in playbooks}
            featured = [by_id[i] for i in featured_order if i in by_id]
            featured_set = set(featured_order)
            rest = [p for p in playbooks if p.id not in featured_set]
            playbooks = featured + rest[:8]

        # When reading a full guide, surface matching short how-tos above the article
        related_how_tos = []
        if doc_slug:
            related_how_tos = [
                p
                for p in PLAYBOOKS
                if p.doc_slug == doc_slug and get_playbook(p.id, role=role) is not None
            ]

        doc_hits = search_docs(query, role=role) if query else []
        pinned_docs = [d for d in list_doc_summaries(role=role) if d.get("pinned")]
        areas = list_help_areas()
        area_label = next((a["label"] for a in areas if a["key"] == area), "")
        tags = popular_tags(role=role)

        return await self.templates.TemplateResponse(
            request,
            "help_center.html",
            {
                "query": query,
                "area": area,
                "area_label": area_label,
                "tag": tag,
                "areas": areas,
                "tags": tags,
                "how_to": how_to,
                "playbooks": playbooks,
                "related_how_tos": related_how_tos,
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
