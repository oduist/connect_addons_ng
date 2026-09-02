# -*- encoding: utf-8 -*-

{
    'name': 'Oduist Connect ElevenLabs Sale',
    'version': '19.0.1.0.0',
    'author': 'Oduist',
    'maintainer': 'Oduist',
    'live_test_url': 'https://connect-demo-18.oduist.com/',
    'price': 999,
    'currency': 'EUR',
    'support': 'support@oduist.com',
    'license': 'Other proprietary',
    'category': 'Phone',
    'summary': 'AI Sale Management',
    'description': "AI Sale Management",
    "depends": ['connect_elevenlabs', 'sale_management', 'website_sale'],
    'data': [
        'data/tools.xml',
    ],
    'demo': [
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'images': ['static/description/icon.png'],
    'post_init_hook': 'post_init_hook',
}
