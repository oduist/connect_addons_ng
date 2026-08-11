/** @odoo-module **/
import {registry} from "@web/core/registry"
import {LivekitPhoneSysTray} from "@connect_livekit/components/phone/tray/tray"
import {LivekitPhone} from "@connect_livekit/components/phone/phone/phone"
import {EventBus} from "@odoo/owl"

const serviceRegistry = registry.category("services")
const sysTrayRegistry = registry.category("systray")
const mainComponents = registry.category("main_components")

export const livekitPhoneService = {
    dependencies: ["orm"],
    async start(env, {orm}) {
        const pathname = document.location.pathname
        if (!pathname.includes("/odoo")) {
            console.log(`[LiveKit Phone] Doesn't work on path: ${pathname}`)
            return
        }
        const config = await orm.call('connect.user', 'get_livekit_phone_config')
        if (!config.enabled) {
            console.log('LiveKit Web Phone is not enabled for user.')
            return
        }
        const bus = new EventBus()
        sysTrayRegistry.add('connectLivekitPhoneSysTray', {Component: LivekitPhoneSysTray, props: {bus}})
        mainComponents.add('connectLivekitPhone', {Component: LivekitPhone, props: {bus, config}})
    }
}
serviceRegistry.add("ConnectLivekitPhoneService", livekitPhoneService)
