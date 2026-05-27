from odoo import fields, models


class Number(models.Model):
    _name = 'connect.number'
    _description = 'Phone Number'
    _rec_name = 'phone_number'
    _order = 'phone_number'

    is_default = fields.Boolean(string='Default')
    phone_number = fields.Char(required=True)
    friendly_name = fields.Char()
    # ODU-12: stable core enum. Provider-specific destinations
    # ('fs_fifo', 'twiml', 'elevenlabs_agent') used to be selection_add'ed
    # by each provider module; they now collapse into destination='provider'
    # + destination_provider_id pointing at which provider routes the call.
    # The per-provider M2O fields (fs_fifo_id, twiml, elevenlabs_agent) stay
    # on the provider-side inherit and remain the actual destination
    # pointer.
    # ondelete dict-form is required when provider modules drop a
    # previously selection_add'ed value (e.g. 'twiml', 'fs_fifo',
    # 'elevenlabs_agent' in ODU-12). The per-value mapping lets Odoo's
    # cleanup walk individual orphaned values cleanly.
    destination = fields.Selection(selection=[
        ('user', 'User'),
        ('callflow', 'CallFlow'),
        ('provider', 'Provider'),
    ], ondelete={
        'user': 'set null',
        'callflow': 'set null',
        'provider': 'set null',
    })
    callflow = fields.Many2one('connect.callflow', ondelete='set null')
    user = fields.Many2one('connect.user', ondelete='set null')
    provider_id = fields.Many2one(
        'connect.provider', ondelete='set null', index=True, copy=False,
        help='Telephony provider that owns this DID (provenance).',
    )
    destination_provider_id = fields.Many2one(
        'connect.provider', ondelete='set null',
        string='Destination Provider',
        help='When destination=provider, which provider routes inbound '
             'calls. Provider modules surface their per-provider M2O '
             '(fs_fifo_id, twiml, …) conditional on this field.',
    )

    def write(self, vals):
        if 'destination' in vals:
            dest = vals['destination']
            if dest != 'user':
                vals.setdefault('user', False)
            if dest != 'callflow':
                vals.setdefault('callflow', False)
            if dest != 'provider':
                vals.setdefault('destination_provider_id', False)
        return super().write(vals)
