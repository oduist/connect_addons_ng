{
    'name': 'Oduist Connect Infobip',
    'version': '19.0.1.1.1',
    'author': 'Oduist',
    'category': 'Phone',
    'summary': 'Infobip integration for Oduist Connect',
    'depends': ['connect'],
    # No external_dependencies: the Infobip API is called with plain
    # requests — the official Python SDK does not cover the Voice/Calls
    # and Numbers APIs (ADR-036).
    'data': [
        'security/access_rules.xml',
        'views/menu.xml',
        'views/settings_views.xml',
        'views/user_views.xml',
        'views/exten_views.xml',
        'views/number_views.xml',
        'views/call_views.xml',
        'views/message_views.xml',
        'views/message_configuration_views.xml',
        'views/outgoing_callerid_views.xml',
        'views/whatsapp_sender_views.xml',
        'views/whatsapp_template_views.xml',
        'wizard/sms_composer_views.xml',
        'wizard/whatsapp_composer_views.xml',
        'data/ir_cron.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'connect_infobip/static/src/icomoon/style.css',
            'connect_infobip/static/src/components/phone/*/*',
            'connect_infobip/static/src/js/main.js',
            'connect_infobip/static/src/js/utils.js',
            'connect_infobip/static/src/widgets/phone_field/*',
            'connect_infobip/static/src/services/actions/*',
            'connect_infobip/static/src/services/active_calls/*',
            'connect_infobip/static/src/services/mail/*',
        ],
    },
    'post_init_hook': 'post_init_hook',
    'installable': True,
    'application': False,
    'license': 'Other proprietary',
}
