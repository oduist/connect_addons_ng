{
    'name': 'Oduist Connect Account',
    'version': '18.0.1.0.1',
    'category': 'Phone',
    'summary': 'Accounting integration for Oduist Connect',
    'author': 'Oduist',
    'depends': ['connect', 'account'],
    'data': [
        'security/webhook.xml',
        'views/account_move_views.xml',
        'views/call_views.xml',
    ],
    'post_init_hook': 'post_init_hook',
    'images': ['static/description/icon.png'],
    'installable': True,
    'application': False,
    'license': 'Other proprietary',
}
