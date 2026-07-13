"""Adopt the legacy Twilio-only models before provider separation.

The Odoo 18 branch already kept TwiML applications and SIP domains in
``connect_twilio``, but their technical model names still used the shared
``connect.*`` namespace.  Rename their tables before the registry loads the
new ``connect.twilio.*`` models so record ids and PostgreSQL foreign keys are
preserved in place.
"""

import logging


_logger = logging.getLogger(__name__)


MODEL_TABLE_RENAMES = (
    ('connect_twiml', 'connect_twilio_twiml'),
    ('connect_domain', 'connect_twilio_domain'),
)

MODEL_RENAMES = (
    ('connect.twiml', 'connect.twilio.twiml'),
    ('connect.domain', 'connect.twilio.domain'),
)


def _table_exists(cr, table):
    cr.execute(
        "SELECT 1 FROM information_schema.tables WHERE table_name = %s",
        (table,),
    )
    return bool(cr.fetchone())


def migrate(cr, version):
    if not version:
        return

    _logger.info(
        "connect_twilio pre-migration: from %s to 18.0.2.0.1", version)

    for source, target in MODEL_TABLE_RENAMES:
        if not _table_exists(cr, source):
            continue
        if _table_exists(cr, target):
            raise RuntimeError(
                f"cannot preserve {source}: target table {target} already exists")
        cr.execute(f'ALTER TABLE "{source}" RENAME TO "{target}"')
        _logger.info("renamed Twilio table %s -> %s", source, target)

    for old_model, new_model in MODEL_RENAMES:
        cr.execute(
            "UPDATE ir_model_data SET model = %s WHERE model = %s",
            (new_model, old_model),
        )
        _logger.info(
            "updated %s ir.model.data rows from %s to %s",
            cr.rowcount, old_model, new_model,
        )

    if _table_exists(cr, 'connect_twilio_twiml'):
        cr.execute(
            """
            UPDATE connect_twilio_twiml
               SET model = 'connect.twilio.domain'
             WHERE model = 'connect.domain'
            """
        )
        _logger.info("updated %s TwiML model references", cr.rowcount)

    _logger.info("connect_twilio legacy model adoption complete")
