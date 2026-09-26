#!/usr/bin/env python3
"""Standalone REST contract test for connect_voiceml.

Spins up a mock VoiceML REST server, points the ``voiceml-python-sdk`` at it,
and exercises every REST call the module makes — originate, sync, SIP
domain/credential provisioning, messaging, recording fetch, routes-v2 and the
raw OutgoingCallerIds client — asserting the exact HTTP method, path (with the
``.json`` suffix and SIP / routes-v2 sub-paths), Basic auth, and the
form-encoded field names. Runs with no Odoo and no VoiceML fleet.

Run::

    PYTHONPATH=/path/to/voiceml-python-sdk/src python3 connect_voiceml/tools/rest_contract.py
"""

import base64
import json
import sys
import threading
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import httpx

from voiceml import Client
from voiceml.models import CreateApplicationRequest, CreateCallRequest

ACCOUNT_SID = "AC_TEST_ACCOUNT_SID"
API_KEY = "test-api-key"

# Fake sids — deliberately not ``AC``/``SK``/``SD``-style 32-hex, so they can
# never trip GitHub's secret scanner.
SIDS = {
    "call": "CA-call-1",
    "message": "SM-message-1",
    "application": "AP-app-1",
    "number": "PN-number-1",
    "recording": "RE-rec-1",
    "domain": "SD-domain-1",
    "cred_list": "CL-list-1",
    "credential": "CR-cred-1",
    "ocid": "OC-ocid-1",
}


class _Handler(BaseHTTPRequestHandler):
    requests = []

    def _handle(self, method):
        length = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(length).decode("utf-8") if length else ""
        parsed = urllib.parse.urlsplit(self.path)
        _Handler.requests.append({
            "method": method,
            "path": parsed.path,
            "auth": self.headers.get("Authorization"),
            "body": body,
        })
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b"{}")

    def do_GET(self):
        self._handle("GET")

    def do_POST(self):
        self._handle("POST")

    def do_PUT(self):
        self._handle("PUT")

    def do_DELETE(self):
        self._handle("DELETE")

    def log_message(self, *args):
        pass


def start_server():
    server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, "http://127.0.0.1:{}".format(server.server_address[1])


def call(fn):
    """Run an SDK call, tolerating response-validation errors.

    The mock returns ``{}`` for every response, so the SDK's Pydantic
    ``model_validate`` raises after the request has already been sent. The
    contract under test is the *request*, so the response body is irrelevant.
    """
    try:
        fn()
    except Exception:
        pass


def latest():
    return _Handler.requests[-1]


def parse_form(body):
    return urllib.parse.parse_qs(body)


def main():
    server, base_url = start_server()
    client = Client(account_sid=ACCOUNT_SID, api_key=API_KEY, base_url=base_url)
    root = "/2010-04-01/Accounts/{}".format(ACCOUNT_SID)
    expected_auth = "Basic " + base64.b64encode(
        "{}:{}".format(ACCOUNT_SID, API_KEY).encode()
    ).decode()

    # --- originate (connect.settings.originate_call) ------------------------
    call(lambda: client.calls.create(CreateCallRequest(
        to="sip:1001@example.com",
        from_="+18005551234",
        twiml="<Response><Dial><Number>+18005559999</Number></Dial></Response>",
        status_callback="https://odoo.example.com/voiceml/webhook/callstatus",
        status_callback_event=["initiated", "answered", "completed"],
        record=True,
        recording_channels="dual",
        recording_status_callback="https://odoo.example.com/voiceml/webhook/recordingstatus",
        recording_status_callback_event="completed",
    )))

    # --- messaging (connect.message.send) -----------------------------------
    call(lambda: client.messages.create(
        to="+18005559999", body="hello", from_="+18005551234"))

    # --- TwiML apps (connect.voiceml.application) ---------------------------
    call(lambda: client.applications.create(CreateApplicationRequest(
        friendly_name="VoiceML App",
        voice_url="https://odoo.example.com/voiceml/webhook/application/1",
        status_callback="https://odoo.example.com/voiceml/webhook/callstatus",
    )))
    call(lambda: client.applications.list())

    # --- numbers (connect.voiceml.number.sync) ------------------------------
    call(lambda: client.incoming_phone_numbers.list())
    call(lambda: client.incoming_phone_numbers.update(
        SIDS["number"], friendly_name="Main", voice_url="https://odoo.example.com/voiceml/webhook/number"))

    # --- recordings (connect.voiceml.recording.on_recording_status) ---------
    call(lambda: client.recordings.get(SIDS["recording"]))

    # --- SIP domain provisioning (connect.voiceml.domain.create_domain) -----
    call(lambda: client.sip.domains.create(
        domain_name="test.example.com",
        friendly_name="Test Domain",
        voice_url="https://odoo.example.com/voiceml/webhook/domain",
        voice_method="POST",
        sip_registration=True,
    ))
    call(lambda: client.sip.domains.list())
    call(lambda: client.sip.credential_lists.create(friendly_name="Test Domain"))
    call(lambda: client.sip.domains.auth.registrations.credential_list_mappings(
        SIDS["domain"]).create(credential_list_sid=SIDS["cred_list"]))
    call(lambda: client.sip.domains.auth.calls.credential_list_mappings(
        SIDS["domain"]).create(credential_list_sid=SIDS["cred_list"]))

    # --- per-user SIP credential (connect.voiceml.user._create_sip_account) --
    call(lambda: client.sip.credential_lists.credentials(SIDS["cred_list"]).create(
        username="1001", password="s3cret-pass"))
    call(lambda: client.sip.credential_lists.credentials(SIDS["cred_list"]).update(
        SIDS["credential"], password="new-pass"))
    call(lambda: client.sip.credential_lists.credentials(SIDS["cred_list"]).delete(
        SIDS["credential"]))
    call(lambda: client.sip.credential_lists.delete(SIDS["cred_list"]))
    call(lambda: client.sip.domains.delete(SIDS["domain"]))

    # --- routes v2 inbound processing region (connect.voiceml.number.sync) ---
    call(lambda: client.routes_v2.phone_numbers.update(
        "+18005551234", voice_region="us1"))
    call(lambda: client.routes_v2.sip_domains.update(
        "test.example.com", voice_region="us1"))

    # --- raw OutgoingCallerIds client (connect.voiceml.outgoing_callerid) ----
    raw = httpx.Client(auth=(ACCOUNT_SID, API_KEY), base_url=base_url, timeout=30)
    call(lambda: raw.get(root + "/OutgoingCallerIds.json"))
    call(lambda: raw.post(root + "/OutgoingCallerIds.json",
                          data={"PhoneNumber": "+18005551234", "FriendlyName": "Office"}))
    call(lambda: raw.post(root + "/OutgoingCallerIds/{}.json".format(SIDS["ocid"]),
                          data={"FriendlyName": "Office"}))
    call(lambda: raw.delete(root + "/OutgoingCallerIds/{}.json".format(SIDS["ocid"])))
    raw.close()

    server.shutdown()

    # =========================================================================
    # Assertions
    # =========================================================================
    requests = _Handler.requests
    expected = [
        ("POST", root + "/Calls.json"),
        ("POST", root + "/Messages.json"),
        ("POST", root + "/Applications.json"),
        ("GET", root + "/Applications.json"),
        ("GET", root + "/IncomingPhoneNumbers.json"),
        ("POST", root + "/IncomingPhoneNumbers/{}.json".format(SIDS["number"])),
        ("GET", root + "/Recordings/{}.json".format(SIDS["recording"])),
        ("POST", root + "/SIP/Domains.json"),
        ("GET", root + "/SIP/Domains.json"),
        ("POST", root + "/SIP/CredentialLists.json"),
        ("POST", root + "/SIP/Domains/{}/Auth/Registrations/CredentialListMappings.json".format(SIDS["domain"])),
        ("POST", root + "/SIP/Domains/{}/Auth/Calls/CredentialListMappings.json".format(SIDS["domain"])),
        ("POST", root + "/SIP/CredentialLists/{}/Credentials.json".format(SIDS["cred_list"])),
        ("POST", root + "/SIP/CredentialLists/{}/Credentials/{}.json".format(SIDS["cred_list"], SIDS["credential"])),
        ("DELETE", root + "/SIP/CredentialLists/{}/Credentials/{}.json".format(SIDS["cred_list"], SIDS["credential"])),
        ("DELETE", root + "/SIP/CredentialLists/{}.json".format(SIDS["cred_list"])),
        ("DELETE", root + "/SIP/Domains/{}.json".format(SIDS["domain"])),
        ("POST", "/v2/PhoneNumbers/%2B18005551234"),
        ("POST", "/v2/SipDomains/test.example.com"),
        ("GET", root + "/OutgoingCallerIds.json"),
        ("POST", root + "/OutgoingCallerIds.json"),
        ("POST", root + "/OutgoingCallerIds/{}.json".format(SIDS["ocid"])),
        ("DELETE", root + "/OutgoingCallerIds/{}.json".format(SIDS["ocid"])),
    ]

    failures = []

    if len(requests) != len(expected):
        failures.append("request count: got {}, want {}".format(len(requests), len(expected)))

    for i, (want_method, want_path) in enumerate(expected):
        if i >= len(requests):
            failures.append("missing request {} {} {}".format(i, want_method, want_path))
            continue
        got = requests[i]
        if got["method"] != want_method or got["path"] != want_path:
            failures.append(
                "req {}: got {} {} want {} {}".format(
                    i, got["method"], got["path"], want_method, want_path))

    for i, got in enumerate(requests):
        if got["auth"] != expected_auth:
            failures.append("req {}: bad auth".format(i))

    # Spot-check form field names (Twilio PascalCase on the wire).
    def find(path, method=None):
        return next((r for r in requests if r["path"] == path
                     and (method is None or r["method"] == method)), None)

    calls_body = parse_form(find(root + "/Calls.json")["body"])
    for key in ("To", "From", "Twiml", "StatusCallback", "StatusCallbackEvent",
                "Record", "RecordingChannels", "RecordingStatusCallback",
                "RecordingStatusCallbackEvent"):
        if key not in calls_body:
            failures.append("Calls body missing {}".format(key))

    msg_body = parse_form(find(root + "/Messages.json")["body"])
    for key in ("To", "From", "Body"):
        if key not in msg_body:
            failures.append("Messages body missing {}".format(key))

    dom_body = parse_form(find(root + "/SIP/Domains.json")["body"])
    for key in ("DomainName", "VoiceUrl", "VoiceMethod", "SipRegistration"):
        if key not in dom_body:
            failures.append("SIP Domains body missing {}".format(key))

    cred_body = parse_form(find(
        root + "/SIP/CredentialLists/{}/Credentials.json".format(SIDS["cred_list"]))["body"])
    for key in ("Username", "Password"):
        if key not in cred_body:
            failures.append("Credentials body missing {}".format(key))

    mapping_body = parse_form(find(
        root + "/SIP/Domains/{}/Auth/Registrations/CredentialListMappings.json".format(SIDS["domain"]))["body"])
    if "CredentialListSid" not in mapping_body:
        failures.append("mapping body missing CredentialListSid")

    routes_body = parse_form(find("/v2/PhoneNumbers/%2B18005551234")["body"])
    if "VoiceRegion" not in routes_body:
        failures.append("routes-v2 phone body missing VoiceRegion")

    ocid_body = parse_form(find(root + "/OutgoingCallerIds.json", "POST")["body"])
    for key in ("PhoneNumber", "FriendlyName"):
        if key not in ocid_body:
            failures.append("OutgoingCallerIds body missing {}".format(key))

    if failures:
        print("FAIL — {} problem(s):".format(len(failures)))
        for f in failures:
            print("  -", f)
        return 1

    print("PASS — {} requests verified: methods, paths, Basic auth, and form fields.".format(len(requests)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
