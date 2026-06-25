"""Migrate FreeSWITCH settings back from the
`connect.provider.freeswitch.config` singleton onto `connect.settings`
(ADR-031 / ODU-46).

Inverse of `19.0.1.8.25`: restore the prefixed columns on
`connect_settings` and copy the single config-table row across. The
`connect.provider.freeswitch.config` model is removed with this release,
so Odoo drops its table during the upgrade; this script only carries the
data. Idempotent via `information_schema`.

Name map (config column -> connect_settings column); `firewall_*` keep
their names, `active_calls` becomes `freeswitch_calls`.
"""
import logging

_logger = logging.getLogger(__name__)

# (config_column, connect_settings_column, sql_type)
COLUMNS = [
    ('socket_url', 'freeswitch_socket_url', 'varchar'),
    ('domain', 'freeswitch_domain', 'varchar'),
    ('ice_servers', 'freeswitch_ice_servers', 'text'),
    ('log_level', 'freeswitch_log_level', 'varchar'),
    ('sofia_log_level', 'freeswitch_sofia_log_level', 'varchar'),
    ('xmlrpc_host', 'freeswitch_xmlrpc_host', 'varchar'),
    ('xmlrpc_port', 'freeswitch_xmlrpc_port', 'integer'),
    ('xmlrpc_user', 'freeswitch_xmlrpc_user', 'varchar'),
    ('xmlrpc_password', 'freeswitch_xmlrpc_password', 'varchar'),
    ('status', 'freeswitch_status', 'varchar'),
    ('uptime', 'freeswitch_uptime', 'varchar'),
    ('active_calls', 'freeswitch_calls', 'varchar'),
    ('registrations', 'freeswitch_registrations', 'varchar'),
    ('gateway_statuses', 'freeswitch_gateway_statuses', 'text'),
    ('firewall_enabled', 'firewall_enabled', 'boolean'),
    ('firewall_service_url', 'firewall_service_url', 'varchar'),
    ('firewall_service_token', 'firewall_service_token', 'varchar'),
    ('display_firewall_service_token', 'display_firewall_service_token', 'varchar'),
    ('firewall_heartbeat_interval', 'firewall_heartbeat_interval', 'integer'),
    ('firewall_event_retention_days', 'firewall_event_retention_days', 'integer'),
    ('firewall_tcp_ports', 'firewall_tcp_ports', 'varchar'),
    ('firewall_udp_ports', 'firewall_udp_ports', 'varchar'),
    ('firewall_banned_timeout', 'firewall_banned_timeout', 'integer'),
    ('firewall_authenticated_timeout', 'firewall_authenticated_timeout', 'integer'),
    ('firewall_expire_short_timeout', 'firewall_expire_short_timeout', 'integer'),
    ('firewall_expire_long_timeout', 'firewall_expire_long_timeout', 'integer'),
]


def _col_exists(cr, table, column):
    cr.execute(
        "SELECT 1 FROM information_schema.columns "
        "WHERE table_name = %s AND column_name = %s",
        (table, column),
    )
    return bool(cr.fetchone())


def _table_exists(cr, table):
    cr.execute(
        "SELECT 1 FROM information_schema.tables WHERE table_name = %s",
        (table,),
    )
    return bool(cr.fetchone())


def migrate(cr, version):
    if not version:
        return

    # The ORM creates the new columns from the connect_freeswitch fields on
    # upgrade; add them defensively so the copy below is self-contained.
    for _src, dst, sqltype in COLUMNS:
        if not _col_exists(cr, 'connect_settings', dst):
            cr.execute(
                f'ALTER TABLE connect_settings ADD COLUMN "{dst}" {sqltype}')

    if not _table_exists(cr, 'connect_provider_freeswitch_config'):
        _logger.info('connect_freeswitch: no config table to migrate from')
        return

    cr.execute("SELECT id FROM connect_settings ORDER BY id LIMIT 1")
    row = cr.fetchone()
    if not row:
        _logger.info('connect_freeswitch: no connect_settings row yet')
        return
    settings_id = row[0]

    present = [
        (src, dst) for src, dst, _t in COLUMNS
        if _col_exists(cr, 'connect_provider_freeswitch_config', src)
    ]
    if not present:
        return

    select_parts = ', '.join(f'"{src}"' for src, _dst in present)
    cr.execute(
        f'SELECT {select_parts} FROM connect_provider_freeswitch_config '
        f'ORDER BY id LIMIT 1')
    cfg_row = cr.fetchone()
    if not cfg_row:
        return

    sets, params = [], []
    for (src, dst), value in zip(present, cfg_row):
        if value is not None:
            sets.append(f'"{dst}" = %s')
            params.append(value)
    if sets:
        params.append(settings_id)
        cr.execute(
            f'UPDATE connect_settings SET {", ".join(sets)} WHERE id = %s',
            params,
        )
        _logger.info(
            'connect_freeswitch: restored %d fields onto connect_settings',
            len(sets),
        )

    # Odoo deletes the obsolete model's ir.model record but skips the SQL
    # DROP (the model is already absent from the registry by now), leaving an
    # orphan table. Drop it explicitly so the revert is clean.
    cr.execute('DROP TABLE IF EXISTS connect_provider_freeswitch_config CASCADE')
