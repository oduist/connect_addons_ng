"""Keep existing call analysis when recording retention is reduced."""

import logging


_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return

    cr.execute(
        """
        UPDATE connect_call AS target
           SET transcript = latest.transcript
          FROM (
                SELECT DISTINCT ON (recording.call)
                       recording.call AS call_id,
                       recording.transcript
                  FROM connect_recording AS recording
                 WHERE recording.call IS NOT NULL
                   AND COALESCE(recording.transcript, '') != ''
                 ORDER BY recording.call, recording.id DESC
               ) AS latest
         WHERE target.id = latest.call_id
           AND COALESCE(target.transcript, '') = ''
        """
    )
    transcript_count = cr.rowcount

    cr.execute(
        """
        UPDATE connect_call AS target
           SET summary = latest.summary
          FROM (
                SELECT DISTINCT ON (recording.call)
                       recording.call AS call_id,
                       recording.summary
                  FROM connect_recording AS recording
                 WHERE recording.call IS NOT NULL
                   AND COALESCE(recording.summary, '') != ''
                 ORDER BY recording.call, recording.id DESC
               ) AS latest
         WHERE target.id = latest.call_id
           AND COALESCE(target.summary, '') = ''
        """
    )
    _logger.info(
        'Backfilled call analysis from recordings: %s transcript(s), %s summary(s).',
        transcript_count,
        cr.rowcount,
    )
