# ADR-065: Delay Telnyx warm-transfer briefing playback

## Status

Accepted as a reversible experiment.

## Context

Telnyx AI Assistant warm transfers can ring and connect a registered WebRTC
recipient while the recipient hears no private briefing. The transfer leg is
otherwise healthy: SIP answers successfully, RTP packets flow, and Telnyx
reports a normal recipient hangup rather than a signaling or registration
error.

The Telnyx Transfer tool supports `warm_message_delay_ms`. When it is set,
Telnyx starts the generated warm-transfer audio after the specified delay
instead of attaching the audio URL directly to the dial command. This gives a
new WebRTC media path time to become ready before the private briefing begins.

The same Transfer tool does not expose caller-side hold music. During the
private briefing the caller receives Telnyx's transfer progress/ringback. Hold
music would require replacing the built-in transfer with custom Call Control
or conference orchestration that parks the caller, starts playback, calls and
briefs the recipient, stops playback, and bridges the legs.

## Decision

Add `warm_transfer_message_delay_ms` to
`connect.telnyx.ai_assistant`, defaulting to 2000 milliseconds. Publish the
value as the Transfer tool's `warm_message_delay_ms` setting.

The experiment must remain reversible without a deployment. Setting the Odoo
field to `0` publishes `null` to Telnyx and restores the previous immediate
warm-message behavior. Administrators should disable the delay when a test
call still has silent briefing audio, or when it introduces a noticeable new
pause without improving media delivery.

Do not add hold music to this change. Treat custom caller hold audio as a
separate feature because it changes transfer ownership from Telnyx's built-in
tool to Odoo-managed call orchestration and needs its own failure recovery,
recording, webhook, and bridge-state design.

## Consequences

- WebRTC recipients get a two-second media-settling window before the private
  briefing starts.
- The delay can be disabled from the assistant form by setting it to zero and
  pushing the assistant to Telnyx.
- PSTN and SIP recipients also receive the configured delay; administrators
  can set it to zero for assistants where immediate playback works better.
- Callers continue to hear transfer progress/ringback rather than music while
  the recipient is being briefed.
- Music on hold remains possible only through a later custom Call Control or
  conference-based transfer implementation.
