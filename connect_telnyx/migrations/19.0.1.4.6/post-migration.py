"""Re-link destinations that older builds left without their extension.

Before the _set_dst fix, saving an extension stored model/res_id on it but
never wrote the back-link on the destination: the extension list showed
"1001 -> user" while the user had no extension number, and every inbound
number routed to them answered 404. Re-saving the extension does not help
(an unchanged destination is not sent), so the upgrade repairs it once.
"""
from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    env['connect.telnyx.exten']._repair_dst_links()
