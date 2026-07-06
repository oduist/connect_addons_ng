"""Post-migration: adopt PBX data after provider model separation (ADR-031).

Runs AFTER the connect_freeswitch registry is loaded during
`odoo -u connect_freeswitch` (the connect 19.0.4.0.0 pre-migration has
already renamed the old core tables to `_*_legacy`).

Copies the legacy shared PBX data into the new FreeSWITCH-owned models,
preserving record ids so every FK value stays valid:

  _connect_exten_legacy               -> connect_freeswitch_exten
  _connect_callflow_legacy            -> connect_freeswitch_callflow
  _connect_callflow_choice_legacy     -> connect_freeswitch_callflow_choice
  _connect_callflow_connect_user_rel_legacy -> connect_freeswitch_callflow_connect_user_rel
  _connect_number_legacy              -> connect_freeswitch_number
  _connect_endpoint_legacy            -> connect_freeswitch_endpoint
  _connect_outgoing_callerid_legacy   -> connect_freeswitch_outgoing_callerid

plus the legacy connect_user columns (exten, outgoing_callerid) into the
new per-provider columns, and repairs foreign keys of surviving tables
(connect_fs_fifo, fs_fifo_endpoint_rel) that still point at the renamed
legacy tables.

Production reality (owner decision): exactly one production database
exists and it runs connect_freeswitch only, so every legacy row belongs
to FreeSWITCH — no per-provider row filtering is needed. connect_twilio /
connect_asterisk ship no data migration.
"""

import logging

_logger = logging.getLogger(__name__)

# Reference strings stored in the legacy exten.model column -> new models.
EXTEN_MODEL_REMAP = {
    'connect.callflow': 'connect.freeswitch.callflow',
    'connect.endpoint': 'connect.freeswitch.endpoint',
    # unchanged: connect.user, connect.fs_fifo
}

# Legacy exten destinations that do NOT exist on the FreeSWITCH side.
EXTEN_SKIP_MODELS = ('connect.twiml',)


def _table_exists(cr, table):
    cr.execute(
        "SELECT 1 FROM information_schema.tables WHERE table_name = %s",
        (table,),
    )
    return bool(cr.fetchone())


def _columns(cr, table):
    cr.execute(
        """
        SELECT column_name FROM information_schema.columns
         WHERE table_name = %s
        """,
        (table,),
    )
    return {row[0] for row in cr.fetchall()}


def _copy_table(cr, source, target, where=''):
    """Id-preserving copy of all columns common to source and target."""
    if not _table_exists(cr, source) or not _table_exists(cr, target):
        return 0
    cr.execute(f'SELECT COUNT(*) FROM "{target}"')
    if cr.fetchone()[0]:
        _logger.info("%s already populated; skipping copy from %s", target, source)
        return 0
    common = sorted(_columns(cr, source) & _columns(cr, target))
    if not common:
        return 0
    cols = ', '.join(f'"{c}"' for c in common)
    cr.execute(
        f'INSERT INTO "{target}" ({cols}) SELECT {cols} FROM "{source}" {where}')
    copied = cr.rowcount
    if 'id' in common:
        cr.execute(
            f"SELECT setval(pg_get_serial_sequence('{target}', 'id'),"
            f" (SELECT COALESCE(MAX(id), 1) FROM \"{target}\"))")
    _logger.info("copied %s rows %s -> %s", copied, source, target)
    return copied


def _fix_fk(cr, table, column, ref_table, ondelete='SET NULL'):
    """Re-point a FK that still targets a renamed legacy table."""
    if not _table_exists(cr, table) or not _table_exists(cr, ref_table):
        return
    cr.execute(
        """
        SELECT con.conname, ref.relname
          FROM pg_constraint con
          JOIN pg_class rel ON rel.oid = con.conrelid
          JOIN pg_class ref ON ref.oid = con.confrelid
          JOIN pg_attribute att ON att.attrelid = con.conrelid
               AND att.attnum = ANY(con.conkey)
         WHERE con.contype = 'f'
           AND rel.relname = %s
           AND att.attname = %s
        """,
        (table, column),
    )
    for conname, referenced in cr.fetchall():
        if referenced == ref_table:
            continue
        cr.execute(f'ALTER TABLE "{table}" DROP CONSTRAINT "{conname}"')
        cr.execute(
            f'ALTER TABLE "{table}" ADD CONSTRAINT "{conname}" '
            f'FOREIGN KEY ("{column}") REFERENCES "{ref_table}"(id) '
            f'ON DELETE {ondelete}')
        _logger.info(
            "repointed FK %s.%s: %s -> %s", table, column, referenced, ref_table)


def migrate(cr, version):
    if not version:
        return  # fresh install; nothing to migrate

    _logger.info(
        "connect_freeswitch post-migration: from %s to 19.0.2.0.0", version)

    # 1. Extensions (skip Twilio-only destinations, remap model strings).
    skip = ', '.join("'%s'" % m for m in EXTEN_SKIP_MODELS)
    copied = _copy_table(
        cr, '_connect_exten_legacy', 'connect_freeswitch_exten',
        where=f"WHERE model IS NULL OR model NOT IN ({skip})")
    if copied:
        for old, new in EXTEN_MODEL_REMAP.items():
            cr.execute(
                'UPDATE connect_freeswitch_exten SET model = %s WHERE model = %s',
                (new, old))

    # 2. Callflows, choices, ring_users M2M.
    copied = _copy_table(cr, '_connect_callflow_legacy', 'connect_freeswitch_callflow')
    if copied:
        # FreeSWITCH IVR is DTMF-only; neutralize any speech values that a
        # previously-installed Twilio module could have left behind.
        cr.execute(
            """
            UPDATE connect_freeswitch_callflow
               SET gather_input_type = 'dtmf'
             WHERE gather_input_type IS DISTINCT FROM 'dtmf'
            """)
    _copy_table(
        cr, '_connect_callflow_choice_legacy', 'connect_freeswitch_callflow_choice')
    if (_table_exists(cr, '_connect_callflow_connect_user_rel_legacy')
            and _table_exists(cr, 'connect_freeswitch_callflow_connect_user_rel')):
        cr.execute('SELECT COUNT(*) FROM connect_freeswitch_callflow_connect_user_rel')
        if not cr.fetchone()[0]:
            cr.execute(
                """
                INSERT INTO connect_freeswitch_callflow_connect_user_rel
                       (connect_freeswitch_callflow_id, connect_user_id)
                SELECT connect_callflow_id, connect_user_id
                  FROM _connect_callflow_connect_user_rel_legacy
                """)
            _logger.info("copied %s callflow ring_users links", cr.rowcount)

    # 3. Numbers, endpoints, caller IDs.
    copied = _copy_table(cr, '_connect_number_legacy', 'connect_freeswitch_number')
    if copied:
        # Twilio-only destinations do not exist on the FreeSWITCH model.
        cr.execute(
            """
            UPDATE connect_freeswitch_number
               SET destination = NULL
             WHERE destination NOT IN ('user', 'callflow', 'fs_fifo')
            """)
    _copy_table(cr, '_connect_endpoint_legacy', 'connect_freeswitch_endpoint')
    _copy_table(
        cr, '_connect_outgoing_callerid_legacy',
        'connect_freeswitch_outgoing_callerid')

    # 4. connect_user provider columns from the legacy core columns.
    user_cols = _columns(cr, 'connect_user')
    if 'exten' in user_cols and 'freeswitch_exten' in user_cols:
        cr.execute(
            """
            UPDATE connect_user u
               SET freeswitch_exten = u.exten
             WHERE u.exten IS NOT NULL
               AND u.freeswitch_exten IS NULL
               AND EXISTS (SELECT 1 FROM connect_freeswitch_exten e
                            WHERE e.id = u.exten)
            """)
        _logger.info("linked %s users to their FreeSWITCH extension", cr.rowcount)
        cr.execute(
            """
            UPDATE connect_user u
               SET freeswitch_exten_number = e.number
              FROM connect_freeswitch_exten e
             WHERE u.freeswitch_exten = e.id
            """)
    if 'outgoing_callerid' in user_cols and 'freeswitch_outgoing_callerid' in user_cols:
        cr.execute(
            """
            UPDATE connect_user u
               SET freeswitch_outgoing_callerid = u.outgoing_callerid
             WHERE u.outgoing_callerid IS NOT NULL
               AND u.freeswitch_outgoing_callerid IS NULL
               AND EXISTS (SELECT 1 FROM connect_freeswitch_outgoing_callerid c
                            WHERE c.id = u.outgoing_callerid)
            """)
        _logger.info(
            "linked %s users to their FreeSWITCH caller ID", cr.rowcount)

    # 5. Recompute stored related exten_number columns of copied tables.
    for table in ('connect_freeswitch_callflow', 'connect_freeswitch_endpoint'):
        cr.execute(
            f"""
            UPDATE "{table}" t
               SET exten_number = e.number
              FROM connect_freeswitch_exten e
             WHERE t.exten = e.id
            """)
    if _table_exists(cr, 'connect_fs_fifo'):
        cr.execute(
            """
            UPDATE connect_fs_fifo t
               SET exten_number = e.number
              FROM connect_freeswitch_exten e
             WHERE t.exten = e.id
            """)

    # 6. Repair FKs of surviving tables that still point at legacy tables.
    _fix_fk(cr, 'connect_fs_fifo', 'exten', 'connect_freeswitch_exten')
    _fix_fk(cr, 'connect_fs_fifo', 'fallback_exten_id', 'connect_freeswitch_exten')
    _fix_fk(cr, 'fs_fifo_endpoint_rel', 'endpoint_id',
            'connect_freeswitch_endpoint', ondelete='CASCADE')

    _logger.info("connect_freeswitch post-migration done")
