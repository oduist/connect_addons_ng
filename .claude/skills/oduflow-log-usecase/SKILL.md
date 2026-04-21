---
name: oduflow-log-usecase
description: "Log an Oduflow MCP session into the repo's `.oduflow/use-cases/` directory for future reference and statistics. Use this skill when the user asks to record/log/save an Oduflow interaction — phrases like «запиши oduflow», «залогируй oduflow use-case», «сохрани вызов oduflow», «log oduflow», «record oduflow usage». Accepts a slug argument (e.g. `fix-shipment-search`) and creates/updates `YYYY-MM-DD-<slug>.md` with the full task description, every Oduflow MCP call (tool name, arguments, result) and final outcome. Used to build a corpus of real Oduflow usage in this repo."
---

# oduflow-log-usecase — Oduflow MCP usage log in the repository

This skill saves a detailed report of an Oduflow MCP session into a Markdown file inside `.oduflow/use-cases/`. The goal is to accumulate full "raw" examples of how Oduflow is applied in this repository: what tasks are solved, with which calls, what responses come back. Files are committed to git alongside the code.

This is NOT a replacement for `.memory/` (task context). This is specifically a log of MCP interactions with Oduflow.

## When to trigger

The user explicitly asks to record oduflow call(s). Typical phrases:

- «запиши этот oduflow»
- «залогируй oduflow use-case»
- «сохрани вызов oduflow»
- «log oduflow»
- «record oduflow usage»
- «добавь в .oduflow»

Do not run automatically after every MCP call. Only on explicit user request.

## Arguments

The skill accepts one argument — the task/use-case **slug** in kebab-case (short description, <40 characters). Example: `fix-shipment-search`, `upgrade-supply-contract`, `debug-mrp-production`.

If the user has not provided a slug — ask with one phrase: "What slug should I use for the file?" and suggest 1-2 options derived from the current dialogue.

## Workflow

1. **Determine metadata.** Run in parallel:
   - `date +%Y-%m-%d` — date for the filename and header
   - `git rev-parse --show-toplevel` — repo root (to know the exact absolute path to `.oduflow/use-cases/`)
   - `git branch --show-current` — current branch (for metadata)

2. **Compose the filename.** Format: `YYYY-MM-DD-<slug>.md`. Path: `<repo_root>/.oduflow/use-cases/YYYY-MM-DD-<slug>.md`.

   - If a file with this name already exists — **append** a new section (new call/step) to the end, do not overwrite. This allows accumulating multi-step scenarios.
   - If another use-case was recorded the same day — it has a different slug, so the file will be different.

3. **Gather content from the current dialogue.** Rely ONLY on what actually happened in the session. Do not invent parameters and do not paraphrase MCP responses — copy them verbatim.

   For each Oduflow MCP call record:
   - **Tool** — full tool name (e.g. `mcp__oduflow_velesagro__upgrade_odoo_modules`)
   - **Arguments** — JSON block with all passed parameters (exactly what was sent)
   - **Result** — verbatim MCP response. If the response is large, save it in full inside a fenced block; you may collapse it with `<details>`, but do not truncate the content.
   - **Observation / takeaway** — 1-3 lines: what it yielded, what conclusion was drawn, what was done next.

4. **File template** (when creating a new file):

   ```markdown
   # <slug> — <YYYY-MM-DD>

   **Branch:** `<git branch>`
   **Goal:** <one or two sentences — what task was being solved>
   **Related files/PR:** <list, if relevant; otherwise omit the section>

   ## Context

   <1-2 paragraphs: why Oduflow was used, what needed to be checked/done>

   ---

   ## Step 1. <short step name>

   **Tool:** `mcp__oduflow_velesagro__<name>`

   **Arguments:**
   ```json
   { ... }
   ```

   **Result:**
   ```
   <verbatim response>
   ```

   **Observation:** <what was seen, what was done next>

   ---

   ## Step 2. ...

   ...

   ---

   ## Outcome

   <2-4 lines: how it ended, what works/does not work, what are the next actions>
   ```

   When appending to an existing file — add a new `## Step N.` at the end (before the `## Outcome` section), and update `## Outcome` if something new emerged.

5. **Write the file** via Write (new) or Edit (append).

6. **Short report to the user** at the end: relative path to the created/updated file and one sentence about the content. Do not retell the whole file.

## Rules

- **Do not commit.** The user will commit themselves. Just create/update the file.
- **Do not invent MCP calls.** If the current dialogue contained no Oduflow calls — warn the user and do not create an empty file.
- **No secrets** in arguments/responses: if a response contains tokens/passwords — mask them (`***`) and mention this in the Observation.
- **Language** — English; translate from Russian where needed.
- **No emojis.**
- **The folder already exists** (`.oduflow/use-cases/`) — do not recreate it, do not add `.gitkeep` or README.
