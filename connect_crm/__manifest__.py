{
    'name': 'Oduist Connect CRM',
    'version': '19.0.1.0.0',
    'category': 'Phone',
    'summary': 'CRM integration for Oduist Connect',
    'depends': ['connect', 'crm', 'utm'],
    'data': [
        'security/webhook.xml',
        'views/crm_lead_views.xml',
        'views/call_views.xml',
        'views/utm_views.xml',
        'views/settings_views.xml',
    ],
    'post_init_hook': 'post_init_hook',
    'installable': True,
    'application': False,
    'license': 'Other proprietary',
}
