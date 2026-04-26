# Connect ElevenLabs Knowledge Module Specification

## Module Info

- **Name:** Oduist Connect ElevenLabs Knowledge
- **Technical:** `connect_elevenlabs_knowledge`
- **Version:** 19.0.1.0.0
- **Depends:** `connect_elevenlabs`
- **Application:** False
- **License:** Other proprietary

## Overview

Adds the ElevenLabs knowledge-base document model and ties documents to agents so the conversational AI can reference URLs, files (PDF/EPUB/DOCX/TXT/HTML/MD), or inline text.

## Models (connect_elevenlabs_knowledge/models/)

### 1. knowledge.py — `connect.elevenlabs_knowledge` (NEW)

| Field | Type | Notes |
|---|---|---|
| `name` | Char | required |
| `knowledge_id` | Char | ElevenLabs document ID |
| `document_type` | Selection | `url`, `file`, `text` (default `url`) |
| `file_name` / `file` | Char / Binary | For `file` type; allowed extensions: `.epub .pdf .docx .txt .html .md` |
| `url` | Char | For `url` type |
| `text` | Text | For `text` type |
| `description` | Text | |
| `created_at` / `updated_at` | Datetime | readonly |
| `document_size` | Integer | readonly |
| `force_delete` | Boolean | |
| `state` | Selection | `draft` / `creating` / `active` / `error` |
| `error_message` | Text | readonly |
| `agent_ids` | Many2many (`connect.elevenlabs_agent` via `agent_knowledge_rel`) | |
| `agent_count` | Integer (compute) | |

**Methods:** `create`/`write`/`unlink` override to sync with ElevenLabs; `create_elevenlabs_knowledge_base()`, `update_elevenlabs_knowledge_base()`, `delete_elevenlabs_knowledge_base()`. Context key `skip_elevenlabs` bypasses sync.

### 2. agent.py — `_inherit = 'connect.elevenlabs_agent'`

Adds `knowledge_base` Many2many field (reciprocal side of `agent_knowledge_rel`). Overrides `_compute_prompt_config()` to inject the active knowledge-base entries (`{type, name, id}`) into the agent prompt config. Helper methods: `add_knowledge_documents(ids)`, `remove_knowledge_documents(ids)`, `clear_knowledge_base()`.

### 3. settings.py — `_inherit = 'connect.settings'`

One-liner: appends `'connect_elevenlabs_knowledge'` to `ODUIST_MODULES`.

## Views

- `views/knowledge.xml` — tree/form/search for knowledge documents.
- `views/agent.xml` — adds the Knowledge tab to the agent form.
- `views/settings.xml` — (optional) knowledge-base section in the ElevenLabs settings tab.

## Security

- `admin.xml` / `user.xml` — `ir.model.access` for the new model on admin and user groups.

## License

Enforced via `check_license('connect_elevenlabs_knowledge', silent=True)` in the knowledge CRUD paths; silent failure degrades gracefully (no sync, no crash).
