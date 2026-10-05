"""Fold the former connect_s3 module into connect_twilio.

S3 recording storage now ships inside connect_twilio. On a database where
connect_s3 was installed, its records (settings fields, selection values, the
S3 Storage view, action and menu) must keep their database ids and values, so
their external ids move to connect_twilio before it loads, and connect_s3 is
marked uninstalled so Odoo does not try to remove or reload it.
"""
import logging

_logger = logging.getLogger(__name__)

OLD = 'connect_s3'
NEW = 'connect_twilio'


def migrate(cr, version):
    if not version:
        return
    cr.execute(
        "SELECT id, state FROM ir_module_module WHERE name = %s", (OLD,))
    old = cr.fetchone()
    if not old:
        return
    old_id, old_state = old
    cr.execute("SELECT id FROM ir_module_module WHERE name = %s", (NEW,))
    new_id = cr.fetchone()[0]

    # Both modules extended connect.settings and connect.recording, so the
    # per-module model xmlids exist twice; keep the connect_twilio copy.
    cr.execute(
        """
        DELETE FROM ir_model_data old
         USING ir_model_data new
         WHERE old.module = %s AND new.module = %s AND old.name = new.name
        """,
        (OLD, NEW),
    )
    cr.execute(
        "UPDATE ir_model_data SET module = %s WHERE module = %s", (NEW, OLD))
    moved = cr.rowcount
    for table in ('ir_model_constraint', 'ir_model_relation'):
        cr.execute(
            "UPDATE {} SET module = %s WHERE module = %s".format(table),
            (new_id, old_id),
        )
    cr.execute(
        """
        UPDATE ir_module_module
           SET state = 'uninstalled', latest_version = NULL
         WHERE id = %s
        """,
        (old_id,),
    )
    _logger.info(
        'Merged %s (state %s) into %s: %s external ids moved.',
        OLD, old_state, NEW, moved)
