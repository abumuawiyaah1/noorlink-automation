from functools import lru_cache
from typing import Any, List, Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Loaded from environment (.env locally, Railway Variables in production)."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # —— App ——
    app_name: str = "NoorLink Automation"
    app_version: str = "1.0.0"
    debug: bool = False
    environment: str = "development"

    # Absolute URL to logo PNG used in transactional emails
    email_logo_url: str = "https://noorlink.co/images/logo.png"

    # —— Supabase (Dashboard → Project Settings → API) ——
    supabase_url: str = Field(
        ...,
        description="Project URL, e.g. https://xxxx.supabase.co",
    )
    supabase_key: str = Field(
        ...,
        description="anon/public key (client-safe; not used for server writes)",
    )
    supabase_service_key: str = Field(
        ...,
        description="service_role key — backend only, bypasses RLS",
    )
    # Direct Postgres URI (Supabase pooler) for SQLAdmin dashboard
    database_url: str = ""

    # —— Stripe (Dashboard → Developers → API keys + Webhooks) ——
    stripe_secret_key: str
    stripe_publishable_key: str
    stripe_webhook_secret: str
    # Optional Dashboard payment method configuration id (pmc_...) for wallets/Link
    stripe_payment_method_configuration: str = ""

    # —— Simbase (eSIM provisioning + usage guard) ——
    simbase_api_key: str = ""
    simbase_api_base_url: str = "https://api.simbase.com/v2"
    simbase_webhook_secret: str = ""

    # —— Citrus Mobile (reseller eSIM API) ——
    # Auth: Authorization: Bearer rsk_...
    citrus_api_key: str = ""
    citrus_api_base_url: str = "https://citrusmobile.com/api/v2/reseller"
    # HMAC signing secret from POST /webhooks (whsec_...) — verify X-Citrus-Signature
    citrus_webhook_secret: str = ""
    # mock | citrus | esimaccess | telna | zesimo | simbase  (default when no map hit)
    esim_provider: str = "mock"

    # —— eSIM Access (Redtea) ——
    # Partner portal → AccessCode. Used as RT-AccessCode + HMAC key.
    esim_access_access_code: str = ""
    esim_access_api_base_url: str = "https://api.esimaccess.com/api/v1/open"
    # Optional shared secret if Access adds webhook signing later
    esim_access_webhook_secret: str = ""
    # When true, Saudi/Umrah orders must map to esimaccess (Phase A restriction)
    # Accepts true/false/1/0/yes/no; blank Railway vars fall back to True.
    esim_access_enforce_saudi: bool = True

    # —— Telna Connect Flex ——
    # Raw API token from support@telna.com / Flex developer onboarding.
    # Send as Authorization: <token> — no "Bearer" prefix (Telna requirement).
    telna_api_token: str = ""
    telna_ordering_base_url: str = "https://ppo-api.telna.com/v1/ordering"
    telna_diagnostic_base_url: str = "https://ppo-api.telna.com/v1/diagnostic"
    # Optional account id required by some Flex tenants on /products and work-orders
    telna_account_id: str = ""

    # —— Zesimo Reseller API ——
    # Portal → API Keys. Authorization: Bearer {token}
    # Docs: https://zesimo.com/portal/docs
    zesimo_api_key: str = ""
    zesimo_api_base_url: str = "https://zesimo.com/api/v1"

    # —— WeConnect / Droam Platform API (portal.noorlink.co) ——
    # OAuth: POST {base}/oauth/v1/token with client_id=email, client_secret=password.
    # Docs: https://api.droam.com/#907965c8-7d87-4b75-a4db-1d089aebd08d
    weconnect_email: str = ""
    weconnect_password: str = ""
    weconnect_base_url: str = "https://portal.noorlink.co/rest/v3"

    # —— Resend (email delivery) ——
    # From address must use a domain verified in Resend (prefer noorlink.co).
    resend_api_key: str
    resend_from_email: str = "NoorLink <noreply@noorlink.co>"
    support_email: str = "support@noorlink.co"
    # Comma-separated extra inboxes for new-ticket staff alerts
    support_staff_notify_emails: str = ""
    # Auto-refund unanswered refund tickets after N hours (strict low-usage policy)
    support_auto_refund_wait_hours: int = 48
    # Max order amount (cents) eligible for 48h auto-refund
    support_auto_refund_max_cents: int = 5000
    # Affiliate payout requests: auto-approve (not auto-pay) if staff unattended
    affiliate_auto_payout_wait_hours: int = 72
    # Max payout amount (cents) eligible for 72h auto-approve
    affiliate_auto_payout_max_cents: int = 50000
    # Resend webhook signing secret for inbound support email (email.received)
    resend_inbound_webhook_secret: str = ""
    # Resend webhook signing secret for delivery events (bounce, complaint, delivered)
    resend_events_webhook_secret: str = ""

    # Ops alerts when Stripe is paid but fulfillment/QR delivery fails
    ops_alert_email: str = ""
    slack_webhook_url: str = ""

    # Optional public review links (shown in post-delivery emails)
    # Trustpilot preferred; Google optional secondary.
    trustpilot_review_url: str = ""
    google_review_url: str = ""
    # Trustpilot Automatic Feedback Service — BCC on fulfillment emails only.
    # Example: yourdomain.com+xxxxx@invite.trustpilot.com
    trustpilot_invite_bcc: str = ""

    # Protected bearer token for scheduled cron hits (Insider release + promo expiry)
    cron_secret: str = ""

    # —— Auth (sessions + admin dashboard) ——
    secret_key: str = "change-this-in-production"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    admin_enabled: bool = True
    admin_session_max_age: int = 86400
    # Comma-separated IPs allowed to reach /admin (empty = allow all). Also use Cloudflare Access.
    admin_allowed_ips: str = ""

    # —— URLs ——
    # Next.js frontend (Stripe success/cancel redirects)
    app_url: str = "http://localhost:3000"
    stripe_success_path: str = "/success"
    stripe_cancel_path: str = "/checkout"
    # Comma-separated allowed CORS origins (include your Vercel/frontend URL)
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"

    # Railway injects these automatically — optional reference / logging
    railway_public_domain: Optional[str] = None
    railway_static_url: Optional[str] = None
    port: Optional[int] = None

    @field_validator("esim_access_enforce_saudi", mode="before")
    @classmethod
    def _coerce_enforce_saudi(cls, value: Any) -> Any:
        if value is None:
            return True
        if isinstance(value, str):
            cleaned = value.strip().lower()
            if cleaned == "":
                return True
            if cleaned in {"1", "true", "yes", "on", "y"}:
                return True
            if cleaned in {"0", "false", "no", "off", "n"}:
                return False
            # Mis-pasted secret / garbage must not crash boot — default on
            return True
        return value

    @property
    def supabase_admin_key(self) -> str:
        """Always use service role for server-side persistence."""
        return self.supabase_service_key

    @property
    def admin_allowed_ip_list(self) -> List[str]:
        return [ip.strip() for ip in self.admin_allowed_ips.split(",") if ip.strip()]

    @property
    def cors_origin_list(self) -> List[str]:
        if self.cors_origins.strip() == "*":
            return ["*"]
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def stripe_success_url(self) -> str:
        return f"{self.app_url.rstrip('/')}{self.stripe_success_path}"

    @property
    def stripe_cancel_url(self) -> str:
        return f"{self.app_url.rstrip('/')}{self.stripe_cancel_path}"


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    env = (settings.environment or "").strip().lower()
    if env in {"production", "prod"}:
        if settings.cors_origins.strip() == "*":
            raise ValueError("CORS_ORIGINS must not be '*' in production.")
        if settings.secret_key.strip() in {"", "change-this-in-production"}:
            raise ValueError("SECRET_KEY must be set to a strong value in production.")
    return settings


# Backwards-compatible module-level instance
settings = get_settings()
