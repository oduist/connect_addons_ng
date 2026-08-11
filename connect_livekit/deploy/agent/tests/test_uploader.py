"""Uploader state + scan tests using a fake Odoo client."""
from connect_livekit_agent.config import AgentSettings
from connect_livekit_agent.uploader import Uploader


class _FakeOdoo:
    def __init__(self):
        self.uploaded = []

    def upload_recording_sync(self, filename, data):
        self.uploaded.append((filename, data))
        return True


def _settings(tmp_path):
    return AgentSettings(
        odoo_url="x", agent_token="y",
        egress_out_dir=str(tmp_path / "out"),
        state_dir=str(tmp_path / "state"),
    )


def test_scan_uploads_and_records_state(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "connect_livekit_agent.uploader.Uploader._is_stable",
        lambda self, path: True)
    out = tmp_path / "out"
    out.mkdir()
    (out / "EG_1.ogg").write_bytes(b"audio")
    (out / "notes.txt").write_bytes(b"ignore me")
    odoo = _FakeOdoo()
    up = Uploader(_settings(tmp_path), odoo)
    up.scan_once()
    assert odoo.uploaded == [("EG_1.ogg", b"audio")]
    # Second scan does not re-upload (state persisted).
    up2 = Uploader(_settings(tmp_path), odoo)
    up2.scan_once()
    assert len(odoo.uploaded) == 1
