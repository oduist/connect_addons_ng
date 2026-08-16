# ADR-053: Ignore stale Telnyx reconnect requests

## Status
Accepted

## Context

The vendored `@telnyx/webrtc` client automatically reconnects its signaling
WebSocket after a background browser tab is resumed. Replacing the socket
increments an internal generation counter and rejects requests that still
belong to the previous generation with `StaleRequestError`.

That rejection is an expected cancellation: the old request must not affect the
new healthy socket. However, the SDK has internal fire-and-forget signaling
requests whose rejected promises reach Odoo's global `unhandledrejection`
handler. Odoo then shows an `UncaughtPromiseError` dialog even though the phone
is reconnecting normally.

Changing the vendored minified bundle would create a local SDK fork and would
need to be repeated on every Telnyx SDK update. Disabling automatic reconnect
would make the web phone less reliable.

## Decision

Register a `connect_telnyx` Odoo error handler before the standard client-error
dialog handler. It consumes an unhandled rejection only when all of these are
true:

- it is a promise rejection;
- the original error name is exactly `StaleRequestError`;
- the message starts with the SDK's `Stale request cancelled` text.

The handler prevents the browser's default rejection handling and returns
handled. Every other Telnyx, Odoo, RPC, media, or JavaScript error continues
through the normal Odoo error pipeline.

Token-driven client replacement also awaits the old client's `disconnect()`
before constructing the replacement, and explicit `connect()`/`disconnect()`
promises are caught at the integration boundary. This avoids adding
application-level races around the SDK's own reconnect lifecycle.

## Consequences

- Returning to an Odoo tab no longer displays a client-error dialog for the
  expected cancellation of an obsolete Telnyx signaling request.
- Automatic WebSocket recovery remains enabled, and genuine registration,
  network, microphone, and call errors remain visible.
- The vendored SDK stays byte-for-byte upstream, so future SDK upgrades do not
  need to carry a minified local patch.
- The change is limited to browser assets and documentation; Python source and
  the cross-series Python identity invariant are unaffected.
