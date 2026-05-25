"""Drop NOT NULL on connect_user columns that used to be Twilio-required.

In 19.0.1.1.3 the following fields on connect.user (inherited from
connect_twilio) lose their required=True so the user model is usable
on installations that also carry connect_freeswitch (or any other
provider) without forcing every user to carry Twilio-shaped data:

  - username
  - domain (Many2one -> connect.domain)
  - twilio_edge
  - sip_priority
  - client_priority
  - sip_ring_timeout
  - client_ring_timeout

Field defaults still apply on fresh records, but existing rows on a
mixed-install DB can now legitimately have NULL here. Odoo's auto-init
will not drop the NOT NULL constraint added by previous required=True
declarations, so we drop them manually here. Idempotent.
"""
import logging

_logger = logging.getLogger(__name__)

_RELAXED_COLUMNS = (
    'username',
    'domain',
    'twilio_edge',
    'sip_priority',
    'client_priority',
    'sip_ring_timeout',
    'client_ring_timeout',
)


def migrate(cr, version):
    if not version:
        return
    for col in _RELAXED_COLUMNS:
        cr.execute(
            f'ALTER TABLE connect_user ALTER COLUMN "{col}" DROP NOT NULL'
        )
    _logger.info(
        'connect_user NOT NULL dropped on: %s',
        ', '.join(_RELAXED_COLUMNS),
    )
