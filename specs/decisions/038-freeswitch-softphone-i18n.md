# ADR-038: Localize the FreeSWITCH browser softphone

## Status
Accepted

## Context

Issue #47: the softphone widget shipped with hardcoded UI strings. The
original mix of Russian and English was already reduced to English-only
earlier (commit 2248333), but none of the JS strings went through Odoo's
`_t()`, string literals inside OWL template expressions
(`t-esc="... || 'Unknown'"`, ternary `t-att-title`) are invisible to the
translation exporter, and the repository shipped **no i18n catalog at
all** — no module had an `i18n/` directory, so even the auto-extracted
OWL text nodes (Dialer, Answer, …) had nothing to translate against.
The customer base is Swiss (de_CH / fr_CH / it_CH).

Python-side parking toasts and `UserError`s
(`fs_parking_slot.py`, the park branch of `call.py`) surface in the same
softphone panel and were also untranslated.

## Decision

1. **Wrap JS strings in `_t()`** from `@web/core/l10n/translation` in
   `phone_systray.js` (connection/call state texts), `parking_panel.js`
   (toasts, slot labels) and `endpoint_password.js`. String literals in
   OWL template expressions move into component getters
   (`displayCallerName`, `revealToggleLabel`) so they are extractable.
   Plain OWL text nodes and static `title`/`placeholder`/`aria-label`
   attributes stay as-is — the exporter picks them up automatically.
2. **`verto_client.js` is deliberately not translated.** Its error
   strings reach only `console.error` (developer-facing), and the file
   is a dependency-free protocol client; adding an `@web` import for
   invisible strings is not worth it. If its `onError` is ever wired to
   the notification service, translate the strings in that change.
3. **Wrap the Python parking strings in `_()`** — they render as toasts
   inside the softphone parking panel.
4. **Ship a hand-maintained catalog scoped to the softphone UI**:
   `i18n/connect_freeswitch.pot` + `de.po`, `fr.po`, `it.po`, `ru.po`
   (~53 terms). A full-module export (hundreds of field/view terms) is
   out of scope for the issue; untranslated terms simply stay English.
   Every entry carries the comments Odoo 19's PoFileReader requires
   (`#. module:`, `#. odoo-javascript`/`#. odoo-python`, a
   `#: code:...:0` occurrence) — without them the record is dropped or
   the whole module load fails. The pot and po comments are kept
   identical because the loader merges pot comments over po entries.
5. **Base language codes for file names** (`de.po`, not `de_DE.po`):
   Odoo loads `i18n/<base>.po` then `i18n/<ll_CC>.po` for a `ll_CC`
   lang, so one `de.po` serves de_DE and de_CH, `fr.po` serves
   fr_FR/fr_CH, `it.po` serves it_IT/it_CH. German translations avoid
   «ß» so the same text is valid Swiss High German. Country-specific
   files can be added later only if wording must diverge.
6. **`ru.po` included** — near-zero cost while the catalog is written.

## Consequences

- The softphone (dialer, parking panel, endpoint-password widget and
  parking toasts) renders in the user's UI language for de/fr/it/ru,
  falling back to English elsewhere.
- JS/OWL translations are read straight from the po files (no DB
  import), but the in-process translation cache means **a server
  restart is required** after changing po files on a live deployment.
- The catalog is maintained by hand: when adding softphone strings,
  add the po entries in the same commit (`odoo-bin i18n export` can be
  used as an oracle for msgid spelling). Machine translations can be
  refined by the customer directly in the po files.
- `connect_freeswitch/tests/test_i18n.py` guards the catalog: it loads
  the web and python bundles for de_DE/fr_CH/it_CH/ru_RU and asserts
  key terms are present and non-empty (this also proves the base-lang
  fallback for the Swiss locales).
