/** @odoo-module **/
import {registry} from "@web/core/registry"
import {ConnectActiveCallsTray} from "./active_calls_tray"
import {ConnectActiveCallsPopup} from "./active_calls_popup"
import {ConnectEventBus} from "@connect/utils/event_bus"


export const ConnectActiveCallsService = {
    dependencies: ["orm"],
    async start(env, {orm}) {
        // Shared active-calls systray widget. It lives in the core connect
        // module (which owns the connect.call ledger it reads) so that a single
        // icon is shown regardless of how many telephony providers are
        // installed. Only Connect users see it.
        // Odoo 15 variant: no @web/core/user; check the group over RPC.
        if (!(await orm.call("res.users", "has_group", ["connect.group_user"]))) {
            return
        }
        let bus = new ConnectEventBus()
        registry.category("systray").add('activeCallsTray', {Component: ConnectActiveCallsTray, props: {bus}})
        registry.category("main_components").add('activeCallsPopup', {Component: ConnectActiveCallsPopup, props: {bus}})
    }
}

registry.category('services').add("connect_active_calls", ConnectActiveCallsService)
