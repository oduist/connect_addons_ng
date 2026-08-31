{
    'name': 'Connect Memory',
    'version': '19.0.1.0.2',
    'category': 'Phone',
    'summary': 'External AI memory (Hindsight, Cognee)',
    'description': """
Connect Memory — base module
============================

External AI memory for Odoo, provider-neutral (engines: Hindsight, Cognee, …).

Odoo **does not call** the memory engine directly. It emits neutral domain
events into the ``connect.memory.outbox`` table (JSONB); a separate external
service pulls them on the engine side, loads them into the brain, and writes
answers back into ``connect.memory.inbox``.

This base module provides:

* **the contract** — ``connect.memory.outbox`` / ``connect.memory.inbox``
  tables, the capture mixin, the pull/ack/inbox HTTP endpoints, the
  ``sensitivity`` policy, config;
* **the partner layer** — customer correspondence capture (``mail.message`` on
  ``res.partner``) and the "Customer summary" operation (reflect).

Domain modules (``connect_memory_sale``, …) depend on it and add capture of
their own data.
    """,
    'author': 'Oduist',
    'website': 'https://oduist.com',
    'license': 'Other proprietary',
    'images': ['static/description/icon.png'],
    'depends': [
        'connect',
    ],
    'data': [
        'security/ir.model.access.csv',
        'data/memory_data.xml',
        'views/memory_outbox_views.xml',
        'views/memory_inbox_views.xml',
        # Before settings.xml: it hangs the Settings entry off menu_memory_config.
        'views/memory_menus.xml',
        'views/settings.xml',
        'views/res_partner_views.xml',
        'views/memory_backfill_views.xml',
    ],
    'post_init_hook': 'post_init_hook',
    'installable': True,
    'application': True,
    'auto_install': False,
}
