# ADR-026: Blank the caller-id NAME on outbound PSTN legs

## Status
Accepted

## Context

ADR-021 made outbound PSTN calls present the user's
`connect.user.outgoing_callerid.number` instead of the bare extension. As
part of that change the caller-id **name** was also pushed outwards
(`effective_caller_id_name = outgoing_callerid.friendly_name` on the
UA-originated dialplan route, and `origination_caller_id_name = cid_name`
on the click-to-call B-leg).

A live SIP trace toward the gateway (peoplefone) revealed two problems with
sending the name:

```
From: "C..line Rochat" <sip:+41215121141@83.228.193.184>;tag=...
Remote-Party-ID: "C..line Rochat" <sip:+41215121141@...>;party=calling;...
```

1. **Information disclosure.** The internal caller's personal name leaks to
   the PSTN and to the called party. The `friendly_name` is useful inside
   Odoo for identification, but there is no reason to advertise *who* is
   calling to the outside world — only the agreed outbound number should be
   presented.
2. **Encoding corruption.** Non-ASCII characters in the display name are
   mangled. "Céline" became "C..line": FreeSWITCH cleans the caller-id name
   to ASCII (`switch_clean_name_string`), replacing each byte with the high
   bit set by `.`, so the two UTF-8 bytes of `é` turned into `..`. Odoo
   serves the XML correctly as UTF-8 (`text/xml; charset=utf-8`); the
   corruption is entirely inside FreeSWITCH and cannot be fixed from Odoo
   without stripping the diacritics ourselves.

Both problems disappear if we simply do not send a display name on the
outbound trunk leg.

## Decision

Keep `connect.user.outgoing_callerid.friendly_name` in Odoo for internal
use, but **never send a caller-id display name on a leg that reaches the
PSTN**. Present only the number.

- **UA-originated calls** (`dialplan_outgoing_route` template +
  `connect.freeswitch.outgoing_route.generate_dialplan`): the route still
  sets `effective_caller_id_number` from `outgoing_callerid.number`, and now
  always blanks the name right before `bridge`:

  ```xml
  {% if cid_num %}
  <action application="set" data="effective_caller_id_number={{ cid_num }}"/>
  {% endif %}
  <action application="set" data="effective_caller_id_name="/>
  ```

  `generate_dialplan` no longer resolves or passes `cid_name`.

- **Click-to-call** (`connect.call._build...` originate in
  `connect_freeswitch/models/call.py`): the external B-leg sends an empty
  `origination_caller_id_name`; internal calls keep the name so the called
  colleague still sees who is ringing:

  ```python
  b_leg_name = cid_name if exten else ''
  ```

Blanking the name (`effective_caller_id_name` empty) makes Sofia emit a
nameless `From: <sip:NUMBER@host>` (and likewise for Remote-Party-ID /
P-Asserted-Identity), so nothing beyond the outbound number is disclosed.

Internal extension-to-extension calls are unaffected — they use
`dialplan_user_bridge` (which never touches caller-id) and the directory's
`effective_caller_id_*`, so a colleague still sees the caller's extension
and name.

## Alternatives considered

- **Transliterate the name to ASCII** (e.g. `unicodedata.normalize('NFKD')`
  → "Celine Rochat"). Fixes the corruption but still discloses the caller's
  identity to the PSTN, which is the more important concern. Rejected.
- **Send the number as the display name** (`name == number`). Avoids leaking
  the personal name and always yields a valid `From`, but adds a redundant
  display name and is not what was wanted (an empty name). Rejected.
- **Make it configurable** (per-route / per-user toggle to send the name).
  Deferred — the privacy-by-default behavior is the right default; a toggle
  can be added later if a deployment needs branded CNAM.

## Cross-branch backport

Per `CLAUDE.md` versioning rules, the same fix ports to the `18.0` branch
with the aligned tail version. The backport ships as a separate PR. No
FreeSWITCH image rebuild is needed — only Odoo-side template/model files
change, nothing under `connect_freeswitch/deploy/`.
