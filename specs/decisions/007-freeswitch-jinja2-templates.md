# ADR-007: Replace ElementTree XML generation with Jinja2 templates

**Status:** Accepted
**Date:** 2026-03-18

## Context

FreeSWITCH XML configs (directory, dialplan, configuration) were generated programmatically using `xml.etree.ElementTree` (`ET.Element`/`ET.SubElement`) across 7 files (~580 lines). This approach had two problems:

1. **Readability** — The Python code that builds XML trees is hard to read. You can't see the XML structure at a glance; it's buried in nested `ET.SubElement()` calls.
2. **Customizability** — Administrators had no way to modify the generated XML without changing Python code.

Jinja2 was already a project dependency (used for TwiML rendering in `connect_twilio`).

## Decision

Replace all ElementTree XML generation with Jinja2 templates stored in a new Odoo model `connect.freeswitch.template`.

### Architecture

**Two layers:**
- **Envelope** (controller) — The `<document>/<section>` wrapper stays as simple string formatting in the controller. It's structural boilerplate that admins should not edit.
- **Fragments** (templates) — The actual config content is stored as Jinja2 templates. Each template has a stable `key` for code lookup and an editable `content` field.

**11 templates** covering directory (user, full), dialplan (user bridge, IVR, ring group, inbound DID, outgoing route, system), and configuration (sofia, gateway, xml_rpc).

### Model design

- `key` (unique, readonly) — stable identifier used in code
- `content` — editable Jinja2 template
- `default_content` — factory default for reset
- `is_customized` — computed flag (content != default_content)
- Templates seeded via `data/fs_templates.xml` with `noupdate="1"`

### Rendering

Template content is cached with `@tools.ormcache`. Uses `jinja2.StrictUndefined` to fail loudly on missing variables. Only `connect.group_admin` can edit templates.

### Signature change

Model methods changed from `generate_dialplan(self, context_el, params)` (mutating an ET parent) to `generate_dialplan(self, params)` (returning an XML string). The controller concatenates strings.

## Consequences

- XML templates are now readable — the actual XML structure is visible
- Administrators can customize generated configs through the Odoo UI (PBX > XML Templates)
- "Reset to Default" button allows recovery from broken customizations
- Template cache avoids extra DB queries on every FreeSWITCH request
- No ElementTree dependency in the XML generation path
