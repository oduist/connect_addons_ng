{
    'name': 'Oduist Connect',
    'version': '19.0.1.0.0',
    'category': 'Phone',
    'summary': 'Communication platform for Odoo',
    'depends': ['base'],
    'data': [
        'security/groups.xml',
        'security/access_rules.xml',
        'security/record_rules.xml',
        'views/menu.xml',
        'views/settings.xml',
        'views/user_views.xml',
        'views/endpoint_views.xml',
    ],
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
}
