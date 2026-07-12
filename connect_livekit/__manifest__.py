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
        'security/access_rules.xml',
        'views/menu.xml',
        'views/settings_views.xml',
        'views/room_views.xml',
        'views/meet_templates.xml',
        'views/trunk_views.xml',
        'views/number_views.xml',
        'views/outgoing_callerid_views.xml',
        'views/user_views.xml',
    ],
    'assets': {
        # Standalone bundle for the public meeting page; the vendored
        # livekit-client UMD build only loads there.
        'connect_livekit.assets_meet': [
            'connect_livekit/static/lib/livekit-client.umd.min.js',
            'connect_livekit/static/src/meet/meet.js',
            'connect_livekit/static/src/meet/meet.scss',
        ],
        # Web phone widget: the livekit-client SDK is lazy-loaded on the
        # first call, not bundled into the backend assets.
        'web.assets_backend': [
            'connect_livekit/static/src/components/phone/*/*',
            'connect_livekit/static/src/js/main.js',
        ],
    },
    'installable': True,
    'application': False,
    'license': 'Other proprietary',
}
