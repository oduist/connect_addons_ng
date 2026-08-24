# Security

`connect_crm` relies on the standard Connect security groups and adds a small set
of webhook access rules so that inbound telephony events can create and update
leads.

## Connect groups

The module does not define new groups. Access to the CRM auto-create settings
follows the core convention:

| Group | On CRM features |
|-------|-----------------|
| `connect.group_user` (Connect User) | Read access, in line with core; sees linked leads/sources on calls per standard CRM rights. |
| `connect.group_admin` (Connect Administrator) | Full CRUD, including the **CRM** tab of the settings form. |
| `connect.group_webhook` (Connect Webhook) | The dedicated identity used by public webhook controllers — see below. |

CRM records themselves (`crm.lead`, `utm.source`) keep their normal Odoo CRM/UTM
access rights; `connect_crm` only adds telephony fields and behavior on top.

## Webhook access rules

`security/webhook.xml` grants the webhook identity the minimum it needs to
journal telephony events into CRM. This is the group carried by the special
`connect.user_connect_webhook` user that public controllers run as.

| Model | Read | Create | Write | Unlink |
|-------|:----:|:------:|:-----:|:------:|
| `crm.lead` | ✓ | ✓ | ✓ | — |
| `mail.alias_domain` | ✓ | — | — | — |
| `crm.stage` | ✓ | — | — | — |
| `crm.team` | ✓ | — | — | — |

A matching record rule (`crm_lead_webhook_rule`) lets the webhook group read,
create and write **all** leads (`[(1, '=', 1)]`) — it is not scoped to a
salesperson, because webhook-driven creation happens before any assignment.

!!! warning "Webhook identity can create leads"
    The webhook group can create and modify any lead. That is required for
    telephony-driven lead creation, but it means the webhook credentials must be
    protected like any other integration secret. Deletion is never granted.
