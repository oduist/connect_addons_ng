# ADR-018: Callflow language as Selection + multi-language Piper bundle

## Status
Accepted

## Context

`connect.callflow.language` was a free-text `Char` (default `'en-US'`),
consumed by two backends:

* **Twilio** — value passed verbatim to `<Say language="...">` (BCP-47).
* **FreeSWITCH** — `_get_piper_language()` stripped the region (`en-US` → `en`)
  and the result was passed to `mod_piper_tts` via `speak data="piper|<code>|<text>"`.

The bundled FreeSWITCH image only carried two Piper voice models keyed by
short codes: `en` (`en_US-lessac-medium`) and `ru` (`ru_RU-irina-medium`).
Any other code (e.g. typing `fr`) crashed at synthesis time because no
matching `<model>` existed in `piper_tts.conf.xml`.

Two problems to fix:

1. The admin had no way to discover which language codes actually work.
   Free-text invited typos and unsupported values.
2. Stripping the region collapsed `pt-BR` and `pt-PT` to a single `pt`
   model, preventing regional variants from coexisting.

## Decision

1. Convert `connect.callflow.language` from `Char` to `Selection`. The
   selection list is produced by a new model method
   `_get_language_selection()` so any addon can override it.
2. Use full **BCP-47 codes** (`en-US`, `pt-BR`, …) as both the Selection
   keys and the Piper model `language` attribute. Twilio Say already
   expects BCP-47 — no transformation needed on that side.
3. `connect_freeswitch._get_piper_language()` now returns `self.language`
   unchanged. `piper_tts.conf.xml` is regenerated with BCP-47 keys.
4. The bundled FreeSWITCH image gains medium-quality Piper voices for
   every code in the default selection — the intersection of Twilio Polly
   languages and Piper's medium voice catalog (26 languages).
5. A defensive post-migration coalesces any stored `language` value
   outside the selection back to `'en-US'`.

## Implementation

### Default language set

Intersection of Twilio Polly and Piper medium voices (one voice per code):

| Code | Voice | Code | Voice |
|------|-------|------|-------|
| ca-ES | upc_ona | pl-PL | gosia |
| cs-CZ | jirka | pt-BR | faber |
| da-DK | talesyntese | pt-PT | tugão *(stored locally as `tugao`)* |
| de-DE | thorsten | ro-RO | mihai |
| en-GB | alba | ru-RU | irina |
| en-US | lessac | sk-SK | lili |
| es-ES | davefx | sv-SE | nst |
| es-MX | claude (high) | tr-TR | dfki |
| fi-FI | harri | uk-UA | ukrainian_tts |
| fr-FR | siwis | vi-VN | vais1000 |
| hu-HU | anna | zh-CN | huayan |
| is-IS | salka | | |
| it-IT | paola | | |
| nl-BE | nathalie | | |
| nl-NL | mls | | |

`pt_PT-tugão`: filename downloaded from upstream contains a non-ASCII
character; we save it locally under the ASCII-only name `pt_PT-tugao-medium.onnx`
so the path in `piper_tts.conf.xml` and on the filesystem stays portable.

### Dialplan call sites

The Jinja2 templates in `data/fs_templates.xml` already render
`speak data="piper|{{ lang }}|{{ prompt }}"`. With the new
`_get_piper_language()` they receive `en-US` instead of `en`. The Piper
config picks up the same key from `<model language="en-US" ...>`.

### Backward compatibility

* Existing rows with `'en-US'` / `'ru-RU'` (the only defaults ever shipped)
  are valid Selection values → no data migration of those.
* The 19.0.3.1.2 post-migration of `connect` rewrites any other stored
  values to `'en-US'`. A warning is logged listing the original values.
* New Odoo code requires the new FreeSWITCH image: the language token
  format changed (short → BCP-47). Image and module versions are bumped
  together (`oduist/freeswitch:1.1.0`, `connect_freeswitch 19.0.1.9.0`).

## Consequences

* Admins choose from a clearly labelled list and cannot enter an
  unsupported value through the UI.
* Adding a language is a three-line change: a new tuple in
  `_get_language_selection`, a new `<model>` in `piper_tts.conf.xml`, and
  a new spec line in the Dockerfile download loop. Documented in
  `docs/admin/freeswitch-setup.md`.
* Image size grows by ~1.5–2 GB (≈26 voice models × ~50–70 MB). We accept
  the trade-off; a future ADR may introduce lazy download.
* `_get_piper_language()` stays on the FreeSWITCH side as a single point
  of mapping in case any future Piper model adopts a non-BCP-47 key.
