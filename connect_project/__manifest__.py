{
    'name': 'Oduist Connect Project',
    'version': '19.0.1.0.1',
    'category': 'Phone',
    'summary': 'Project integration for Oduist Connect',
    'author': 'Oduist',
    'depends': ['connect', 'project'],
    'data': [
        'security/webhook.xml',
        'views/project_views.xml',
        'views/task_views.xml',
        'views/call_views.xml',
    ],
    'post_init_hook': 'post_init_hook',
    'images': ['static/description/icon.png'],
    'installable': True,
    'application': False,
    'license': 'Other proprietary',
}
