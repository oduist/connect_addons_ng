# -*- coding: utf-8 -*-
from odoo import http, release
from odoo.http import request

# The JSON dispatcher was renamed from "json" to "jsonrpc" in Odoo 19.
JSON_ROUTE_TYPE = "jsonrpc" if release.version_info[0] >= 19 else "json"


class ConnectBookController(http.Controller):
    """Thin JSON wrapper over the ``connect.book`` model for the client actions."""

    @http.route("/connect_book/book", type=JSON_ROUTE_TYPE, auth="user")
    def book(self):
        # get_book enforces the Connect user group itself.
        return request.env["connect.book"].get_book()

    @http.route("/connect_book/admin", type=JSON_ROUTE_TYPE, auth="user")
    def admin_book(self):
        # get_admin_book enforces the Connect admin group itself.
        return request.env["connect.book"].get_admin_book()
