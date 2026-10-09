"""Let existing Telnyx recordings request a fresh link on playback.

Recordings stored before 19.0.1.4.7 kept only the signed RecordingUrl, which
expires 10 minutes after the webhook. Their ``sid`` is the Telnyx recording
UUID, so copying it into ``telnyx_recording_id`` is enough for playback and
transcription to fetch a new link. Twilio SIDs and attachment-backed
recordings do not match: only UUID SIDs with a signed S3 URL are touched.
"""


def migrate(cr, version):
    if not version:
        return
    cr.execute(
        """
        UPDATE connect_recording
           SET telnyx_recording_id = sid
         WHERE telnyx_recording_id IS NULL
           AND sid ~* '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
           AND media_url LIKE '%%X-Amz-Signature=%%'
        """
    )
