/** @odoo-module **/
import {registry} from "@web/core/registry"
import {PhoneSysTray} from "@connect_telnyx/components/phone/tray/tray"
import {Phone} from "@connect_telnyx/components/phone/phone/phone"
import {ConnectEventBus} from "@connect/utils/event_bus"

const serviceRegistry = registry.category("services")
const sysTrayRegistry = registry.category("systray")
const mainComponents = registry.category("main_components")

export function isTelnyxStaleRequestError(error) {
    return Boolean(error && error.name === "StaleRequestError" &&
        error.message && error.message.startsWith("Stale request cancelled"))
}

export function telnyxStaleRequestErrorHandler(_env, error, originalError) {
    if (!error.unhandledRejectionEvent || !isTelnyxStaleRequestError(originalError)) {
        return false
    }
    error.unhandledRejectionEvent.preventDefault()
    return true
}

registry.category("error_handlers").add(
    "connectTelnyxStaleRequestErrorHandler",
    telnyxStaleRequestErrorHandler,
    {sequence: 96},
)

export const phoneService = {
    dependencies: ["orm"],
    async start(env, {orm}) {
        const pathname = document.location.pathname
        // Odoo 15 serves the backend under /web (the /odoo scheme is 17.2+).
        if (pathname.startsWith("/web")) {
            const token_data = await orm.call('connect.user', 'get_telnyx_client_token')
            if (token_data.token) {
                let bus = new ConnectEventBus()
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
