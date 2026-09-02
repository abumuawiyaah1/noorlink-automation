from pydantic import BaseModel, EmailStr, Field
from typing import Literal, Optional


class RootResponse(BaseModel):
    message: str
    status: str
    timestamp: str
    docs: str
    health: str


class HealthResponse(BaseModel):
    status: str
    service: str
    timestamp: str
    version: str


class EmailDiagnosticsResponse(BaseModel):
    ok: bool
    resend_configured: bool
    from_email: str
    from_domain: Optional[str] = None
    expected_domain: str = "noorlink.co"
    domain_matches: bool
    hint: Optional[str] = None
    test_send_ok: Optional[bool] = Field(None, serialization_alias="testSendOk")
    test_send_id: Optional[str] = Field(None, serialization_alias="testSendId")
    test_send_error: Optional[str] = Field(None, serialization_alias="testSendError")

    model_config = {"populate_by_name": True}


class ApiTestResponse(BaseModel):
    success: bool
    message: str
    environment: str


class NewsletterSubscribeRequest(BaseModel):
    email: EmailStr
    dream_destination: Optional[str] = Field(None, alias="dreamDestination")

    model_config = {"populate_by_name": True}


class NewsletterSubscribeResponse(BaseModel):
    success: bool
    message: Optional[str] = None


class NewsletterUnsubscribeRequest(BaseModel):
    email: EmailStr


class NewsletterUnsubscribeResponse(BaseModel):
    success: bool
    message: Optional[str] = None


class ContactFormRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    email: EmailStr
    subject: Optional[str] = Field(None, max_length=200)
    message: str = Field(..., min_length=1, max_length=5000)
    order_id: Optional[str] = Field(None, alias="orderId", max_length=40)
    language: Optional[str] = Field(None, max_length=8)

    model_config = {"populate_by_name": True}


class ContactFormResponse(BaseModel):
    success: bool
    ticket_id: Optional[str] = Field(None, serialization_alias="ticketId")
    message: Optional[str] = None

    model_config = {"populate_by_name": True}


class DeviceCheckRequest(BaseModel):
    device_name: str = Field(..., alias="deviceName")

    model_config = {"populate_by_name": True}


class DeviceCheckResponse(BaseModel):
    compatible: bool
    device_name: str = Field(..., serialization_alias="deviceName")
    message: Optional[str] = None
    matched_model: Optional[str] = Field(None, serialization_alias="matchedModel")

    model_config = {"populate_by_name": True}


OrderStatus = Literal[
    "pending",
    "paid",
    "delivered",
    "active",
    "suspended",
    "expired",
    "refunded",
    "failed",
]


class Order(BaseModel):
    id: str
    order_number: str = Field(..., serialization_alias="orderNumber")
    email: EmailStr
    country: str
    flag: Optional[str] = None
    package_name: str = Field(..., serialization_alias="packageName")
    price: float
    currency: str = "USD"
    status: OrderStatus
    created_at: str = Field(..., serialization_alias="createdAt")
    qr_code_url: Optional[str] = Field(None, serialization_alias="qrCodeUrl")
    activation_code: Optional[str] = Field(
        None, serialization_alias="activationCode"
    )
    data_used_gb: Optional[float] = Field(None, serialization_alias="dataUsedGb")
    data_total_gb: Optional[float] = Field(None, serialization_alias="dataTotalGb")
    validity_days: Optional[int] = Field(None, serialization_alias="validityDays")
    days_remaining: Optional[int] = Field(None, serialization_alias="daysRemaining")
    data_remaining_gb: Optional[float] = Field(
        None, serialization_alias="dataRemainingGb"
    )
    fulfillment_pending: bool = Field(False, serialization_alias="fulfillmentPending")
    allowance_status: Optional[str] = Field(None, serialization_alias="allowanceStatus")
    is_gift: bool = Field(False, serialization_alias="isGift")
    gift_recipient_name: Optional[str] = Field(None, serialization_alias="giftRecipientName")
    gift_recipient_email: Optional[str] = Field(None, serialization_alias="giftRecipientEmail")
    package_id: Optional[str] = Field(None, serialization_alias="packageId")
    activation_status: Optional[str] = Field(None, serialization_alias="activationStatus")
    activated_at: Optional[str] = Field(None, serialization_alias="activatedAt")
    usage_synced_at: Optional[str] = Field(None, serialization_alias="usageSyncedAt")
    usage_pct: Optional[float] = Field(None, serialization_alias="usagePct")
    topup_supported: bool = Field(False, serialization_alias="topupSupported")
    topup_reason: Optional[str] = Field(None, serialization_alias="topupReason")
    wallet_balance_usd: Optional[float] = Field(None, serialization_alias="walletBalanceUsd")

    model_config = {"populate_by_name": True}


class GiftCheckoutDetails(BaseModel):
    recipient_email: EmailStr = Field(..., alias="recipientEmail")
    recipient_name: str = Field(..., min_length=1, max_length=80, alias="recipientName")
    gift_message: Optional[str] = Field(None, max_length=280, alias="giftMessage")
    sender_name: Optional[str] = Field(None, max_length=80, alias="senderName")

    model_config = {"populate_by_name": True}


class CheckoutAttribution(BaseModel):
    utm_source: Optional[str] = Field(None, alias="utmSource", max_length=120)
    utm_medium: Optional[str] = Field(None, alias="utmMedium", max_length=120)
    utm_campaign: Optional[str] = Field(None, alias="utmCampaign", max_length=120)
    utm_content: Optional[str] = Field(None, alias="utmContent", max_length=120)
    utm_term: Optional[str] = Field(None, alias="utmTerm", max_length=120)
    landing_path: Optional[str] = Field(None, alias="landingPath", max_length=240)
    referrer: Optional[str] = Field(None, max_length=240)

    model_config = {"populate_by_name": True}


class CheckoutSessionRequest(BaseModel):
    country: str
    price: float
    flag: Optional[str] = None
    email: EmailStr
    phone: Optional[str] = None
    travel_date: Optional[str] = Field(None, alias="travelDate")
    package_id: Optional[str] = Field(None, alias="packageId")
    promo_code: Optional[str] = Field(None, alias="promoCode")
    affiliate_ref: Optional[str] = Field(None, alias="affiliateRef")
    attribution: Optional[CheckoutAttribution] = None
    wants_topup: bool = Field(False, alias="wantsTopUp")
    is_gift: bool = Field(False, alias="isGift")
    gift: Optional[GiftCheckoutDetails] = None

    model_config = {"populate_by_name": True}


class OrderLookupResponse(BaseModel):
    order: Optional[Order] = None
    found: bool
    message: Optional[str] = None


class TopUpOptionsResponse(BaseModel):
    success: bool
    supported: bool = False
    provider: Optional[str] = None
    amounts_usd: list[float] = Field(default_factory=list, serialization_alias="amountsUsd")
    min_usd: Optional[float] = Field(None, serialization_alias="minUsd")
    max_usd: Optional[float] = Field(None, serialization_alias="maxUsd")
    reason: Optional[str] = None
    order_number: Optional[str] = Field(None, serialization_alias="orderNumber")

    model_config = {"populate_by_name": True}


class TopUpSessionRequest(BaseModel):
    order_id: str = Field(..., alias="orderId", min_length=4)
    email: EmailStr
    fund_usd: float = Field(..., alias="fundUsd", gt=0)

    model_config = {"populate_by_name": True}


class TopUpSessionResponse(BaseModel):
    success: bool
    checkout_url: Optional[str] = Field(None, serialization_alias="checkoutUrl")
    session_id: Optional[str] = Field(None, serialization_alias="sessionId")
    retail_usd: Optional[float] = Field(None, serialization_alias="retailUsd")
    fund_usd: Optional[float] = Field(None, serialization_alias="fundUsd")
    message: Optional[str] = None

    model_config = {"populate_by_name": True}


class SupportMessageItem(BaseModel):
    direction: str
    from_email: str = Field(..., serialization_alias="fromEmail")
    subject: Optional[str] = None
    body: str
    created_at: Optional[str] = Field(None, serialization_alias="createdAt")
    ticket_number: Optional[str] = Field(None, serialization_alias="ticketNumber")

    model_config = {"populate_by_name": True}


class OrderSupportMessagesResponse(BaseModel):
    success: bool
    messages: list[SupportMessageItem] = Field(default_factory=list)
    ticket_number: Optional[str] = Field(None, serialization_alias="ticketNumber")
    message: Optional[str] = None

    model_config = {"populate_by_name": True}


class OrderResendEsRequest(BaseModel):
    order_id: str = Field(..., alias="orderId", min_length=4)
    email: EmailStr

    model_config = {"populate_by_name": True}


class OrderResendEsResponse(BaseModel):
    success: bool
    order_number: Optional[str] = Field(None, serialization_alias="orderNumber")
    message: Optional[str] = None

    model_config = {"populate_by_name": True}


class PromoValidateRequest(BaseModel):
    code: str = Field(..., min_length=2, max_length=40)
    country: str = Field(..., min_length=2, max_length=120)
    price: float = Field(0, ge=0)
    package_id: str = Field(..., alias="packageId", min_length=2)

    model_config = {"populate_by_name": True}


class PromoValidateResponse(BaseModel):
    valid: bool
    code: Optional[str] = None
    percent_off: Optional[int] = Field(None, serialization_alias="percentOff")
    discount_amount: Optional[float] = Field(None, serialization_alias="discountAmount")
    final_price: Optional[float] = Field(None, serialization_alias="finalPrice")
    message: Optional[str] = None
    ends_at: Optional[str] = Field(None, serialization_alias="endsAt")

    model_config = {"populate_by_name": True}


class CronRunResponse(BaseModel):
    success: bool
    expired_promos: int = Field(0, serialization_alias="expiredPromos")
    insider: Optional[dict] = None
    catalog_sync: Optional[dict] = Field(None, serialization_alias="catalogSync")
    expiry_reminders: Optional[dict] = Field(None, serialization_alias="expiryReminders")
    usage_sync: Optional[dict] = Field(None, serialization_alias="usageSync")
    monthly_summary: Optional[dict] = Field(None, serialization_alias="monthlySummary")
    log_retention: Optional[dict] = Field(None, serialization_alias="logRetention")
    auto_refunds: Optional[dict] = Field(None, serialization_alias="autoRefunds")
    affiliate_payouts: Optional[dict] = Field(None, serialization_alias="affiliatePayouts")
    message: Optional[str] = None

    model_config = {"populate_by_name": True}


class DailyReportResponse(BaseModel):
    success: bool
    sent: int = 0
    skipped: Optional[str] = None
    error: Optional[str] = None
    subject: Optional[str] = None
    ny_date: Optional[str] = Field(None, serialization_alias="nyDate")
    recipients: Optional[list[str]] = None
    errors: Optional[list[str]] = None

    model_config = {"populate_by_name": True}


class AdminReportsResponse(BaseModel):
    success: bool
    daily: Optional[dict] = None
    weekly: Optional[dict] = None
    monthly: Optional[dict] = None

    model_config = {"populate_by_name": True}


class FulfillmentResolveResponse(BaseModel):
    success: bool
    country: Optional[str] = None
    data_gb: Optional[float] = Field(None, serialization_alias="dataGb")
    validity_days: Optional[int] = Field(None, serialization_alias="validityDays")
    wants_topup: bool = Field(False, serialization_alias="wantsTopUp")
    mapped: Optional[dict] = None
    chosen: Optional[dict] = None
    ladder: Optional[str] = None
    breakage_policy: Optional[dict] = Field(None, serialization_alias="breakagePolicy")
    fulfillment_mode: Optional[dict] = Field(None, serialization_alias="fulfillmentMode")
    breakage_margin_estimates: Optional[dict] = Field(
        None, serialization_alias="breakageMarginEstimates"
    )
    message: Optional[str] = None

    model_config = {"populate_by_name": True}


class BreakageStrategySummaryResponse(BaseModel):
    success: bool
    summary: dict


class BreakageCountryPolicyResponse(BaseModel):
    success: bool
    country: str
    policy: dict
    fulfillment_mode: Optional[dict] = Field(None, serialization_alias="fulfillmentMode")
    bundles: list[dict] = Field(default_factory=list)


class BreakageAllowanceResponse(BaseModel):
    success: bool
    allowance: Optional[dict] = None
    profit_estimate: Optional[dict] = Field(None, serialization_alias="profitEstimate")
    message: Optional[str] = None

    model_config = {"populate_by_name": True}


class CheckoutSessionResponse(BaseModel):
    success: bool
    session_id: Optional[str] = Field(None, serialization_alias="sessionId")
    checkout_url: Optional[str] = Field(None, serialization_alias="checkoutUrl")
    order_id: Optional[str] = Field(None, serialization_alias="orderId")
    message: Optional[str] = None
    email_sent: Optional[bool] = Field(None, serialization_alias="emailSent")
    email_error: Optional[str] = Field(None, serialization_alias="emailError")
    discount_amount: Optional[float] = Field(None, serialization_alias="discountAmount")
    final_price: Optional[float] = Field(None, serialization_alias="finalPrice")
    promo_code: Optional[str] = Field(None, serialization_alias="promoCode")
    affiliate_ref: Optional[str] = Field(None, serialization_alias="affiliateRef")

    model_config = {"populate_by_name": True}


class CheckoutConfigResponse(BaseModel):
    publishable_key: str = Field(..., serialization_alias="publishableKey")

    model_config = {"populate_by_name": True}


class ExpressPaymentIntentResponse(BaseModel):
    success: bool
    client_secret: Optional[str] = Field(None, serialization_alias="clientSecret")
    payment_intent_id: Optional[str] = Field(None, serialization_alias="paymentIntentId")
    order_id: Optional[str] = Field(None, serialization_alias="orderId")
    final_price: Optional[float] = Field(None, serialization_alias="finalPrice")
    discount_amount: Optional[float] = Field(None, serialization_alias="discountAmount")
    affiliate_ref: Optional[str] = Field(None, serialization_alias="affiliateRef")
    message: Optional[str] = None

    model_config = {"populate_by_name": True}


class AffiliateResolveResponse(BaseModel):
    valid: bool
    code: Optional[str] = None
    type: Optional[str] = None
    display_name: Optional[str] = Field(None, serialization_alias="displayName")
    organization_name: Optional[str] = Field(None, serialization_alias="organizationName")
    customer_discount_percent: Optional[int] = Field(
        None, serialization_alias="customerDiscountPercent"
    )
    landing_path: Optional[str] = Field(None, serialization_alias="landingPath")
    pays_cash: Optional[bool] = Field(None, serialization_alias="paysCash")
    message: Optional[str] = None

    model_config = {"populate_by_name": True}


class AffiliateReferralLinkResponse(BaseModel):
    success: bool
    code: Optional[str] = None
    url: Optional[str] = None
    customer_discount_percent: Optional[int] = Field(
        None, serialization_alias="customerDiscountPercent"
    )
    referrer_reward_percent: Optional[int] = Field(
        None, serialization_alias="referrerRewardPercent"
    )
    message: Optional[str] = None

    model_config = {"populate_by_name": True}


class AffiliateCommissionItem(BaseModel):
    order_number: Optional[str] = Field(None, serialization_alias="orderNumber")
    commission_cents: Optional[int] = Field(None, serialization_alias="commissionCents")
    status: Optional[str] = None
    fulfilled_at: Optional[str] = Field(None, serialization_alias="fulfilledAt")

    model_config = {"populate_by_name": True}


class AffiliateDashboardResponse(BaseModel):
    success: bool
    code: Optional[str] = None
    type: Optional[str] = None
    display_name: Optional[str] = Field(None, serialization_alias="displayName")
    referral_url: Optional[str] = Field(None, serialization_alias="referralUrl")
    customer_discount_percent: Optional[int] = Field(
        None, serialization_alias="customerDiscountPercent"
    )
    commission_percent: Optional[int] = Field(None, serialization_alias="commissionPercent")
    pays_cash: Optional[bool] = Field(None, serialization_alias="paysCash")
    approved_balance_cents: Optional[int] = Field(None, serialization_alias="approvedBalanceCents")
    paid_total_cents: Optional[int] = Field(None, serialization_alias="paidTotalCents")
    payout_minimum_cents: Optional[int] = Field(None, serialization_alias="payoutMinimumCents")
    ready_for_payout: Optional[bool] = Field(None, serialization_alias="readyForPayout")
    recent_commissions: list[AffiliateCommissionItem] = Field(
        default_factory=list, serialization_alias="recentCommissions"
    )
    message: Optional[str] = None

    model_config = {"populate_by_name": True}


class AffiliateCreateRequest(BaseModel):
    code: str = Field(..., min_length=3, max_length=32)
    type: Literal["influencer", "mosque", "connector", "customer"]
    display_name: Optional[str] = Field(None, alias="displayName")
    organization_name: Optional[str] = Field(None, alias="organizationName")
    contact_email: Optional[EmailStr] = Field(None, alias="contactEmail")
    payout_email: Optional[EmailStr] = Field(None, alias="payoutEmail")
    referrer_email: Optional[EmailStr] = Field(None, alias="referrerEmail")
    customer_discount_percent: Optional[int] = Field(None, alias="customerDiscountPercent")
    commission_percent: Optional[int] = Field(None, alias="commissionPercent")
    payout_minimum_cents: Optional[int] = Field(None, alias="payoutMinimumCents")
    landing_path: Optional[str] = Field(None, alias="landingPath")
    status: Literal["pending", "active", "paused"] = "active"

    model_config = {"populate_by_name": True}


class AffiliatePayoutRequestPublic(BaseModel):
    code: str = Field(..., min_length=2, max_length=32)
    email: EmailStr

    model_config = {"populate_by_name": True}


class AffiliatePayoutRequestResponse(BaseModel):
    success: bool
    code: Optional[str] = None
    approved_balance_cents: Optional[int] = Field(None, serialization_alias="approvedBalanceCents")
    message: Optional[str] = None

    model_config = {"populate_by_name": True}


class AffiliatePayoutRequest(BaseModel):
    affiliate_id: str = Field(..., alias="affiliateId")
    method: Optional[str] = "manual"
    reference: Optional[str] = None
    notes: Optional[str] = None

    model_config = {"populate_by_name": True}


class SearchLogRequest(BaseModel):
    destination: str = Field(..., min_length=1, max_length=120)


class SearchLogResponse(BaseModel):
    success: bool
    destination: str
    message: Optional[str] = None


class PopularDestinationItem(BaseModel):
    destination: str
    query: str
    href: str
    flag: str


class TrendingDestinationItem(PopularDestinationItem):
    count: int


class DeviceModelItem(BaseModel):
    id: str
    name: str


class DeviceBrandItem(BaseModel):
    id: str
    name: str
    models: list[DeviceModelItem]


class CompatibleDevicesResponse(BaseModel):
    success: bool
    brands: list[DeviceBrandItem]


PricingStrategy = Literal["MANUAL", "AUTOMATED"]
MarginStatus = Literal["manual", "automated", "floor_applied"]
PlanCategory = Literal["fixed", "unlimited", "flexible"]
DisplayBadge = Literal["best_choice", "flexible"]


class FormattedPriceParts(BaseModel):
    dollars: str
    cents: str


class EsimPlanItem(BaseModel):
    id: str
    country_id: str = Field(..., serialization_alias="countryId")
    name: str
    data_gb: Optional[float] = Field(None, serialization_alias="dataGb")
    duration_days: Optional[int] = Field(None, serialization_alias="durationDays")
    price: float
    formatted_price_parts: FormattedPriceParts = Field(
        ..., serialization_alias="formattedPriceParts"
    )
    currency: str = "USD"
    is_rechargeable: bool = Field(False, serialization_alias="isRechargeable")
    is_pay_as_you_go: bool = Field(False, serialization_alias="isPayAsYouGo")
    pricing_strategy: PricingStrategy = Field(
        "MANUAL", serialization_alias="pricingStrategy"
    )
    margin_status: MarginStatus = Field("manual", serialization_alias="marginStatus")
    plan_category: PlanCategory = Field("fixed", serialization_alias="planCategory")
    display_badge: Optional[DisplayBadge] = Field(
        None, serialization_alias="displayBadge"
    )
    coming_soon: bool = Field(False, serialization_alias="comingSoon")

    model_config = {"populate_by_name": True}


class PlanCategoryGroups(BaseModel):
    fixed: list[EsimPlanItem] = Field(default_factory=list)
    unlimited: list[EsimPlanItem] = Field(default_factory=list)
    flexible: list[EsimPlanItem] = Field(default_factory=list)


class PlansByCountryResponse(BaseModel):
    success: bool
    country_id: str = Field(..., serialization_alias="countryId")
    country_name: Optional[str] = Field(None, serialization_alias="countryName")
    flag: Optional[str] = None
    plans: list[EsimPlanItem]
    plan_groups: PlanCategoryGroups = Field(
        default_factory=PlanCategoryGroups,
        serialization_alias="planGroups",
    )
    product_type: Optional[str] = Field(None, serialization_alias="productType")
    coverage_countries: Optional[list[str]] = Field(
        None, serialization_alias="coverageCountries"
    )
    coverage_exclusions: Optional[list[str]] = Field(
        None, serialization_alias="coverageExclusions"
    )
    region_slug: Optional[str] = Field(None, serialization_alias="regionSlug")

    model_config = {"populate_by_name": True}


class PopularAnalyticsResponse(BaseModel):
    success: bool
    trending: list[TrendingDestinationItem]
    fallback: list[PopularDestinationItem]
    fallback_labels: list[str] = Field(
        ...,
        serialization_alias="fallbackLabels",
        description="High-intent defaults: Umrah, Turkey, Europe",
    )

    model_config = {"populate_by_name": True}
