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
   public Internet, run the [SIP Firewall service](firewall.md). It
   blocks brute-force registrations at the kernel level and gives you
   an audit trail of every authentication attempt inside Odoo.
