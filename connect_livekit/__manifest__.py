{
    'name': 'Oduist Connect LiveKit',
    'version': '19.0.1.0.0',
    'author': 'Oduist',
    'category': 'Phone',
    'summary': 'LiveKit integration for Oduist Connect',
    'depends': ['connect'],
    'external_dependencies': {
        'python': ['livekit-api'],
    },
    'data': [
        'views/menu.xml',
        'views/settings_views.xml',
    ],
    'installable': True,
    'application': False,
    'license': 'Other proprietary',
}
