"""FreeSWITCH (Oduist Connect) telephony configuration schemas."""

from typing import List, Literal

from pydantic import BaseModel, Field


class FreeswitchConfigurationRequest(BaseModel):
    """Request schema for FreeSWITCH configuration.

    FreeSWITCH is driven through an Odoo instance running the Oduist
    Connect modules: Odoo posts inbound webhooks to Dograh and exposes
    the call-control endpoints (originate/hangup) Dograh calls back.
    """

    provider: Literal["freeswitch"] = Field(default="freeswitch")
    account_id: str = Field(
        ...,
        description=(
            "Account identifier sent by Odoo in inbound webhooks "
            "(must equal the Dograh Account ID in Odoo Connect settings)"
        ),
    )
    odoo_url: str = Field(
        ...,
        description="Odoo base URL (e.g., https://odoo.example.com)",
    )
    service_token: str = Field(
        ...,
        description=(
            "Shared secret: verifies Odoo inbound webhooks and "
            "authenticates Dograh calls to Odoo /dograh/api/*"
        ),
    )
    from_numbers: List[str] = Field(
        default_factory=list,
        description="Caller ID numbers for outbound calls (optional)",
    )


class FreeswitchConfigurationResponse(BaseModel):
    """Response schema for FreeSWITCH configuration with masked secrets."""

    provider: Literal["freeswitch"] = Field(default="freeswitch")
    account_id: str
    odoo_url: str
    service_token: str  # Masked
    from_numbers: List[str]
