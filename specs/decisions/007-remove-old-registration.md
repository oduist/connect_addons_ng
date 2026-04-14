# 007 - Remove Old Registration System

## Problem

The `connect.settings` model contained an old registration system that communicated with `api1.oduist.com/instance/` for instance registration, usage tracking, and version checking. This has been superseded by the new `oduist.license` model and license server.

## Options Considered

1. **Keep both systems** — confusing for users, maintenance burden
2. **Remove old registration** — clean break, new license system handles everything

## Decision

Remove all old registration fields, methods, and UI (Registration tab, System tab) from `connect.settings`. The new `oduist.license` model handles licensing, registration numbers, and instance identification.

## What Was Removed

- **Fields:** `customer_code`, `registration_number`, `registration_key`, `is_registered`, `i_agree_to_*`, `admin_name`, `admin_phone`, `admin_email`, `company_name`, `company_country`, `installation_date`, `module_version`, `odoo_version`, `latest_versions`
- **Methods:** `register_instance()`, `update_instance_registration()`, `prepare_registration_data()`, `update_usage()`, `make_usage_request()`, `check_latest_versions()`, `get_module_version()`, `get_module_list()`, `set_default_admin_and_company()`, `set_instance_uid()`
- **UI:** Registration tab, System tab from settings form

## What Was Kept

- `instance_uid`, `api_url`, `web_base_url` — used by core and integrations
- `call_duration_limit` — used by `connect_twilio` for Twilio call `timeLimit` (moved to General tab)
- `set_defaults()` — called from `functions.xml` during install/upgrade
- `check_api_url()` — used by `connect_twilio`
