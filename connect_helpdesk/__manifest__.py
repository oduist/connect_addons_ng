{
    'name': 'Oduist Connect Helpdesk',
    'version': '19.0.1.0.1',
    'category': 'Phone',
    'summary': 'Helpdesk integration for Oduist Connect',
    'depends': ['connect', 'helpdesk'],
    'data': [
        'security/webhook.xml',
        'views/ticket_views.xml',
        'views/call_views.xml',
        'views/settings_views.xml',
    ],
    'post_init_hook': 'post_init_hook',
    'images': ['static/description/icon.png'],
    'installable': True,
    'application': False,
    'license': 'Other proprietary',
}
