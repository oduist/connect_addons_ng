"""Pre-migration: monolithic connect (2.x) -> split connect + connect_twilio (19.0.3.1.0).

Runs BEFORE the ORM registry is rebuilt during `odoo -u connect -i connect_twilio`.

Goals:
  1. Archive tables of models that were removed from the codebase, so the admin
     can recover the data manually if needed (PBX groups, scheduled calls,
     transcription rules, documentation).
  2. Rebrand `ir.model.data` rows for records that MOVED from connect to
     connect_twilio (same xmlid name, different owning module). After rebranding,
     connect_twilio's XML load updates the existing record in place instead of
     creating a duplicate.
  3. Rename group xmlids (`group_connect_*` -> `group_*`) and the module
     category xmlid so the existing res.groups rows survive and user
     memberships are preserved.
  4. Bulk-delete old ir.model.access and ir.rule rows owned by module
     `connect` -- they will be re-seeded by the new XML under different xmlids.
  5. Delete a handful of known orphan menus/views/actions that no longer exist
     in any module so the UI does not show zombies.
"""

import logging

_logger = logging.getLogger(__name__)


# Records that moved from `connect` to `connect_twilio` under the SAME xmlid name.
# After rebranding the `module` column, the connect_twilio XML load will update
# the existing record in place.
MOVED_TO_TWILIO_NAMES = [
    # ir.cron
    'fetch_call_prices',
    # connect.twiml seed data
    'domain_route_call',
    'twiml_reject',
    'twiml_connection_failed',
    # connect.message_content_template seed data
    'voice_call_request',
    # ir.actions.act_window
    'action_connect_whatsapp_sender',
    'action_connect_whatsapp_composer',
    'action_connect_message_content_template',
]

# Old xmlid -> new xmlid for records that stayed in `connect` but were renamed.
RENAME_IN_CONNECT = [
    ('group_connect_admin',    'group_admin'),
    ('group_connect_user',     'group_user'),
    ('group_connect_webhook',  'group_webhook'),
    ('module_connect_category', 'module_category_connect'),
]

# XML IDs in module `connect` that have no counterpart anywhere in the new
# codebase. Both the ir.model.data row AND the underlying record will be
# deleted (only for "safe" model types: menus, views, actions, crons).
ORPHAN_XMLIDS = [
    # Top-level menus replaced by menu_connect_root etc.
    'connect_top_menu',
    'connect_voice_menu',
    'connect_messaging_menu',
    'connect_ai_menu',
    'connect_reports_menu',
    'connect_settings_menu',
    'connect_debug_menu',
    'connect_documentation_menu',
    'connect_sms_menu',
    'connect_debug_messages_menu',
    # PBX group UI
    'connect_pbx_group_menu',
    'connect_pbx_group_tree',
    'connect_pbx_group_form',
    'connect_pbx_group_action',
    # Twiml/domain views -- connect_twilio uses different view ids
    'twiml_action',
    'connect_twiml_form',
    'connect_twiml_search',
    'domain_action',
    'connect_domain_list',
    'connect_domain_form',
    # Whatsapp/MCT menus -- connect_twilio uses menu_connect_*
    'connect_whatsapp_sender_menu',
    'connect_message_content_template_menu',
    # Removed wizards
    'action_connect_originate_to_wizard',
    'view_connect_originate_to_wizard_form',
    'view_connect_purchase_confirm_form',
    # Twiml park/unpark seed data -- not present in connect_twilio
    'twiml_park_call',
    'twiml_unpark_call',
]

# Only delete the backing record if its model is one of these (menus/views/
# actions/crons are safe; arbitrary model rows we leave alone).
SAFE_BACKING_MODELS = frozenset({
    'ir.ui.menu',
    'ir.ui.view',
    'ir.cron',
    'ir.actions.act_window',
    'ir.actions.server',
    'ir.actions.client',
    'ir.model.access',
    'ir.module.category',
})

# Tables to archive (model removed entirely). Key is the model's main table;
# additional entries cover M2M rel tables that would otherwise be dropped.
ARCHIVE_TABLES = [
    ('connect_pbx_group',                  '_connect_pbx_group_archive'),
    ('connect_scheduled_call',             '_connect_scheduled_call_archive'),
    ('connect_transcription_rule',         '_connect_transcription_rule_archive'),
    ('connect_documentation',              '_connect_documentation_archive'),
    ('connect_pbx_group_connect_user_rel', '_connect_pbx_group_connect_user_rel_archive'),
    ('connect_user_connect_pbx_group_rel', '_connect_user_connect_pbx_group_rel_archive'),
    ('connect_pbx_group_res_users_rel',    '_connect_pbx_group_res_users_rel_archive'),
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

    _logger.info("connect pre-migration: from %s to 19.0.3.1.0", version)

    # 1. Archive dropped-model tables so Odoo's registry cleanup leaves data alone.
    for source, archive in ARCHIVE_TABLES:
        _archive_table(cr, source, archive)

    # 2. Rebrand records that moved to connect_twilio (same xmlid name).
    cr.execute(
        """
        UPDATE ir_model_data
           SET module = 'connect_twilio'
         WHERE module = 'connect'
           AND name = ANY(%s)
        """,
        (MOVED_TO_TWILIO_NAMES,),
    )
    _logger.info("rebranded %s ir.model.data rows connect -> connect_twilio", cr.rowcount)

    # 3. Rename groups (+ module category) so user memberships survive.
    for old, new in RENAME_IN_CONNECT:
        cr.execute(
            """
            UPDATE ir_model_data
               SET name = %s
             WHERE module = 'connect'
               AND name = %s
            """,
            (new, old),
        )
        if cr.rowcount:
            _logger.info("renamed xmlid connect.%s -> connect.%s", old, new)

    # 4. Wipe old ir.model.access and ir.rule rows owned by `connect`.
    # The new XML re-seeds them under new xmlids (access_*_admin etc.).
    cr.execute(
        """
        DELETE FROM ir_model_access
         WHERE id IN (
           SELECT res_id FROM ir_model_data
            WHERE module = 'connect' AND model = 'ir.model.access'
         )
        """
    )
    access_deleted = cr.rowcount
    cr.execute(
        """
        DELETE FROM ir_model_data
         WHERE module = 'connect' AND model = 'ir.model.access'
        """
    )
    _logger.info(
        "deleted %s ir.model.access rows and %s ir.model.data entries",
        access_deleted, cr.rowcount,
    )

    cr.execute(
        """
        DELETE FROM ir_rule
         WHERE id IN (
           SELECT res_id FROM ir_model_data
            WHERE module = 'connect' AND model = 'ir.rule'
         )
        """
    )
    rules_deleted = cr.rowcount
    cr.execute(
        """
        DELETE FROM ir_model_data
         WHERE module = 'connect' AND model = 'ir.rule'
        """
    )
    _logger.info(
        "deleted %s ir.rule rows and %s ir.model.data entries",
        rules_deleted, cr.rowcount,
    )

    # 4b. Drop IMD rows for selection values owned by `connect`. Otherwise
    # Odoo's `_process_end` would iterate them and try to unlink selection
    # rows for old fields (twilio_edge, sip_priority, fallback_destination,
    # destination=twiml, ...) -- triggering an Odoo 19 core bug where
    # `field.ondelete` is a str instead of a dict
    # (AttributeError: 'str' object has no attribute 'get').
    # The selection rows themselves are either re-registered by NEW field
    # classes (in connect_twilio) or left as benign leftovers.
    cr.execute(
        """
        DELETE FROM ir_model_data
         WHERE module = 'connect'
           AND model = 'ir.model.fields.selection'
        """
    )
    _logger.info("deleted %s selection-value ir.model.data rows", cr.rowcount)

    # 5. Drop named orphan xmlids (menus/views/actions with no counterpart).
    cr.execute(
        """
        SELECT id, model, res_id
          FROM ir_model_data
         WHERE module = 'connect'
           AND name = ANY(%s)
        """,
        (ORPHAN_XMLIDS,),
    )
    orphans = cr.fetchall()
    imd_ids = [row[0] for row in orphans]
    by_model = {}
    for _imd_id, model, res_id in orphans:
        if res_id:
            by_model.setdefault(model, set()).add(res_id)

    for model, res_ids in by_model.items():
        if model not in SAFE_BACKING_MODELS:
            continue
        table = model.replace('.', '_')
        if not _table_exists(cr, table):
            continue
        ids = list(res_ids)
        # Detach self-referential children so FK constraints don't block the delete.
        # ir.ui.menu has parent_id; ir.ui.view has inherit_id. Other OLD modules
        # (connect_byoc, connect_crm, ...) may have menus/views hanging off the
        # orphaned roots we are about to drop.
        if model == 'ir.ui.menu':
            cr.execute(
                'UPDATE ir_ui_menu SET parent_id = NULL WHERE parent_id = ANY(%s)',
                (ids,),
            )
            if cr.rowcount:
                _logger.info("reparented %s orphaned menu children to top level", cr.rowcount)
        elif model == 'ir.ui.view':
            cr.execute(
                'UPDATE ir_ui_view SET inherit_id = NULL WHERE inherit_id = ANY(%s)',
                (ids,),
            )
            if cr.rowcount:
                _logger.info("detached %s views inheriting from orphaned views", cr.rowcount)
        cr.execute(
            f'DELETE FROM "{table}" WHERE id = ANY(%s)',
            (ids,),
        )
        _logger.info("deleted %s orphan rows from %s", cr.rowcount, table)

    if imd_ids:
        cr.execute("DELETE FROM ir_model_data WHERE id = ANY(%s)", (imd_ids,))
        _logger.info("deleted %s orphan ir.model.data rows", cr.rowcount)

    _logger.info("connect pre-migration complete")
