from urllib.parse import quote

from datetime import datetime, timezone
import logging
from typing import Optional

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import get_settings
from app.services.email_service import (
    EmailDeliveryError,
    send_checkout_acknowledgment,
    send_support_ticket_confirmation,
)
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
    ContactFormRequest,
    ContactFormResponse,
    CronRunResponse,
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
    PromoValidateRequest,
    PromoValidateResponse,
    RootResponse,
)

logger = logging.getLogger(__name__)
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


def _db_error(exc: Exception) -> HTTPException:
    logger.error("Database error: %s", exc)
    if _is_production:
        return HTTPException(
            status_code=503,
            detail="Database temporarily unavailable. Please try again.",
        )
    detail = str(exc).strip() or "Database temporarily unavailable. Please try again."
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
    return HTTPException(
        status_code=503,
        detail="Database temporarily unavailable. Please try again.",
    )


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


def _validate_gift_checkout(body: CheckoutSessionRequest) -> None:
    from app.services.gift_orders import validate_gift_checkout

    validate_gift_checkout(body)


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
    db_ok = db.ping_database()
    return HealthResponse(
        status="healthy" if db_ok else "degraded",
        service="noorlink-automation",
        timestamp=datetime.now(timezone.utc).isoformat(),
        version=settings.app_version,
    )


@app.get("/api/diagnostics/email", response_model=EmailDiagnosticsResponse)
async def email_diagnostics(
    probe: bool = Query(False),
    authorization: Optional[str] = Header(None),
):
    """Resend configuration check. probe=1 sends a test email (internal auth in production)."""
    if probe and _is_production:
        require_internal_in_production(authorization)
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
async def test_endpoint(authorization: Optional[str] = Header(None)):
    if _is_production:
        require_internal_in_production(authorization)
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

    return CronRunResponse(
        success=True,
        expired_promos=expired,
        insider=insider_result,
        catalog_sync=catalog_sync,
        expiry_reminders=expiry_reminders,
        message="Cron tasks completed.",
    )


@app.get("/api/fulfillment/resolve", response_model=FulfillmentResolveResponse)
async def fulfillment_resolve(
    country: str = Query(..., min_length=2),
    data_gb: float = Query(..., alias="dataGb", gt=0),
    validity_days: int = Query(..., alias="days", gt=0),
    wants_topup: bool = Query(False, alias="wantsTopUp"),
    authorization: Optional[str] = Header(None),
):
    require_internal_in_production(authorization)
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
    authorization: Optional[str] = Header(None),
):
    require_internal_in_production(authorization)
    """Breakage-fulfillment strategy counts and pilot countries (from WeConnect P1 pricelist)."""
    from app.services.breakage_strategy import strategy_summary

    return BreakageStrategySummaryResponse(success=True, summary=strategy_summary())


@app.get("/api/fulfillment/strategy/country", response_model=BreakageCountryPolicyResponse)
async def breakage_strategy_country(
    country: str = Query(..., min_length=2),
    data_gb: Optional[float] = Query(None, alias="dataGb"),
    validity_days: Optional[int] = Query(None, alias="days"),
    authorization: Optional[str] = Header(None),
):
    require_internal_in_production(authorization)
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
    order_number: str = Query(..., alias="orderNumber", min_length=4),
    email: str = Query(..., min_length=3),
    authorization: Optional[str] = Header(None),
):
    require_internal_in_production(authorization)
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
    try:
        ticket_id = db.create_support_ticket(
            name=body.name,
            email=str(body.email),
            subject=body.subject,
            message=body.message,
        )
    except db.SupabaseRepositoryError as exc:
        raise _db_error(exc) from exc

    try:
        send_support_ticket_confirmation(
            to_email=str(body.email),
            name=body.name,
            ticket_id=ticket_id,
            subject=body.subject,
            message=body.message,
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


@app.get("/api/orders/lookup", response_model=OrderLookupResponse)
async def orders_lookup(
    order_id: str = Query(..., alias="orderId"),
    email: str = Query(...),
):
    try:
        order = db.lookup_order(order_id, email)
    except db.SupabaseRepositoryError as exc:
        raise _db_error(exc) from exc
    if not order:
        return OrderLookupResponse(found=False, order=None)
    return OrderLookupResponse(found=True, order=order)


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

    try:
        created = db.create_order(
            email=str(body.email),
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
            email=str(body.email),
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

    try:
        created = db.create_order(
            email=str(body.email),
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
            email=str(body.email),
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
    try:
        if body.is_gift and gift_meta:
            from app.services.email_service import send_gift_checkout_acknowledgment

            send_gift_checkout_acknowledgment(
                to_email=str(body.email),
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
        else:
            send_checkout_acknowledgment(
                to_email=str(body.email),
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
                "Payment session created, but confirmation email failed. "
                "You can still complete payment on Stripe."
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

        return JSONResponse({"received": True, "handled": True})

    if event.type != "checkout.session.completed":
        return JSONResponse({"received": True, "handled": False})

    session_data = extract_checkout_session_completed(event)
    if not session_data:
        return JSONResponse({"received": True, "handled": False})

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

    try:
        process_paid_order(
            order_number=order_number,
            stripe_checkout_session_id=session_id,
            stripe_payment_intent_id=session_data.get("payment_intent_id"),
        )
    except FulfillmentError as exc:
        logger.error("Fulfillment failed after payment for %s: %s", order_number, exc)
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

    return JSONResponse(
        {
            "received": True,
            "handled": True,
            "order_number": order_number,
        }
    )
