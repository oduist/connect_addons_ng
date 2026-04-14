"""Migrate WebRTC settings from endpoint to user level.

In 19.0.1.3.0, WebRTC fields (webrtc_enabled, webrtc_ring) moved from
connect.endpoint to connect.user. This script copies existing WebRTC
settings to the corresponding connect.user records.
"""
import logging
import secrets

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return

    # Check if the old columns still exist
    cr.execute("""
        SELECT column_name FROM information_schema.columns
        WHERE table_name = 'connect_endpoint' AND column_name = 'webrtc_enabled'
    """)
    if not cr.fetchone():
        _logger.info("Column webrtc_enabled not found on connect_endpoint, skipping migration")
        return

    # Find endpoints with WebRTC enabled and copy settings to their user
    cr.execute("""
        SELECT DISTINCT e.connect_user_id, e.webrtc_ring
        FROM connect_endpoint e
        WHERE e.webrtc_enabled = true
          AND e.connect_user_id IS NOT NULL
    """)
    rows = cr.fetchall()

    for connect_user_id, webrtc_ring in rows:
        webrtc_password = secrets.token_urlsafe(16)
        cr.execute("""
            UPDATE connect_user
            SET webrtc_enabled = true,
                originate_ring = %s,
                webrtc_password = %s
            WHERE id = %s
        """, (webrtc_ring if webrtc_ring is not None else True,
              webrtc_password, connect_user_id))

    _logger.info("Migrated WebRTC settings for %d users", len(rows))
