# ADR-005: FreeSWITCH Call Recording via mod_http_cache

**Date:** 2026-03-18
**Status:** Accepted

## Problem

FreeSWITCH needs to record calls and upload recordings to Odoo so they appear in the Connect UI with playback support. Several challenges emerged:

1. **Recording delivery mechanism** — FreeSWITCH records locally, but recordings must end up in Odoo
2. **HTTPS upload** — mod_http_cache needs SSL CA certificates to upload over HTTPS
3. **Race condition** — recording upload (PUT) arrives before CDR creates the channel record in Odoo
4. **Duplicate recordings** — `export` propagates `execute_on_answer` to both call legs, causing two uploads
5. **Caller ID** — SIP username (e.g. `user`) used as caller number instead of extension number
6. **Playback** — recordings must be accessible via the HTML audio widget in Odoo forms

## Options Considered

### Recording upload
- **A) mod_http_cache with HTTPS upload to Odoo** — FreeSWITCH uploads the .wav file via HTTP PUT directly to an Odoo webhook endpoint
- **B) Shared volume** — mount a shared directory between FS and Odoo containers
- **C) S3/external storage** — upload to S3, store URL in Odoo

### Recording storage in Odoo
- **A) ir.attachment (separate)** — store as standalone attachment, reference by ID in media_url
- **B) Binary field with `attachment=True`** — store on the model with filestore backend (like asterisk_plus)
- **C) Binary field with `attachment=False`** — store directly in PostgreSQL

## Chosen Approach

### Upload: mod_http_cache HTTPS PUT (Option A)
FreeSWITCH `record_session` uses an `https://` URL pointing to Odoo's recording webhook. mod_http_cache handles the PUT upload with SSL certificates configured.

### Storage: Binary field with `attachment=True` (Option B)
Recording data stored in `recording_attachment` field (Binary, attachment=True) on `connect.recording`. This stores the file in Odoo's filestore (filesystem), not in PostgreSQL. The audio widget uses `/web/content?model=connect.recording&field=recording_attachment&...` for playback.

## Implementation Details

### Dialplan generation (`fs_user.py`, `fs_callflow.py`)
- Recording URL uses `web.base.url` (not `connect.api_url`) — always HTTPS in production
- Uses `set` (not `export`) for `execute_on_answer` — only the A-leg records, preventing duplicate uploads
- `RECORD_STEREO=true` for stereo recording (each party on separate channel)
- `media_bug_answer_req=true` — recording starts only after answer

### FreeSWITCH Docker image
- `http_cache.conf.xml` configured with `ssl-cacert=/etc/ssl/certs/ca-certificates.crt` and `ssl-verifypeer=true`
- Runtime image includes `ca-certificates` package
- All shared library dependencies auto-collected via `ldd` scanning (no manual tracking)

### Recording webhook (`freeswitch_recording.py`)
- Route: `PUT/POST /freeswitch/webhook/recording/<filename>`
- Deduplicates by `call_sid` (UUID) — if recording already exists, returns 200 immediately
- Saves recording even if channel doesn't exist yet (race condition with CDR)
- Stores file in `recording_attachment` field, filename in `recording_filename`

### CDR handler (`call.py`)
- After creating channel from CDR, searches for orphan recordings (`call_sid` match, no channel linked)
- Links orphan recordings to the newly created channel, call, and partner

### CDR parser (`freeswitch_cdr.py`)
- Falls back to `effective_caller_id_number` (from channel variables set by Odoo directory) when `caller_id_number` is a non-numeric SIP username

### Recording widget (`recording.py`)
- If `recording_attachment` exists: serves via `/web/content?model=connect.recording&field=recording_attachment&...`
- Otherwise falls back to `media_url` (for Twilio/external recordings)
- HTML5 `<audio>` element with controls

## Key Decisions

| Decision | Rationale |
|----------|-----------|
| `set` not `export` | `export` copies the variable to the B-leg, causing both legs to record and upload the same file |
| `web.base.url` not `api_url` | `api_url` is a Connect-specific setting that may be HTTP; `web.base.url` is always set correctly by Odoo |
| Save recording without channel | Recording PUT arrives before CDR POST; link later in CDR handler |
| `attachment=True` on Binary field | Stores in filestore (filesystem), not PostgreSQL — better for large binary data |
| `ssl-cacert` in http_cache.conf | mod_http_cache defaults to `{certs_dir}/cacert.pem` which doesn't exist; point to system CA bundle |

## Files Changed

- `connect/models/recording.py` — added `recording_attachment`, `recording_filename` fields; updated widget
- `connect_freeswitch/controllers/freeswitch_recording.py` — recording webhook with dedup and orphan handling
- `connect_freeswitch/controllers/freeswitch_cdr.py` — effective_caller_id fallback, orphan recording linking
- `connect_freeswitch/models/call.py` — link orphan recordings after channel creation
- `connect_freeswitch/models/fs_user.py` — `set` instead of `export`, `web.base.url`
- `connect_freeswitch/models/fs_callflow.py` — same as fs_user.py
- `connect_freeswitch/deploy/freeswitch/conf/autoload_configs/http_cache.conf.xml` — SSL CA cert config
- `connect_freeswitch/deploy/Dockerfile` — auto-collected shared libs, proper entrypoint
- `connect_freeswitch/deploy/docker-entrypoint.sh` — POSIX-compatible entrypoint with sound download
