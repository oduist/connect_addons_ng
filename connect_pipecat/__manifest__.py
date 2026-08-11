{
    'name': 'Oduist Connect Pipecat',
    'version': '18.0.1.0.0',
    'author': 'Oduist',
    'category': 'Phone',
    'summary': 'Pipecat AI voice agents for FreeSWITCH',
    'depends': ['connect', 'connect_freeswitch'],
    'data': [
        'security/access_rules.xml',
        'data/fs_templates.xml',
        'views/agent_views.xml',
        'views/settings.xml',
    ],
    'post_init_hook': 'post_init_hook',
    'images': ['static/description/icon.png'],
    'installable': True,
    'application': False,
    'license': 'Other proprietary',
}
