# -*- coding: utf-8 -*-
{
    'name': 'Oduist Connect Book',
    'version': '19.0.1.0.0',
    'category': 'Phone',
    'summary': 'Read the Connect documentation inside Odoo',
    'author': 'Oduist',
    'maintainer': 'Oduist',
    'support': 'support@oduist.com',
    'license': 'Other proprietary',
    'description': """
Connect Book
============

Crawls every installed ``connect*`` module, reads the Markdown pages from its
``docs`` folder -- the very same files the documentation site is built from --
and assembles them into two books inside the Odoo UI: the User Guide and the
administrator-only Admin Guide.

The documentation lives next to the module code, so what you read always
matches what you run. No separate wiki, nothing to keep in sync by hand.
""",
    'depends': ['connect', 'web'],
    'data': [
        'views/connect_book_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            '/connect_book/static/src/book/book.scss',
            '/connect_book/static/src/book/book.js',
            '/connect_book/static/src/book/book.xml',
            '/connect_book/static/src/admin/adminbook.js',
        ],
    },
    'images': ['static/description/icon.png'],
    'installable': True,
    'application': False,
    'auto_install': False,
}
