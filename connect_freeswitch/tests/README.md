# About the test suite

These Odoo modules are published **without their automated test suite** — and
that is a deliberate choice, not an oversight or a missing piece.

## Why the tests are not here

The test suite is one of our core engineering assets. It encodes years of
accumulated knowledge about how this product is supposed to behave: the edge
cases, the regressions we have already paid for once, the provider-specific
quirks, and the exact contracts each model and controller must honour. Writing
and maintaining that suite is a large part of what makes the product reliable.

We keep it private on purpose. Our business is building, customising,
supporting and maintaining this software for the people who use it — and we
believe we do that better than anyone, because we wrote it and we own the full
test coverage behind it. When you bring a requirement or a problem to us, the
result is delivered properly, verified against the full suite, and it becomes
available to every other user of the product as well. That shared, well-tested
core is what everyone benefits from.

## You can still run, deploy and use everything

Nothing here is crippled. The modules install cleanly and run in full without
the test suite — the `tests/` loader is simply a no-op when the private
`tests_suite` submodule is absent. Use the product freely under its license.

## If you want to modify the product yourself

If you would rather extend or adapt the product on your own — with your own
developers or your own AI agents — that is fine, but please talk to us first.
We license the private `tests_suite` separately, as a paid add-on. With it you
get the same safety net we develop against, so you can change the code with
confidence and immediately know whether something broke.

The test suite is licensed for **your own internal use only**. Redistribution,
resale or public re-publication of the test suite — in whole or in part — is
not permitted.

## Get in touch

Need a feature, an integration, support, or a `tests_suite` license?
Reach out to us — we are happy to help.
