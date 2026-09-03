# Security

## Security Groups

Connect defines three security groups:

| Group | XML ID | Purpose |
|-------|--------|---------|
| **Connect User** | `connect.group_user` | Read access to calls, messages, recordings. Can make calls and send messages. |
| **Connect Admin** | `connect.group_admin` | Full CRUD on all Connect models. Can configure settings, users, callflows. |
| **Connect Webhook** | `connect.group_webhook` | Create and read access for webhook-created records. Used by the system webhook user. |

### Assigning Groups

When you create a PBX user and link it to an Odoo user, the Connect User group is automatically assigned. Admins must be assigned the Connect Admin group manually via Odoo user settings.

### Users without a Connect group

An internal Odoo user who belongs to none of the Connect groups sees no trace
of Connect:

- **The Connect app is hidden.** `menu_connect_root` is gated on Connect User /
  Connect Admin, so the app and every provider submenu under it are absent from
  the apps menu.
- **The Calls / Messages smart buttons are hidden** on partners, leads,
  employees, sale orders, invoices, tasks, projects and helpdesk tickets. Their
  counts are computed with `sudo()`, so before the gate the buttons rendered for
  everyone and only failed on click.
- **The web phone does not load.** The provider bootstrap RPCs answer "not
  enabled" for such a user, so no softphone widget registers and the browser
  does no PBX lookups on page load.

Two things this deliberately does **not** do:

- **A direct URL still returns an `AccessError`.** Hiding the menu is not a
  permission; the access rules are what answer for a user who navigates to a
  Connect page by URL, bookmark or a restored last action. Grant Connect User
  to a user who is meant to have access.
- **It does not restrict their own user record.** Reading `res.users` —
  their own preferences, or any read whose field list covers the PBX-user link —
  works normally for every internal user. The PBX user records themselves stay
  unreadable to them.

## Access Control Matrix

| Model | User | Admin | Webhook |
|-------|------|-------|---------|
| Calls | Read, Write, Create | Full | Read, Write, Create |
| Channels | Read | Full | Read, Write, Create |
| Messages | Read, Write, Create | Full | Read, Write, Create |
| Recordings | Read | Full | Read, Write, Create |
| PBX Users | Read | Full | Read |
| Numbers (per provider) | Read | Full | — |
| Caller IDs (per provider) | Read | Full | — |
| Extensions (per provider) | Read | Full | — |
| Call Flows (per provider) | Read | Full | — |
| Endpoints (per provider) | Read, Write (own) | Full | — |
| Settings | — | Full | — |
| Favorites | Full | Full | — |
| Debug Log | — | Full | Create |

Numbers, caller IDs, extensions, call flows and endpoints are per-provider
models owned by `connect_twilio`, `connect_freeswitch` and `connect_asterisk`;
their access rules ship with those modules and follow the same pattern.

## Protected Fields

Sensitive fields are masked in the UI for non-managers (`base.group_erp_manager`):

- **OpenAI API Key** — displays `****` unless user is an ERP Manager
- **Twilio Auth Token** — displays `****` unless user is an ERP Manager
- **Twilio API Secret** — displays `****` unless user is an ERP Manager

## Webhook Security

### Twilio

When **Verify Requests** is enabled in settings, all incoming Twilio webhooks are validated using the `X-Twilio-Signature` header. This ensures requests genuinely come from Twilio.

!!! warning
    Always enable request verification in production. Disable only for development/debugging.

### FreeSWITCH

FreeSWITCH webhooks (`/freeswitch/xml`, `/freeswitch/webhook/*`) do not have signature verification. Ensure FreeSWITCH and Odoo communicate over a trusted network or use firewall rules to restrict access.

### Webhook User

A special inactive Odoo user (`connect.user_connect_webhook`) is defined in core data. All webhook handlers use this user's context to process provider events with explicit model permissions. This user belongs to the Connect Webhook group and has read-only access to PBX users so routing callbacks can resolve their destination.

## Record Rules

- **Users** see only calls, messages, and recordings associated with their PBX user account
- **Admins** see all records across all users
- PBX user records are restricted: each user can only see their own PBX user record

## Best Practices

1. **Use HTTPS** — Both Twilio and Verto WebRTC require secure connections
2. **Enable request verification** for Twilio webhooks in production
3. **Restrict FreeSWITCH access** — Use firewall rules to limit which IPs can reach `/freeswitch/*` endpoints
4. **Rotate API keys** regularly
5. **Limit admin access** — Only grant Connect Admin to users who need to configure the system
6. **Deploy the SIP firewall** — for any FreeSWITCH host exposed to the
   public Internet, run the [SIP Firewall service](../../FreeSWITCH/admin/firewall.md). It
   blocks brute-force registrations at the kernel level and gives you
   an audit trail of every authentication attempt inside Odoo.
