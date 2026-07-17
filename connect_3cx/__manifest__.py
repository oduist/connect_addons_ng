{
    'name': 'Oduist Connect 3CX',
    'version': '18.0.1.0.0',
    'author': 'Oduist',
    'category': 'Phone',
    'summary': '3CX integration for Oduist Connect',
    'depends': ['connect', 'web'],
    'data': [
        'views/menu.xml',
        'views/user_views.xml',
        'views/settings.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'connect_3cx/static/src/widgets/phone_field/*',
        ],
    },
    'post_init_hook': 'post_init_hook',
    'installable': True,
    'application': False,
    'license': 'Other proprietary',
}
