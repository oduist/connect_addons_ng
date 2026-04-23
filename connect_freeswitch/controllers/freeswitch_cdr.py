import logging

from odoo import http
from odoo.http import request, Response

logger = logging.getLogger(__name__)

# Session-scoped advisory-lock key for the inline CDR fast-path.
# Arbitrary 64-bit constant — only needs to be stable and not collide with
# other advisory-lock users in the same database.
_INLINE_LOCK_KEY = 0x46535743445201


class FreeSwitchCDRController(http.Controller):
    """Controller for FreeSWITCH CDR (Call Detail Record) webhooks.

    Receives CDR data from mod_xml_cdr after each call ends.

    Implementation note: the handler only *persists* the raw payload to
    ``connect.freeswitch.cdr.inbox`` and returns 200 immediately. A cron
    worker (see ``connect_freeswitch/data/cdr_inbox_cron.xml``) then parses
    and processes the payload asynchronously. This decouples the webhook
    response time from processing, eliminates A-leg/B-leg race conditions
    by serializing per-chain inside the cron, and avoids the ad-hoc
    ``pg_advisory_lock`` + manual ``cr.commit()`` dance the old inline
    handler required.
    """

    @http.route(
        '/freeswitch/webhook/cdr',
        type='http', auth='public', methods=['POST'], csrf=False,
    )
    def cdr_webhook(self, **kwargs):
        """Persist a CDR payload to the inbox and return 200.

        mod_xml_cdr sends URL-encoded POST with the 'cdr' parameter
        containing the XML CDR data, unless `encode=false` is configured,
        in which case the XML is the raw request body.
        """
        cdr_xml = kwargs.get('cdr') or request.httprequest.get_data(as_text=True)
        if not cdr_xml:
            logger.warning('Empty CDR received from FreeSWITCH')
            return Response('No CDR data', status=400)

        Inbox = request.env['connect.freeswitch.cdr.inbox'].sudo()
        try:
            Inbox.receive(cdr_xml)
        except Exception as e:
            logger.exception('Failed to enqueue FreeSWITCH CDR: %s', e)
            return Response('Enqueue error', status=500)

        # Fast-path singleton: when FreeSWITCH bursts sibling CDRs (A-leg +
        # B-leg arrive within milliseconds), only the first webhook worker
        # acquires the advisory lock and runs process_pending. The others
        # return immediately — their inbox row is already persisted and the
        # running worker's BATCH_CHAINS loop will pick it up, or the cron
        # backstop will. Session-scoped (not xact) because process_pending
        # commits mid-flight and we need the lock to span those commits.
        cr = request.env.cr
        cr.execute("SELECT pg_try_advisory_lock(%s)", [_INLINE_LOCK_KEY])
        if cr.fetchone()[0]:
            try:
                Inbox.process_pending()
            except Exception:
                logger.exception('Inline CDR processing failed — cron will retry')
            finally:
                cr.execute("SELECT pg_advisory_unlock(%s)", [_INLINE_LOCK_KEY])

        return Response('OK', status=200)
