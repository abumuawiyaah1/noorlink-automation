"""Shared fixtures for Simbase / API tests."""

from __future__ import annotations

import os

# Minimal env so Settings / app import succeed without a real .env
os.environ.setdefault("SUPABASE_URL", "https://example.supabase.co")
os.environ.setdefault("SUPABASE_KEY", "test-anon-key")
os.environ.setdefault("SUPABASE_SERVICE_KEY", "test-service-key")
os.environ.setdefault("STRIPE_SECRET_KEY", "sk_test_x")
os.environ.setdefault("STRIPE_PUBLISHABLE_KEY", "pk_test_x")
os.environ.setdefault("STRIPE_WEBHOOK_SECRET", "whsec_test")
os.environ.setdefault("RESEND_API_KEY", "re_test")
os.environ.setdefault("SIMBASE_API_KEY", "sb_test_key")
os.environ.setdefault("SIMBASE_API_BASE_URL", "https://api.simbase.com/v2")
os.environ.setdefault("SIMBASE_WEBHOOK_SECRET", "test_webhook_secret_key")
os.environ.setdefault("CITRUS_API_KEY", "rsk_test_key")
os.environ.setdefault("CITRUS_API_BASE_URL", "https://citrusmobile.com/api/v2/reseller")
os.environ.setdefault("CITRUS_WEBHOOK_SECRET", "whsec_test_secret")
os.environ.setdefault("ESIM_PROVIDER", "mock")
os.environ.setdefault("SECRET_KEY", "test-secret")

from app.core.config import get_settings

get_settings.cache_clear()
