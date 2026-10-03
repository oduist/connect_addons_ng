"""Pre-migration: detach surviving FKs before provider model separation.

Runs BEFORE the connect_freeswitch registry init. During init Odoo's
``check_foreign_keys`` re-points ``connect_fs_fifo.exten`` /
``fallback_exten_id`` at the new ``connect_freeswitch_exten`` table — but the
new table is only populated by our post-migration, so any non-NULL value
would violate the fresh FK and abort the upgrade.

Stash the values into temporary ``_mig_*`` columns, NULL the originals and
drop the stale constraints; the post-migration copies the legacy data and
restores the stashed values. The ``fs_fifo_endpoint_rel`` M2M rows get the
same treatment (stashed into a temp table).
"""

import logging

_logger = logging.getLogger(__name__)


def _table_exists(cr, table):
    cr.execute(
        "SELECT 1 FROM information_schema.tables WHERE table_name = %s",
        (table,),
    )
    return bool(cr.fetchone())


def _column_exists(cr, table, column):
    cr.execute(
        """
        SELECT 1 FROM information_schema.columns
         WHERE table_name = %s AND column_name = %s
        """,
        (table, column),
    )
    return bool(cr.fetchone())


def _drop_fk(cr, table, column):
    cr.execute(
        """
        SELECT con.conname
          FROM pg_constraint con
          JOIN pg_class rel ON rel.oid = con.conrelid
          JOIN pg_attribute att ON att.attrelid = con.conrelid
               AND att.attnum = ANY(con.conkey)
         WHERE con.contype = 'f'
           AND rel.relname = %s
           AND att.attname = %s
        """,
        (table, column),
    )
    for (conname,) in cr.fetchall():
        cr.execute(f'ALTER TABLE "{table}" DROP CONSTRAINT "{conname}"')
        _logger.info("dropped stale FK %s on %s.%s", conname, table, column)


def migrate(cr, version):
    if not version:
        return  # fresh install; nothing to migrate
    # Only needed on the provider-separation upgrade path: the legacy
    # archive exists only when the connect 19.0.4.0.0 pre-migration ran.
    if not _table_exists(cr, '_connect_exten_legacy'):
        return

    _logger.info(
        "connect_freeswitch pre-migration: from %s to 19.0.2.0.0", version)

    if _table_exists(cr, 'connect_fs_fifo'):
        for column, stash in (
                ('exten', '_mig_exten'),
                ('fallback_exten_id', '_mig_fallback_exten_id')):
            if not _column_exists(cr, 'connect_fs_fifo', column):
                continue
            cr.execute(
                f'ALTER TABLE connect_fs_fifo ADD COLUMN IF NOT EXISTS "{stash}" integer')
            cr.execute(
                f'UPDATE connect_fs_fifo SET "{stash}" = "{column}", "{column}" = NULL '
                f'WHERE "{column}" IS NOT NULL')
            _drop_fk(cr, 'connect_fs_fifo', column)

    if (_table_exists(cr, 'fs_fifo_endpoint_rel')
            and not _table_exists(cr, '_fs_fifo_endpoint_rel_legacy')):
        cr.execute(
            'CREATE TABLE _fs_fifo_endpoint_rel_legacy AS '
            'SELECT * FROM fs_fifo_endpoint_rel')
        cr.execute('DELETE FROM fs_fifo_endpoint_rel')
        _drop_fk(cr, 'fs_fifo_endpoint_rel', 'endpoint_id')
        _logger.info("stashed fs_fifo_endpoint_rel rows")
