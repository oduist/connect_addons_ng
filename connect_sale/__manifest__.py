{
    'name': 'Oduist Connect Sale',
    'version': '19.0.1.0.0',
    'category': 'Phone',
    'summary': 'Sale integration for Oduist Connect',
    'author': 'Oduist',
    'depends': ['connect', 'sale'],
    'data': [
        'security/webhook.xml',
        'views/sale_order_views.xml',
        'views/call_views.xml',
    ],
    'post_init_hook': 'post_init_hook',
    'images': ['static/description/icon.png'],
    'installable': True,
    'application': False,
    'license': 'Other proprietary',
}
