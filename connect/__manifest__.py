{
    'name': 'Oduist Connect',
    'version': '19.0.3.1.14',
    'author': 'Oduist',
    'category': 'Phone',
    'summary': 'Communication platform for Odoo',
    'depends': ['base', 'mail', 'contacts', 'sms'],
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
        'views/endpoint_views.xml',
        'views/call_views.xml',
        'views/channel_views.xml',
        'views/message_views.xml',
        'views/recording_views.xml',
        'views/number_views.xml',
        'views/outgoing_callerid_views.xml',
        'views/provider_views.xml',
        'views/exten_views.xml',
        'views/callflow_views.xml',
        'views/debug_views.xml',
        'views/res_partner_views.xml',
        'views/message_configuration_views.xml',
        'views/license.xml',
        # Wizards
        'wizard/transfer_views.xml',
        'wizard/sms_composer_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            '/connect/static/src/components/license_banner/*',
        ],
    },
    'post_init_hook': 'post_init_hook',
    'installable': True,
    'application': True,
    'license': 'Other proprietary',
}
