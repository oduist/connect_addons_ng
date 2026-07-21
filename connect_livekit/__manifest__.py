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
        'views/agent_views.xml',
        'wizard/ai_call_wizard_views.xml',
    ],
    'assets': {
        # The public meeting page (static/src/meet/*) is NOT bundled: it is
        # served outside the Odoo web client and references its script/CSS
        # as plain static files (see views/meet_templates.xml).
        #
        # Web phone widget: the livekit-client SDK is lazy-loaded on the
        # first call, not bundled into the backend assets.
        'web.assets_backend': [
            'connect_livekit/static/src/components/phone/*/*',
            'connect_livekit/static/src/js/main.js',
        ],
    },
    'installable': True,
    'images': ['static/description/icon.png'],
    'application': False,
    'license': 'Other proprietary',
}
