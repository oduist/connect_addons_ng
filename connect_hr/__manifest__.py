{
    'name': 'Oduist Connect HR',
    'version': '18.0.1.0.1',
    'category': 'Phone',
    'summary': 'HR integration for Oduist Connect',
    'author': 'Oduist',
    'depends': ['connect', 'hr'],
    'data': [
        'security/webhook.xml',
        'views/hr_employee_views.xml',
        'views/call_views.xml',
    ],
    'post_init_hook': 'post_init_hook',
    'images': ['static/description/icon.png'],
    'installable': True,
    'application': False,
    'license': 'Other proprietary',
}
