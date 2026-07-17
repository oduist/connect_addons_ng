{
    'name': 'Oduist Connect',
    'version': '19.0.4.2.0',
    'author': 'Oduist',
    'category': 'Phone',
    'summary': 'Communication platform for Odoo',
    'depends': ['base', 'mail', 'contacts', 'sms', 'resource'],
    'external_dependencies': {
        'python': ['phonenumbers', 'jinja2', 'openai', 'PyJWT'],
    },
    'data': [
        # Security
        'security/groups.xml',
        'security/access_rules.xml',
        'security/record_rules.xml',
        'security/license.xml',
        # Data
        'data/res_users.xml',
        'data/functions.xml',
        'data/ir_cron.xml',
        'data/license.xml',
        # Views
        'views/menu.xml',
        'views/settings.xml',
        'views/user_views.xml',
        'views/call_views.xml',
        'views/channel_views.xml',
        'views/message_views.xml',
        'views/recording_views.xml',
        'views/schedule_views.xml',
        'views/debug_views.xml',
        'views/res_partner_views.xml',
        'views/license.xml',
        # Wizards
        'wizard/transfer_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            '/connect/static/src/components/license_banner/*',
            '/connect/static/src/components/calls/*',
            '/connect/static/src/services/active_calls/*',
        ],
    },
    'post_init_hook': 'post_init_hook',
    'images': ['static/description/icon.png'],
    'installable': True,
    'application': True,
    'license': 'Other proprietary',
}
