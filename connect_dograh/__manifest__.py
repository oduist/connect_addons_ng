{
    'name': 'Oduist Connect Dograh',
    'version': '19.0.1.0.0',
    'author': 'Oduist',
    'category': 'Phone',
    'summary': 'Dograh AI voice agents for FreeSWITCH',
    'depends': ['connect', 'connect_freeswitch'],
    # No external_dependencies: Dograh is called with plain requests
    # (inbound run webhook + health check, ADR-038).
    'data': [
        'security/access_rules.xml',
        'data/fs_templates.xml',
        'views/menu.xml',
        'views/agent_views.xml',
        'views/settings_views.xml',
    ],
    'post_init_hook': 'post_init_hook',
    'installable': True,
    'application': False,
    'license': 'Other proprietary',
}
