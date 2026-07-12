# Customer Onboarding Runbook — FreeSWITCH

This runbook walks an operator through onboarding a new customer on the
**FreeSWITCH** provider — from an empty host to a smoke-tested phone
system. It is an ordered checklist with pointers: the detailed reference
for every screen, field and failure mode lives in
[FreeSWITCH Integration Setup](freeswitch-setup.md) and
[Firewall Service](firewall.md); this page only fixes the *order* of the
steps and the values that must be captured along the way.

!!! note "Scope"
    Until multi-tenancy lands, every customer gets a **dedicated
    FreeSWITCH host**. The customer's Odoo runs elsewhere (their existing
    Odoo deployment) and talks to the FreeSWITCH host over the public
    network. This runbook covers the FreeSWITCH provider only — Twilio,
    Telnyx, Asterisk and Infobip customers follow the corresponding
    setup guide instead.

## Onboarding at a glance

1. [Collect prerequisites](#1-prerequisites)
2. [Provision the host](#2-provision-the-host)
3. [DNS, Traefik, Let's Encrypt](#3-dns-traefik-lets-encrypt)
4. [Compose layout and secrets](#4-compose-layout)
5. [Odoo: modules and FreeSWITCH settings](#5-odoo-modules-and-settings)
6. [Firewall service](#6-firewall)
7. [Trunk gateway, DIDs, routes, caller IDs](#7-trunk-gateway-dids-routes-caller-ids)
8. [Users and endpoints](#8-users-and-endpoints)
9. [Smoke tests](#9-smoke-tests)
10. [Handover record](#10-handover-record)

## 1. Prerequisites

Collect **before** starting; every item below blocks a later step.

| Item | Why |
|---|---|
| Linux host (VM or bare metal) with a **public IPv4** and root access | SIP/RTP does not survive Docker NAT — all telephony containers run with `network_mode: host`; the firewall service needs `NET_ADMIN` against the host kernel. |
| Docker Engine + compose plugin installed | Everything runs as containers. |
| DNS control for the customer's FreeSWITCH FQDN (e.g. `fs.customer.example.com`) | Let's Encrypt (TLS-ALPN) validates against this name; Verto WSS and XML-RPC use it. |
| Customer's Odoo: public URL + admin login | Modules are installed and all PBX configuration is done there. |
| SIP trunk credentials from the provider | Proxy, username/password (or the provider's IP list for IP-auth trunks), the DID numbers. |
| A password vault entry for this customer | Four secrets are generated during onboarding (webhook token, firewall token, ESL password, XML-RPC password) and several fields mask themselves after saving — record values at the moment of generation. |

Ports that must be reachable on the FreeSWITCH host (open in the cloud
security group / host firewall):

| Port | Proto | Purpose |
|---|---|---|
| 80 | TCP | Traefik HTTP→HTTPS redirect (ACME uses TLS-ALPN on 443, not this port). |
| 443 | TCP | Traefik TLS edge: XML-RPC (`/RPC2`) from Odoo, firewall dashboard/sync (`/firewall`). |
| 5080 | UDP+TCP | SIP signaling (sofia `external` profile) — trunks and SIP phones. |
| 16000–17000 | UDP | RTP media. |
| 48082 | TCP | Verto WSS — browser softphone signaling. |

Internal-only, never expose: `8080/tcp` (mod_xml_rpc plain HTTP, behind
Traefik), `8081/tcp` (firewall service HTTP, behind Traefik),
`8021/tcp` (FreeSWITCH ESL, localhost only).

## 2. Provision the host

1. Install Docker and the compose plugin ([official
   instructions](https://docs.docker.com/engine/install/)).
2. Copy the deploy folder from the addons repo to the host, e.g.:

    ```bash
    scp -r connect_freeswitch/deploy/ root@fs.customer.example.com:/opt/freeswitch
    ```

    The folder carries the FreeSWITCH static configuration
    (`freeswitch/conf/`), the Traefik dynamic config (`traefik/`) and the
    `.env` / compose templates that the next steps customize. Keep
    `/opt/freeswitch` under configuration management or note it in the
    handover record — it is the only state on the host besides Docker
    volumes.

## 3. DNS, Traefik, Let's Encrypt

1. Create an **A record** for the FQDN pointing at the host's public IP
   and wait until it resolves publicly — ACME validation fails otherwise.
2. Edit `/opt/freeswitch/.env`:

    ```bash
    COMPOSE_PROJECT_NAME=fs
    # Customer's Odoo, used by FreeSWITCH for xml_curl/CDR/recording callbacks
    ODOO_URL=https://odoo.customer.example.com
    FS_DOMAIN=fs.customer.example.com
    ACME_EMAIL=ops@example.com
    # Keep the staging CA enabled until the whole stack comes up cleanly,
    # then comment it out and remove the acme volume to get the real cert:
    ACME_CASERVER=https://acme-staging-v02.api.letsencrypt.org/directory
    ```

3. Traefik requests the certificate automatically on first start (next
   step); the FreeSWITCH entrypoint extracts the same certificate from
   the shared ACME volume for Verto WSS and DTLS-SRTP. Details:
   [TLS/SSL Certificates](freeswitch-setup.md#tlsssl-certificates).

!!! warning "Switch off the staging CA before handover"
    While `ACME_CASERVER` points at staging, browsers and Odoo (with
    **Verify TLS Certificate** on) reject the certificate. After the
    stack is verified: comment the line out, `docker compose down`,
    `docker volume rm fs_traefik-acme`, `docker compose up -d`.

## 4. Compose layout

The shipped `connect_freeswitch/deploy/docker-compose.yml` is a
**development** stack — it bundles Odoo + Postgres and runs FreeSWITCH
from the upstream `safarov/freeswitch` image. For a customer host use
the production layout below: only `traefik`, `fs` and `firewall`, with
the `oduist/freeswitch` image (its entrypoint extracts the ACME
certificate for `FS_DOMAIN`, applies `FS_ESL_PASSWORD`, and ships the
curated module set incl. Piper TTS).

Generate the secrets first and record all of them in the vault:

```bash
# FreeSWITCH -> Odoo webhook token (>=24 chars, [A-Za-z0-9_-])
openssl rand -base64 32 | tr '+/' '-_'
# Firewall <-> Odoo shared token (same alphabet/length rules)
openssl rand -base64 32 | tr '+/' '-_'
# ESL password (fs and firewall containers must match)
openssl rand -base64 24 | tr '+/' '-_'
```

Append them to `/opt/freeswitch/.env`:

```bash
FS_WEBHOOK_TOKEN=<webhook token>
FS_ESL_PASSWORD=<esl password>
FIREWALL_AGENT_TOKEN=<firewall token>
FIREWALL_DASHBOARD_PASSWORD=<pick a strong password>
```

`docker-compose.yml` (template — no customer-specific values, everything
comes from `.env`):

```yaml
services:
  # TLS edge: terminates HTTPS for XML-RPC (/RPC2) and the firewall
  # dashboard (/firewall); requests the Let's Encrypt certificate that
  # the fs entrypoint reuses for Verto WSS.
  traefik:
    image: traefik:v3.3
    container_name: traefik
    restart: unless-stopped
    command:
      - "--global.checknewversion=false"
      - "--global.sendanonymoususage=false"
      - "--entrypoints.web.address=:80"
      - "--entrypoints.web.http.redirections.entrypoint.to=websecure"
      - "--entrypoints.web.http.redirections.entrypoint.scheme=https"
      - "--entrypoints.websecure.address=:443"
      - "--entrypoints.websecure.http.tls.certresolver=letsencrypt"
      - "--entrypoints.websecure.http.tls.domains[0].main=${FS_DOMAIN:?Set FS_DOMAIN in .env}"
      - "--providers.file.filename=/etc/traefik/dynamic.yml"
      - "--providers.file.watch=true"
      - "--certificatesresolvers.letsencrypt.acme.email=${ACME_EMAIL:?Set ACME_EMAIL in .env}"
      - "--certificatesresolvers.letsencrypt.acme.storage=/acme/acme.json"
      - "--certificatesresolvers.letsencrypt.acme.tlschallenge=true"
      - "--certificatesresolvers.letsencrypt.acme.caserver=${ACME_CASERVER:-https://acme-v02.api.letsencrypt.org/directory}"
    ports:
      - "80:80"
      - "443:443"
    extra_hosts:
      - "host.docker.internal:host-gateway"
    volumes:
      - ./traefik/dynamic.yml:/etc/traefik/dynamic.yml:ro
      - traefik-acme:/acme

  fs:
    image: oduist/freeswitch:latest   # pin the current release tag in production
    container_name: freeswitch
    hostname: freeswitch
    network_mode: host
    restart: unless-stopped
    environment:
      - SOUND_RATES=8000:16000
      - SOUND_TYPES=music:en-us-callie
      - EPMD=false
      - DUMPCAP=false
      - ODOO_URL=${ODOO_URL}
      - FS_WEBHOOK_TOKEN=${FS_WEBHOOK_TOKEN}
      - FS_DOMAIN=${FS_DOMAIN}
      - FS_ESL_PASSWORD=${FS_ESL_PASSWORD}
    volumes:
      - freeswitch-sounds:/usr/share/freeswitch/sounds
      - ./freeswitch/conf:/etc/freeswitch
      - ./freeswitch/logs:/var/log/freeswitch
      - traefik-acme:/etc/traefik

  # SIP brute-force protection; see docs/admin/firewall.md.
  firewall:
    image: oduist/freeswitch-firewall:1.1.0
    container_name: firewall
    network_mode: host
    restart: unless-stopped
    cap_add:
      - NET_ADMIN
    environment:
      - ODOO_URL=${ODOO_URL}
      - AGENT_TOKEN=${FIREWALL_AGENT_TOKEN}
      - FS_ESL_HOST=127.0.0.1
      - FS_ESL_PORT=8021
      - FS_ESL_PASSWORD=${FS_ESL_PASSWORD}
      - HTTP_BIND_HOST=127.0.0.1
      - HTTP_BIND_PORT=8081
      - DASHBOARD_USER=admin
      - DASHBOARD_PASSWORD=${FIREWALL_DASHBOARD_PASSWORD}
    volumes:
      - firewall-cache:/var/lib/connect-firewall

volumes:
  freeswitch-sounds:
  firewall-cache:
  traefik-acme:
```

Extend `/opt/freeswitch/traefik/dynamic.yml` (the copied file already
routes `/RPC2`) with the firewall router:

```yaml
http:
  routers:
    freeswitch-xmlrpc:
      rule: "PathPrefix(`/RPC2`)"
      entryPoints: [websecure]
      service: freeswitch-xmlrpc
      tls: {}
    firewall:
      rule: "PathPrefix(`/firewall`)"
      entryPoints: [websecure]
      service: firewall
      tls: {}
  services:
    freeswitch-xmlrpc:
      loadBalancer:
        servers:
          - url: "http://host.docker.internal:8080"
    firewall:
      loadBalancer:
        servers:
          - url: "http://host.docker.internal:8081"
```

Then start the stack:

```bash
cd /opt/freeswitch
docker compose up -d
docker exec -it freeswitch fs_cli -x "status"   # sanity: FreeSWITCH is up
```

!!! note "First start before Odoo is configured"
    Until the webhook token is paired in Odoo (next step), every
    FreeSWITCH → Odoo call fails with HTTP 401 by design. Expect noisy
    xml_curl errors in the FreeSWITCH log at this point.

## 5. Odoo: modules and settings

1. Install `connect` and `connect_freeswitch` in the customer's Odoo —
   see [Installation](installation.md#installing-the-modules).
2. Open **Connect → FreeSWITCH → Configuration → Settings** and fill in
   (field-by-field reference:
   [Odoo Configuration](freeswitch-setup.md#odoo-configuration)):

    | Field | Value |
    |---|---|
    | WebSocket URL | `wss://fs.customer.example.com:48082` |
    | Domain | `fs.customer.example.com` |
    | FreeSWITCH Webhook Token | The `FS_WEBHOOK_TOKEN` value from `.env` — the field masks itself after saving, see [Webhook Token Pairing](freeswitch-setup.md#webhook-token-pairing). |
    | XML-RPC Host | `fs.customer.example.com` |
    | XML-RPC Port | `443` |
    | XML-RPC User / Password | Pick and vault a credential pair. FreeSWITCH fetches these from Odoo through xml_curl when `mod_xml_rpc` loads — set them here, then restart the `fs` container once so the module picks them up. |
    | Verify TLS Certificate | On (production certificate). Off only while the staging CA is active. |

3. Restart the `fs` container (`docker compose restart fs`) so
   FreeSWITCH re-reads directory/dialplan/configuration with the paired
   token and the XML-RPC credentials.
4. Click **CHECK STATUS** on the settings form — **Server Status** must
   show `UP — <version>`. Anything else: follow the decision table in
   [Checking server status](freeswitch-setup.md#checking-server-status).

## 6. Firewall

Full reference: [Firewall Service](firewall.md). Onboarding order:

1. In **Connect → FreeSWITCH → Configuration → Settings**, page
   **Firewall**:
    * toggle **Firewall Enabled** on;
    * set **Firewall Service URL** to `https://fs.customer.example.com`
      (Odoo appends `/firewall/sync`; Traefik routes the `/firewall`
      prefix to the service — the default
      `http://host.docker.internal:8081` only works when Odoo runs on
      the same host);
    * paste the `FIREWALL_AGENT_TOKEN` value from `.env` into
      **Firewall Service Token** (masks after saving);
    * keep the default port lists (`5060,5061,5080,5081`) and timeouts.
2. **Connect → FreeSWITCH → Firewall → Whitelist**: add the trunk
   provider's signaling IPs and the customer's office NAT exits. Saving
   syncs to the service immediately.

    !!! note "Whitelist vs. gateway Inbound IPs"
        The firewall whitelist only keeps an IP from being *auto-banned*
        at the kernel level. Accepting unauthenticated INVITEs from an
        IP-auth trunk is separate — that is the **Inbound IPs** field on
        the [SIP Gateway](freeswitch-setup.md#sip-gateways) record
        (sofia ACL).

3. **Connect → FreeSWITCH → Firewall → Agent Status** must show the
   agent *online* within one heartbeat interval (60 s). If not:
   [firewall troubleshooting](firewall.md#troubleshooting).

## 7. Trunk gateway, DIDs, routes, caller IDs

All under the **Connect → FreeSWITCH** menu; saving a gateway restarts
the sofia `external` profile automatically — no manual reload step.

1. **Configuration → SIP Gateways** — create the trunk from the
   provider's credentials (fields:
   [SIP Gateways](freeswitch-setup.md#sip-gateways)). For IP-auth trunks
   fill **Inbound IPs**. Verify registration:

    ```bash
    docker exec -it freeswitch fs_cli -x "sofia status gateway <name>"
    # State must be REGED (for register=true trunks)
    ```

2. **Numbers** — one record per DID, each routed to a user, callflow or
   FIFO. A leading `+` is matched tolerantly; digits beyond that must
   match what the trunk actually delivers (see
   [DID format mismatch](freeswitch-setup.md#inbound-call-dropped-with-404-did-format-mismatch)).
3. **Configuration → Outgoing Routes** — at minimum one catch-all route
   (pattern `^\+\d{7,}$`) through the trunk gateway; add
   national/emergency patterns per customer dial habits
   ([examples](freeswitch-setup.md#outgoing-routes)).
4. **Outgoing Caller IDs** — create the customer's DIDs as caller IDs
   and flag one as **Default**; optionally assign per-user numbers on
   the Connect User form. Resolution order:
   [Outbound Caller ID](freeswitch-setup.md#outbound-caller-id-did).

## 8. Users and endpoints

1. Create PBX users under **Connect → Users** — extension, Odoo user
   link, groups ([PBX Users](core-setup.md#pbx-users)). With several
   provider modules co-installed, set each user's **Originate Provider**
   to FreeSWITCH so click-to-call uses this host.
2. For every user create at least one endpoint under
   **Connect → FreeSWITCH → Endpoints** — the SIP/Verto password is
   auto-generated; copy it from the form for desk phones
   ([Endpoints](freeswitch-setup.md#endpoints)).

## 9. Smoke tests

Run all of these before declaring the customer live. Each line has a
detailed fallback reference.

| # | Test | Pass criterion | If it fails |
|---|---|---|---|
| 1 | **CHECK STATUS** button in FreeSWITCH settings | `UP — <version>`, registrations/gateways listed | [Status decision table](freeswitch-setup.md#checking-server-status) |
| 2 | Browser softphone: dial `9196` (echo) | You hear yourself echoed back | [Echo test](freeswitch-setup.md#echo-test); no audio → RTP 16000–17000/udp blocked |
| 3 | Browser softphone: dial `9664` | Hold music plays | [Testing](freeswitch-setup.md#testing) |
| 4 | Outbound PSTN call to a mobile | Call connects; the mobile shows the customer's default caller ID | `sofia status gateway <name>`; [Outgoing Routes](freeswitch-setup.md#outgoing-routes) |
| 5 | Inbound call to each DID | Rings the configured user/callflow | [DID troubleshooting](freeswitch-setup.md#inbound-call-dropped-with-404-did-format-mismatch) |
| 6 | Click-to-call from a partner form in Odoo | User's phone rings, then the destination | User's **Originate Provider** = FreeSWITCH; endpoint registered |
| 7 | Call history | Calls from tests 4–6 appear under **Connect → Calls** with recordings (if enabled) | CDR webhook / webhook token pairing ([XML cURL Integration](freeswitch-setup.md#xml-curl-integration)) |
| 8 | Firewall liveness | `curl -s https://fs.customer.example.com/firewall/healthz` returns `{"status":"ok","odoo":true,"esl":true}`; agent *online* in Odoo | [Firewall troubleshooting](firewall.md#troubleshooting) |

## 10. Handover record

Record these in the customer's operations vault/wiki when the smoke
tests pass — the next operator (and the next onboarding) starts from
this table:

| Item | Value to record |
|---|---|
| FreeSWITCH FQDN + host IP | `fs.customer.example.com`, provider/region of the VM |
| Deploy path on the host | e.g. `/opt/freeswitch` (compose, `.env`, Traefik config) |
| Odoo URL | the `ODOO_URL` the containers point at |
| Secrets (vault reference) | webhook token, firewall token, ESL password, XML-RPC user/password, firewall dashboard password |
| Trunk provider | account, proxy, auth mode (register vs IP-auth), support contact |
| DIDs | numbers and their routing (user/callflow) |
| Image tags deployed | `oduist/freeswitch:<tag>`, `oduist/freeswitch-firewall:<tag>` |
| Date of Let's Encrypt switch to production CA | to correlate future renewal issues |

Routine operations after handover (trunk password rotation, unbanning
IPs, monitoring) are covered by the
[Operations Runbook](freeswitch-setup.md#operations-runbook) section and
[Firewall daily operations](firewall.md#daily-operations).
