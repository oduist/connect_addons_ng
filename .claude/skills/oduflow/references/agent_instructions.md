# Oduflow Agent Instructions

## Core Workflow

```
1. list_environments          — Check if an environment for the current branch exists
2. create_environment         — If not, provision one (branch, repo_url, odoo_image)
3. Write / edit code locally
4. git push
5. pull_and_apply — Pull changes; errors/tracebacks are returned directly in the response
6. If errors in response → fix code → go to step 4
7. run_odoo_tests            — Run Odoo tests for the changed modules
8. delete_environment          — Tear down when done
```

## MCP Tools Quick Reference

### Environment Lifecycle

| Tool | When to use |
|---|---|
| `list_environments` | Check existing environments before creating a new one |
| `create_environment(branch_name, repo_url, odoo_image, template_name?)` | Provision an environment. Pass `template_name="none"` for greenfield projects |
| `get_environment_info(branch_name)` | Get full environment details: database name, URL, repo, image, template, extra addons, workspace, container status, CPU/RAM stats |
| `delete_environment(branch_name)` | Tear down when the task is complete or cancelled |
| `start_environment` / `stop_environment` | Resume or pause a stopped environment |
| `restart_environment(branch_name)` | Restart the Odoo container (rarely needed — `pull_and_apply` handles this) |
| `rebuild_environment(branch_name)` | Recreate the container from scratch if it's broken, without losing DB or filestore |

### Code → Environment Sync

| Tool | When to use |
|---|---|
| `pull_and_apply(branch_name)` | **Always call after every `git push`**. Automatically decides: install new modules, upgrade changed modules, restart for Python changes, or do nothing for XML/JS (hot-reloaded). **Errors and tracebacks are returned directly in the tool response** — do NOT call `get_environment_logs` after this. |

### Odoo Module Operations

| Tool | When to use |
|---|---|
| `install_odoo_modules(branch_name, modules)` | Install modules for the first time. Comma-separated list. **Returns full output including errors.** |
| `upgrade_odoo_modules(branch_name, modules)` | Force-upgrade modules. Usually handled by `pull_and_apply`. **Returns full output including errors.** |
| `run_odoo_tests(branch_name, modules)` | Run Odoo tests for specific modules. **Returns full test output.** |
| `list_installed_modules(branch_name, name_filter?, state_filter?)` | List Odoo modules with name/state filtering. Default: installed modules only. |

### ORM & Scripting

| Tool | When to use |
|---|---|
| `run_odoo_shell(branch_name, python_code)` | Execute Python in Odoo shell with full ORM access. Use `print()` to produce output. |
| `write_file_in_odoo(branch_name, path, content, user?)` | Write a text file inside the container (CSV imports, scripts, configs). Do NOT use for source code. |
| `http_request_to_odoo(branch_name, path, method?, body?, headers?, session_id?)` | HTTP request to the running Odoo instance. Test controllers, JSON-RPC, REST endpoints. |
| `search_in_odoo(branch_name, pattern, path?, glob?, max_results?)` | Grep for a pattern inside container files. |

### Debugging & Logs

> `install_odoo_modules`, `upgrade_odoo_modules`, `run_odoo_tests`, and `pull_and_apply` run via `docker exec`. Their output is **returned directly in the tool response** and does **NOT** appear in `get_environment_logs`.
>
> `get_environment_logs` shows logs from the **running Odoo server** (main container process) — runtime errors while serving requests.

| Tool | What it shows |
|---|---|
| `get_environment_logs(branch_name, n_lines?, grep?, level?)` | Logs from the **running Odoo server**. Use `grep` for substring filtering, `level` for "ERROR"/"WARNING"/"CRITICAL". |
| `read_file_in_odoo(branch_name, path, read_range?)` | Read a text file or list a directory inside the container. Supports `read_range="START:END"`. **Prefer over `run_odoo_command` with `cat`/`ls`.** |
| `run_odoo_command(branch_name, command, user?)` | Run shell commands inside the container. Use `user="root"` for privileged ops. |

### Database & Other

| Tool | When to use |
|---|---|
| `run_db_query(branch_name, query)` | Run SQL queries directly against PostgreSQL. |
| `setup_repo_auth(repo_url)` | Cache git credentials for a private repo. URL format: `https://user:PAT@github.com/owner/repo.git`. Call once before `create_environment`. |
| `create_service(name, image, port, hostname?, env_vars?)` | Spin up a sidecar (Redis, Meilisearch, etc.). Accessible via `oduflow-svc-{name}:{port}`. |
| `list_services` / `get_service_logs(name)` / `delete_service(name)` | Manage auxiliary services. |

### Template Management (use with caution)

| Tool | When to use |
|---|---|
| `list_templates` | List available database template profiles |
| `save_as_template(branch_name)` | Make a branch the new template baseline. **Requires explicit user permission.** |
| `delete_template(template_name)` | **Destructive.** Remove a template profile. **Requires explicit user permission.** |

## Working with Large Outputs

When output exceeds ~5K characters, Oduflow automatically caches and returns a smart summary with an `output_id`.

| Mode | What it does |
|---|---|
| `read_output(output_id, mode="errors")` | Show only ERROR/WARNING lines with context |
| `read_output(output_id, mode="grep", grep="pattern")` | Search for a substring (case-insensitive) |
| `read_output(output_id, mode="lines", start=100, end=200)` | Read a specific line range |
| `read_output(output_id, mode="tail")` | Last 100 lines |
| `read_output(output_id, mode="info")` | Metadata: line count, char count, error count |

Cache lifetime: 1 hour.

## Smart Pull — What Happens Automatically

| What changed | Action taken |
|---|---|
| New `__manifest__.py` (new module) | **Install** the module |
| `__manifest__.py` version/data/assets changed | **Upgrade** the module |
| `*.py` with `fields.*` changes | **Upgrade** the module |
| `security/*.xml` | **Upgrade** the module |
| `*.py` without field changes | **Restart** the container |
| `*.xml` (views, data) / `*.js` | **Nothing** — hot-reloaded via `--dev=xml` |

## Database Migrations Workflow

Migrations only run during module upgrade, NOT during environment creation. `create_environment` from a template clones the DB as-is without running migrations.

**Correct workflow:**
1. Commit migration script + version bump in `__manifest__.py`
2. `git push` → `pull_and_apply` (triggers migration)
3. Verify with `run_db_query` or `run_odoo_command`
4. Check `get_environment_logs` if something went wrong

**Never recreate an environment to test migrations — always use `upgrade_odoo_modules` or `pull_and_apply`.**
