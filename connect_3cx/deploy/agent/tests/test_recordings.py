"""XAPI recording poller."""
from unittest.mock import AsyncMock, MagicMock

from connect_3cx_agent.recordings import RecordingPoller


def make_poller(settings, rows, audio=b"RIFFdata"):
    tcx = MagicMock()
    tcx.configured.return_value = True
    tcx.list_recordings_after = AsyncMock(return_value=rows)
    tcx.download_recording = AsyncMock(return_value=audio)
    odoo = MagicMock()
    odoo.put_file = AsyncMock(return_value="OK")
    poller = RecordingPoller(tcx=tcx, odoo=odoo, settings=settings,
                             state_path=settings.state_path)
    return poller, tcx, odoo


async def test_poll_uploads_and_advances(settings):
    rows = [
        {"Id": 11, "CallId": 17, "FromCallerNumber": "+15551234567",
         "Duration": "00:00:42"},
        {"Id": 12},
    ]
    poller, tcx, odoo = make_poller(settings, rows)
    sent = await poller.poll_once()
    assert sent == 2
    assert poller.last_rec_id == 12
    assert poller.uploaded_count == 2
    tcx.list_recordings_after.assert_awaited_with(0)
    first_path = odoo.put_file.call_args_list[0].args[0]
    assert first_path.startswith("/3cx/webhook/recording/11.wav?")
    assert "callid=17" in first_path
    assert "caller=%2B15551234567" in first_path
    # State persisted: a fresh poller resumes after 12.
    poller2, _, _ = make_poller(settings, [])
    assert poller2.last_rec_id == 12


async def test_failed_upload_stops_advancing(settings):
    rows = [{"Id": 21}, {"Id": 22}]
    poller, tcx, odoo = make_poller(settings, rows)
    odoo.put_file = AsyncMock(side_effect=Exception("odoo down"))
    sent = await poller.poll_once()
    assert sent == 0
    assert poller.last_rec_id == 0
    assert poller.failed_count == 1


async def test_oversize_and_empty_rejected(settings):
    settings.recording_max_mb = 0
    rows = [{"Id": 31}]
    poller, tcx, odoo = make_poller(settings, rows, audio=b"x" * 10)
    await poller.poll_once()
    assert poller.failed_count == 1
    assert not odoo.put_file.called
