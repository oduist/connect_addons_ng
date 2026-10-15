# Security

This module ships no new security groups. It relies on the standard Connect
groups and on Odoo's own Helpdesk access rules.

## Access groups

| Group | Meaning for this module |
|-------|-------------------------|
| `connect.group_user` (Connect User) | Read access to Connect data. Users see the **Ticket** column and the linked ticket on call forms subject to their normal Helpdesk rights. |
| `connect.group_admin` (Connect Administrator) | Full access, including editing the **Helpdesk** page on the Connect settings form (auto-create rules, default team and assignee). |
| `connect.group_webhook` (Connect Webhook) | The identity used by provider webhook controllers; granted limited Helpdesk access so incoming call events can attach and create tickets (see below). |

Actual ticket visibility and editing follow Odoo Helpdesk's own team/assignment
access rules — this module does not widen them for regular users.

## Webhook access rules

Provider webhooks run as the Connect Webhook user, which is not a normal
Helpdesk user. `security/webhook.xml` grants it the minimum needed to link and
create tickets from call events:

| Model | Read | Create | Write | Unlink |
|-------|------|--------|-------|--------|
| `helpdesk.ticket` | yes | yes | yes | no |
| `helpdesk.stage` | yes | no | no | no |
| `helpdesk.team` | yes | no | no | no |

An additional record rule (`helpdesk_ticket_webhook_rule`,
`domain_force = [(1, '=', 1)]`) lets the webhook user see and match **all**
tickets regardless of team, which is required for phone-number lookup to work
across teams. The webhook user can create and update tickets but can never
delete them.

!!! warning "Do not reuse the webhook user interactively"
    The Connect Webhook identity exists only for unauthenticated provider
    callbacks. Its broad `[(1,'=',1)]` ticket rule is scoped to that automated
    flow — do not add human users to `connect.group_webhook`.
