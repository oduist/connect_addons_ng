# Licensing & Trial

All Oduist Connect modules are distributed under the **Business Source License
1.1 (BSL 1.1)** — a source-available license. The source is published in a
public repository so anyone can inspect, download and install it, but production
use is licensed as described below. Each module ships its own `LICENSE` file.

## What BSL 1.1 means in practice

- **Free non-production use.** Evaluation, development and staging use is free.
  You may read and modify the source and have partners or freelancers adapt it
  for your own instance.
- **30-day production trial.** When a module is installed, a 30-day trial for
  that module starts **automatically** — no registration required. During the
  trial the module is fully functional in production so you can evaluate it.
- **Commercial license for continued production use.** To keep a module working
  in production after its trial, you buy a commercial license. Purchases are
  **per instance** (see below).
- **Eventual open source.** Each released version carries a **Change Date**.
  On that date the version automatically becomes available under the
  **GNU LGPL-3.0-or-later**, and the BSL restrictions for that version end. The
  Change Date is set per module and moves forward with new major versions, so
  older releases open up on schedule.

!!! note "Modifying the code does not grant production rights"
    BSL restricts *use*, not *modification*. Editing or removing the licensing
    code is technically possible, but running a module in production beyond its
    trial without a valid commercial license is a breach of the license
    regardless. Please buy a license instead.

## Instance binding

On first use the module generates a unique **Instance UID** for the database.
A commercial license is issued for, and bound to, that specific Instance UID —
one license per Odoo instance. Copying the database or moving to a new instance
produces a new UID and requires the license to be re-issued for it.

## Buying a license

Licenses are purchased directly from within Odoo:

1. Open **Connect → Configuration → License** (the *License Configuration* form).
2. Review the installed Oduist modules and their status.
3. Use **Buy** to start checkout; Odoo opens the Oduist payment link for the
   selected modules and your instance.
4. After payment the instance receives a signed license token bound to its
   Instance UID; the module status switches from trial to licensed.

Pricing and further details are available at
[oduist.com/pricing](https://oduist.com/pricing).

## When a trial expires

If a module's trial ends and no commercial license is active for the instance:

- **Only that module's own features stop working.** The rest of your Odoo
  installation — and other, still-licensed Connect modules — keep working
  normally. Nothing else is blocked or degraded.
- A **license banner** appears in the interface indicating the module needs a
  license.

To resolve it, either **buy a license** for the module or **uninstall** the
module from the instance.

## Refreshing license and pricing

The *License Configuration* form has an **Update License / Pricing** button. It
re-checks every installed Oduist module against the licensing service and
reports the outcome in a notification — modules checked, modules licensed, and
the instance registration number — then re-reads the record so refreshed prices
and versions are visible. A failed check surfaces as an error dialog instead.

!!! note "A freshly installed module is on trial, not expired"
    Each module stamps its own install date and starts a 30-day trial from it.
    A module whose install date cannot be determined is treated as a full
    trial, never as an elapsed one.

## License banner and status

A systray banner surfaces the most important licensing state across installed
Oduist modules, with priority *trial expired → trial active → demo*:

- **Trial active** — informational, showing days remaining (a warning in the
  last 7 days).
- **Trial expired** — a call to buy a license to continue.
- **Demo** — shown for demo/evaluation license tokens.

## Optional subscriptions

The *License Configuration* form also offers opt-in subscriptions (critical
security alerts, onboarding guidance, product news). These are disabled by
default and are independent of licensing; enabling one shares the configured
notification email with Oduist.
