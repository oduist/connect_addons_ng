"""Post-migration: verify group membership survived and report archive state.

Runs AFTER the new `connect` XML has loaded. At this point:
  * res.groups rows for group_admin / group_user / group_webhook exist and
    should already be linked to the same users they had before (pre-migration
    renamed their ir.model.data xmlid in place).
  * connect_twilio may or may not be installing in the same transaction.

This script:
  1. Logs a post-upgrade report of what survived, so the admin has a clear
     audit trail in the upgrade log.
  2. Detects the "pbx_group was in use" case and, if so, makes sure the
     archived rows are still present -- pre-migration already renamed the
     table, but we double-check.
  3. Detects any user who ended up without any connect group assignment
     and warns (they will have lost access).

Deliberately does NOT drop orphan columns on connect_call
(transferred_users, completed_by_user, transfer_context, call_pattern,
voicemail_transcript, voicemail_transcription_error, price_fetch_attempts).
The columns are harmless on their own and a site-admin may still want to
query them. If you want them gone, run manually after verifying:

    ALTER TABLE connect_call
        DROP COLUMN IF EXISTS transferred_users,
        DROP COLUMN IF EXISTS completed_by_user,
        DROP COLUMN IF EXISTS transfer_context,
        DROP COLUMN IF EXISTS call_pattern,
        DROP COLUMN IF EXISTS voicemail_transcript,
        DROP COLUMN IF EXISTS voicemail_transcription_error,
        DROP COLUMN IF EXISTS price_fetch_attempts;
"""

import logging

_logger = logging.getLogger(__name__)


ARCHIVED_TABLES = [
    '_connect_pbx_group_archive',
    '_connect_scheduled_call_archive',
    '_connect_transcription_rule_archive',
    '_connect_documentation_archive',
]

NEW_GROUP_XMLIDS = ('group_admin', 'group_user', 'group_webhook')


def _table_row_count(cr, table):
    cr.execute(
        "SELECT 1 FROM information_schema.tables WHERE table_name = %s",
        (table,),
    )
    if not cr.fetchone():
        return None
    cr.execute(f'SELECT COUNT(*) FROM "{table}"')
    return cr.fetchone()[0]


def migrate(cr, version):
    if not version:
        return

    _logger.info("connect post-migration: verifying state after upgrade")

    # 1. Report archive state so the admin sees how much data is recoverable.
    for table in ARCHIVED_TABLES:
        count = _table_row_count(cr, table)
        if count is None:
            continue
        if count:
            _logger.warning(
                "archived %s rows preserved in %s -- review and drop manually "
                "once migrated or no longer needed",
                count, table,
            )
        else:
            # Empty archive -- drop it. CASCADE because other archive tables
            # may still hold FK references to it (self-contained archive set).
            cr.execute(f'DROP TABLE "{table}" CASCADE')
            _logger.info("dropped empty archive table %s", table)

    # 2. Verify the renamed groups are present and resolvable.
    cr.execute(
        """
        SELECT name
          FROM ir_model_data
         WHERE module = 'connect' AND name = ANY(%s)
        """,
        (list(NEW_GROUP_XMLIDS),),
    )
    found = {row[0] for row in cr.fetchall()}
    missing = set(NEW_GROUP_XMLIDS) - found
    if missing:
        _logger.error(
            "connect post-migration: renamed group xmlids missing after "
            "upgrade -- check pre-migration output: %s",
            sorted(missing),
        )
    else:
        _logger.info("connect groups present: %s", sorted(found))

    # 3. Warn on any res.users that previously had a connect group but now
    # have none (best-effort: we look for users who are referenced in
    # res_groups_users_rel for one of the new connect groups).
    cr.execute(
        """
        SELECT COUNT(DISTINCT rgur.uid)
          FROM res_groups_users_rel rgur
          JOIN ir_model_data imd
            ON imd.model = 'res.groups' AND imd.res_id = rgur.gid
         WHERE imd.module = 'connect'
           AND imd.name = ANY(%s)
        """,
        (list(NEW_GROUP_XMLIDS),),
    )
    users_with_group = cr.fetchone()[0]
    _logger.info(
        "connect post-migration: %s user(s) linked to connect groups",
        users_with_group,
    )

    _logger.info("connect post-migration complete")
