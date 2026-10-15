/** @odoo-module **/

import { registry } from "@web/core/registry";
import { BookApp } from "@connect_book/book/book";

/**
 * The "Admin Guide" client action.
 * Identical two-pane viewer as the User Guide, but it pulls the administrator
 * pages from the admin-only endpoint. The endpoint itself enforces the Connect
 * admin group server-side.
 */
export class AdminBookApp extends BookApp {
    static endpoint = "/connect_book/admin";
}

registry.category("actions").add("connect_book.admin", AdminBookApp);
