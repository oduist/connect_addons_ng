"""Drop the obsolete Default flag from Telnyx Numbers.

The field never had behavior; outbound defaults are owned by
connect.telnyx.outgoing_callerid.
"""


def migrate(cr, version):
    if not version:
        return
    cr.execute(
        """
        ALTER TABLE IF EXISTS connect_telnyx_number
        DROP COLUMN IF EXISTS is_default
        """
    )
