# -*- coding: utf-8 -*-

{
    'name': 'Connect ElevenLabs - Twilio Bridge',
    'version': '19.0.1.1.5',
    'author': 'Oduist',
    'maintainer': 'Oduist',
    'support': 'support@oduist.com',
    'license': 'Other proprietary',
    'category': 'Phone',
    'summary': 'Twilio provider bridge for Connect ElevenLabs',
    'description': "Implements Twilio-specific render/transfer for connect.elevenlabs_agent.",
    'depends': ['connect_elevenlabs', 'connect_twilio'],
    'data': [
        'views/agent.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': True,
}
