/** @odoo-module **/
import {registry} from "@web/core/registry"
import {PhoneSysTray} from "@connect_telnyx/components/phone/tray/tray"
import {Phone} from "@connect_telnyx/components/phone/phone/phone"
import {user} from "@web/core/user"

const uid = user.userId
const serviceRegistry = registry.category("services")
const sysTrayRegistry = registry.category("systray")
const mainComponents = registry.category("main_components")
import {EventBus} from "@odoo/owl"

export const phoneService = {
    dependencies: ["orm"],
    async start(env, {orm}) {
        const pathname = document.location.pathname
        if (pathname.includes("/odoo")) {
            const token_data = await orm.call('connect.user', 'get_telnyx_client_token')
            if (token_data.token) {
                let bus = new EventBus()
                sysTrayRegistry.add('connectTelnyxPhoneSysTray', {Component: PhoneSysTray, props: {bus}})
                mainComponents.add('connectTelnyxPhone', {Component: Phone, props: {bus, token_data}})
            }
            else if (token_data.error) {
                console.warn(token_data.error)
            }
            else {
                console.log('Telnyx Web Phone is not enabled for user.')
            }
        } else {
            console.log(`[Phone] Doesn't work on path: ${pathname}`)
        }
    }
}
serviceRegistry.add("ConnectTelnyxPhoneService", phoneService)