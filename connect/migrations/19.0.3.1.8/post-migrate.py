"""Backfill connect.user.provider.binding from existing user-side field
clusters declared by provider modules.

For each connect.user row:
  - `username NOT NULL` (column added by connect_twilio) → bind to twilio
  - `webrtc_enabled = TRUE` (column added by connect_freeswitch) → bind to
    freeswitch

ElevenLabs has no per-user fields today, so no binding is created on
backfill. Bindings can still be added manually through the user form's
Providers notebook page.

Implementation uses raw SQL + information_schema column checks because
this post-migrate runs at `connect` upgrade time — provider modules are
loaded later in the same upgrade pass, so their fields aren't visible on
the ORM yet. The columns are already on `connect_user` from previous
installs of those modules, hence the SQL path works.

Idempotent: each (user_id, provider_id) INSERT is gated on a NOT EXISTS
guard against the unique constraint.
"""
import logging

from odoo import api, SUPERUSER_ID

_logger = logging.getLogger(__name__)


def _col_exists(cr, table, column):
    cr.execute(
        "SELECT 1 FROM information_schema.columns "
        "WHERE table_name = %s AND column_name = %s",
        (table, column),
    )
    return bool(cr.fetchone())


def _provider_id(cr, code):
    cr.execute(
        "SELECT id FROM connect_provider WHERE code = %s",
        (code,),
    )
    row = cr.fetchone()
    return row[0] if row else None


def migrate(cr, version):
    if not version:
        return

    twilio = _provider_id(cr, 'twilio')
    freeswitch = _provider_id(cr, 'freeswitch')

    counts = {}

    if twilio and _col_exists(cr, 'connect_user', 'username'):
        cr.execute(
            """
            INSERT INTO connect_user_provider_binding
                (user_id, provider_id, create_uid, write_uid,
                 create_date, write_date)
            SELECT u.id, %s, 1, 1, NOW(), NOW()
            FROM connect_user u
            WHERE u.username IS NOT NULL
              AND NOT EXISTS (
                  SELECT 1 FROM connect_user_provider_binding b
                  WHERE b.user_id = u.id AND b.provider_id = %s
              )
            """,
            (twilio, twilio),
        )
        counts['twilio'] = cr.rowcount

    if freeswitch and _col_exists(cr, 'connect_user', 'webrtc_enabled'):
        cr.execute(
            """
            INSERT INTO connect_user_provider_binding
                (user_id, provider_id, create_uid, write_uid,
                 create_date, write_date)
            SELECT u.id, %s, 1, 1, NOW(), NOW()
            FROM connect_user u
            WHERE u.webrtc_enabled = TRUE
              AND NOT EXISTS (
                  SELECT 1 FROM connect_user_provider_binding b
                  WHERE b.user_id = u.id AND b.provider_id = %s
              )
            """,
            (freeswitch, freeswitch),
        )
        counts['freeswitch'] = cr.rowcount

    _logger.info(
        'connect.user.provider.binding backfill: %s',
        ', '.join(f'{k}={v}' for k, v in counts.items() if v),
    )

    # Bulk INSERTs bypassed the ORM, so the stored compute
    # connect.user.provider_ids did not refresh. Force a recompute on
    # every affected user.
    if any(counts.values()):
        env = api.Environment(cr, SUPERUSER_ID, {})
        users = env['connect.user'].with_context(active_test=False).search([])
        users._compute_provider_ids()
        users.flush_recordset(['provider_ids'])
