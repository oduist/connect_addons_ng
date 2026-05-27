"""ODU-12: migrate legacy `connect.number.destination` Selection-extension
values ('fs_fifo', 'twiml', 'elevenlabs_agent') to the new typed scheme
(destination='provider' + destination_provider_id).

Each provider module used to selection_add its own destination value;
this post-migrate runs on `connect` upgrade and consolidates those
values into the stable core scheme. The provider-specific Many2one
pointers (fs_fifo_id, twiml, elevenlabs_agent) stay where they are —
they remain the actual destination resource pointer; only the
Selection value normalises.

Idempotent: gated on the legacy value being present in the destination
column.
"""
import logging

_logger = logging.getLogger(__name__)

LEGACY_VALUE_TO_PROVIDER_CODE = {
    'fs_fifo': 'freeswitch',
    'twiml': 'twilio',
    'elevenlabs_agent': 'elevenlabs',
}


def migrate(cr, version):
    if not version:
        return

    # Resolve provider ids from codes.
    cr.execute("SELECT code, id FROM connect_provider")
    code_to_id = dict(cr.fetchall())

    counts = {}
    for legacy, code in LEGACY_VALUE_TO_PROVIDER_CODE.items():
        pid = code_to_id.get(code)
        if not pid:
            continue
        cr.execute(
            "UPDATE connect_number "
            "SET destination = 'provider', destination_provider_id = %s "
            "WHERE destination = %s",
            (pid, legacy),
        )
        if cr.rowcount:
            counts[legacy] = cr.rowcount

    if counts:
        _logger.info(
            'connect.number destination normalised: %s',
            ', '.join(f'{k}={v}' for k, v in counts.items()),
        )
