"""Durable inbox for FreeSWITCH CDR events.

Webhook requests store the raw CDR payload here and return 200 immediately.
A cron worker picks up pending rows, parses the XML, and hands off to
``connect.call.on_freeswitch_cdr``. Rows of the same call chain are locked
and processed together in FIFO order, so the A-leg always commits before
the B-leg reads — no advisory locks or manual commits required inside
the call-event pipeline.
"""
import logging
import re
from xml.etree import ElementTree as ET

from odoo import api, fields, models

logger = logging.getLogger(__name__)

# Replace colons inside XML tag names (SIP headers like `sip:to-host` break
# the XML namespace parser).
_TAG_COLON_RE = re.compile(r'<(/?)([a-zA-Z_][\w.-]*):([a-zA-Z_][\w.-]*)')
# Light-weight extractors used at receive time for observability.
_UUID_RE = re.compile(r'<uuid>([^<]+)</uuid>')
_CHAIN_RE = re.compile(r'<odoo_chain_id>([^<]+)</odoo_chain_id>')


class FreeSwitchCdrInbox(models.Model):
    _name = 'connect.freeswitch.cdr.inbox'
    _description = 'FreeSWITCH CDR Inbox'
    _order = 'id asc'

    MAX_ATTEMPTS = 5
    BATCH_CHAINS = 50
    STUCK_MINUTES = 5

    payload = fields.Text(required=True, readonly=True)
    uuid = fields.Char(index=True, readonly=True, string='Channel UUID')
    chain_id = fields.Char(index=True, readonly=True, string='Chain ID')
    state = fields.Selection(
        [
            ('pending', 'Pending'),
            ('processing', 'Processing'),
            ('done', 'Done'),
            ('failed', 'Failed'),
        ],
        default='pending',
        required=True,
        index=True,
    )
    attempts = fields.Integer(default=0, readonly=True)
    last_error = fields.Text(readonly=True)
    processed_at = fields.Datetime(readonly=True)

    # ------------------------------------------------------------------
    # Entry points
    # ------------------------------------------------------------------

    @api.model
    def receive(self, payload):
        """Persist a raw CDR payload. Returns the created inbox record id."""
        if not payload:
            return False
        uuid, chain = self._extract_ids(payload)
        rec = self.sudo().with_context(tracking_disable=True).create({
            'payload': payload,
            'uuid': uuid,
            'chain_id': chain or uuid,
        })
        return rec.id

    @api.model
    def process_pending(self):
        """Cron: claim one chain-id group at a time and process it.

        Uses ``FOR UPDATE SKIP LOCKED`` so multiple cron workers can run in
        parallel on disjoint chains. Per-chain FIFO ordering eliminates
        the A-leg/B-leg race that the old webhook handler worked around
        with session-scoped advisory locks and manual commits.
        """
        for _ in range(self.BATCH_CHAINS):
            if not self._process_one_chain():
                break

    @api.model
    def reap_stuck(self):
        """Return long-'processing' rows to 'pending' (recovers from worker crashes)."""
        threshold = fields.Datetime.subtract(
            fields.Datetime.now(), minutes=self.STUCK_MINUTES)
        stuck = self.sudo().search([
            ('state', '=', 'processing'),
            ('write_date', '<', threshold),
        ])
        if stuck:
            stuck.write({'state': 'pending'})
            logger.warning(
                'Reset %d stuck CDR inbox row(s) back to pending',
                len(stuck))

    @api.model
    def vacuum(self, days=7):
        """Remove completed rows older than ``days``."""
        threshold = fields.Datetime.subtract(
            fields.Datetime.now(), days=days)
        old = self.sudo().search([
            ('state', '=', 'done'),
            ('processed_at', '<', threshold),
        ])
        if old:
            count = len(old)
            old.unlink()
            logger.info('Vacuumed %d done CDR inbox row(s)', count)

    def action_retry(self):
        """Admin action: re-queue failed rows for another attempt."""
        self.filtered(lambda r: r.state == 'failed').write({
            'state': 'pending',
            'last_error': False,
        })

    # ------------------------------------------------------------------
    # Processing
    # ------------------------------------------------------------------

    def _process_one_chain(self):
        """Claim one chain (via SKIP LOCKED), process all its pending rows.

        Returns True if a chain was claimed, False if nothing pending.
        """
        self.env.cr.execute("""
            SELECT COALESCE(chain_id, uuid)
            FROM connect_freeswitch_cdr_inbox
            WHERE state = 'pending'
            ORDER BY id ASC
            LIMIT 1
            FOR UPDATE SKIP LOCKED
        """)
        row = self.env.cr.fetchone()
        if not row:
            return False
        chain_key = row[0]

        self.env.cr.execute("""
            SELECT id FROM connect_freeswitch_cdr_inbox
            WHERE state = 'pending'
              AND COALESCE(chain_id, uuid) = %s
            ORDER BY id ASC
            FOR UPDATE
        """, [chain_key])
        ids = [r[0] for r in self.env.cr.fetchall()]
        if not ids:
            return False

        records = self.browse(ids)
        records.write({'state': 'processing'})

        for rec in records:
            self._run_single(rec)

        # Release FOR UPDATE locks and publish writes to other workers.
        self.env.cr.commit()
        return True

    def _run_single(self, rec):
        """Process one inbox row inside a savepoint so a bad payload
        does not poison the rest of the chain batch."""
        try:
            with self.env.cr.savepoint():
                rec._process_payload()
            rec.write({
                'state': 'done',
                'processed_at': fields.Datetime.now(),
                'last_error': False,
            })
        except Exception as e:
            logger.exception(
                'CDR inbox %s processing failed', rec.id)
            new_attempts = rec.attempts + 1
            rec.write({
                'attempts': new_attempts,
                'last_error': str(e)[:2000],
                'state': 'failed' if new_attempts >= self.MAX_ATTEMPTS else 'pending',
            })

    def _process_payload(self):
        """Parse this row's payload and dispatch to connect.call."""
        self.ensure_one()
        cdr_data = self._parse_cdr_xml(self.payload)
        webhook_user = self.env.ref('connect.user_connect_webhook')
        self.env['connect.call'].with_user(webhook_user).on_freeswitch_cdr(cdr_data)

    # ------------------------------------------------------------------
    # Parsing (moved from controllers/freeswitch_cdr.py)
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_ids(payload):
        u = _UUID_RE.search(payload)
        c = _CHAIN_RE.search(payload)
        return (
            u.group(1).strip() if u else '',
            c.group(1).strip() if c else '',
        )

    @classmethod
    def _parse_cdr_xml(cls, xml_str):
        """Parse FreeSWITCH CDR XML into the dict consumed by
        ``connect.call.on_freeswitch_cdr``."""
        xml_str = _TAG_COLON_RE.sub(r'<\1\2_\3', xml_str)
        root = ET.fromstring(xml_str)

        uuid = cls._xml_text(root, './/uuid')

        caller_profile = root.find('.//caller_profile')
        caller = ''
        called = ''
        direction = 'inbound'
        if caller_profile is not None:
            caller = cls._xml_text(caller_profile, 'caller_id_number')
            called = cls._xml_text(caller_profile, 'destination_number')
            direction = cls._xml_text(caller_profile, 'direction', 'inbound')

        hangup_cause = cls._xml_text(root, './/hangup_cause', 'NORMAL_CLEARING')

        duration = 0
        billsec = cls._xml_text(root, './/billsec')
        if billsec:
            duration = int(billsec)
        else:
            times = root.find('.//times')
            if times is not None:
                answered = cls._xml_text(times, 'answered_time', '0')
                hangup = cls._xml_text(times, 'hangup_time', '0')
                if answered != '0' and hangup != '0':
                    duration = (int(hangup) - int(answered)) // 1000000

        variables = root.find('.//variables')
        caller_pbx_user_id = None
        called_pbx_user_id = None
        other_leg_uuid = None
        chain_id = None
        odoo_number_id = None

        if variables is not None:
            effective_caller = cls._xml_text(variables, 'effective_caller_id_number')
            if effective_caller and not caller.isdigit():
                caller = effective_caller

            other_leg_uuid = (
                cls._xml_text(variables, 'odoo_parent_uuid')
                or cls._xml_text(variables, 'Other-Leg-Unique-ID')
            )
            chain_id = cls._xml_text(variables, 'odoo_chain_id')

            odoo_user = cls._xml_text(variables, 'odoo_connect_user_id')
            odoo_called_user = cls._xml_text(variables, 'odoo_called_user_id')
            if other_leg_uuid:
                if odoo_user:
                    called_pbx_user_id = int(odoo_user)
            else:
                if odoo_user:
                    caller_pbx_user_id = int(odoo_user)
                if odoo_called_user:
                    called_pbx_user_id = int(odoo_called_user)

            odoo_number_id = cls._xml_text(variables, 'odoo_number_id')

        return {
            'uuid': uuid,
            'caller': caller,
            'called': called,
            'direction': direction,
            'hangup_cause': hangup_cause,
            'duration': duration,
            'caller_pbx_user_id': caller_pbx_user_id,
            'called_pbx_user_id': called_pbx_user_id,
            'other_leg_uuid': other_leg_uuid,
            'chain_id': chain_id,
            'odoo_number_id': int(odoo_number_id) if odoo_number_id else None,
        }

    @staticmethod
    def _xml_text(element, path, default=''):
        el = element.find(path)
        if el is not None and el.text:
            return el.text.strip()
        return default
