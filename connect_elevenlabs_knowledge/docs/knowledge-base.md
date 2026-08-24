# Managing the Knowledge Base

Open **Connect ▸ ElevenLabs ▸ Knowledge**. Each row is a
`connect.elevenlabs_knowledge` document that mirrors one document in the
ElevenLabs Conversational-AI knowledge base.

## Creating a document

Create a record and pick a **Document Type**:

=== "URL"
    Set **URL**. On save, Connect calls
    `knowledge_base.documents.create_from_url`.

=== "File"
    Upload a **File**. Allowed extensions are enforced by a constraint:
    `.epub`, `.pdf`, `.docx`, `.txt`, `.html`, `.md`. Anything else raises a
    validation error. The file is sent via `create_from_file`.

=== "Text"
    Type the content into **Text**. Sent via `create_from_text`.

On creation the record moves through the **state** bar:

- **draft** → **creating** while the API call is in flight →
- **active** once ElevenLabs returns a document id (stored in **Document ID** /
  `knowledge_id`), or
- **error** with the failure captured in **Error Information**.

If a document ends in **error**, fix the input and use the **Retry Creation**
button (`action_retry_creation`), which re-runs the creation call.

!!! note "Creation happens automatically"
    The remote document is created as part of the Odoo `create`. There is no
    separate "push" button — saving the record is what creates it in ElevenLabs.

## Renaming and deleting

- **Renaming**: changing **Name** on an *active* document pushes the new name to
  ElevenLabs (`documents.update`). A failed rename is logged but does not block
  the Odoo save.
- **Deleting**: unlinking the Odoo record deletes the remote document
  (`documents.delete`). If ElevenLabs refuses because the document is still used
  by an agent, the deletion raises the ElevenLabs error message. Tick **Force
  Delete** on the document beforehand to delete it even while agents reference
  it (`force=True`).

## Syncing from ElevenLabs

Documents can also be imported from ElevenLabs. On the **ElevenLabs settings
form** this add-on adds a **SYNC KNOWLEDGE** button (next to the tools sync
button; visible only when ElevenLabs is enabled). It runs
`action_sync_from_elevenlabs`, which lists owned documents from ElevenLabs and:

- creates an Odoo record for any document not already present (defaulting the
  type to *URL*), and
- updates name / description / size on documents already linked by
  `knowledge_id`.

Use this after importing documents directly in the ElevenLabs dashboard, or to
reconcile Odoo with the remote knowledge base.

## Attaching documents to an agent

The add-on adds a **Knowledge Base** tab to the ElevenLabs agent form
(`connect.elevenlabs_agent`). Link documents there, or from a document use
**View Agents** to see which agents already use it.

When an agent's linked documents change, the affected agents are re-synced to
ElevenLabs automatically so the change takes effect. Only documents that are
**active** and have a `knowledge_id` are included in the agent's prompt
configuration — draft or errored documents are skipped.

!!! tip "Agent count"
    Each document shows an **Agents** count and the **Used by Agents** list, so
    you can see reuse before editing or deleting a document.

## Fields reference

| Field | Notes |
|-------|-------|
| `name` | Document title; renaming an active doc pushes to ElevenLabs |
| `document_type` | `url` / `file` / `text` |
| `url` / `file` / `text` | Source content per type |
| `knowledge_id` | ElevenLabs document id (read-only) |
| `state` | `draft` / `creating` / `active` / `error` |
| `error_message` | Last failure detail (read-only) |
| `description` | Free-text description (synced from ElevenLabs on import) |
| `document_size` | Size in bytes (read-only, from ElevenLabs) |
| `created_at` / `updated_at` | Timestamps (read-only) |
| `force_delete` | Allow deletion while agents still reference the document |
| `agent_ids` / `agent_count` | Agents linked via the shared `agent_knowledge_rel` relation |

## Troubleshooting

- **Stuck in `error`** — read **Error Information**, correct the URL/file/text,
  then **Retry Creation**. API errors (bad key, unreachable ElevenLabs) surface
  here.
- **Cannot delete** — the remote document is in use by an agent; either detach
  it from the agents first or enable **Force Delete**.
- **Nothing happens on save** — confirm the ElevenLabs API key is set and valid
  in the connect_elevenlabs settings; the client is obtained from
  `connect.settings.get_elevenlabs_client()`.
