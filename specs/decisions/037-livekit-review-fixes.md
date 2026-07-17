# 037: LiveKit provider review fixes

## Problem

The first review pass for `connect_livekit` found three places where local
state and LiveKit-side state could diverge:

1. Outbound click-to-call notified the browser before the ledger had a call
   row that authorized the user to join the new `out-*` room.
2. Egress recordings were requested with a relative filepath, while the
   uploader watches the shared `/out` volume.
3. Moving DIDs or outbound caller IDs between trunks only re-pushed the new
   trunk, leaving the old LiveKit trunk with stale number lists.

## Decisions

1. **Create the outbound call before notifying the web phone.** The
   click-to-call flow creates a `connect.call` with `livekit_room_name`,
   caller/called metadata and caller user before it emits the bus `join`
   action. The SIP channel is linked to that call when LiveKit returns a
   call id, and later participant webhooks continue updating the same
   ledger row.
2. **Write egress files into `/out`.** Meeting recordings use an absolute
   `/out/{room_name}-{time}` filepath so the egress container writes into
   the Docker volume mounted by the uploader sidecar.
3. **Sync old and new trunks on reassignment.** When `connect.livekit.number`
   or `connect.livekit.outgoing_callerid` changes its trunk, the code
   captures the old trunk before `write()` and re-pushes the old and new
   trunks after the record has moved.

## Consequences

Outbound browser joins no longer depend on webhook ordering, egress files are
visible to the uploader without extra deployment configuration, and trunk
number lists stay correct after admin edits.
