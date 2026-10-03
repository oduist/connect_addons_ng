"""Drop the obsolete Default flag from FreeSWITCH Numbers.

The field never had behavior; outbound defaults are owned by
connect.freeswitch.outgoing_callerid.
"""


def migrate(cr, version):
    if not version:
        return
    cr.execute(
        """
        ALTER TABLE IF EXISTS connect_freeswitch_number
        DROP COLUMN IF EXISTS is_default
        """
    )
