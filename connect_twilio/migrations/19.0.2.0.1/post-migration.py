"""Drop the obsolete Default flag from Twilio Numbers.

The field never had behavior; outbound defaults are owned by
connect.twilio.outgoing_callerid.
"""


def migrate(cr, version):
    if not version:
        return
    cr.execute(
        """
        ALTER TABLE IF EXISTS connect_twilio_number
        DROP COLUMN IF EXISTS is_default
        """
    )
