# ADR-060: Credentials for the recording media proxy

**Status:** Accepted
**Date:** 2026-08-21

## Context

With `proxy_recordings` enabled (the default), `connect.recording._get_recording_widget()`
points the audio element at `/connect/recording/<id>` and the controller fetches
the provider's media server-side. The core implementation fetched it
anonymously:

```python
def _serve_media(self, media_url):
    # Base implementation - integration modules should override with proper auth
    response = req.get(media_url)
    if response.status_code == 200:
        ...
    return http.Response(status=404)
```

No provider module ever supplied that override. The failure mode is silent
and misleading: the route answers `404`, the `<audio>` element has nothing to
play, and the recording list shows **every recording as 0 seconds** — while
`connect.recording.duration` says 8, 12, 26 seconds, because the metadata came
from the provider API and is correct. Nothing is logged, so the only way to
find the cause is to fetch the media URL by hand.

Two Twilio configurations reach it:

- **HTTP Basic Auth required** on recording media (an account setting). The
  media is on `api.twilio.com` and the account credentials would open it.
- **External Storage.** Twilio writes the media to the account's own S3 bucket
  and keeps only metadata; `recording.media_url` is a bucket URL, and the
  Twilio API answers `404` for the media itself. Anonymous fetch gets `403`.

## Decision

Credentials come from a model hook, `connect.settings.get_media_auth(media_url)`,
returning `None` in core. `_serve_media()` passes its result to `requests.get`
(with a timeout), and provider modules override it. `connect_twilio` returns
`(account_sid, auth_token)` — **only** when the URL's host is `twilio.com` or a
subdomain of it.

The host check is the point of putting this on the URL rather than on the
provider alone. An External Storage bucket is a third party as far as the
Twilio credentials are concerned, and a media URL comes from a webhook: sending
the account's auth token to whatever host it names would hand the account over
to anyone who can forge one. A lookalike host (`api.twilio.com.evil.example`)
must not match either, which a substring test would have allowed.

A fetch that does not return `200` now answers `502` and logs the upstream
status and URL, noting whether credentials were sent. The UI cannot report
this — a 0-second player is all the browser can show — so the log has to.

## Consequences

- Accounts that require Basic Auth on recording media play in Odoo.
- **External Storage is not supported for in-Odoo playback.** Twilio does not
  serve the media, and Connect holds no bucket credentials. The proxy logs the
  `403`; the fix is either to turn External Storage off for the account, or to
  add bucket credentials to Connect — a separate feature, deliberately not
  built here.
- Providers that publish plainly-readable media (Infobip downloads into
  attachments; Bird fetches by cron) are unaffected: `get_media_auth()` keeps
  answering `None` for them.
