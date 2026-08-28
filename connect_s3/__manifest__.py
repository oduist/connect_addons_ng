{
    'name': 'Oduist Connect S3 Recording Storage',
    'version': '19.0.1.0.0',
    'category': 'Phone',
    'summary': 'Store Twilio recordings in your own S3 bucket',
    'description': """
Connect S3 Recording Storage
============================

Stores Twilio call recordings in a customer-owned AWS S3 bucket instead of
Twilio's cloud, so the customer owns the media lifecycle and avoids Twilio
storage charges.

Built on Twilio's *External S3 Storage* feature: once it is enabled on the
account, Twilio writes the audio into the bucket itself and the recording URL
Odoo receives points at S3. Odoo never uploads — it provisions the bucket,
creates the Twilio-side AWS credential, and reads the media back for playback,
proxy download and OpenAI transcription.

Recordings created before the switch stay on Twilio and keep working
(mixed mode). Retention is delegated to an S3 lifecycle rule; when the audio
expires the transcript and summary are kept.

Twilio's voice recording settings are Console-only, so enabling external
storage is a one-off manual step — the settings page shows the exact checklist
and the two values to paste.
    """,
    'author': 'Oduist',
    'website': 'https://oduist.com',
    'license': 'Other proprietary',
    'images': ['static/description/icon.png'],
    'external_dependencies': {'python': ['boto3']},
    'depends': [
        'connect',
        'connect_twilio',
    ],
    'data': [
        'views/settings.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
