"""
eSIM provisioning adapter.

Production: replace with your carrier/MVNE API. Development: deterministic mock credentials.
"""

from __future__ import annotations

import hashlib
import logging
from typing import Any, Dict
from urllib.parse import quote

logger = logging.getLogger(__name__)

# Demo SM-DP+ host — swap for real provider endpoint in production
MOCK_SMDP_HOST = "smdp.noorlink-demo.example"


def provision_esim(order_row: Dict[str, Any]) -> Dict[str, str]:
    """
    Return QR image URL and human-readable activation code for the order.
    """
    order_number = order_row["order_number"]
    digest = hashlib.sha256(order_number.encode()).hexdigest()[:12].upper()
    activation_code = f"NL-{digest}"
    lpa_string = f"LPA:1${MOCK_SMDP_HOST}${activation_code}"

    qr_code_url = (
        "https://api.qrserver.com/v1/create-qr-code/"
        f"?size=320x320&data={quote(lpa_string)}"
    )

    logger.info("Provisioned mock eSIM for order %s", order_number)
    return {
        "activation_code": activation_code,
        "qr_code_url": qr_code_url,
        "lpa_string": lpa_string,
        "provider": "noorlink-mock",
    }
