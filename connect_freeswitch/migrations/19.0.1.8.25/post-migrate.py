"""Migrate FS settings off `connect.settings` into the new singleton
`connect.provider.freeswitch.config` (ADR-025 / ODU-23).

Renames (strip `freeswitch_` prefix where present; `firewall_*` kept):
  freeswitch_socket_url       → socket_url
  freeswitch_domain           → domain
  freeswitch_ice_servers      → ice_servers
  freeswitch_log_level        → log_level
  freeswitch_sofia_log_level  → sofia_log_level
  freeswitch_xmlrpc_host      → xmlrpc_host
  freeswitch_xmlrpc_port      → xmlrpc_port
  freeswitch_xmlrpc_user      → xmlrpc_user
  freeswitch_xmlrpc_password  → xmlrpc_password
  freeswitch_status           → status
  freeswitch_uptime           → uptime
  freeswitch_calls            → active_calls
  freeswitch_registrations    → registrations
  freeswitch_gateway_statuses → gateway_statuses
  firewall_*                  → firewall_* (kept)
"""
import logging

_logger = logging.getLogger(__name__)

LEGACY_COLUMNS = [
    ('freeswitch_socket_url', 'socket_url'),
    ('freeswitch_domain', 'domain'),
    ('freeswitch_ice_servers', 'ice_servers'),
    ('freeswitch_log_level', 'log_level'),
    ('freeswitch_sofia_log_level', 'sofia_log_level'),
    ('freeswitch_xmlrpc_host', 'xmlrpc_host'),
    ('freeswitch_xmlrpc_port', 'xmlrpc_port'),
    ('freeswitch_xmlrpc_user', 'xmlrpc_user'),
    ('freeswitch_xmlrpc_password', 'xmlrpc_password'),
    ('freeswitch_status', 'status'),
    ('freeswitch_uptime', 'uptime'),
    ('freeswitch_calls', 'active_calls'),
    ('freeswitch_registrations', 'registrations'),
    ('freeswitch_gateway_statuses', 'gateway_statuses'),
    ('firewall_enabled', 'firewall_enabled'),
    ('firewall_service_url', 'firewall_service_url'),
    ('firewall_service_token', 'firewall_service_token'),
    ('display_firewall_service_token', 'display_firewall_service_token'),
    ('firewall_heartbeat_interval', 'firewall_heartbeat_interval'),
    ('firewall_event_retention_days', 'firewall_event_retention_days'),
    ('firewall_tcp_ports', 'firewall_tcp_ports'),
    ('firewall_udp_ports', 'firewall_udp_ports'),
    ('firewall_banned_timeout', 'firewall_banned_timeout'),
    ('firewall_authenticated_timeout', 'firewall_authenticated_timeout'),
    ('firewall_expire_short_timeout', 'firewall_expire_short_timeout'),
    ('firewall_expire_long_timeout', 'firewall_expire_long_timeout'),
]


def _col_exists(cr, table, column):
    cr.execute(
        "SELECT 1 FROM information_schema.columns "
        "WHERE table_name = %s AND column_name = %s",
        (table, column),
    )
    return bool(cr.fetchone())


def migrate(cr, version):
    if not version:
        return

    cr.execute("SELECT id FROM connect_provider_freeswitch_config LIMIT 1")
    row = cr.fetchone()
    if row:
        singleton_id = row[0]
    else:
        cr.execute(
            "INSERT INTO connect_provider_freeswitch_config "
            "(create_uid, write_uid, create_date, write_date) "
            "VALUES (1, 1, NOW(), NOW()) RETURNING id"
        )
        singleton_id = cr.fetchone()[0]

    legacy_present = [
        (legacy, new) for legacy, new in LEGACY_COLUMNS
        if _col_exists(cr, 'connect_settings', legacy)
    ]
    if legacy_present:
        select_parts = ', '.join(f'"{legacy}"' for legacy, _ in legacy_present)
        cr.execute(f'SELECT {select_parts} FROM connect_settings LIMIT 1')
        row = cr.fetchone()
        if row:
            sets, params = [], []
            for (legacy, new), value in zip(legacy_present, row):
                if value is not None:
                    sets.append(f'"{new}" = %s')
                    params.append(value)
            if sets:
                params.append(singleton_id)
                cr.execute(
                    f'UPDATE connect_provider_freeswitch_config '
                    f'SET {", ".join(sets)} WHERE id = %s',
                    params,
                )
                _logger.info('connect_freeswitch: migrated %d fields', len(sets))

    for legacy, _ in LEGACY_COLUMNS:
        if _col_exists(cr, 'connect_settings', legacy):
            cr.execute(f'ALTER TABLE connect_settings DROP COLUMN "{legacy}"')
            _logger.info('connect_freeswitch: dropped connect_settings.%s', legacy)
