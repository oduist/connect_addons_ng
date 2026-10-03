"""Pre-migration: provider model separation (19.0.4.0.0, ADR-031).

Runs BEFORE the ORM registry is rebuilt during `odoo -u connect`.

The PBX-configuration models leave the core module and become independent
per-provider models (connect.freeswitch.*, connect.twilio.*,
connect.asterisk.*). This script only protects the data:

  1. Rename the moving tables to `_*_legacy` archives so Odoo's registry
     cleanup (`_process_end` -> ir.model.unlink with MODULE_UNINSTALL_FLAG)
     cannot drop them. Provider post-migrations copy the rows out of the
     archives (id-preserving); a later cleanup release drops the archives.
  2. Delete `ir.model.fields.selection` xmlid rows owned by the connect
     modules — same Odoo 19 ondelete-str bug dodge as in 19.0.3.1.0:
     without this, `_process_end` crashes trying to unlink selection rows
     of removed fields. The selections of surviving fields are re-registered
     on load.
  3. Delete the sms.composer inherit view + its ACL row: the wizard moved to
     connect_twilio (which re-creates both under its own module). On
     databases without connect_twilio the view would reference a dropped
     field (outgoing_callerid) and break the composer.

The legacy `connect_user` columns (exten, exten_number, outgoing_callerid)
are intentionally left in place — the FreeSWITCH post-migration reads them;
a later cleanup release removes them.
"""

import logging

_logger = logging.getLogger(__name__)


# Tables whose models leave the core module. Renamed (not dropped) so the
# provider post-migrations can copy the rows.
ARCHIVE_TABLES = [
    ('connect_exten',                     '_connect_exten_legacy'),
    ('connect_callflow',                  '_connect_callflow_legacy'),
    ('connect_callflow_choice',           '_connect_callflow_choice_legacy'),
    ('connect_callflow_connect_user_rel', '_connect_callflow_connect_user_rel_legacy'),
    ('connect_number',                    '_connect_number_legacy'),
    ('connect_endpoint',                  '_connect_endpoint_legacy'),
    ('connect_outgoing_callerid',         '_connect_outgoing_callerid_legacy'),
    ('connect_user_callflow',             '_connect_user_callflow_legacy'),
    ('connect_user_callflow_call',        '_connect_user_callflow_call_legacy'),
    ('connect_message_configuration',     '_connect_message_configuration_legacy'),
]

# xmlids owned by `connect` whose records must go away together with the
# moved sms.composer wizard (re-created by connect_twilio under its module).
SMS_COMPOSER_XMLIDS = [
    ('view_sms_composer_form_connect', 'ir.ui.view', 'ir_ui_view'),
    ('access_sms_composer_user', 'ir.model.access', 'ir_model_access'),
]


def _table_exists(cr, table):
    cr.execute(
        "SELECT 1 FROM information_schema.tables WHERE table_name = %s",
        (table,),
    )
    return bool(cr.fetchone())


def _archive_table(cr, source, archive):
    if not _table_exists(cr, source):
        return
    if _table_exists(cr, archive):
        _logger.warning(
            "archive target %s already exists; dropping source %s without archiving",
            archive, source,
        )
        cr.execute(f'DROP TABLE IF EXISTS "{source}" CASCADE')
        return
    cr.execute(f'ALTER TABLE "{source}" RENAME TO "{archive}"')
    _logger.info("archived table %s -> %s", source, archive)


def migrate(cr, version):
    if not version:
        return  # fresh install; nothing to migrate

    _logger.info("connect pre-migration: from %s to 19.0.4.0.0", version)

    # 1. Archive the moving tables.
    for source, archive in ARCHIVE_TABLES:
        _archive_table(cr, source, archive)

    # 2. Odoo 19 ondelete-str bug dodge (see module docstring). Provider
    # modules re-register their selections on load, so dropping the xmlid
    # bookkeeping rows is safe.
    cr.execute(
        """
        DELETE FROM ir_model_data
         WHERE module IN ('connect', 'connect_twilio', 'connect_freeswitch',
                          'connect_asterisk', 'connect_crm')
           AND model = 'ir.model.fields.selection'
        """
    )
    _logger.info("deleted %s selection-value ir.model.data rows", cr.rowcount)

    # 3. Remove the moved sms.composer view and ACL row (re-seeded by
    # connect_twilio when installed).
    for name, model, table in SMS_COMPOSER_XMLIDS:
        cr.execute(
            """
            SELECT res_id FROM ir_model_data
             WHERE module = 'connect' AND name = %s AND model = %s
            """,
            (name, model),
        )
        row = cr.fetchone()
        if not row:
            continue
        if row[0] and _table_exists(cr, table):
            cr.execute(f'DELETE FROM "{table}" WHERE id = %s', (row[0],))
        cr.execute(
            """
            DELETE FROM ir_model_data
             WHERE module = 'connect' AND name = %s AND model = %s
            """,
            (name, model),
        )
        _logger.info("removed moved record connect.%s", name)
