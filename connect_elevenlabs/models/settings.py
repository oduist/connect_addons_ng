"""Remnants of EL extensions to `connect.settings`.

Most EL settings moved to `connect.provider.elevenlabs.config` in
ODU-11 (ADR-023 Phase 6 / ADR-025). What stays on `connect.settings`:

- the `transcript_provider` Selection extension (EL is one of the
  selectable transcription backends — a core field with an EL option,
  not an EL-specific field).
- the license-side registration via `ODUIST_MODULES`.
"""
from odoo import fields, models
from odoo.addons.connect.models.license import ODUIST_MODULES

ODUIST_MODULES.append('connect_elevenlabs')


class Elevenlabsettings(models.Model):
    _inherit = 'connect.settings'

    transcript_provider = fields.Selection(
        selection_add=[('elevenlabs', 'Elevenlabs')],
        ondelete={'elevenlabs': 'set default'},
    )
