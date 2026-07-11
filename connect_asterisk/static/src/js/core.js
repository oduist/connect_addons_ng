/** @odoo-module **/
import {registry} from "@web/core/registry"
import {PhoneSysTray} from "@connect_asterisk/components/tray/tray"
import {Phone} from "@connect_asterisk/components/phone/phone"
import {EventBus} from "@odoo/owl"
import {user} from "@web/core/user"

const uid = user.userId

export const phoneService = {
    dependencies: ["orm"],
    async start(env, {orm}) {
        if (!await user.hasGroup('connect.group_user') &&
            !await user.hasGroup('connect.group_admin')) return

        const pathname = document.location.pathname
        if (pathname.includes("/odoo")) {
            const settings = await orm.call("connect.settings", "asterisk_get_phone_settings")
            if (!settings.phone_enabled) return
            const config = await orm.call('res.users', 'get_sip_user_config', [uid])

            if (config && config.user_config) {
                let bus = new EventBus()
                registry.category("systray").add('phoneSysTray', {Component: PhoneSysTray, props: {bus}})
                registry.category("main_components").add('mainPhone', {Component: Phone, props: {bus}})
            }
        } else {
            console.log(`[Phone] Doesn't work on path: ${pathname}`)
        }
    }
}
registry.category("services").add("connect_asterisk_phone", phoneService)
