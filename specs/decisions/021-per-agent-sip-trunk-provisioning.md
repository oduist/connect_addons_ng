# ADR-021: Per-Agent SIP-Trunk Provisioning via EL Phone Numbers

**Status:** Accepted
**Date:** 2026-05-23
**Supersedes:** ADR-018, ADR-019 (per-agent fields)
**Relates:** ADR-020 (closes its "deferred per-agent provisioning")

## Context

ADR-020 removed the relay/audio-fork transports and folded the
provider matrix down to a single SIP-trunk path for both Twilio and
FreeSWITCH. It kept a *tenant-level* SIP-credentials block on
`connect.settings` (`elevenlabs_sip_enabled`, `..._auth_method`,
`..._username`, `..._password`) plus a read-only sanity-check method
`elevenlabs_sync_sip_trunks`, and explicitly deferred per-number
provisioning via `POST /v1/convai/phone-numbers` until "a real
consumer" existed.

That consumer is here. ElevenLabs accepts SIP INVITEs only for
**registered phone-number entities** in the account. To route an
inbound FreeSWITCH or Twilio call to a specific agent, we have to
register a `phone_number` with `provider=sip_trunk` and attach it
to the target agent on the EL side. The tenant-level digest
fields don't do that — they describe the FS-to-EL hop, not the
per-agent registration on the EL side, and they carry credentials
that aren't used now that EL prefers IP-allow-list auth for
`sip_trunk` phone numbers.

The sibling repo (`connect_addons`, Twilio-only) already
implements this pattern. This ADR ports it to
`connect_addons_ng/19.0` and extends it to the FreeSWITCH bridge.

## Decision

### 1. Per-agent phone-number registration

`connect.elevenlabs_agent` (core) gains two fields:

```python
el_virtual_number_uid    # Char, readonly, groups=group_erp_manager
                         # phone_number_id returned by EL on register
el_inbound_allowed_ips   # Text, IP/CIDR allow-list (newline/comma)
                         # default is bridge-specific (see §5)
```

A helper registers/refreshes the entity, using the agent's
`agent_uid` as the SIP identifier:

```python
def _ensure_el_virtual_number(self):
    client = self.env['connect.settings'].get_elevenlabs_client()
    allowed = _parse_allow_list(self.el_inbound_allowed_ips)
    inbound_cfg = InboundSipTrunkConfigRequestModel(
        allowed_addresses=allowed or None,
    )
    if self.el_virtual_number_uid:
        try:
            client.conversational_ai.phone_numbers.update(
                self.el_virtual_number_uid,
                agent_id=self.agent_uid,
                inbound_trunk_config=inbound_cfg,
            )
            return
        except ApiError as e:
            if e.status_code != 404:
                logger.warning(...)
                return
            # 404 — entity gone on EL side, fall through to create.
            self.with_context(skip_el_sync=True).el_virtual_number_uid = False
    result = client.conversational_ai.phone_numbers.create(
        request=PhoneNumbersCreateRequestBody_SipTrunk(
            provider='sip_trunk',
            phone_number=self.agent_uid,
            label='EL Agent SIP Route ({})'.format(self.agent_uid[:12]),
            inbound_trunk_config=inbound_cfg,
        ),
    )
    client.conversational_ai.phone_numbers.update(
        result.phone_number_id, agent_id=self.agent_uid,
    )
    self.with_context(skip_el_sync=True).el_virtual_number_uid = (
        result.phone_number_id)
```

A companion `_remove_el_virtual_number()` deletes the entity and
clears the local field.

### 2. Trigger

Provisioning is bound to `exten` lifecycle:

* `write()` with truthy `exten` → `_ensure_el_virtual_number()`.
* `write()` clearing `exten` → `_remove_el_virtual_number()`.
* `unlink()` → `_remove_el_virtual_number()` for hygiene.

Assigning an extension is the moment the agent enters the phone
system; that's when the SIP route must exist on the EL side. No
extension means the agent is a draft — no EL entity is created.

### 3. FreeSWITCH dialplan

The `dialplan_elevenlabs_sip` template now bridges on the
registered identifier (the agent's `agent_uid`), not on the
dialed extension number:

```xml
<action application="bridge"
        data="{absolute_codec_string='PCMU,PCMA'}sofia/gateway/{{ gateway_name }}/{{ agent_uid }}"/>
```

`extension_number` still gates the FS `<condition>`. The
`connect.freeswitch.gateway` named `elevenlabs` keeps pointing to
EL's SIP termination host — one trunk per account, per-agent
routing through the SIP user part.

### 4. Conversation Initiation Webhook (workspace-level)

`connect.settings` gets a computed read-only field:

```python
elevenlabs_conversation_initiation_webhook_url = fields.Char(
    compute='_get_conversation_initiation_webhook_url')
# = api_url + '/connect_elevenlabs/conversation_init'
```

shown verbatim in the settings form (copy widget) so operators can
mirror it into the EL dashboard, and pushed automatically via:

```python
def _push_elevenlabs_initiation_webhook(self):
    client.conversational_ai.settings.update(
        conversation_initiation_client_data_webhook={
            'url': self.elevenlabs_conversation_initiation_webhook_url,
            'request_headers': {
                'x-elevenlabs-agent-token': self.elevenlabs_agent_token,
            },
        },
    )
```

called from `elevenlabs_reset_token` and `elevenlabs_sync`. One
workspace webhook serves every agent — the per-agent override
that `update_elevenlabs_agent` used to push in ADR-020's final
shape is dropped.

### 5. Bridge-specific defaults for `el_inbound_allowed_ips`

* `connect_elevenlabs_twilio` defaults to Twilio's SIP signaling
  ranges (`TWILIO_SIP_SIGNALING_IPS`).
* `connect_elevenlabs_freeswitch` leaves it empty (allow-all).
  Operators fill in the FreeSWITCH public IP for production. The
  dev/test environment used in this repo is behind dynamic NAT,
  so an empty default is the pragmatic choice.

### Demolition

Removed:

* `connect.settings.elevenlabs_sip_enabled`, `..._auth_method`,
  `..._username`, `..._password`, plus their `display_*` mirrors
  and the `PROTECTED_FIELDS` entries.
* `connect.settings.elevenlabs_sync_sip_trunks` method and the
  "SIP Trunk" page in the settings view.
* The `workspace_overrides.conversation_initiation_client_data_webhook`
  block in `_build_platform_settings` (per-agent push of the
  webhook URL).

## Consequences

* One `phone_number` entity per **routable** agent in the EL
  account. Cleanup on `exten` removal and on agent `unlink` keeps
  the EL account tidy. A pre-existing entity for the same
  `agent_uid` (e.g. left over from a previous run) is matched on
  HTTP 409 from `create` and re-bound via `update`.
* Auth is IP-based. The default on the FreeSWITCH bridge is
  permissive; production deployments must populate
  `el_inbound_allowed_ips` with their FreeSWITCH public IP.
* `connect.freeswitch.gateway` named `elevenlabs` remains the
  FreeSWITCH-side trunk and is still configured manually
  (operator provides EL's SIP termination host).
* Workspace-level webhook means one EL API call instead of N on
  every agent save. Trade-off: all agents share the same webhook
  URL — which is exactly what we rendered into the per-agent
  override anyway.

## Migration

The dropped tenant-level columns on `connect.settings`
(`elevenlabs_sip_enabled`, `elevenlabs_sip_auth_method`,
`elevenlabs_sip_username`, `elevenlabs_sip_password`, plus the two
`display_*` mirrors) were introduced in ADR-018 and never
populated by any active code path. Orphan columns left in the DB
after the field removal are harmless and are dropped naturally
when the DB is recreated for the next deploy. View references are
cleaned up by the standard `-u connect_elevenlabs` cycle.

Existing EL `phone_number` entities (if any) survive the upgrade.
The first save of an agent with an `exten` will reconcile the
entity for that `agent_uid` (create-or-update via `agent_id`).

## Out of scope

* Outbound calls originated by ElevenLabs through the trunk
  (ADR-020 out-of-scope, preserved).
* Restoring the relay-side audio path for analytics / prompt
  injection (ADR-020 out-of-scope, preserved).
* Multi-trunk-per-agent topology (one EL account is assumed to
  service one Odoo tenant; cross-tenant routing isn't modelled).
