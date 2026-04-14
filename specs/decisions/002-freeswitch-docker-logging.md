# ADR-002: FreeSWITCH Docker Logging to stdout

**Date:** 2026-03-17
**Status:** Accepted

## Problem
FreeSWITCH logs were written to `/var/log/freeswitch/freeswitch.log` inside the container, invisible to `docker logs`. `mod_console` requires a TTY which Docker doesn't provide, so console output was lost.

## Options Considered
1. **Remove mod_logfile, keep mod_console** — Doesn't work: mod_console needs a TTY that Docker containers don't have.
2. **Redirect mod_logfile to /dev/stdout (chosen)** — Standard Docker pattern (used by nginx, etc.). Remove mod_console as redundant.
3. **Symlink log file to /dev/stdout in Dockerfile** — Works but less explicit than a config change.

## Decision
Option 2 — Point mod_logfile at `/dev/stdout` and remove mod_console. Disabled rollover and rotate-on-hup since they're meaningless for stdout.
