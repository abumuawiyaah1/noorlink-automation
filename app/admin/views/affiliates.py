from __future__ import annotations

from app.admin.roles import ROLE_ADMIN, ROLE_SUPPORT
from app.admin.views.base import AuditedModelView
from app.db.models import Affiliate, AffiliateCommission, AffiliatePayout


class AffiliateAdmin(AuditedModelView, model=Affiliate):
    name = "Affiliate"
    name_plural = "Affiliates"
    icon = "fa-solid fa-handshake"
    allowed_roles = (ROLE_ADMIN, ROLE_SUPPORT)

    column_list = [
        Affiliate.code,
        Affiliate.type,
        Affiliate.display_name,
        Affiliate.status,
        Affiliate.commission_percent,
        Affiliate.customer_discount_percent,
        Affiliate.payout_email,
        Affiliate.created_at,
    ]
    column_searchable_list = [
        Affiliate.code,
        Affiliate.display_name,
        Affiliate.contact_email,
        Affiliate.referrer_email,
    ]
    column_filters = [Affiliate.type, Affiliate.status]
    column_default_sort = [(Affiliate.created_at, True)]

    form_columns = [
        Affiliate.code,
        Affiliate.type,
        Affiliate.display_name,
        Affiliate.organization_name,
        Affiliate.contact_email,
        Affiliate.payout_email,
        Affiliate.referrer_email,
        Affiliate.status,
        Affiliate.customer_discount_percent,
        Affiliate.commission_percent,
        Affiliate.payout_minimum_cents,
        Affiliate.landing_path,
        Affiliate.notes,
    ]

    form_widget_args = {"notes": {"rows": 4}}


class AffiliateCommissionAdmin(AuditedModelView, model=AffiliateCommission):
    name = "Commission"
    name_plural = "Commissions"
    icon = "fa-solid fa-coins"
    allowed_roles = (ROLE_ADMIN, ROLE_SUPPORT)

    can_create = False
    can_delete = False
    can_edit = False

    column_list = [
        AffiliateCommission.order_number,
        AffiliateCommission.commission_cents,
        AffiliateCommission.commission_percent,
        AffiliateCommission.status,
        AffiliateCommission.fulfilled_at,
    ]
    column_searchable_list = [AffiliateCommission.order_number]
    column_filters = [AffiliateCommission.status]
    column_default_sort = [(AffiliateCommission.fulfilled_at, True)]


class AffiliatePayoutAdmin(AuditedModelView, model=AffiliatePayout):
    name = "Payout"
    name_plural = "Payouts"
    icon = "fa-solid fa-money-bill-transfer"
    allowed_roles = (ROLE_ADMIN,)

    column_list = [
        AffiliatePayout.affiliate_id,
        AffiliatePayout.amount_cents,
        AffiliatePayout.method,
        AffiliatePayout.reference,
        AffiliatePayout.paid_at,
    ]
    column_filters = [AffiliatePayout.method]
    column_default_sort = [(AffiliatePayout.paid_at, True)]

    form_columns = [
        AffiliatePayout.affiliate_id,
        AffiliatePayout.amount_cents,
        AffiliatePayout.method,
        AffiliatePayout.reference,
        AffiliatePayout.notes,
        AffiliatePayout.paid_at,
    ]
