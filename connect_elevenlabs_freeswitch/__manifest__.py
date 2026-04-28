# -*- coding: utf-8 -*-

{
    'name': 'Connect ElevenLabs - FreeSWITCH Bridge',
    'version': '1.0.0',
    'author': 'Oduist',
    'maintainer': 'Oduist',
    'support': 'support@oduist.com',
    'license': 'Other proprietary',
    'category': 'Phone',
    'summary': 'FreeSWITCH provider bridge for Connect ElevenLabs',
    'description': "FreeSWITCH-side ElevenLabs Conversational AI integration. Bridges inbound calls to ElevenLabs via SIP trunk (default). mod_audio_fork transport reserved for a follow-up sprint.",
    'depends': ['connect_elevenlabs', 'connect_freeswitch'],
    'data': [
        'data/templates.xml',
        'views/agent.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': True,
}
