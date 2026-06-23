# ADR-021: Apply `connect.user.outgoing_callerid` on the outgoing-route dialplan

## Status
Accepted

## Context

A SIP/Verto user registered with FreeSWITCH gets `effective_caller_id_*`
seeded from their `connect.user.exten_number` via the directory template
(`connect_freeswitch/controllers/freeswitch_xml.py` → directory user
XML). When the user then dials an external number, the existing
`dialplan_outgoing_route` template just bridged the call through the
gateway:

```xml
<extension name="outgoing_{{ route_id }}">
  <condition field="destination_number" expression="{{ pattern }}">
    <action application="set" data="odoo_call_direction=outgoing"/>
    <action application="export" data="nolocal:absolute_codec_string=PCMU,PCMA"/>
    <action application="bridge" data="{{ bridge_data }}"/>
  </condition>
</extension>
```

There was no caller-ID rewrite on the B-leg, so the PSTN side saw the
extension number ("101") instead of the user's configured
`connect.user.outgoing_callerid` — which is precisely the field whose
purpose is to control what the called party sees. The substitution
never happened.

## Decision

Push the user's `outgoing_callerid.number` (and `friendly_name`) into
the dialplan template via `connect.freeswitch.outgoing_route.generate_dialplan`:

1. `generate_dialplan(params)` reads the calling user from the channel
   variable `variable_odoo_connect_user_id` (which the directory
   template already exports).
2. If that user has an `outgoing_callerid` configured, the route passes
   `cid_name` / `cid_num` into the template.
3. The template emits two extra actions before `bridge` only when
   `cid_num` is set:

   ```xml
   {% if cid_num %}
   <action application="set" data="effective_caller_id_number={{ cid_num }}"/>
   <action application="set" data="effective_caller_id_name={{ cid_name }}"/>
   {% endif %}
   ```

This overrides the caller-ID **only for the outbound leg through the
gateway**. Internal extension-to-extension calls continue to use the
directory's `effective_caller_id_*` (= extension number), so callees
still see "101" when their colleague rings them.

## Alternatives considered

- **Push `outgoing_callerid` into `outbound_caller_id_*` in the directory
  template.** Rejected — `outbound_caller_id_*` is documented as the
  default outbound caller-ID, but its propagation through Sofia gateways
  depends on `caller-id-in-from` and other profile settings, so the fix
  would be silently gateway-specific. Setting `effective_caller_id_*` in
  the dialplan immediately before `bridge` is explicit and works
  regardless of gateway configuration.
- **Override caller-ID in `freeswitch_xml.py` directory render.**
  Rejected — directory-level override would also leak the PSTN
  caller-ID into internal calls.

## Cross-branch backport

Per `CLAUDE.md` versioning rules, the same fix ports to the `18.0`
branch with the aligned tail version (`18.0.1.9.3` for
`connect_freeswitch`). The backport ships as a separate PR.
