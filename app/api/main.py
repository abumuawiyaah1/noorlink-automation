from urllib.parse import quote

from datetime import datetime, timezone
import logging
import secrets
from typing import Optional

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.config import get_settings
from app.core.logging_setup import configure_app_logging
from app.services.email_service import (
    EmailDeliveryError,
    send_checkout_acknowledgment,
)
from app.services.support_categories import normalize_support_category
from app.services.support_notifications import dispatch_ticket_created_notifications
from app.services.fulfillment import FulfillmentError, process_paid_order
from app.services.ops_alerts import notify_fulfillment_failure
from app.services.insider_release import expire_finished_promos, release_due_insider_issues
from app.services.promo_codes import normalize_code
from app.services.checkout_pricing import (
    CheckoutPricingError,
    authoritative_checkout_price,
)
from .internal_auth import require_cron_secret, require_internal_in_production

from .analytics import router as analytics_router
from .devices import check_device
from .devices_router import router as devices_router
from .plans_router import router as plans_router
from .affiliates_router import router as affiliates_router
from .webhooks import router as webhooks_router
from . import supabase_repository as db
from .stripe_checkout import (
    StripeCheckoutError,
    create_stripe_checkout_session,
    create_stripe_payment_intent,
)
from .stripe_webhook import (
    StripeWebhookError,
    construct_stripe_event,
    extract_checkout_session_completed,
    extract_payment_intent_succeeded,
    stripe_event_amount_cents,
)
from .schemas import (
    ApiTestResponse,
    CheckoutConfigResponse,
    CheckoutSessionRequest,
    CheckoutSessionResponse,
    ExpressPaymentIntentResponse,
    PayPalCaptureRequest,
    PayPalCaptureResponse,
    PayPalConfigResponse,
    PayPalCreateOrderResponse,
    ContactFormRequest,
    ContactFormResponse,
    CronRunResponse,
    DailyReportResponse,
    AdminReportsResponse,
    DeviceCheckRequest,
    DeviceCheckResponse,
    EmailDiagnosticsResponse,
    FulfillmentResolveResponse,
    BreakageStrategySummaryResponse,
    BreakageCountryPolicyResponse,
    BreakageAllowanceResponse,
    HealthResponse,
    NewsletterSubscribeRequest,
    NewsletterSubscribeResponse,
    NewsletterUnsubscribeRequest,
    NewsletterUnsubscribeResponse,
    OrderLookupResponse,
    OrderResendEsRequest,
    OrderResendEsResponse,
    PromoValidateRequest,
    PromoValidateResponse,
    TopUpOptionsResponse,
    TopUpSessionRequest,
    TopUpSessionResponse,
    TopUpPayPalCreateResponse,
    TopUpPayPalCaptureRequest,
    TopUpPayPalCaptureResponse,
    OrderSupportMessagesResponse,
    RootResponse,
)

logger = logging.getLogger(__name__)
configure_app_logging()
settings = get_settings()
_is_production = settings.environment.lower() == "production"

app = FastAPI(
    title="NoorLink Automation API",
    description="Automated eSIM purchase and delivery system",
    version=settings.app_version,
    docs_url=None if _is_production else "/docs",
    redoc_url=None if _is_production else "/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(analytics_router)
app.include_router(devices_router)
app.include_router(plans_router)
app.include_router(webhooks_router)
app.include_router(affiliates_router)

from app.admin.setup import mount_admin  # noqa: E402

mount_admin(app)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """Log full traceback for unexpected 5xx before Cloudflare sees a generic error."""
    if isinstance(exc, RequestValidationError):
        return JSONResponse(status_code=422, content={"detail": exc.errors()})
    if isinstance(exc, (HTTPException, StarletteHTTPException)):
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail},
            headers=dict(getattr(exc, "headers", None) or {}),
        )
    logger.exception(
        "Unhandled exception on %s %s",
        request.method,
        request.url.path,
    )
    detail = (
        "Something went wrong. Please try again in a moment."
        if _is_production
        else str(exc)[:500]
    )
    return JSONResponse(status_code=500, content={"detail": detail})


def _is_retryable_db_error(exc: Exception) -> bool:
    text = str(exc).lower()
    tokens = (
        "timeout",
        "timed out",
        "temporar",
        "connection",
        "connect",
        "unavailable",
        "overloaded",
        "502",
        "503",
        "504",
        "upstream",
        "pool",
        "too many",
        "server disconnected",
        "network",
        "reset by peer",
        "cloudflare",
    )
    return any(token in text for token in tokens)


def _db_error(exc: Exception) -> HTTPException:
    """Map repository failures to HTTP errors with full local stack traces."""
    logger.error(
        "Database/repository error: %s",
        exc,
        exc_info=(type(exc), exc, exc.__traceback__),
    )
    customer = "Database temporarily unavailable. Please try again."
    if _is_production:
        if _is_retryable_db_error(exc):
            return HTTPException(status_code=503, detail=customer)
        # Permanent/schema/RLS-style failures still 503 for customers (no leak),
        # but ops logs now have the full traceback above.
        return HTTPException(status_code=503, detail=customer)

    detail = str(exc).strip() or customer
    if any(
        token in detail
        for token in (
            "bootstrap_checkout_minimal",
            "Checkout tables are missing",
            "Could not find the table",
            "Could not find the",
            "PGRST",
            "column",
            "violates",
            "permission denied",
            "RLS",
        )
    ):
        return HTTPException(status_code=503, detail=detail[:500])
    return HTTPException(status_code=503, detail=customer)


def _prepare_checkout_pricing(body: CheckoutSessionRequest):
    if not body.package_id or not str(body.package_id).strip():
        raise HTTPException(
            status_code=400,
            detail="packageId is required. Go back and select a plan.",
        )
    try:
        catalog_price = authoritative_checkout_price(
            package_id=str(body.package_id),
            country=body.country,
            client_price=body.price if body.price > 0 else None,
        )
    except db.ManagedPackagePriceMismatchError as exc:
        raise HTTPException(
            status_code=400,
            detail="Package price does not match our catalog. Refresh and try again.",
        ) from exc
    except CheckoutPricingError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    from app.services.affiliates import AffiliateError, prepare_checkout_discounts

    try:
        pricing = prepare_checkout_discounts(
            catalog_price=catalog_price,
            country=body.country,
            buyer_email=str(body.email),
            package_id=str(body.package_id),
            promo_code=body.promo_code,
            affiliate_ref=body.affiliate_ref,
        )
    except AffiliateError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return catalog_price, pricing


def _checkout_attribution_metadata(body: CheckoutSessionRequest) -> Optional[dict]:
    from app.services.order_attribution import clean_attribution_payload

    if not body.attribution:
        return None
    raw = body.attribution.model_dump(by_alias=False, exclude_none=True)
    return clean_attribution_payload(raw)


def _validate_gift_checkout(body: CheckoutSessionRequest) -> None:
    from app.services.gift_orders import validate_gift_checkout

    validate_gift_checkout(body)


def _checkout_buyer_email(body: CheckoutSessionRequest) -> str:
    """Real email when provided; temporary pending address until Stripe supplies one."""
    if body.email:
        return str(body.email).strip().lower()
    return f"pending+{secrets.token_hex(8)}@checkout.noorlink.pending"


def _is_pending_checkout_email(email: Optional[str]) -> bool:
    value = (email or "").strip().lower()
    return value.endswith("@checkout.noorlink.pending") or value.startswith("pending+")


def _build_gift_metadata(body: CheckoutSessionRequest) -> Optional[dict]:
    from app.services.gift_orders import build_gift_metadata

    return build_gift_metadata(body)


def _verify_stripe_paid_amount(order_row: dict, event) -> bool:
    expected = int(order_row.get("amount_cents") or 0)
    received = stripe_event_amount_cents(event)
    if not expected or not received:
        return True
    if expected != received:
        logger.error(
            "Stripe amount mismatch for order %s: expected %s got %s",
            order_row.get("order_number"),
            expected,
            received,
        )
        return False
    return True


@app.get("/", response_model=RootResponse)
async def root():
    return RootResponse(
        message="🚀 NoorLink Automation API",
        status="operational",
        timestamp=datetime.now(timezone.utc).isoformat(),
        docs="/docs",
        health="/health",
    )


@app.get("/health", response_model=HealthResponse)
async def health_check():
    from app.db.engine import ping_admin_database

    db_ok = db.ping_database()
    admin_db_ok = ping_admin_database() if (settings.database_url or "").strip() else None
    status = "healthy" if db_ok else "degraded"
    if admin_db_ok is False:
        status = "degraded"
    return HealthResponse(
        status=status,
        service="noorlink-automation",
        timestamp=datetime.now(timezone.utc).isoformat(),
        version=settings.app_version,
    )


@app.get("/api/diagnostics/email", response_model=EmailDiagnosticsResponse)
async def email_diagnostics(
    request: Request,
    probe: bool = Query(False),
    authorization: Optional[str] = Header(None),
):
    """Resend configuration check. probe=1 sends a test email (internal auth in production)."""
    if probe and _is_production:
        require_internal_in_production(request, authorization)
    from_email = (settings.resend_from_email or "").strip()
    configured = bool((settings.resend_api_key or "").strip())
    domain = None
    if "@" in from_email:
        domain = from_email.rsplit("@", 1)[-1].rstrip(">").strip().lower()

    expected = "noorlink.co"
    matches = domain == expected
    hint = None
    if not configured:
        hint = "Set RESEND_API_KEY in Railway."
    elif not matches:
        hint = (
            f"RESEND_FROM_EMAIL is '{from_email}'. "
            f"Update it to an address on @{expected} "
            f"(e.g. NoorLink <noreply@{expected}>)."
        )

    test_send_ok = None
    test_send_id = None
    test_send_error = None
    if probe and configured:
        try:
            from app.services.email_service import send_email

            test_send_id = send_email(
                to_email="delivered@resend.dev",
                subject="NoorLink Resend probe",
                html_body="<p>Resend probe from api.noorlink.co diagnostics.</p>",
            )
            test_send_ok = True
        except Exception as exc:
            test_send_ok = False
            test_send_error = str(exc)[:400]
            hint = (
                "Resend rejected the probe send. "
                f"Error: {test_send_error}"
            )

    return EmailDiagnosticsResponse(
        ok=configured and matches and (test_send_ok is not False),
        resend_configured=configured,
        from_email=from_email or "(empty)",
        from_domain=domain,
        expected_domain=expected,
        domain_matches=matches,
        hint=hint,
        test_send_ok=test_send_ok,
        test_send_id=test_send_id,
        test_send_error=test_send_error,
    )


@app.get("/api/test", response_model=ApiTestResponse)
async def test_endpoint(request: Request, authorization: Optional[str] = Header(None)):
    if _is_production:
        require_internal_in_production(request, authorization)
    return ApiTestResponse(
        success=True,
        message="API is working!",
        environment=settings.environment if not _is_production else "production",
    )


@app.post("/api/newsletter/subscribe", response_model=NewsletterSubscribeResponse)
async def newsletter_subscribe(body: NewsletterSubscribeRequest):
    try:
        db.save_newsletter_subscriber(
            str(body.email),
            body.dream_destination,
        )
    except db.SupabaseRepositoryError as exc:
        raise _db_error(exc) from exc
    return NewsletterSubscribeResponse(
        success=True,
        message="You are subscribed to NoorLink Insider.",
    )


@app.post("/api/newsletter/unsubscribe", response_model=NewsletterUnsubscribeResponse)
async def newsletter_unsubscribe(body: NewsletterUnsubscribeRequest):
    try:
        found = db.unsubscribe_newsletter_subscriber(str(body.email))
    except db.SupabaseRepositoryError as exc:
        raise _db_error(exc) from exc

    if not found:
        return NewsletterUnsubscribeResponse(
            success=True,
            message="That email is not on the Insider list.",
        )

    return NewsletterUnsubscribeResponse(
        success=True,
        message="You’re unsubscribed from NoorLink Insider.",
    )


@app.post("/api/promo/validate", response_model=PromoValidateResponse)
async def promo_validate(body: PromoValidateRequest):
    if not body.package_id or not str(body.package_id).strip():
        return PromoValidateResponse(
            valid=False,
            message="Select a plan before applying a promo code.",
        )
    try:
        catalog_price = authoritative_checkout_price(
            package_id=str(body.package_id),
            country=body.country,
            client_price=body.price if body.price > 0 else None,
        )
    except (CheckoutPricingError, db.ManagedPackagePriceMismatchError):
        return PromoValidateResponse(
            valid=False,
            message="Select a valid plan before applying a promo code.",
        )

    try:
        db.expire_promo_codes()
    except db.SupabaseRepositoryError:
        pass

    subtotal_cents = int(round(catalog_price * 100))
    code = normalize_code(body.code)
    try:
        row = db.get_promo_code(code)
        discount = validate_promo_row(row, subtotal_cents=subtotal_cents)
    except PromoCodeError as exc:
        return PromoValidateResponse(valid=False, message=str(exc))

    return PromoValidateResponse(
        valid=True,
        code=discount.code,
        percent_off=discount.percent_off,
        discount_amount=round(discount.discount_cents / 100.0, 2),
        final_price=round(discount.final_cents / 100.0, 2),
        ends_at=discount.ends_at,
        message="Promo applied.",
    )


def _require_cron_secret(authorization: Optional[str]) -> None:
    require_cron_secret(authorization)


@app.post("/api/cron/run", response_model=CronRunResponse)
async def cron_run(authorization: Optional[str] = Header(None)):
    """Expire promos, send Insider issues, sync catalog, eSIM expiry reminders. Requires CRON_SECRET."""
    _require_cron_secret(authorization)

    expired = 0
    insider_result = None
    catalog_sync = None
    try:
        expired = expire_finished_promos()
    except db.SupabaseRepositoryError as exc:
        raise _db_error(exc) from exc

    try:
        insider_result = release_due_insider_issues()
    except db.SupabaseRepositoryError as exc:
        raise _db_error(exc) from exc
    except EmailDeliveryError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    try:
        from app.services.provider_catalog import sync_telna_catalog

        catalog_sync = await sync_telna_catalog(use_builtin_on_failure=True)
    except Exception as exc:
        logger.warning("Provider catalog sync failed during cron: %s", exc)
        catalog_sync = {"success": False, "error": str(exc)[:240]}

    expiry_reminders = None
    try:
        from app.services.expiry_reminders import process_esim_expiry_reminders

        expiry_reminders = process_esim_expiry_reminders()
    except Exception as exc:
        logger.warning("eSIM expiry reminders failed during cron: %s", exc)
        expiry_reminders = {"success": False, "error": str(exc)[:240]}

    usage_sync = None
    try:
        from app.services.usage_sync_cron import process_esim_usage_sync

        usage_sync = process_esim_usage_sync()
    except Exception as exc:
        logger.warning("eSIM usage sync failed during cron: %s", exc)
        usage_sync = {"success": False, "error": str(exc)[:240]}

    monthly_summary = None
    # Monthly admin brief sends on the 1st at 6:00 New York via /api/cron/admin-reports.

    log_retention = None
    try:
        from app.services.ops_log_retention import purge_old_ops_logs

        log_retention = purge_old_ops_logs(retention_days=90)
    except Exception as exc:
        logger.warning("Ops log retention failed during cron: %s", exc)
        log_retention = {"error": str(exc)[:240]}

    auto_refunds = None
    try:
        from app.services.support_auto_refund import process_unanswered_auto_refunds

        auto_refunds = process_unanswered_auto_refunds()
    except Exception as exc:
        logger.warning("Support auto-refund cron failed: %s", exc)
        auto_refunds = {"success": False, "error": str(exc)[:240]}

    affiliate_payouts = None
    try:
        from app.services.affiliate_payout_requests import process_unanswered_affiliate_payouts

        affiliate_payouts = process_unanswered_affiliate_payouts()
    except Exception as exc:
        logger.warning("Affiliate payout auto-approve cron failed: %s", exc)
        affiliate_payouts = {"success": False, "error": str(exc)[:240]}

    return CronRunResponse(
        success=True,
        expired_promos=expired,
        insider=insider_result,
        catalog_sync=catalog_sync,
        expiry_reminders=expiry_reminders,
        usage_sync=usage_sync,
        monthly_summary=monthly_summary,
        log_retention=log_retention,
        auto_refunds=auto_refunds,
        affiliate_payouts=affiliate_payouts,
        message="Cron tasks completed.",
    )


@app.post("/api/cron/daily-report", response_model=DailyReportResponse)
async def cron_daily_report(authorization: Optional[str] = Header(None)):
    """Send the 6:00 New York admin daily brief. Requires CRON_SECRET."""
    _require_cron_secret(authorization)
    try:
        from app.services.admin_daily_summary import send_daily_summary_email

        result = send_daily_summary_email()
    except Exception as exc:
        logger.warning("Daily summary email failed: %s", exc)
        return DailyReportResponse(success=False, sent=0, error=str(exc)[:240])

    return DailyReportResponse(
        success=bool(result.get("sent")) or bool(result.get("skipped")),
        sent=int(result.get("sent") or 0),
        skipped=result.get("skipped"),
        error=result.get("error"),
        subject=result.get("subject"),
        ny_date=result.get("ny_date"),
        recipients=result.get("recipients"),
        errors=result.get("errors") or None,
    )


@app.post("/api/cron/admin-reports", response_model=AdminReportsResponse)
async def cron_admin_reports(authorization: Optional[str] = Header(None)):
    """Send scheduled daily, weekly (Monday), and monthly (1st) admin briefs."""
    _require_cron_secret(authorization)

    daily_result: dict = {"sent": 0}
    weekly_result: dict = {"sent": 0}
    monthly_result: dict = {"sent": 0}

    try:
        from app.services.admin_daily_summary import send_daily_summary_email

        daily_result = send_daily_summary_email()
    except Exception as exc:
        logger.warning("Daily summary email failed: %s", exc)
        daily_result = {"sent": 0, "error": str(exc)[:240]}

    try:
        from app.services.admin_weekly_summary import send_weekly_summary_email

        weekly_result = send_weekly_summary_email()
    except Exception as exc:
        logger.warning("Weekly summary email failed: %s", exc)
        weekly_result = {"sent": 0, "error": str(exc)[:240]}

    try:
        from app.services.admin_monthly_summary import send_monthly_summary_email

        monthly_result = send_monthly_summary_email()
    except Exception as exc:
        logger.warning("Monthly summary email failed: %s", exc)
        monthly_result = {"sent": 0, "error": str(exc)[:240]}

    device_catalog = None
    try:
        from app.services.device_catalog_monitor import run_device_catalog_monitor

        device_catalog = run_device_catalog_monitor()
    except Exception as exc:
        logger.warning("Device catalog monitor failed: %s", exc)
        device_catalog = {"sent": 0, "error": str(exc)[:240]}

    return AdminReportsResponse(
        success=True,
        daily=daily_result,
        weekly=weekly_result,
        monthly=monthly_result,
        device_catalog=device_catalog,
    )


@app.get("/api/fulfillment/resolve", response_model=FulfillmentResolveResponse)
async def fulfillment_resolve(
    request: Request,
    country: str = Query(..., min_length=2),
    data_gb: float = Query(..., alias="dataGb", gt=0),
    validity_days: int = Query(..., alias="days", gt=0),
    wants_topup: bool = Query(False, alias="wantsTopUp"),
    authorization: Optional[str] = Header(None),
):
    require_internal_in_production(request, authorization)
    """
    Debug/admin: show map vs smart cascade choice for a sellable ladder step.
    Does not call upstream provider APIs — catalog cache / builtin seed only.
    """
    from app.services.fulfillment_resolver import explain_fulfillment

    result = explain_fulfillment(
        country=country,
        data_gb=data_gb,
        validity_days=validity_days,
        wants_topup=wants_topup,
    )
    return FulfillmentResolveResponse(success=True, **result)


@app.get("/api/fulfillment/strategy/summary", response_model=BreakageStrategySummaryResponse)
async def breakage_strategy_summary(
    request: Request,
    authorization: Optional[str] = Header(None),
):
    require_internal_in_production(request, authorization)
    """Breakage-fulfillment strategy counts and pilot countries (from WeConnect P1 pricelist)."""
    from app.services.breakage_strategy import strategy_summary

    return BreakageStrategySummaryResponse(success=True, summary=strategy_summary())


@app.get("/api/fulfillment/strategy/country", response_model=BreakageCountryPolicyResponse)
async def breakage_strategy_country(
    request: Request,
    country: str = Query(..., min_length=2),
    data_gb: Optional[float] = Query(None, alias="dataGb"),
    validity_days: Optional[int] = Query(None, alias="days"),
    authorization: Optional[str] = Header(None),
):
    require_internal_in_production(request, authorization)
    from app.services.breakage_strategy import (
        bundles_for_country,
        fulfillment_mode_for_order,
        resolve_country_policy,
    )

    policy = resolve_country_policy(country)
    mode = fulfillment_mode_for_order(
        country=country,
        data_gb=data_gb,
        validity_days=validity_days,
    )
    return BreakageCountryPolicyResponse(
        success=True,
        country=policy.country_slug,
        policy={
            "country": policy.country,
            "mode": policy.policy,
            "reason": policy.policy_reason,
            "price_mb_usd": policy.price_mb_usd,
            "price_gb_usd": policy.price_gb_usd,
            "margin_10gb_100pct": policy.margin_10gb_100pct,
            "margin_10gb_50pct": policy.margin_10gb_50pct,
            "breakage_score": policy.breakage_score,
            "region_hint": policy.region_hint,
        },
        fulfillment_mode=mode,
        bundles=bundles_for_country(country),
    )


@app.get("/api/fulfillment/allowance", response_model=BreakageAllowanceResponse)
async def breakage_allowance_lookup(
    request: Request,
    order_number: str = Query(..., alias="orderNumber", min_length=4),
    email: str = Query(..., min_length=3),
    authorization: Optional[str] = Header(None),
):
    require_internal_in_production(request, authorization)
    order = db.lookup_order(order_number, email)
    if not order:
        return BreakageAllowanceResponse(
            success=False,
            message="Order not found for that email.",
        )
    from app.services.breakage_allowance import breakage_profit_estimate

    row = db.get_breakage_allowance_by_order_number(order_number)
    if not row:
        return BreakageAllowanceResponse(
            success=False,
            message="No breakage allowance for this order.",
        )
    return BreakageAllowanceResponse(
        success=True,
        allowance=row,
        profit_estimate=breakage_profit_estimate(row),
    )


@app.post("/api/contact", response_model=ContactFormResponse)
async def contact_submit(body: ContactFormRequest):
    order_number = (body.order_id or "").strip().upper() or None
    ticket_id: str
    ticket_category: Optional[str] = None

    try:
        from app.db.engine import get_engine
        from app.services.support_messaging import (
            SupportMessagingError,
            create_ticket_from_contact,
        )

        if get_engine() is not None:
            created = create_ticket_from_contact(
                name=body.name,
                email=str(body.email),
                subject=body.subject,
                message=body.message,
                order_number=order_number,
                language=body.language,
            )
            ticket_id = created["ticket_number"]
            ticket_category = created.get("category")
        else:
            ticket_category = normalize_support_category(body.subject)
            ticket_id = db.create_support_ticket(
                name=body.name,
                email=str(body.email),
                subject=body.subject,
                message=body.message,
                order_number=order_number,
                category=ticket_category,
            )
    except SupportMessagingError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except db.SupabaseRepositoryError as exc:
        raise _db_error(exc) from exc

    try:
        dispatch_ticket_created_notifications(
            ticket_id=ticket_id,
            name=body.name,
            email=str(body.email),
            subject=body.subject,
            message=body.message,
            order_number=order_number,
            category=ticket_category,
        )
    except EmailDeliveryError as exc:
        logger.error(
            "Support ticket %s saved but confirmation email failed: %s",
            ticket_id,
            exc,
        )
        return ContactFormResponse(
            success=True,
            ticket_id=ticket_id,
            message=(
                "Your message has been received (ticket saved), but we could not "
                "send the confirmation email right now. We will still reply within 24 hours."
            ),
        )

    return ContactFormResponse(
        success=True,
        ticket_id=ticket_id,
        message="Your message has been received. We sent a confirmation email with your ticket ID.",
    )


@app.get("/api/device-check", response_model=DeviceCheckResponse)
async def device_check_get(
    device_name: str = Query(..., alias="deviceName", min_length=3),
):
    compatible, matched = check_device(device_name)
    if not compatible:
        try:
            from app.services.device_catalog_monitor import record_device_check_miss

            record_device_check_miss(device_name, source="api")
        except Exception:
            logger.debug("Device check miss logging failed", exc_info=True)
    return DeviceCheckResponse(
        compatible=compatible,
        device_name=device_name,
        matched_model=matched,
        message=(
            "Your device supports eSIM."
            if compatible
            else "We could not confirm compatibility for this device."
        ),
    )


@app.post("/api/device-check", response_model=DeviceCheckResponse)
async def device_check_post(body: DeviceCheckRequest):
    compatible, matched = check_device(body.device_name)
    if not compatible:
        try:
            from app.services.device_catalog_monitor import record_device_check_miss

            record_device_check_miss(body.device_name, source="api")
        except Exception:
            logger.debug("Device check miss logging failed", exc_info=True)
    return DeviceCheckResponse(
        compatible=compatible,
        device_name=body.device_name,
        matched_model=matched,
        message=(
            "Your device supports eSIM."
            if compatible
            else "We could not confirm compatibility for this device."
        ),
    )


def _lookup_order_response(
    order_row: Optional[dict],
    *,
    refresh: bool = False,
) -> OrderLookupResponse:
    if not order_row:
        return OrderLookupResponse(found=False, order=None)

    row = order_row
    if refresh and str(row.get("iccid") or "").strip():
        try:
            from app.services.esim_usage_sync import sync_order_usage_blocking

            row = sync_order_usage_blocking(row, source="api_refresh")
        except Exception as exc:
            logger.warning("Usage refresh on lookup failed for %s: %s", row.get("order_number"), exc)

    allowance = db.get_breakage_allowance_by_order_id(str(row["id"]))
    from app.services.order_customer_view import enrich_order_row

    _, order = enrich_order_row(row, allowance_row=allowance)
    return OrderLookupResponse(found=True, order=order)


@app.get("/api/orders/topup/options", response_model=TopUpOptionsResponse)
async def orders_topup_options(
    order_id: str = Query(..., alias="orderId"),
    email: str = Query(...),
):
    try:
        row = db.lookup_order(order_id, email)
    except db.SupabaseRepositoryError as exc:
        raise _db_error(exc) from exc
    if not row:
        return TopUpOptionsResponse(
            success=False,
            supported=False,
            reason="Order not found for that email.",
        )
    from app.api.paypal_checkout import paypal_enabled
    from app.services.esim_topup import topup_capabilities_async

    order_row = db.get_order_row_by_order_number(row.order_number)
    if not order_row:
        return TopUpOptionsResponse(success=False, supported=False, reason="Order not found.")
    caps = await topup_capabilities_async(order_row)
    return TopUpOptionsResponse(
        success=True,
        supported=bool(caps.get("supported")),
        provider=caps.get("provider"),
        mode=caps.get("mode"),
        amounts_usd=list(caps.get("amounts_usd") or []),
        packages=list(caps.get("packages") or []),
        min_usd=caps.get("min_usd"),
        max_usd=caps.get("max_usd"),
        reason=caps.get("reason"),
        order_number=row.order_number,
        paypal_available=paypal_enabled(),
    )


@app.post("/api/orders/topup/session", response_model=TopUpSessionResponse)
async def orders_topup_session(body: TopUpSessionRequest):
    try:
        looked_up = db.lookup_order(body.order_id, str(body.email))
    except db.SupabaseRepositoryError as exc:
        raise _db_error(exc) from exc
    if not looked_up:
        return TopUpSessionResponse(
            success=False,
            message="Order not found for that email.",
        )

    row = db.get_order_row_by_order_number(looked_up.order_number)
    if not row:
        return TopUpSessionResponse(success=False, message="Order not found.")

    from app.services.esim_topup import TopUpError, resolve_topup_checkout_quote

    try:
        quote = await resolve_topup_checkout_quote(
            row,
            fund_usd=body.fund_usd,
            offer_id=body.offer_id,
            package_slug=body.package_slug,
            package_code=body.package_code,
            period_num=body.period_num,
        )
    except TopUpError as exc:
        return TopUpSessionResponse(success=False, message=str(exc))

    from .stripe_checkout import StripeCheckoutError, create_topup_checkout_session

    try:
        session = create_topup_checkout_session(
            parent_order_number=looked_up.order_number,
            parent_order_id=str(row["id"]),
            email=str(body.email),
            iccid=str(quote["iccid"]),
            fund_usd=quote.get("fund_usd"),
            retail_cents=int(quote["retail_cents"]),
            display_name=str(quote["display_name"]),
            topup_provider=str(quote["topup_provider"]),
            offer_id=quote.get("offer_id"),
            package_slug=quote.get("package_slug"),
            package_code=quote.get("package_code"),
            period_num=quote.get("period_num"),
            wholesale_usd=quote.get("wholesale_usd"),
        )
    except StripeCheckoutError as exc:
        logger.error("Top-up checkout failed: %s", exc)
        return TopUpSessionResponse(
            success=False,
            message="Could not start payment. Try again in a minute.",
        )

    return TopUpSessionResponse(
        success=True,
        checkout_url=session.url,
        session_id=session.id,
        retail_usd=float(quote["retail_usd"]),
        fund_usd=quote.get("fund_usd"),
        offer_id=quote.get("offer_id"),
        message="Redirect to Stripe to add data to your eSIM.",
    )


@app.post("/api/orders/topup/paypal/create", response_model=TopUpPayPalCreateResponse)
async def orders_topup_paypal_create(body: TopUpSessionRequest):
    from app.api.paypal_checkout import PayPalCheckoutError, create_paypal_order, paypal_enabled

    if not paypal_enabled():
        return TopUpPayPalCreateResponse(
            success=False,
            message="PayPal checkout is not configured yet.",
        )

    try:
        looked_up = db.lookup_order(body.order_id, str(body.email))
    except db.SupabaseRepositoryError as exc:
        raise _db_error(exc) from exc
    if not looked_up:
        return TopUpPayPalCreateResponse(
            success=False,
            message="Order not found for that email.",
        )

    row = db.get_order_row_by_order_number(looked_up.order_number)
    if not row:
        return TopUpPayPalCreateResponse(success=False, message="Order not found.")

    from app.services.esim_topup import TopUpError, resolve_topup_checkout_quote

    try:
        quote = await resolve_topup_checkout_quote(
            row,
            fund_usd=body.fund_usd,
            offer_id=body.offer_id,
            package_slug=body.package_slug,
            package_code=body.package_code,
            period_num=body.period_num,
        )
    except TopUpError as exc:
        return TopUpPayPalCreateResponse(success=False, message=str(exc))

    order_number = looked_up.order_number
    retail_usd = float(quote["retail_usd"])
    success_url = (
        f"{settings.app_url.rstrip('/')}/dashboard"
        f"?orderId={order_number}&email={str(body.email).strip().lower()}&topup=1&paypal=1"
    )
    cancel_url = f"{settings.app_url.rstrip('/')}/dashboard"

    try:
        paypal_order_id = create_paypal_order(
            order_number=f"TOPUP:{order_number}",
            amount_usd=retail_usd,
            description=str(quote["display_name"]),
            return_url=success_url,
            cancel_url=cancel_url,
        )
    except PayPalCheckoutError as exc:
        logger.error("PayPal top-up create failed for %s: %s", order_number, exc)
        return TopUpPayPalCreateResponse(
            success=False,
            message="Could not start PayPal. Try again in a minute.",
        )

    pending = {
        paypal_order_id: {
            "created_at": datetime.now(timezone.utc).isoformat(),
            "email": str(body.email).strip().lower(),
            "topup_provider": quote["topup_provider"],
            "retail_cents": int(quote["retail_cents"]),
            "retail_usd": retail_usd,
            "fund_usd": quote.get("fund_usd"),
            "offer_id": quote.get("offer_id"),
            "package_slug": quote.get("package_slug"),
            "package_code": quote.get("package_code"),
            "period_num": quote.get("period_num"),
            "wholesale_usd": quote.get("wholesale_usd"),
            "iccid": quote.get("iccid"),
        }
    }
    try:
        db.merge_order_metadata(order_number, {"pending_paypal_topups": pending})
    except db.SupabaseRepositoryError as exc:
        logger.error("Could not store PayPal top-up pending for %s: %s", order_number, exc)
        return TopUpPayPalCreateResponse(
            success=False,
            message="Could not start PayPal. Try again in a minute.",
        )

    return TopUpPayPalCreateResponse(
        success=True,
        paypal_order_id=paypal_order_id,
        retail_usd=retail_usd,
        fund_usd=quote.get("fund_usd"),
        offer_id=quote.get("offer_id"),
        message="PayPal top-up order created.",
    )


@app.post("/api/orders/topup/paypal/capture", response_model=TopUpPayPalCaptureResponse)
async def orders_topup_paypal_capture(body: TopUpPayPalCaptureRequest):
    from app.api.paypal_checkout import PayPalCheckoutError, capture_paypal_order, paypal_enabled

    if not paypal_enabled():
        return TopUpPayPalCaptureResponse(
            success=False,
            message="PayPal checkout is not configured yet.",
        )

    try:
        looked_up = db.lookup_order(body.order_id, str(body.email))
    except db.SupabaseRepositoryError as exc:
        raise _db_error(exc) from exc
    if not looked_up:
        return TopUpPayPalCaptureResponse(
            success=False,
            message="Order not found for that email.",
        )

    row = db.get_order_row_by_order_number(looked_up.order_number)
    if not row:
        return TopUpPayPalCaptureResponse(success=False, message="Order not found.")

    meta = row.get("metadata") if isinstance(row.get("metadata"), dict) else {}
    pending_map = meta.get("pending_paypal_topups") if isinstance(meta, dict) else None
    pending = None
    if isinstance(pending_map, dict):
        pending = pending_map.get(body.paypal_order_id)
    if not isinstance(pending, dict):
        return TopUpPayPalCaptureResponse(
            success=False,
            message="PayPal top-up session expired. Please choose an amount again.",
        )

    try:
        payload, custom_id, payer_email = capture_paypal_order(body.paypal_order_id)
    except PayPalCheckoutError as exc:
        logger.error("PayPal top-up capture failed for %s: %s", looked_up.order_number, exc)
        return TopUpPayPalCaptureResponse(success=False, message=str(exc))

    expected_order = f"TOPUP:{looked_up.order_number}"
    if custom_id and custom_id != expected_order and custom_id != looked_up.order_number:
        logger.error(
            "PayPal top-up custom_id mismatch for %s: %s",
            looked_up.order_number,
            custom_id,
        )
        return TopUpPayPalCaptureResponse(
            success=False,
            message="PayPal payment does not match this order.",
        )

    nl = payload.get("_noorlink") if isinstance(payload.get("_noorlink"), dict) else {}
    amount_raw = nl.get("amount_value")
    try:
        paid_cents = int(round(float(amount_raw) * 100)) if amount_raw is not None else 0
    except (TypeError, ValueError):
        paid_cents = 0
    expected_cents = int(pending.get("retail_cents") or 0)
    if expected_cents and paid_cents and expected_cents != paid_cents:
        logger.error(
            "PayPal top-up amount mismatch for %s: expected %s got %s",
            looked_up.order_number,
            expected_cents,
            paid_cents,
        )
        return TopUpPayPalCaptureResponse(
            success=False,
            message="PayPal amount does not match this top-up.",
        )

    from app.services.esim_topup import TopUpError, process_topup_checkout

    period_num = pending.get("period_num")
    try:
        period_num = int(period_num) if period_num is not None else None
    except (TypeError, ValueError):
        period_num = None

    try:
        await process_topup_checkout(
            order_number=looked_up.order_number,
            fund_usd=float(pending["fund_usd"]) if pending.get("fund_usd") is not None else None,
            offer_id=pending.get("offer_id"),
            package_slug=pending.get("package_slug"),
            package_code=pending.get("package_code"),
            period_num=period_num,
            topup_provider=pending.get("topup_provider"),
            retail_cents=expected_cents or None,
            stripe_session_id=f"paypal:{body.paypal_order_id}",
            buyer_email=payer_email or str(body.email).strip().lower(),
        )
    except TopUpError as exc:
        logger.error("PayPal top-up fulfillment failed for %s: %s", looked_up.order_number, exc)
        return TopUpPayPalCaptureResponse(success=False, message=str(exc)[:200])

    # Clear this pending entry
    if isinstance(pending_map, dict):
        remaining = {k: v for k, v in pending_map.items() if k != body.paypal_order_id}
        try:
            client = db.get_supabase_client()
            fresh = db.get_order_row_by_order_number(looked_up.order_number) or row
            fresh_meta = fresh.get("metadata") if isinstance(fresh.get("metadata"), dict) else {}
            fresh_meta = {**fresh_meta, "pending_paypal_topups": remaining}
            client.table("orders").update({"metadata": fresh_meta}).eq(
                "order_number", looked_up.order_number
            ).execute()
        except Exception:
            logger.warning(
                "Could not clear pending PayPal top-up for %s", looked_up.order_number
            )

    return TopUpPayPalCaptureResponse(
        success=True,
        order_number=looked_up.order_number,
        message="PayPal top-up completed.",
    )


@app.get("/api/orders/lookup", response_model=OrderLookupResponse)
async def orders_lookup(
    request: Request,
    order_id: str = Query(..., alias="orderId"),
    email: str = Query(...),
    refresh: bool = Query(False),
):
    from app.services.api_rate_limit import check_rate_limit

    forwarded = request.headers.get("x-forwarded-for")
    ip_address = (
        forwarded.split(",")[0].strip()
        if forwarded
        else (request.client.host if request.client else "unknown")
    )
    allowed, retry_after = check_rate_limit(
        f"order-lookup:{ip_address}",
        max_calls=30,
        window_seconds=60,
    )
    if not allowed:
        raise HTTPException(
            status_code=429,
            detail=f"Too many order lookups. Try again in {retry_after} seconds.",
        )

    try:
        order = db.lookup_order(order_id, email)
    except db.SupabaseRepositoryError as exc:
        raise _db_error(exc) from exc
    if not order:
        return OrderLookupResponse(found=False, order=None)
    try:
        row = db.get_order_row_by_order_number(order.order_number)
    except db.SupabaseRepositoryError as exc:
        raise _db_error(exc) from exc
    if not row:
        return OrderLookupResponse(found=True, order=order)
    return _lookup_order_response(row, refresh=refresh)


@app.post("/api/orders/resend-esim", response_model=OrderResendEsResponse)
async def orders_resend_esim(body: OrderResendEsRequest, request: Request):
    from app.services.api_rate_limit import check_rate_limit
    from app.services.customer_self_service import (
        CustomerSelfServiceError,
        customer_resend_esim_email,
    )
    from app.services.security_threats import log_security_event

    forwarded = request.headers.get("x-forwarded-for")
    ip_address = forwarded.split(",")[0].strip() if forwarded else (
        request.client.host if request.client else None
    )

    allowed, retry_after = check_rate_limit(
        f"order-resend:{ip_address or 'unknown'}",
        max_calls=10,
        window_seconds=60,
    )
    if not allowed:
        raise HTTPException(
            status_code=429,
            detail=f"Too many resend attempts. Try again in {retry_after} seconds.",
        )

    try:
        result = customer_resend_esim_email(
            order_number=body.order_id,
            email=str(body.email),
        )
    except CustomerSelfServiceError as exc:
        log_security_event(
            threat_type="order_probe",
            source="customer_resend",
            message=str(exc)[:500],
            severity="info",
            ip_address=ip_address,
            order_number=body.order_id.strip().upper(),
        )
        return OrderResendEsResponse(success=False, message=str(exc))
    except db.SupabaseRepositoryError as exc:
        raise _db_error(exc) from exc

    return OrderResendEsResponse(
        success=True,
        order_number=result.get("order_number"),
        message="QR email sent — check inbox and spam.",
    )


@app.get("/api/orders/support-messages", response_model=OrderSupportMessagesResponse)
async def orders_support_messages(
    order_id: str = Query(..., alias="orderId"),
    email: str = Query(...),
):
    try:
        order = db.lookup_order(order_id, email)
    except db.SupabaseRepositoryError as exc:
        raise _db_error(exc) from exc
    if not order:
        return OrderSupportMessagesResponse(
            success=False,
            message="Order not found for that email.",
        )

    try:
        from app.db.engine import get_engine
        from app.services.support_messaging import (
            SupportMessagingError,
            list_messages_for_order,
            list_tickets_for_order,
        )

        if get_engine() is None:
            return OrderSupportMessagesResponse(
                success=True,
                messages=[],
                message="Support messaging not available yet.",
            )

        messages = list_messages_for_order(order.order_number, customer_email=str(email))
        tickets = list_tickets_for_order(order.order_number)
        ticket_number = tickets[0].ticket_number if tickets else None
        return OrderSupportMessagesResponse(
            success=True,
            messages=messages,
            ticket_number=ticket_number,
        )
    except SupportMessagingError as exc:
        return OrderSupportMessagesResponse(success=False, message=str(exc))


@app.get("/api/orders/by-session", response_model=OrderLookupResponse)
async def orders_by_stripe_session(
    session_id: str = Query(..., alias="sessionId", min_length=8),
    email: str = Query(..., min_length=3),
):
    """Post-checkout success page — resolve order from Stripe session_id + email."""
    try:
        order = db.lookup_order_by_stripe_session(session_id, email=email)
    except db.SupabaseRepositoryError as exc:
        raise _db_error(exc) from exc
    if not order:
        return OrderLookupResponse(
            found=False,
            order=None,
            message="Order not found yet. Refresh in a minute or use My eSIMs.",
        )
    return OrderLookupResponse(found=True, order=order)


@app.get("/api/orders/by-payment-intent", response_model=OrderLookupResponse)
async def orders_by_stripe_payment_intent(
    payment_intent_id: str = Query(..., alias="paymentIntentId", min_length=8),
    email: str = Query(..., min_length=3),
):
    """Success page after Express Checkout (Apple Pay / Google Pay / Link)."""
    try:
        order = db.lookup_order_by_stripe_payment_intent(
            payment_intent_id,
            email=email,
        )
    except db.SupabaseRepositoryError as exc:
        raise _db_error(exc) from exc
    if not order:
        return OrderLookupResponse(
            found=False,
            order=None,
            message="Order not found yet. Refresh in a minute or use My eSIMs.",
        )
    return OrderLookupResponse(found=True, order=order)


@app.get("/api/checkout/config", response_model=CheckoutConfigResponse)
async def checkout_config():
    """Publishable key for on-page Express Checkout Element."""
    settings = get_settings()
    key = (settings.stripe_publishable_key or "").strip()
    if not key:
        raise HTTPException(status_code=503, detail="Stripe publishable key not configured")
    return CheckoutConfigResponse(publishable_key=key)


@app.get("/api/checkout/paypal/config", response_model=PayPalConfigResponse)
async def paypal_config():
    """Public PayPal client id when Business checkout is configured."""
    from app.api.paypal_checkout import paypal_enabled

    settings = get_settings()
    enabled = paypal_enabled()
    return PayPalConfigResponse(
        enabled=enabled,
        client_id=(settings.paypal_client_id or "").strip() or None if enabled else None,
        mode=(settings.paypal_mode or "sandbox").strip().lower() or "sandbox",
    )


@app.post("/api/checkout/paypal/create-order", response_model=PayPalCreateOrderResponse)
async def paypal_create_order(body: CheckoutSessionRequest):
    """Create pending NoorLink order + PayPal order for Smart Buttons."""
    from app.api.paypal_checkout import (
        PayPalCheckoutError,
        create_paypal_order,
        paypal_enabled,
    )

    if not paypal_enabled():
        raise HTTPException(status_code=503, detail="PayPal checkout is not configured yet.")
    if body.is_gift:
        raise HTTPException(
            status_code=400,
            detail="Gift orders use card checkout. Please use the gift form.",
        )

    catalog_price, pricing = _prepare_checkout_pricing(body)
    from app.services.affiliates import affiliate_metadata_patch

    promo = pricing.promo
    affiliate_meta = (
        affiliate_metadata_patch(pricing.affiliate).get("affiliate")
        if pricing.affiliate
        else None
    )
    attribution_meta = _checkout_attribution_metadata(body)
    buyer_email = _checkout_buyer_email(body)

    try:
        created = db.create_order(
            email=buyer_email,
            country=body.country,
            price=catalog_price,
            flag=body.flag,
            travel_date=body.travel_date,
            package_id=body.package_id,
            phone=body.phone,
            promo_code=promo.code if promo else None,
            promo_discount_cents=promo.discount_cents if promo else None,
            promo_subtotal_cents=pricing.subtotal_cents if promo else None,
            total_discount_cents=pricing.discount_cents,
            affiliate_metadata=affiliate_meta,
            attribution_metadata=attribution_meta,
            wants_topup=bool(body.wants_topup),
        )
    except db.ManagedPackagePriceMismatchError as exc:
        raise HTTPException(
            status_code=400,
            detail="Package price does not match our catalog. Refresh and try again.",
        ) from exc
    except db.SupabaseRepositoryError as exc:
        raise _db_error(exc) from exc
    except Exception as exc:
        logger.exception("Unexpected PayPal checkout order failure")
        raise HTTPException(
            status_code=503,
            detail="Checkout is temporarily unavailable. Please try again.",
        ) from exc

    order = created.order
    settings = get_settings()
    return_url = f"{settings.app_url.rstrip('/')}/success"
    cancel_url = f"{settings.app_url.rstrip('/')}/checkout?canceled=1"

    try:
        paypal_order_id = create_paypal_order(
            order_number=order.order_number,
            amount_usd=float(order.price),
            description=order.package_name or f"{order.country} eSIM",
            return_url=return_url,
            cancel_url=cancel_url,
        )
        db.merge_order_metadata(
            order.order_number,
            {
                "paypal": {
                    "order_id": paypal_order_id,
                    "mode": (settings.paypal_mode or "sandbox").strip().lower(),
                }
            },
        )
    except PayPalCheckoutError as exc:
        logger.error("PayPal create-order failed for %s: %s", order.order_number, exc)
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except db.SupabaseRepositoryError as exc:
        raise _db_error(exc) from exc

    return PayPalCreateOrderResponse(
        success=True,
        paypal_order_id=paypal_order_id,
        order_id=order.order_number,
        final_price=float(order.price),
        message="PayPal order created.",
    )


@app.post("/api/checkout/paypal/capture", response_model=PayPalCaptureResponse)
async def paypal_capture(body: PayPalCaptureRequest):
    """Capture an approved PayPal order and fulfill the eSIM."""
    from app.api.paypal_checkout import PayPalCheckoutError, capture_paypal_order, paypal_enabled

    if not paypal_enabled():
        raise HTTPException(status_code=503, detail="PayPal checkout is not configured yet.")

    try:
        payload, order_number, payer_email = capture_paypal_order(body.paypal_order_id)
    except PayPalCheckoutError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    if not order_number:
        logger.error("PayPal capture missing order_number for %s", body.paypal_order_id)
        raise HTTPException(status_code=502, detail="PayPal payment missing order reference.")

    meta = payload.get("_noorlink") if isinstance(payload, dict) else {}
    capture_id = None
    amount_value = None
    if isinstance(meta, dict):
        capture_id = meta.get("capture_id")
        amount_value = meta.get("amount_value")

    try:
        row = db.get_order_row_by_order_number(order_number)
    except db.SupabaseRepositoryError as exc:
        raise _db_error(exc) from exc
    if not row:
        raise HTTPException(status_code=404, detail="Order not found for this PayPal payment.")

    expected_cents = int(row.get("amount_cents") or round(float(row.get("price") or 0) * 100))
    if amount_value is not None:
        try:
            received_cents = int(round(float(amount_value) * 100))
        except (TypeError, ValueError):
            received_cents = 0
        if expected_cents and received_cents and expected_cents != received_cents:
            logger.error(
                "PayPal amount mismatch for %s: expected %s got %s",
                order_number,
                expected_cents,
                received_cents,
            )
            raise HTTPException(status_code=400, detail="PayPal amount does not match this order.")

    if payer_email and "@" in payer_email:
        try:
            db.update_order_customer_email(order_number, payer_email)
        except db.SupabaseRepositoryError as exc:
            logger.warning("PayPal email patch failed for %s: %s", order_number, exc)

    try:
        db.merge_order_metadata(
            order_number,
            {
                "paypal": {
                    "order_id": body.paypal_order_id,
                    "capture_id": capture_id,
                    "status": "COMPLETED",
                }
            },
        )
    except db.SupabaseRepositoryError as exc:
        logger.warning("PayPal metadata merge failed for %s: %s", order_number, exc)

    try:
        process_paid_order(order_number=order_number)
    except FulfillmentError as exc:
        logger.error("Fulfillment failed after PayPal for %s: %s", order_number, exc)
        # Payment captured — still send buyer to success; ops alert like Stripe path
        try:
            notify_fulfillment_failure(
                order_number=order_number,
                email=str(payer_email or row.get("email") or ""),
                country=str(row.get("country") or ""),
                package_name=str(row.get("package_name") or "Travel eSIM"),
                error=str(exc),
                context="paypal_capture",
                order_status="paid",
            )
        except Exception:
            logger.exception("Ops alert failed after PayPal for %s", order_number)
    except db.SupabaseRepositoryError as exc:
        raise _db_error(exc) from exc

    final_email = payer_email or str(row.get("email") or "")
    if final_email.endswith("@checkout.noorlink.pending"):
        final_email = payer_email or ""

    return PayPalCaptureResponse(
        success=True,
        order_id=order_number,
        email=final_email or None,
        message="PayPal payment captured.",
    )


@app.post("/api/checkout/payment-intent", response_model=ExpressPaymentIntentResponse)
async def checkout_payment_intent(body: CheckoutSessionRequest):
    """Create order + PaymentIntent for Apple Pay / Google Pay / Link on-page."""
    if body.is_gift:
        raise HTTPException(
            status_code=400,
            detail="Gift orders use secure card checkout. Please use the gift form.",
        )
    catalog_price, pricing = _prepare_checkout_pricing(body)
    from app.services.affiliates import affiliate_metadata_patch

    promo = pricing.promo
    affiliate_meta = (
        affiliate_metadata_patch(pricing.affiliate).get("affiliate")
        if pricing.affiliate
        else None
    )
    attribution_meta = _checkout_attribution_metadata(body)

    buyer_email = _checkout_buyer_email(body)

    try:
        created = db.create_order(
            email=buyer_email,
            country=body.country,
            price=catalog_price,
            flag=body.flag,
            travel_date=body.travel_date,
            package_id=body.package_id,
            phone=body.phone,
            promo_code=promo.code if promo else None,
            promo_discount_cents=promo.discount_cents if promo else None,
            promo_subtotal_cents=pricing.subtotal_cents if promo else None,
            total_discount_cents=pricing.discount_cents,
            affiliate_metadata=affiliate_meta,
            attribution_metadata=attribution_meta,
            wants_topup=bool(body.wants_topup),
        )
    except db.ManagedPackagePriceMismatchError as exc:
        raise HTTPException(
            status_code=400,
            detail="Package price does not match our catalog. Refresh and try again.",
        ) from exc
    except db.SupabaseRepositoryError as exc:
        raise _db_error(exc) from exc
    except Exception as exc:
        logger.exception("Unexpected express checkout order failure")
        raise HTTPException(
            status_code=503,
            detail="Checkout is temporarily unavailable. Please try again.",
        ) from exc

    order = created.order
    amount_cents = int(round(order.price * 100))

    try:
        intent = create_stripe_payment_intent(
            order_number=order.order_number,
            order_id=created.order_id,
            email=None if _is_pending_checkout_email(buyer_email) else buyer_email,
            amount_cents=amount_cents,
            currency=order.currency,
            package_name=order.package_name,
        )
        db.update_order_stripe_payment_intent(order.order_number, intent.id)
    except StripeCheckoutError as exc:
        logger.error("Stripe PaymentIntent failed: %s", exc)
        raise HTTPException(
            status_code=502,
            detail="Payment could not be started. Please try again.",
        ) from exc
    except db.SupabaseRepositoryError as exc:
        raise _db_error(exc) from exc

    return ExpressPaymentIntentResponse(
        success=True,
        client_secret=intent.client_secret,
        payment_intent_id=intent.id,
        order_id=order.order_number,
        final_price=float(order.price),
        discount_amount=round(pricing.discount_cents / 100.0, 2) if pricing.discount_cents else None,
        affiliate_ref=pricing.affiliate.code if pricing.affiliate else None,
        message="PaymentIntent created for express wallets.",
    )


@app.post("/api/checkout/session", response_model=CheckoutSessionResponse)
async def checkout_session(body: CheckoutSessionRequest):
    _validate_gift_checkout(body)
    if body.is_gift:
        body = body.model_copy(update={"affiliate_ref": None, "promo_code": None})
    catalog_price, pricing = _prepare_checkout_pricing(body)
    from app.services.affiliates import affiliate_metadata_patch

    promo = pricing.promo
    promo_code_value = (
        normalize_code(body.promo_code) if body.promo_code and body.promo_code.strip() else None
    )
    affiliate_meta = (
        affiliate_metadata_patch(pricing.affiliate).get("affiliate")
        if pricing.affiliate and not body.is_gift
        else None
    )
    gift_meta = _build_gift_metadata(body)
    attribution_meta = None if body.is_gift else _checkout_attribution_metadata(body)
    buyer_email = _checkout_buyer_email(body)

    try:
        created = db.create_order(
            email=buyer_email,
            country=body.country,
            price=catalog_price,
            flag=body.flag,
            travel_date=body.travel_date,
            package_id=body.package_id,
            phone=body.phone,
            promo_code=promo.code if promo and not body.is_gift else None,
            promo_discount_cents=promo.discount_cents if promo and not body.is_gift else None,
            promo_subtotal_cents=pricing.subtotal_cents if promo and not body.is_gift else None,
            total_discount_cents=pricing.discount_cents if not body.is_gift else 0,
            affiliate_metadata=affiliate_meta,
            attribution_metadata=attribution_meta,
            gift_metadata=gift_meta,
            wants_topup=bool(body.wants_topup),
        )
    except db.ManagedPackagePriceMismatchError as exc:
        raise HTTPException(
            status_code=400,
            detail="Package price does not match our catalog. Refresh and try again.",
        ) from exc
    except db.SupabaseRepositoryError as exc:
        raise _db_error(exc) from exc
    except Exception as exc:
        logger.exception("Unexpected checkout order failure")
        raise HTTPException(
            status_code=503,
            detail=(
                "Checkout is temporarily unavailable. "
                "Confirm Supabase commerce tables exist "
                "(run supabase/bootstrap_checkout_minimal.sql)."
            ),
        ) from exc

    order = created.order
    amount_cents = int(round(order.price * 100))

    try:
        session = create_stripe_checkout_session(
            order_number=order.order_number,
            order_id=created.order_id,
            email=None if _is_pending_checkout_email(buyer_email) else buyer_email,
            package=created.package,
            package_name=order.package_name,
            amount_cents=amount_cents,
            currency=order.currency,
            force_custom_price=pricing.force_custom_price or bool(body.is_gift),
            is_gift=bool(body.is_gift),
        )
        db.update_order_stripe_session(order.order_number, session.id)
    except StripeCheckoutError as exc:
        logger.error("Stripe checkout failed: %s", exc)
        raise HTTPException(
            status_code=502,
            detail="Payment session could not be created. Please try again.",
        ) from exc
    except db.SupabaseRepositoryError as exc:
        raise _db_error(exc) from exc

    # Acknowledgment email should not block redirect to Stripe.
    email_sent = False
    email_error: str | None = None
    skip_ack = _is_pending_checkout_email(buyer_email)
    try:
        if skip_ack:
            pass
        elif body.is_gift and gift_meta:
            from app.services.email_service import send_gift_checkout_acknowledgment

            send_gift_checkout_acknowledgment(
                to_email=buyer_email,
                order_number=order.order_number,
                country=order.country,
                package_name=order.package_name,
                amount=float(order.price),
                currency=order.currency or "USD",
                flag_emoji=order.flag,
                checkout_url=session.url,
                recipient_name=str(gift_meta["recipient_name"]),
                recipient_email=str(gift_meta["recipient_email"]),
            )
            email_sent = True
        else:
            send_checkout_acknowledgment(
                to_email=buyer_email,
                order_number=order.order_number,
                country=order.country,
                package_name=order.package_name,
                amount=float(order.price),
                currency=order.currency or "USD",
                flag_emoji=order.flag,
                checkout_url=session.url,
            )
            email_sent = True
    except EmailDeliveryError as exc:
        email_error = str(exc)[:400]
        logger.error(
            "Checkout acknowledgment email failed for %s: %s",
            order.order_number,
            exc,
        )
        try:
            db.merge_order_metadata(
                order.order_number,
                {"fulfillment": {"ack_email_error": email_error}},
            )
        except Exception:
            logger.warning(
                "Could not persist ack email error for %s",
                order.order_number,
                exc_info=True,
            )

    return CheckoutSessionResponse(
        success=True,
        session_id=session.id,
        checkout_url=session.url,
        order_id=order.order_number,
        message=(
            "Confirmation email sent. Redirect to Stripe to complete payment."
            if email_sent
            else (
                "Payment session created. Enter your email on Stripe if you skipped it here."
                if skip_ack
                else (
                    "Payment session created, but confirmation email failed. "
                    "You can still complete payment on Stripe."
                )
            )
        ),
        email_sent=email_sent,
        email_error=email_error,
        discount_amount=(
            round(pricing.discount_cents / 100.0, 2) if pricing.discount_cents else None
        ),
        final_price=float(order.price),
        promo_code=promo_code_value if promo else None,
        affiliate_ref=pricing.affiliate.code if pricing.affiliate else None,
    )


@app.post("/api/stripe/webhook")
async def stripe_webhook(
    request: Request,
    stripe_signature: str = Header(None, alias="Stripe-Signature"),
):
    payload = await request.body()

    try:
        event = construct_stripe_event(payload, stripe_signature)
    except StripeWebhookError as exc:
        logger.warning("Stripe webhook rejected: %s", exc)
        from app.services.security_threats import log_security_event

        forwarded = request.headers.get("x-forwarded-for")
        ip_address = forwarded.split(",")[0].strip() if forwarded else (
            request.client.host if request.client else None
        )
        log_security_event(
            threat_type="webhook_rejected",
            source="stripe_webhook",
            message=str(exc)[:500],
            severity="warning",
            ip_address=ip_address,
        )
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if event.type == "payment_intent.succeeded":
        intent_data = extract_payment_intent_succeeded(event)
        if not intent_data:
            return JSONResponse({"received": True, "handled": False})

        order_number = intent_data.get("order_number")
        payment_intent_id = intent_data.get("payment_intent_id")

        if not order_number and payment_intent_id:
            try:
                row = db.get_order_row_by_stripe_payment_intent(payment_intent_id)
                if row:
                    order_number = row.get("order_number")
            except db.SupabaseRepositoryError as exc:
                raise _db_error(exc) from exc

        if not order_number:
            logger.error("payment_intent.succeeded missing order identifiers")
            return JSONResponse({"received": True, "handled": False})

        try:
            row = db.get_order_row_by_order_number(order_number)
            if row is None and payment_intent_id:
                row = db.get_order_row_by_stripe_payment_intent(payment_intent_id)
        except db.SupabaseRepositoryError as exc:
            raise _db_error(exc) from exc

        if row and not _verify_stripe_paid_amount(row, event):
            logger.error(
                "Blocking fulfillment for %s due to Stripe amount mismatch",
                order_number,
            )
            return JSONResponse(
                {
                    "received": True,
                    "handled": False,
                    "error": "amount_mismatch",
                    "order_number": order_number,
                }
            )

        paid_email = str(intent_data.get("customer_email") or "").strip().lower()
        if order_number and paid_email and "@" in paid_email:
            try:
                db.update_order_customer_email(str(order_number), paid_email)
            except db.SupabaseRepositoryError as exc:
                logger.warning(
                    "Could not patch buyer email from PaymentIntent for %s: %s",
                    order_number,
                    exc,
                )

        try:
            process_paid_order(
                order_number=order_number,
                stripe_payment_intent_id=payment_intent_id,
            )
        except FulfillmentError as exc:
            logger.error(
                "Fulfillment failed after express payment for %s: %s",
                order_number,
                exc,
            )
            from app.services.ops_event_log import log_ops_event

            log_ops_event(
                event_type="stripe_webhook",
                source="stripe_webhook_express",
                severity="error",
                order_number=order_number,
                message=f"Fulfillment failed: {exc}",
            )
            try:
                row = db.get_order_row_by_order_number(order_number)
                if row is None and payment_intent_id:
                    row = db.get_order_row_by_stripe_payment_intent(payment_intent_id)
                if row:
                    notify_fulfillment_failure(
                        order_number=str(row.get("order_number") or order_number or ""),
                        email=str(row.get("email") or ""),
                        country=str(row.get("country") or ""),
                        package_name=str(row.get("package_name") or "Travel eSIM"),
                        error=str(exc),
                        context="stripe_webhook_express",
                        order_status=str(row.get("status") or "paid"),
                    )
            except Exception:
                logger.exception(
                    "Ops alert failed in express stripe webhook for %s", order_number
                )
            return JSONResponse(
                {
                    "received": True,
                    "handled": True,
                    "fulfillment": "partial",
                    "order_number": order_number,
                }
            )

        from app.services.ops_event_log import log_ops_event

        log_ops_event(
            event_type="stripe_webhook",
            source="stripe_webhook_express",
            order_number=order_number,
            message="payment_intent.succeeded processed",
        )
        return JSONResponse({"received": True, "handled": True})

    if event.type != "checkout.session.completed":
        return JSONResponse({"received": True, "handled": False})

    session_data = extract_checkout_session_completed(event)
    if not session_data:
        return JSONResponse({"received": True, "handled": False})

    if session_data.get("checkout_type") == "topup":
        order_number = session_data.get("order_number")
        topup_provider = str(session_data.get("topup_provider") or "").strip().lower()
        fund_raw = session_data.get("fund_usd")
        fund_usd = None
        if fund_raw not in (None, ""):
            try:
                fund_usd = float(fund_raw)
            except (TypeError, ValueError):
                fund_usd = None

        period_raw = session_data.get("period_num")
        period_num = None
        if period_raw not in (None, ""):
            try:
                period_num = int(period_raw)
            except (TypeError, ValueError):
                period_num = None

        retail_raw = session_data.get("retail_cents")
        retail_cents = None
        if retail_raw not in (None, ""):
            try:
                retail_cents = int(retail_raw)
            except (TypeError, ValueError):
                retail_cents = None

        from app.services.esim_topup import TopUpError, process_topup_checkout, topup_retail_cents

        if topup_provider == "esimaccess":
            expected_cents = retail_cents
        elif fund_usd is not None:
            expected_cents = topup_retail_cents(fund_usd)
        else:
            logger.error("Top-up webhook missing amount metadata for %s", order_number)
            return JSONResponse({"received": True, "handled": False})

        received_cents = session_data.get("amount_cents") or 0
        if expected_cents and received_cents and expected_cents != received_cents:
            logger.error(
                "Top-up amount mismatch for %s: expected %s got %s",
                order_number,
                expected_cents,
                received_cents,
            )
            return JSONResponse(
                {
                    "received": True,
                    "handled": False,
                    "error": "amount_mismatch",
                    "order_number": order_number,
                }
            )

        try:
            import asyncio

            asyncio.run(
                process_topup_checkout(
                    order_number=str(order_number or ""),
                    fund_usd=fund_usd,
                    offer_id=session_data.get("offer_id"),
                    package_slug=session_data.get("package_slug"),
                    package_code=session_data.get("package_code"),
                    period_num=period_num,
                    topup_provider=topup_provider or None,
                    retail_cents=retail_cents or expected_cents,
                    stripe_session_id=session_data.get("session_id"),
                    buyer_email=session_data.get("customer_email"),
                )
            )
        except TopUpError as exc:
            logger.error("Top-up fulfillment failed for %s: %s", order_number, exc)
            return JSONResponse(
                {
                    "received": True,
                    "handled": True,
                    "topup": "failed",
                    "order_number": order_number,
                    "error": str(exc)[:200],
                }
            )

        return JSONResponse(
            {
                "received": True,
                "handled": True,
                "topup": "completed",
                "order_number": order_number,
                "fund_usd": fund_usd,
                "topup_provider": topup_provider or "citrus",
                "offer_id": session_data.get("offer_id"),
            }
        )

    order_number = session_data.get("order_number")
    session_id = session_data.get("session_id")

    if not order_number and session_id:
        try:
            row = db.get_order_row_by_stripe_session(session_id)
            if row:
                order_number = row.get("order_number")
        except db.SupabaseRepositoryError as exc:
            raise _db_error(exc) from exc

    if not order_number and not session_id:
        logger.error("checkout.session.completed missing order identifiers")
        return JSONResponse({"received": True, "handled": False})

    try:
        row = (
            db.get_order_row_by_order_number(order_number)
            if order_number
            else None
        )
        if row is None and session_id:
            row = db.get_order_row_by_stripe_session(session_id)
    except db.SupabaseRepositoryError as exc:
        raise _db_error(exc) from exc

    if row and not _verify_stripe_paid_amount(row, event):
        logger.error(
            "Blocking fulfillment for %s due to Stripe amount mismatch",
            row.get("order_number") or order_number,
        )
        return JSONResponse(
            {
                "received": True,
                "handled": False,
                "error": "amount_mismatch",
                "order_number": row.get("order_number") or order_number,
            }
        )

    resolved_order_number = str(order_number or (row or {}).get("order_number") or "")
    customer_patch = session_data.get("customer_patch") if isinstance(session_data, dict) else None
    if resolved_order_number and isinstance(customer_patch, dict) and customer_patch:
        try:
            db.merge_order_metadata(resolved_order_number, customer_patch)
        except db.SupabaseRepositoryError as exc:
            logger.warning("Stripe customer metadata merge failed for %s: %s", resolved_order_number, exc)

    paid_email = str(session_data.get("customer_email") or "").strip().lower()
    if resolved_order_number and paid_email and "@" in paid_email:
        try:
            db.update_order_customer_email(resolved_order_number, paid_email)
        except db.SupabaseRepositoryError as exc:
            logger.warning(
                "Could not patch buyer email from Stripe for %s: %s",
                resolved_order_number,
                exc,
            )

    try:
        process_paid_order(
            order_number=order_number,
            stripe_checkout_session_id=session_id,
            stripe_payment_intent_id=session_data.get("payment_intent_id"),
        )
    except FulfillmentError as exc:
        logger.error("Fulfillment failed after payment for %s: %s", order_number, exc)
        from app.services.ops_event_log import log_ops_event

        log_ops_event(
            event_type="stripe_webhook",
            source="stripe_webhook",
            severity="error",
            order_number=order_number,
            message=f"Fulfillment failed: {exc}",
        )
        try:
            row = db.get_order_row_by_order_number(order_number) if order_number else None
            if row is None and session_id:
                row = db.get_order_row_by_stripe_session(session_id)
            if row:
                notify_fulfillment_failure(
                    order_number=str(row.get("order_number") or order_number or ""),
                    email=str(row.get("email") or ""),
                    country=str(row.get("country") or ""),
                    package_name=str(row.get("package_name") or "Travel eSIM"),
                    error=str(exc),
                    context="stripe_webhook",
                    order_status=str(row.get("status") or "paid"),
                )
        except Exception:
            logger.exception("Ops alert failed in stripe webhook for %s", order_number)
        # Payment is recorded; Stripe should not retry indefinitely on email failures
        return JSONResponse(
            {
                "received": True,
                "handled": True,
                "fulfillment": "partial",
                "order_number": order_number,
            }
        )
    except db.SupabaseRepositoryError as exc:
        raise _db_error(exc) from exc

    from app.services.ops_event_log import log_ops_event

    log_ops_event(
        event_type="stripe_webhook",
        source="stripe_webhook",
        order_number=order_number,
        message="checkout.session.completed processed",
    )

    return JSONResponse(
        {
            "received": True,
            "handled": True,
            "order_number": order_number,
        }
    )
