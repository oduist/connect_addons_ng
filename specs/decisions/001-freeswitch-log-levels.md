# ADR-001: FreeSWITCH Log Level Configuration

**Date:** 2026-03-17
**Status:** Accepted

## Problem
FreeSWITCH log levels were hardcoded in static config files (`vars.xml`, `switch.conf.xml`, `sofia.conf.xml`). Need to make them configurable from Odoo UI.

## Options Considered
1. **Entrypoint script** — Shell script fetches config from a new Odoo API endpoint before starting FS. Pro: automatic on restart (just restart container). Con: adds complexity, race condition if Odoo isn't ready, needs JSON parsing in shell.
2. **Docker env vars (chosen)** — Pass log levels as env vars (`FS_LOG_LEVEL`, `FS_SOFIA_LOG_LEVEL`) when creating/updating the FS service. FS config reads them via `X-PRE-PROCESS cmd="env-set"`. Pro: simplest, no new API endpoint, no entrypoint script. Con: need to update service env vars + restart to apply changes.
3. **xml_curl configuration binding** — FS fetches switch.conf/console.conf from Odoo dynamically via xml_curl. Pro: fully dynamic. Con: replaces entire config sections, fragile if Odoo is down at boot.

## Decision
Option 2 — Docker environment variables. Simplest approach with no new moving parts. Log levels are non-critical config that rarely changes, so requiring a service env var update + restart is acceptable.
