"""FreeSWITCH (Oduist Connect) telephony provider package.

Vendored by the Oduist connect_dograh Odoo module and overlaid onto the
Dograh API image; see https://github.com/oduist/connect_addons_ng.
"""

from typing import Any, Dict

from api.services.telephony.registry import (
    ProviderSpec,
    ProviderUIField,
    ProviderUIMetadata,
    register,
)

from .config import FreeswitchConfigurationRequest, FreeswitchConfigurationResponse
from .provider import FreeswitchProvider
from .transport import create_transport


def _config_loader(value: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "provider": "freeswitch",
        "account_id": value.get("account_id"),
        "odoo_url": value.get("odoo_url"),
        "service_token": value.get("service_token"),
        "from_numbers": value.get("from_numbers", []),
    }


_UI_METADATA = ProviderUIMetadata(
    display_name="FreeSWITCH (Oduist Connect)",
    docs_url="https://oduist.com/documentation-19-0",
    fields=[
        ProviderUIField(
            name="account_id",
            label="Account ID",
            type="text",
            description=(
                "Identifier that Odoo sends in inbound webhooks; must equal "
                "the Dograh Account ID in Odoo Connect settings"
            ),
        ),
        ProviderUIField(
            name="odoo_url",
            label="Odoo URL",
            type="text",
            description="Odoo base URL (e.g., https://odoo.example.com)",
        ),
        ProviderUIField(
            name="service_token",
            label="Service Token",
            type="password",
            sensitive=True,
            description="Shared secret from Odoo Connect Dograh settings",
        ),
        ProviderUIField(
            name="from_numbers",
            label="From Numbers",
            type="string-array",
            description="Caller ID numbers for outbound calls (optional)",
        ),
    ],
)


SPEC = ProviderSpec(
    name="freeswitch",
    provider_cls=FreeswitchProvider,
    config_loader=_config_loader,
    transport_factory=create_transport,
    transport_sample_rate=16000,
    config_request_cls=FreeswitchConfigurationRequest,
    config_response_cls=FreeswitchConfigurationResponse,
    ui_metadata=_UI_METADATA,
    account_id_credential_field="account_id",
)


register(SPEC)


__all__ = [
    "SPEC",
    "FreeswitchConfigurationRequest",
    "FreeswitchConfigurationResponse",
    "FreeswitchProvider",
    "create_transport",
]
