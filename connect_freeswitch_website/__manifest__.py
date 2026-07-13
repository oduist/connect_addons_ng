{
    'name': 'Oduist Connect FreeSWITCH Website',
    'version': '19.0.1.0.0',
    'author': 'Oduist',
    'category': 'Phone',
    'summary': 'Website widgets for FreeSWITCH phone number working schedules',
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
    'installable': True,
    'application': False,
    'license': 'Other proprietary',
}
