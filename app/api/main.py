from datetime import datetime, timezone
import logging

from fastapi import FastAPI, Header, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import get_settings
from app.services.fulfillment import FulfillmentError, process_paid_order

from .analytics import router as analytics_router
from .devices import check_device
from .devices_router import router as devices_router
from .plans_router import router as plans_router
from . import supabase_repository as db
from .stripe_checkout import StripeCheckoutError, create_stripe_checkout_session
from .stripe_webhook import (
    StripeWebhookError,
    construct_stripe_event,
    extract_checkout_session_completed,
)
from .schemas import (
    ApiTestResponse,
    CheckoutSessionRequest,
    CheckoutSessionResponse,
    ContactFormRequest,
    ContactFormResponse,
    DeviceCheckRequest,
    DeviceCheckResponse,
    HealthResponse,
    NewsletterSubscribeRequest,
    NewsletterSubscribeResponse,
    OrderLookupResponse,
    RootResponse,
)

logger = logging.getLogger(__name__)
settings = get_settings()

app = FastAPI(
    title="NoorLink Automation API",
    description="Automated eSIM purchase and delivery system",
    version=settings.app_version,
    docs_url="/docs",
    redoc_url="/redoc",
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


def _db_error(exc: Exception) -> HTTPException:
    logger.error("Database error: %s", exc)
    return HTTPException(
        status_code=503,
        detail="Database temporarily unavailable. Please try again.",
    )


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


@app.get("/api/test", response_model=ApiTestResponse)
async def test_endpoint():
    return ApiTestResponse(
        success=True,
        message="API is working!",
        environment=settings.environment,
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
    return ContactFormResponse(
        success=True,
        ticket_id=ticket_id,
        message="Your message has been received. We will reply within 24 hours.",
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


@app.post("/api/checkout/session", response_model=CheckoutSessionResponse)
async def checkout_session(body: CheckoutSessionRequest):
    try:
        created = db.create_order(
            email=str(body.email),
            country=body.country,
            price=body.price,
            flag=body.flag,
            travel_date=body.travel_date,
            package_id=body.package_id,
        )
    except db.ManagedPackagePriceMismatchError as exc:
        raise HTTPException(
            status_code=400,
            detail="Package price does not match our catalog. Refresh and try again.",
        ) from exc
    except db.SupabaseRepositoryError as exc:
        raise _db_error(exc) from exc

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

    return CheckoutSessionResponse(
        success=True,
        session_id=session.id,
        checkout_url=session.url,
        order_id=order.order_number,
        message="Redirect to Stripe to complete payment.",
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
        process_paid_order(
            order_number=order_number,
            stripe_checkout_session_id=session_id,
            stripe_payment_intent_id=session_data.get("payment_intent_id"),
        )
    except FulfillmentError as exc:
        logger.error("Fulfillment failed after payment for %s: %s", order_number, exc)
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
