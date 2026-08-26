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
    name: str
    email: EmailStr
    subject: Optional[str] = None
    message: str


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

    model_config = {"populate_by_name": True}


class OrderLookupResponse(BaseModel):
    order: Optional[Order] = None
    found: bool


class CheckoutSessionRequest(BaseModel):
    country: str
    price: float
    flag: Optional[str] = None
    email: EmailStr
    phone: Optional[str] = None
    travel_date: Optional[str] = Field(None, alias="travelDate")
    package_id: Optional[str] = Field(None, alias="packageId")
    promo_code: Optional[str] = Field(None, alias="promoCode")

    model_config = {"populate_by_name": True}


class PromoValidateRequest(BaseModel):
    code: str = Field(..., min_length=2, max_length=40)
    price: float = Field(..., gt=0)
    package_id: Optional[str] = Field(None, alias="packageId")

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
