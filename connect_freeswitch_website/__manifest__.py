{
    'name': 'Oduist Connect FreeSWITCH Website',
    'version': '18.0.1.0.0',
    'author': 'Oduist',
    'category': 'Phone',
    'summary': 'Website widgets for phone schedules',
    'depends': ['connect_freeswitch', 'website'],
    'data': [
        'security/access_rules.xml',
        'views/snippets/s_phone_status.xml',
        'views/snippets/s_phone_opening_hours.xml',
        'views/snippets/snippets.xml',
    ],
    'assets': {
        'web.assets_frontend': [
            'connect_freeswitch_website/static/src/snippets/**/*.js',
        ],
        'website.website_builder_assets': [
            'connect_freeswitch_website/static/src/website_builder/**/*',
        ],
    },
    'images': ['static/description/icon.png'],
    'installable': True,
    'application': False,
    'license': 'Other proprietary',
}
