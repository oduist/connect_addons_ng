---
name: oduflow
description: "Agentic Odoo development with Oduflow MCP. Provisions isolated Docker environments per git branch for testing Odoo modules. Use when: (1) deploying/testing Odoo modules in an environment, (2) running Odoo tests, (3) debugging Odoo module errors, (4) managing Oduflow environments, (5) any task involving push → test → fix cycle for Odoo addons. Triggers on: oduflow commands, Odoo environment management, module install/upgrade/test requests, or when the user wants to test code changes in a live Odoo instance."
---

# Oduflow — Agentic Odoo Development

Oduflow provisions isolated, ephemeral Odoo environments on Docker — one per git branch — with instant creation from reusable database templates. It enables a closed feedback loop: write code → push → install/upgrade → read errors → fix → retry.

## Workflow

```
1. list_environments       — Reuse existing environment if available
2. create_environment      — Provision if needed (branch, repo_url, odoo_image)
3. Edit code locally
4. git commit & push
5. pull_and_apply          — Errors returned directly in response
6. If errors → fix → go to step 4
7. run_odoo_tests          — Validate with tests
8. delete_environment      — Tear down when done
```

## Critical Rules

- **Always `pull_and_apply` after every `git push`** — it auto-detects install/upgrade/restart needs.
- **Read errors from tool responses** — `pull_and_apply`, `install_odoo_modules`, `upgrade_odoo_modules`, `run_odoo_tests` return output directly. Do NOT call `get_environment_logs` for these.
- **Use `get_environment_logs` only for runtime server errors** (errors during request handling).
- **Never edit code inside the container** — edit locally → commit → push → `pull_and_apply`.
- **One task = one branch = one environment.**
- **Show the environment URL** to the user after creation.
- **Only `delete_environment` when task is Done or Cancelled.**
- Template operations (`save_as_template`, `delete_template`) require explicit user permission.

## Large Output Handling

When output exceeds ~5K chars, Oduflow returns a summary with an `output_id`. Use `read_output(output_id, mode=...)` to drill down: `"errors"`, `"grep"`, `"lines"`, `"tail"`, or `"info"`.

## Database Migrations

Migrations run only during upgrade, NOT during `create_environment`. Never recreate an environment to apply migrations — use `pull_and_apply` or `upgrade_odoo_modules`.

## Full Tool Reference

See [references/agent_instructions.md](references/agent_instructions.md) for the complete MCP tools reference, smart pull behavior, and detailed usage patterns.
