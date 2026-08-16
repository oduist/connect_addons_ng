# 058 - Resolve the Telnyx caller consistently for outbound recording

## Status

Accepted

## Context

Calls placed by a Telnyx web phone enter the routing TeXML application as an
inbound SIP leg. Depending on the Telnyx webhook variant, the credential URI
that identifies the PBX user is reported in `Caller`, `From`, or `CallerId`.

The routing guard already resolves those variants through
`connect.user._telnyx_caller()`, but `originate_external_call()` repeated the
lookup using only `Caller`. When Telnyx supplied only `From`, the guard allowed
the known user to dial out and the caller ID fell back correctly, but the
method lost the user before evaluating `record_calls`. The generated `<Dial>`
therefore omitted `record` and `recordingStatusCallback`, so Telnyx never made
a recording.

## Decision

1. Every Telnyx routing path that needs the originating PBX user resolves the
   caller with `connect.user._telnyx_caller()`.
2. `originate_external_call()` uses that normalized identity for both caller
   ID selection and the user's `record_calls` setting.
3. The outbound routing test suite includes the real Telnyx payload shape in
   which the credential URI is present in `From` and `Caller` is absent.
4. When recording is enabled, the generated TeXML must carry both
   `record="record-from-answer"` and the recording status callback.

## Consequences

- Web-phone outbound calls follow the user's recording setting regardless of
  which supported Telnyx caller field is present.
- The routing authorization check, caller ID selection, and recording policy
  cannot disagree about which PBX user originated the call.
- Existing payloads that contain `Caller` retain their current behavior.

## Rejected alternatives

- Fall back to the default caller ID and default recording policy when
  `Caller` is absent: the webhook still identifies the user in `From`, so
  discarding that identity would ignore an explicit per-user setting.
- Enable recording for every outbound route unconditionally: administrators
  must be able to disable recording per user.
