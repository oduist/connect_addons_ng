# Oduist Connect ElevenLabs Knowledge — Administrator Guide

`connect_elevenlabs_knowledge` is an add-on for **connect_elevenlabs** (the
ElevenLabs Conversational-AI voice-agent add-on for Twilio). It manages the
**ElevenLabs knowledge base** from inside Odoo: you create knowledge documents
(from a URL, an uploaded file, or plain text), the module pushes them to the
ElevenLabs Conversational-AI knowledge base, and you attach them to voice agents
so the agent can answer from that content during calls.

## What this module adds on top of connect_elevenlabs

| Area | Capability |
|------|------------|
| **Knowledge documents** | New model `connect.elevenlabs_knowledge` — a document sourced from a URL, a file (`.epub`, `.pdf`, `.docx`, `.txt`, `.html`, `.md`) or raw text |
| **ElevenLabs sync** | Documents are created / renamed / deleted in the ElevenLabs knowledge base automatically on create/write/unlink; a two-way **Sync** pulls existing ElevenLabs documents into Odoo |
| **Agent linkage** | A **Knowledge Base** many2many is added to `connect.elevenlabs_agent`; linked documents are folded into the agent's prompt configuration and re-synced when the link changes |
| **Status tracking** | Each document has a lifecycle state (`draft → creating → active / error`) with an error message and a retry action |
| **Menu** | A **Knowledge** menu under **Connect ▸ ElevenLabs** |

## Dependencies

From `__manifest__.py`:

```python
'depends': ['connect_elevenlabs']
```

Only **connect_elevenlabs** is required. Configure and connect it (ElevenLabs
API key, public API URL) before using this add-on.

## Prerequisites

- A working **connect_elevenlabs** setup with a valid ElevenLabs API key —
  every document operation calls `connect.settings.get_elevenlabs_client()`.
- Network access from Odoo to the ElevenLabs API.

## Menu & access

- **Connect ▸ ElevenLabs ▸ Knowledge** opens the document list/form
  (`connect.elevenlabs_knowledge`).
- Access rights (`security/user.xml`, `security/admin.xml`):

    | Group | Read | Write | Create | Unlink |
    |-------|:----:|:-----:|:------:|:------:|
    | `connect.group_user` | yes | no | no | no |
    | `connect.group_admin` | yes | yes | yes | yes |

    Connect Users can view the knowledge base; only **Connect Administrators**
    can create, edit or delete documents (and thereby change the remote
    ElevenLabs knowledge base).

See [Managing the Knowledge Base](knowledge-base.md) for document types, the
sync behavior, agent linkage and troubleshooting.
